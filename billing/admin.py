from django.contrib import admin
from .models import BusinessProfile, Customer, Invoice, InvoiceItem, Payment

@admin.register(BusinessProfile)
class BusinessAdmin(admin.ModelAdmin):
    list_display = ['business_name', 'user', 'email', 'default_currency']
    search_fields = ['business_name', 'user__username', 'email']

@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ['name', 'company_name', 'business', 'email']
    search_fields = ['name', 'company_name', 'email']
    list_filter = ['business']

class FinancialAdmin(admin.ModelAdmin):
    # Financial writes go through validated application services, including for staff.
    def has_add_permission(self, request):
        return False
    def has_change_permission(self, request, obj=None):
        return False
    def has_delete_permission(self, request, obj=None):
        return False

@admin.register(Invoice)
class InvoiceAdmin(FinancialAdmin):
    list_display = ['invoice_number', 'business', 'customer', 'effective_status', 'total', 'balance_due']
    search_fields = ['invoice_number', 'customer__name']
    list_filter = ['status', 'business', 'issue_date']

@admin.register(InvoiceItem)
class ItemAdmin(FinancialAdmin):
    list_display = ['invoice', 'description', 'quantity', 'unit_price', 'line_total']
    search_fields = ['invoice__invoice_number', 'description']

@admin.register(Payment)
class PaymentAdmin(FinancialAdmin):
    list_display = ['invoice', 'amount', 'payment_date', 'payment_method']
    search_fields = ['invoice__invoice_number', 'reference']
    list_filter = ['payment_method', 'payment_date']
