import json
from datetime import timedelta
from decimal import Decimal
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.test import TestCase, Client
from django.utils import timezone
from billing.models import BusinessProfile, Customer, Invoice, Payment
from billing.services import save_invoice, record_payment

class BillingTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('owner', 'owner@example.com', 'Test-long-pass-384!')
        self.other = User.objects.create_user('other', password='Test-long-pass-384!')
        self.business = BusinessProfile.objects.create(user=self.user)
        self.other_business = BusinessProfile.objects.create(user=self.other)
        self.customer = Customer.objects.create(business=self.business, name='Client', email='client@example.com')
        self.client.force_login(self.user)

    def payload(self, **changes):
        data = {'customer': self.customer.pk, 'issue_date': str(timezone.localdate()),
                'due_date': str(timezone.localdate() + timedelta(days=30)), 'status': 'Unpaid',
                'tax_rate': '15', 'discount': '10', 'items': [
                    {'description': 'Design', 'quantity': '2', 'unit_price': '100.10'},
                    {'description': 'Hosting', 'quantity': '3', 'unit_price': '20'}]}
        return data | changes

    def post(self, url, data):
        return self.client.post(url, json.dumps(data), content_type='application/json')

    def payment(self, invoice, amount):
        return record_payment(self.business, {'invoice': invoice.pk, 'amount': amount,
            'payment_date': timezone.localdate(), 'payment_method': 'EFT'})

    def test_authentication_protection(self):
        self.client.logout()
        for url in ['/', '/api/state/', '/api/customers/', '/api/invoices/', '/api/payments/', '/api/reports/', '/invoices/1/print/']:
            self.assertEqual(self.client.get(url).status_code, 302)

    def test_customer_creation_and_search(self):
        response = self.post('/api/customers/', {'name': 'Alice', 'email': 'alice@example.com', 'company_name': 'Studio'})
        self.assertEqual(response.status_code, 201)
        self.assertEqual(Customer.objects.get(pk=response.json()['id']).business, self.business)
        self.assertEqual(len(self.client.get('/api/customers/?q=studio').json()['customers']), 1)

    def test_invoice_creation_calculates_server_totals(self):
        response = self.post('/api/invoices/', self.payload(total='0.01', amount_paid='9999', invoice_number='FAKE'))
        self.assertEqual(response.status_code, 201, response.content)
        invoice = Invoice.objects.get()
        self.assertEqual(invoice.subtotal, Decimal('260.20'))
        self.assertEqual(invoice.tax_amount, Decimal('39.03'))
        self.assertEqual(invoice.total, Decimal('289.23'))
        self.assertEqual(invoice.balance_due, invoice.total)
        self.assertEqual(invoice.items.count(), 2)
        self.assertTrue(invoice.invoice_number.startswith('INV-'))

    def test_partial_and_final_payment(self):
        invoice = save_invoice(self.business, self.payload())
        self.payment(invoice, '100.00')
        invoice.refresh_from_db()
        self.assertEqual(invoice.balance_due, Decimal('189.23'))
        self.assertEqual(invoice.effective_status, 'Unpaid')
        self.payment(invoice, '189.23')
        invoice.refresh_from_db()
        self.assertEqual(invoice.amount_paid, invoice.total)
        self.assertEqual(invoice.effective_status, 'Paid')
        self.assertEqual(invoice.balance_due, 0)

    def test_overpayments_and_nonpositive_payments_rejected(self):
        invoice = save_invoice(self.business, self.payload())
        for amount in ['289.24', '-1', '0', 'NaN', 'Infinity', '1.001']:
            with self.assertRaises(ValidationError):
                self.payment(invoice, amount)
        self.assertEqual(Payment.objects.count(), 0)

    def test_overdue_logic(self):
        yesterday = timezone.localdate() - timedelta(days=1)
        i = save_invoice(self.business, self.payload(issue_date=str(yesterday), due_date=str(yesterday)))
        self.assertEqual(i.effective_status, 'Overdue')
        draft = save_invoice(self.business, self.payload(issue_date=str(yesterday), due_date=str(yesterday), status='Draft'))
        self.assertEqual(draft.effective_status, 'Draft')

    def test_user_isolation_and_all_invoice_actions(self):
        i = save_invoice(self.business, self.payload())
        self.client.force_login(self.other)
        self.assertEqual(self.client.get('/api/state/').json()['invoices'], [])
        for method in ['get', 'post', 'delete']:
            self.assertEqual(getattr(self.client, method)(f'/api/invoices/{i.pk}/').status_code, 404)
            self.assertEqual(getattr(self.client, method)(f'/api/customers/{self.customer.pk}/').status_code, 404)
        for action in ['paid', 'sent', 'cancel', 'duplicate']:
            self.assertEqual(self.post(f'/api/invoices/{i.pk}/{action}/', {}).status_code, 404)
        self.assertEqual(self.client.get(f'/invoices/{i.pk}/print/').status_code, 404)
        self.assertEqual(self.post('/api/invoices/', self.payload()).status_code, 400)
        self.assertEqual(self.post('/api/payments/', {'invoice': i.pk, 'amount': '1', 'payment_date': str(timezone.localdate()), 'payment_method': 'Cash'}).status_code, 400)

    def test_invalid_invoices_are_atomic(self):
        cases = [self.payload(items=[]), self.payload(discount='999'), self.payload(tax_rate='101'),
                 self.payload(due_date='2000-01-01'), self.payload(items=[{'description': 'X', 'quantity': '0', 'unit_price': '10'}]),
                 self.payload(items=[{'description': 'X', 'quantity': '1', 'unit_price': '-10'}]), self.payload(items=['bad'])]
        for payload in cases:
            self.assertEqual(self.post('/api/invoices/', payload).status_code, 400)
        self.assertEqual(Invoice.objects.count(), 0)

    def test_edit_below_paid_rejected_and_original_retained(self):
        i = save_invoice(self.business, self.payload())
        self.payment(i, '200')
        with self.assertRaises(ValidationError):
            save_invoice(self.business, self.payload(discount='150'), i.pk)
        i.refresh_from_db()
        self.assertEqual(i.total, Decimal('289.23'))
        self.assertEqual(i.items.count(), 2)
        self.assertEqual(self.client.delete(f'/api/invoices/{i.pk}/').status_code, 400)

    def test_duplicate_and_unique_numbers(self):
        i = save_invoice(self.business, self.payload())
        response = self.post(f'/api/invoices/{i.pk}/duplicate/', {})
        self.assertEqual(response.status_code, 200)
        self.assertNotEqual(response.json()['number'], i.invoice_number)
        self.assertEqual(response.json()['status'], 'Draft')

    def test_reports_dates_and_print_escape_html(self):
        self.customer.name = '<script>alert(1)</script>'
        self.customer.save()
        i = save_invoice(self.business, self.payload())
        self.payment(i, '100')
        data = self.client.get('/api/reports/').json()
        self.assertEqual(data['received'], '100.00')
        self.assertEqual(data['outstanding'], '189.23')
        self.assertEqual(self.client.get('/api/reports/?start=2099-01-01').json()['invoice_count'], 0)
        self.assertEqual(self.client.get('/api/reports/?start=nope').status_code, 400)
        response = self.client.get(f'/invoices/{i.pk}/print/')
        self.assertContains(response, '&lt;script&gt;')
        self.assertNotContains(response, '<script>alert')
        self.assertContains(self.client.get('/'), 'initial-state')

    def test_csrf_enforced_and_logout_requires_post(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.user)
        self.assertEqual(client.post('/api/customers/', {}).status_code, 403)
        self.assertEqual(client.get('/accounts/logout/').status_code, 405)

    def test_registration_login_logout(self):
        self.client.logout()
        response = self.client.post('/accounts/register/', {'username': 'newowner', 'email': 'new@example.com',
            'password1': 'Unique-long-pass-872!', 'password2': 'Unique-long-pass-872!'})
        self.assertRedirects(response, '/')
        self.assertTrue(BusinessProfile.objects.filter(user__username='newowner').exists())
        self.client.post('/accounts/logout/')
        self.assertRedirects(self.client.post('/accounts/login/', {'username': 'newowner', 'password': 'Unique-long-pass-872!'}), '/')
