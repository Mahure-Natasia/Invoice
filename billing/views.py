import json
from functools import wraps
from decimal import Decimal
from django.utils import timezone
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.db.models import Q
from django.db.models.deletion import ProtectedError
from django.http import JsonResponse, FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods
from .forms import RegistrationForm, ProfileForm, SettingsForm, CustomerForm, DateFilterForm
from .models import BusinessProfile, Customer, Invoice, Payment
from .services import checked, save_invoice, record_payment, delete_invoice

def business_for(user):
    return BusinessProfile.objects.get_or_create(user=user, defaults={'email': user.email})[0]

def register(request):
    if request.user.is_authenticated:
        return redirect('dashboard')
    form = RegistrationForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        user = form.save()
        business_for(user)
        login(request, user)
        return redirect('dashboard')
    return render(request, 'registration/register.html', {'form': form})

def api(methods):
    def decorate(view):
        @login_required
        @require_http_methods(methods)
        @wraps(view)
        def wrapped(request, *args, **kwargs):
            try:
                data = {}
                if request.content_type == 'application/json' and request.body:
                    data = json.loads(request.body)
                    if not isinstance(data, dict):
                        raise ValidationError('Expected a JSON object.')
                    if any(isinstance(value, (dict, list)) for key, value in data.items() if key != 'items'):
                        raise ValidationError('Form fields must contain single values.')
                    if isinstance(data.get('items'), list):
                        for item in data['items']:
                            if isinstance(item, dict) and any(isinstance(value, (dict, list)) for value in item.values()):
                                raise ValidationError('Item fields must contain single values.')
                return view(request, business_for(request.user), data, *args, **kwargs)
            except (ValidationError, json.JSONDecodeError, UnicodeDecodeError) as exc:
                errors = getattr(exc, 'message_dict', None) or getattr(exc, 'messages', [str(exc)])
                return JsonResponse({'errors': errors}, status=400)
            except ProtectedError:
                return JsonResponse({'errors': ['This record is used in your financial history and cannot be deleted.']}, status=400)
        return wrapped
    return decorate

def customer_data(c):
    return {'id': c.pk, 'name': c.name, 'business': c.company_name, 'email': c.email,
            'phone': c.phone, 'address': c.address, 'vat_number': c.vat_number, 'notes': c.notes}

def invoice_data(i):
    return {'id': i.pk, 'customer': i.customer_id, 'number': i.invoice_number, 'date': i.issue_date,
            'due': i.due_date, 'status': i.effective_status, 'currency': i.currency, 'subtotal': i.subtotal,
            'taxRate': i.tax_rate, 'tax': i.tax_amount, 'discount': i.discount, 'total': i.total,
            'amount_paid': i.amount_paid, 'balance_due': i.balance_due, 'banking': i.banking,
            'notes': i.notes, 'terms': i.terms, 'items': [{'description': x.description, 'quantity': x.quantity,
            'price': x.unit_price, 'line_total': x.line_total} for x in i.items.all()]}

def payment_data(p):
    return {'id': p.pk, 'invoice': p.invoice_id, 'amount': p.amount, 'date': p.payment_date,
            'method': p.payment_method, 'reference': p.reference, 'notes': p.notes}

def report_data(invoices, payments, customers):
    active = [i for i in invoices if i.effective_status not in ('Draft', 'Cancelled')]
    total = lambda values: sum(values, Decimal('0.00'))
    counts = {s: sum(i.effective_status == s for i in invoices) for s, _ in Invoice.STATUSES}
    monthly = {}
    for p in payments:
        key = p.payment_date.strftime('%Y-%m')
        monthly[key] = monthly.get(key, Decimal(0)) + p.amount
    top = []
    for c in customers:
        value = total(i.total for i in active if i.customer_id == c.pk)
        if value:
            top.append({'name': str(c), 'total': value})
    return {'invoice_count': len(invoices), 'payment_count': len(payments), 'counts': counts,
            'invoiced': total(i.total for i in active), 'received': total(p.amount for p in payments),
            'outstanding': total(i.balance_due for i in active),
            'overdue': total(i.balance_due for i in active if i.effective_status == 'Overdue'),
            'monthly': [{'month': k, 'amount': v} for k, v in sorted(monthly.items())],
            'top_customers': sorted(top, key=lambda c: c['total'], reverse=True)[:5]}

def state_data(b):
    invoices = list(b.invoices.prefetch_related('items'))
    customers = list(b.customers.all())
    payments = list(Payment.objects.filter(invoice__business=b).order_by('id'))
    profile = {'name': b.business_name, 'registration': b.registration_number, 'vat': b.vat_number,
               'email': b.email, 'phone': b.phone, 'address': b.address, 'banking': b.banking,
               'logo': '/business/logo/' if b.logo else '', 'owner_name': b.owner_name,
               'bank_name': b.bank_name, 'account_name': b.account_name, 'account_number': b.account_number,
               'branch_code': b.branch_code}
    return {'customers': [customer_data(c) for c in customers], 'invoices': [invoice_data(i) for i in invoices],
            'payments': [payment_data(p) for p in payments], 'profile': profile,
            'settings': {'prefix': b.invoice_prefix, 'next': b.next_invoice_number, 'currency': b.default_currency,
                         'vat': b.default_tax_rate, 'terms': b.payment_terms},
            'summary': report_data(invoices, payments, customers)}

@login_required
def dashboard(request):
    return render(request, 'billing/app.html', {'initial_state': state_data(business_for(request.user))})

@api(['GET'])
def state(request, b, data):
    return JsonResponse(state_data(b))

@api(['GET', 'POST'])
def customers(request, b, data):
    if request.method == 'GET':
        q = request.GET.get('q', '')
        records = b.customers.filter(Q(name__icontains=q) | Q(company_name__icontains=q) | Q(email__icontains=q))
        return JsonResponse({'customers': [customer_data(c) for c in records]})
    form = checked(CustomerForm(data))
    customer = form.save(commit=False)
    customer.business = b
    customer.save()
    return JsonResponse(customer_data(customer), status=201)

@api(['GET', 'POST', 'DELETE'])
def customer(request, b, data, pk):
    c = get_object_or_404(Customer, business=b, pk=pk)
    if request.method == 'DELETE':
        c.delete()
        return JsonResponse({'ok': True})
    if request.method == 'POST':
        c = checked(CustomerForm(data, instance=c)).save()
    return JsonResponse({**customer_data(c), 'invoices': [invoice_data(i) for i in c.invoices.prefetch_related('items')]})

def filtered(request, b):
    f = checked(DateFilterForm(request.GET)).cleaned_data
    invoices = b.invoices.prefetch_related('items').select_related('customer')
    payments = Payment.objects.filter(invoice__business=b).select_related('invoice__customer')
    for key, lookup in [('start', 'gte'), ('end', 'lte')]:
        if f[key]:
            invoices = invoices.filter(**{f'issue_date__{lookup}': f[key]})
            payments = payments.filter(**{f'payment_date__{lookup}': f[key]})
    if f['q']:
        q = f['q']
        invoices = invoices.filter(Q(invoice_number__icontains=q) | Q(customer__name__icontains=q) | Q(customer__company_name__icontains=q))
        payments = payments.filter(Q(invoice__invoice_number__icontains=q) | Q(invoice__customer__name__icontains=q) | Q(invoice__customer__company_name__icontains=q))
    if f['method']:
        payments = payments.filter(payment_method=f['method'])
    invoices = [i for i in invoices if not f['status'] or i.effective_status == f['status']]
    return invoices, list(payments)

@api(['GET', 'POST'])
def invoices(request, b, data):
    if request.method == 'GET':
        return JsonResponse({'invoices': [invoice_data(i) for i in filtered(request, b)[0]]})
    return JsonResponse(invoice_data(save_invoice(b, data)), status=201)

@api(['GET', 'POST', 'DELETE'])
def invoice(request, b, data, pk):
    i = get_object_or_404(Invoice, business=b, pk=pk)
    if request.method == 'DELETE':
        delete_invoice(b, pk)
        return JsonResponse({'ok': True})
    if request.method == 'POST':
        i = save_invoice(b, data, pk)
    return JsonResponse(invoice_data(i))

@api(['POST'])
def invoice_action(request, b, data, pk, action):
    i = get_object_or_404(Invoice, business=b, pk=pk)
    if action == 'paid':
        record_payment(b, {'invoice': pk, 'amount': i.balance_due, 'payment_date': timezone.localdate(), 'payment_method': 'Other'})
        i.refresh_from_db()
    else:
        payload = {'customer': i.customer_id, 'issue_date': i.issue_date, 'due_date': i.due_date,
                   'status': 'Draft' if action == 'duplicate' else 'Cancelled' if action == 'cancel' else 'Unpaid',
                   'tax_rate': i.tax_rate, 'discount': i.discount, 'banking': i.banking, 'notes': i.notes, 'terms': i.terms,
                   'items': list(i.items.values('description', 'quantity', 'unit_price'))}
        if action not in ('duplicate', 'cancel', 'sent'):
            raise Http404
        i = save_invoice(b, payload, None if action == 'duplicate' else pk)
    return JsonResponse(invoice_data(i))

@api(['GET', 'POST'])
def payments(request, b, data):
    if request.method == 'GET':
        return JsonResponse({'payments': [payment_data(p) for p in filtered(request, b)[1]]})
    return JsonResponse(payment_data(record_payment(b, data)), status=201)

@api(['GET'])
def reports(request, b, data):
    invoices, payments = filtered(request, b)
    return JsonResponse(report_data(invoices, payments, b.customers.all()))

@api(['POST'])
def profile(request, b, data):
    checked(ProfileForm(request.POST, request.FILES, instance=b)).save()
    return JsonResponse({'ok': True})

@api(['POST'])
def settings(request, b, data):
    checked(SettingsForm(data, instance=b)).save()
    return JsonResponse({'ok': True})

@login_required
def logo(request):
    b = business_for(request.user)
    if not b.logo:
        raise Http404
    return FileResponse(b.logo.open('rb'))

@login_required
def print_invoice(request, pk):
    i = get_object_or_404(Invoice.objects.select_related('business', 'customer').prefetch_related('items'), pk=pk, business__user=request.user)
    return render(request, 'billing/print.html', {'invoice': i, 'business': i.business, 'customer': i.customer})
