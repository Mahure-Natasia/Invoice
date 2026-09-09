from decimal import Decimal, ROUND_HALF_UP
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Sum, F
from django.utils import timezone
from .forms import InvoiceForm, ItemForm, PaymentForm
from .models import BusinessProfile, Invoice, InvoiceItem

CENT = Decimal('.01')
MAX_MONEY = Decimal('999999999999.99')

def checked(form):
    if not form.is_valid():
        raise ValidationError({key: list(value) for key, value in form.errors.items()})
    return form

def rounded(value):
    result = value.quantize(CENT, rounding=ROUND_HALF_UP)
    if not result.is_finite() or result < 0 or result > MAX_MONEY:
        raise ValidationError('Amount is outside the supported range.')
    return result

def lock_business(business):
    # An initial write serializes SQLite writers as well as locking the row on PostgreSQL.
    BusinessProfile.objects.filter(pk=business.pk).update(next_invoice_number=F('next_invoice_number'))
    return BusinessProfile.objects.select_for_update().get(pk=business.pk)

@transaction.atomic
def save_invoice(business, data, invoice_id=None):
    business = lock_business(business)
    invoice = Invoice.objects.select_for_update().get(pk=invoice_id, business=business) if invoice_id else Invoice(business=business)
    form = checked(InvoiceForm(data, instance=invoice, business=business))
    raw_items = data.get('items')
    if not isinstance(raw_items, list) or not 1 <= len(raw_items) <= 100:
        raise ValidationError('An invoice needs between 1 and 100 line items.')
    items = []
    for raw in raw_items:
        if not isinstance(raw, dict):
            raise ValidationError('Each item must be an object.')
        item = checked(ItemForm(raw)).save(commit=False)
        item.line_total = rounded(item.quantity * item.unit_price)
        items.append(item)
    invoice = form.save(commit=False)
    invoice.subtotal = rounded(sum((x.line_total for x in items), Decimal(0)))
    invoice.tax_amount = rounded(invoice.subtotal * invoice.tax_rate / 100)
    invoice.total = rounded(invoice.subtotal + invoice.tax_amount - invoice.discount)
    invoice.amount_paid = Decimal(0)
    if invoice.pk:
        invoice.amount_paid = invoice.payments.aggregate(value=Sum('amount'))['value'] or Decimal(0)
    if invoice.total < invoice.amount_paid:
        raise ValidationError('Invoice total cannot be less than payments already received.')
    if invoice.amount_paid and invoice.status in ('Draft', 'Cancelled'):
        raise ValidationError('An invoice with payments cannot be drafted or cancelled.')
    invoice.balance_due = invoice.total - invoice.amount_paid
    if not invoice.pk:
        while True:
            number = f'{business.invoice_prefix}{timezone.localdate().year}-{business.next_invoice_number:04d}'
            business.next_invoice_number += 1
            if not business.invoices.filter(invoice_number=number).exists():
                break
        invoice.invoice_number = number
        invoice.currency = business.default_currency
        business.save(update_fields=['next_invoice_number'])
    invoice.status = invoice.effective_status
    invoice.save()
    invoice.items.all().delete()
    for item in items:
        item.invoice = invoice
    InvoiceItem.objects.bulk_create(items)
    return invoice

@transaction.atomic
def record_payment(business, data):
    lock_business(business)
    form = checked(PaymentForm(data, business=business))
    payment = form.save(commit=False)
    invoice = Invoice.objects.select_for_update().get(pk=payment.invoice_id, business=business)
    if invoice.effective_status in ('Draft', 'Cancelled', 'Paid'):
        raise ValidationError('Only unpaid or overdue invoices can receive payments.')
    if payment.payment_date < invoice.issue_date:
        raise ValidationError('Payment date cannot precede the invoice issue date.')
    if payment.amount > invoice.balance_due:
        raise ValidationError('Payment cannot exceed the outstanding balance.')
    payment.save()
    invoice.amount_paid += payment.amount
    invoice.balance_due = invoice.total - invoice.amount_paid
    invoice.status = invoice.effective_status
    invoice.save(update_fields=['amount_paid', 'balance_due', 'status', 'updated_at'])
    return payment

@transaction.atomic
def delete_invoice(business, invoice_id):
    lock_business(business)
    invoice = Invoice.objects.get(pk=invoice_id, business=business)
    if invoice.payments.exists():
        raise ValidationError('Invoices with payments are retained for your financial history.')
    invoice.delete()
