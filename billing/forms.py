from django import forms
from uuid import uuid4
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.contrib.auth.models import User
from django.utils import timezone
from .models import BusinessProfile, Customer, Invoice, InvoiceItem, Payment

class RegistrationForm(UserCreationForm):
    email = forms.EmailField(required=True)
    class Meta:
        model = User
        fields = ['username', 'email', 'password1', 'password2']

    def clean_email(self):
        email = self.cleaned_data['email']
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError('An account already uses this email address. Please log in.')
        return email

class LoginForm(AuthenticationForm):
    """Allow login with either an email address or a username."""
    def clean(self):
        identifier = self.cleaned_data.get('username', '')
        if '@' in identifier and not User.objects.filter(username=identifier).exists():
            matches = list(User.objects.filter(email__iexact=identifier).values_list('username', flat=True)[:2])
            if len(matches) == 1:
                self.cleaned_data['username'] = matches[0]
        return super().clean()

class ProfileForm(forms.ModelForm):
    class Meta:
        model = BusinessProfile
        exclude = ['user', 'default_currency', 'default_tax_rate', 'payment_terms', 'invoice_prefix', 'next_invoice_number']

    def clean_logo(self):
        logo = self.cleaned_data.get('logo')
        if logo and hasattr(logo, 'content_type'):
            if logo.size > 2 * 1024 * 1024 or logo.image.format not in ('PNG', 'JPEG', 'WEBP'):
                raise forms.ValidationError('Use a PNG, JPEG or WebP logo smaller than 2 MB.')
            # Match the served MIME type to validated image content, never an uploaded HTML filename.
            extension = {'PNG': 'png', 'JPEG': 'jpg', 'WEBP': 'webp'}[logo.image.format]
            logo.name = f'{uuid4().hex}.{extension}'
        return logo

class SettingsForm(forms.ModelForm):
    class Meta:
        model = BusinessProfile
        fields = ['default_currency', 'default_tax_rate', 'payment_terms', 'invoice_prefix', 'next_invoice_number']

    def clean_default_currency(self):
        value = self.cleaned_data['default_currency']
        if self.instance.invoices.exists() and value != self.instance.default_currency:
            raise forms.ValidationError('Currency cannot change after invoices exist; reports use one business currency.')
        return value

class CustomerForm(forms.ModelForm):
    class Meta:
        model = Customer
        exclude = ['business']

class InvoiceForm(forms.ModelForm):
    class Meta:
        model = Invoice
        fields = ['customer', 'issue_date', 'due_date', 'status', 'tax_rate', 'discount', 'banking', 'notes', 'terms']

    def __init__(self, *args, business, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['customer'].queryset = Customer.objects.filter(business=business)
        self.fields['status'].choices = [(x, x) for x in ['Draft', 'Unpaid', 'Cancelled']]

    def clean(self):
        data = super().clean()
        if data.get('issue_date') and data.get('due_date') and data['due_date'] < data['issue_date']:
            self.add_error('due_date', 'Due date cannot precede the issue date.')
        return data

class ItemForm(forms.ModelForm):
    class Meta:
        model = InvoiceItem
        fields = ['description', 'quantity', 'unit_price']

class PaymentForm(forms.ModelForm):
    class Meta:
        model = Payment
        fields = ['invoice', 'amount', 'payment_date', 'payment_method', 'reference', 'notes']

    def __init__(self, *args, business, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['invoice'].queryset = Invoice.objects.filter(business=business)

    def clean_payment_date(self):
        value = self.cleaned_data['payment_date']
        if value > timezone.localdate():
            raise forms.ValidationError('Payments cannot be recorded in the future.')
        return value

class DateFilterForm(forms.Form):
    start = forms.DateField(required=False)
    end = forms.DateField(required=False)
    q = forms.CharField(required=False, max_length=200)
    status = forms.ChoiceField(required=False, choices=[('', 'All')] + Invoice.STATUSES)
    method = forms.ChoiceField(required=False, choices=[('', 'All')] + Payment.METHODS)

    def clean(self):
        data = super().clean()
        if data.get('start') and data.get('end') and data['start'] > data['end']:
            raise forms.ValidationError('Start date must be before end date.')
        return data
