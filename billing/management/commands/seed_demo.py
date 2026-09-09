import os
import secrets
from datetime import timedelta
from django.contrib.auth.models import User
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone
from billing.models import BusinessProfile, Customer
from billing.services import save_invoice, record_payment

class Command(BaseCommand):
    help = 'Create an isolated demo account and realistic invoices. Existing accounts are never overwritten.'

    def add_arguments(self, parser):
        parser.add_argument('--username', default='demo')

    @transaction.atomic
    def handle(self, *args, **options):
        username = options['username']
        if User.objects.filter(username=username).exists():
            self.stdout.write('Account already exists; no changes made. Use --username for a separate demo.')
            return
        password = os.getenv('DEMO_PASSWORD') or secrets.token_urlsafe(18)
        user = User.objects.create_user(username, 'demo@example.com', password)
        b = BusinessProfile.objects.create(user=user, business_name='Ubuntu Creative Studio', owner_name='Lerato Dlamini',
            email='accounts@example.com', phone='011 555 0142', address='42 Market Street, Johannesburg',
            bank_name='Demo Bank', account_name='Ubuntu Creative Studio', account_number='0001234567', branch_code='000001',
            banking='Demonstration banking details only. Use the invoice number as reference.')
        names = ['Moya Botanics', 'Soweto Coffee Co.', 'Highveld Consulting', 'Kopano Tech', 'Jozi Design House']
        today = timezone.localdate()
        for n, name in enumerate(names):
            c = Customer.objects.create(business=b, name=['Thando Mokoena','Sipho Nkosi','Aisha Patel','Nandi Khumalo','Pieter Botha'][n],
                company_name=name, email=f'accounts{n+1}@example.com', phone=f'011 555 010{n}', address='Johannesburg, South Africa')
            issued = today - timedelta(days=45 if n == 2 else 10)
            invoice = save_invoice(b, {'customer': c.pk, 'issue_date': issued, 'due_date': issued+timedelta(days=30),
                'status': 'Draft' if n == 0 else 'Cancelled' if n == 4 else 'Unpaid', 'tax_rate':'15','discount':'0',
                'banking':b.banking,'terms':b.payment_terms,'notes':'Thank you for supporting our business.',
                'items':[{'description':'Design services','quantity':str(n+1),'unit_price':'750'},
                         {'description':'Project consultation','quantity':'2','unit_price':'350'}]})
            if n in (1,3):
                record_payment(b, {'invoice':invoice.pk,'amount':'500','payment_date':today,'payment_method':'EFT','reference':'DEMO-PARTIAL'})
                if n == 3:
                    invoice.refresh_from_db()
                    record_payment(b, {'invoice':invoice.pk,'amount':invoice.balance_due,'payment_date':today,'payment_method':'Card','reference':'DEMO-FINAL'})
        self.stdout.write(self.style.SUCCESS(f'Demo created. Username: {username}\nPassword: {password}\nLogin: http://127.0.0.1:8011/accounts/login/'))
