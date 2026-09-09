import json
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from django.contrib.auth.models import User
from django.core.management import call_command, CommandError
from django.test import TestCase
from django.utils import timezone
from billing.models import BusinessProfile, Invoice, Payment

class CommandTests(TestCase):
    def test_demo_seed_is_repeatable_without_overwriting(self):
        output = StringIO()
        call_command('seed_demo', stdout=output)
        self.assertEqual(Invoice.objects.count(), 5)
        self.assertEqual(Payment.objects.count(), 3)
        call_command('seed_demo', stdout=output)
        self.assertEqual(Invoice.objects.count(), 5)

    def test_legacy_import_recalculates_and_preserves_number(self):
        User.objects.create_user('legacy')
        raw = {'customers':[{'id':1,'name':'Legacy Client','email':'legacy@example.com'}],
            'invoices':[{'id':2,'customer':1,'number':'OLD-1001','date':str(timezone.localdate()),
                'due':str(timezone.localdate()),'status':'Paid','total':999,
                'items':[{'description':'Work','quantity':1,'price':100}]}],
            'payments':[{'invoice':2,'date':str(timezone.localdate()),'method':'Cash','amount':100}]}
        with TemporaryDirectory() as directory:
            path = Path(directory) / 'export.json'
            path.write_text(json.dumps(raw))
            call_command('import_legacy', str(path), username='legacy', stdout=StringIO())
            invoice = Invoice.objects.get()
            self.assertEqual(invoice.invoice_number, 'OLD-1001')
            self.assertEqual(invoice.total, 100)
            self.assertEqual(invoice.effective_status, 'Paid')
            with self.assertRaises(CommandError):
                call_command('import_legacy', str(path), username='legacy', stdout=StringIO())

    def test_invalid_import_rolls_back(self):
        User.objects.create_user('invalid')
        with TemporaryDirectory() as directory:
            path = Path(directory) / 'export.json'
            path.write_text(json.dumps({'customers':[{'id':1,'name':'Invalid','email':'not-an-email'}]}))
            with self.assertRaises(CommandError):
                call_command('import_legacy', str(path), username='invalid', stdout=StringIO())
            self.assertFalse(BusinessProfile.objects.filter(user__username='invalid').exists())
