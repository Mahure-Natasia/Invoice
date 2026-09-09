"""Explicit, atomic migration of a user's exported browser data."""
import base64
import json
from decimal import Decimal
from pathlib import Path
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from billing.forms import CustomerForm, ProfileForm, SettingsForm
from billing.models import BusinessProfile
from billing.services import checked, save_invoice, record_payment

class Command(BaseCommand):
    help = 'Import an exported eieaas_invoicing_v1 JSON file into an empty account, with server validation.'

    def add_arguments(self, parser):
        parser.add_argument('file')
        parser.add_argument('--username', required=True)

    @transaction.atomic
    def handle(self, *args, **options):
        try:
            user = User.objects.get(username=options['username'])
            b, _ = BusinessProfile.objects.get_or_create(user=user)
            if b.customers.exists() or b.invoices.exists():
                raise CommandError('Use an empty account. Existing records are never overwritten.')
            raw = json.loads(Path(options['file']).read_text(encoding='utf-8'), parse_float=Decimal)
            p, s = raw.get('profile', {}), raw.get('settings', {})
            profile = {'business_name': p.get('name') or 'My Business', 'registration_number':p.get('registration',''),
                       'vat_number':p.get('vat',''), **{key:p.get(key,'') for key in ['email','phone','address','banking']}}
            checked(ProfileForm(profile, instance=b)).save()
            checked(SettingsForm({'default_currency':s.get('currency','ZAR'),'default_tax_rate':s.get('vat',15),
                'payment_terms':s.get('terms',b.payment_terms),'invoice_prefix':s.get('prefix','INV-'),
                'next_invoice_number':s.get('next',1)}, instance=b)).save()
            customers, invoices = {}, {}
            for c in raw.get('customers', []):
                if str(c['id']) in customers:
                    raise CommandError('Duplicate customer ID in export.')
                form = checked(CustomerForm({**c, 'company_name':c.get('business','')}))
                customer = form.save(commit=False)
                customer.business = b
                customer.save()
                customers[str(c['id'])] = customer.pk
            for i in raw.get('invoices', []):
                if str(i['id']) in invoices:
                    raise CommandError('Duplicate invoice ID in export.')
                invoice = save_invoice(b, {'customer':customers[str(i['customer'])], 'issue_date':i['date'], 'due_date':i['due'],
                    'status':i['status'] if i['status'] in ['Draft','Cancelled'] else 'Unpaid', 'tax_rate':i.get('taxRate',0),
                    'discount':i.get('discount',0),'banking':i.get('banking',''),'notes':i.get('notes',''),'terms':'',
                    'items':[{'description':x['description'],'quantity':x['quantity'],'unit_price':x['price']} for x in i['items']]})
                invoice.invoice_number = str(i['number'])
                invoice.full_clean()
                invoice.save(update_fields=['invoice_number'])
                invoices[str(i['id'])] = invoice.pk
            for p in raw.get('payments', []):
                record_payment(b, {'invoice':invoices[str(p['invoice'])], 'amount':p['amount'], 'payment_date':p['date'],
                    'payment_method':p['method'],'reference':p.get('reference',''),'notes':p.get('notes','')})
            # Save the logo last, after financial validation, to avoid orphan files on failed imports.
            if raw.get('profile', {}).get('logo'):
                header, encoded = raw['profile']['logo'].split(',', 1)
                content_type = header.removeprefix('data:').split(';')[0]
                ext = {'image/png':'png','image/jpeg':'jpg','image/webp':'webp'}.get(content_type)
                if not ext:
                    raise CommandError('Unsupported logo format; export a PNG, JPEG or WebP logo.')
                logo = SimpleUploadedFile('imported.'+ext, base64.b64decode(encoded, validate=True), content_type=content_type)
                checked(ProfileForm(profile, {'logo':logo}, instance=b)).save()
        except (User.DoesNotExist, OSError, ValueError, KeyError, TypeError, ValidationError) as exc:
            raise CommandError(f'Import rolled back: {exc}') from exc
        self.stdout.write(self.style.SUCCESS(f'Imported {len(customers)} customers and {len(invoices)} invoices. Totals were recalculated.'))
