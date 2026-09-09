from decimal import Decimal
from django.conf import settings
from django.core.validators import MinValueValidator, MaxValueValidator
from django.db import models
from django.utils import timezone

ZERO = Decimal('0.00')
def money_field(**kwargs):
    return models.DecimalField(max_digits=14, decimal_places=2, default=ZERO,
                               validators=[MinValueValidator(ZERO)], **kwargs)

class BusinessProfile(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    business_name = models.CharField(max_length=160, default='My Business')
    owner_name = models.CharField(max_length=160, blank=True)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=40, blank=True)
    address = models.TextField(blank=True)
    registration_number = models.CharField(max_length=80, blank=True)
    vat_number = models.CharField(max_length=80, blank=True)
    bank_name = models.CharField(max_length=120, blank=True)
    account_name = models.CharField(max_length=160, blank=True)
    account_number = models.CharField(max_length=80, blank=True)
    branch_code = models.CharField(max_length=40, blank=True)
    banking = models.TextField(blank=True)
    logo = models.ImageField(upload_to='logos/', blank=True)
    default_currency = models.CharField(max_length=3, choices=[('ZAR', 'ZAR'), ('USD', 'USD')], default='ZAR')
    default_tax_rate = models.DecimalField(max_digits=5, decimal_places=2, default=15,
        validators=[MinValueValidator(0), MaxValueValidator(100)])
    payment_terms = models.TextField(blank=True, default='Payment is due within 30 days. Please use the invoice number as your payment reference.')
    invoice_prefix = models.CharField(max_length=20, default='INV-')
    next_invoice_number = models.PositiveIntegerField(default=1, validators=[MinValueValidator(1)])

    def __str__(self):
        return self.business_name

class Customer(models.Model):
    business = models.ForeignKey(BusinessProfile, on_delete=models.CASCADE, related_name='customers')
    name = models.CharField(max_length=160)
    company_name = models.CharField(max_length=160, blank=True)
    email = models.EmailField()
    phone = models.CharField(max_length=40, blank=True)
    address = models.TextField(blank=True)
    vat_number = models.CharField(max_length=80, blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.company_name or self.name

class Invoice(models.Model):
    STATUSES = [(x, x) for x in ['Draft', 'Unpaid', 'Paid', 'Overdue', 'Cancelled']]
    business = models.ForeignKey(BusinessProfile, on_delete=models.CASCADE, related_name='invoices')
    customer = models.ForeignKey(Customer, on_delete=models.PROTECT, related_name='invoices')
    invoice_number = models.CharField(max_length=50)
    issue_date = models.DateField(default=timezone.localdate)
    due_date = models.DateField()
    status = models.CharField(max_length=10, choices=STATUSES, default='Draft')
    currency = models.CharField(max_length=3, default='ZAR')
    subtotal = money_field()
    tax_rate = models.DecimalField(max_digits=5, decimal_places=2, default=15,
        validators=[MinValueValidator(0), MaxValueValidator(100)])
    tax_amount = money_field()
    discount = money_field()
    total = money_field()
    amount_paid = money_field()
    balance_due = money_field()
    banking = models.TextField(blank=True)
    notes = models.TextField(blank=True)
    terms = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['business', 'invoice_number'], name='unique_business_invoice_number'),
                       models.CheckConstraint(condition=models.Q(balance_due__gte=0), name='invoice_balance_nonnegative')]
        ordering = ['id']

    @property
    def effective_status(self):
        if self.status in ('Draft', 'Cancelled'):
            return self.status
        if self.balance_due == 0:
            return 'Paid'
        return 'Overdue' if self.due_date < timezone.localdate() else 'Unpaid'

    def __str__(self):
        return self.invoice_number

class InvoiceItem(models.Model):
    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name='items')
    description = models.CharField(max_length=500)
    quantity = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(Decimal('.01'))])
    unit_price = money_field()
    line_total = money_field()

class Payment(models.Model):
    METHODS = [(x, x) for x in ['EFT', 'Bank Transfer', 'EFT / Bank Transfer', 'Cash', 'Card', 'Other']]
    invoice = models.ForeignKey(Invoice, on_delete=models.PROTECT, related_name='payments')
    amount = models.DecimalField(max_digits=14, decimal_places=2, validators=[MinValueValidator(Decimal('.01'))])
    payment_date = models.DateField(default=timezone.localdate)
    payment_method = models.CharField(max_length=30, choices=METHODS)
    reference = models.CharField(max_length=160, blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.CheckConstraint(condition=models.Q(amount__gt=0), name='payment_positive')]


class StoredUpload(models.Model):
    """Private logo bytes persisted in Invoice's database on ephemeral hosts."""
    name = models.CharField(max_length=255, unique=True)
    content = models.BinaryField()
