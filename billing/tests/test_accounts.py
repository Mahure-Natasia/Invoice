from io import BytesIO
from tempfile import TemporaryDirectory
from PIL import Image
from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, Client, override_settings
from django.core import mail
from billing.models import BusinessProfile

class AccountTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('logo-owner', 'owner@example.com', 'Long-unique-pass-987!')
        self.client.force_login(self.user)

    def test_email_login_and_username_compatibility(self):
        for identifier in ['OWNER@example.com', 'logo-owner']:
            self.client.logout()
            response = self.client.post('/accounts/login/', {'username':identifier, 'password':'Long-unique-pass-987!'})
            self.assertRedirects(response, '/')

    def test_duplicate_registration_email_rejected(self):
        self.client.logout()
        response = self.client.post('/accounts/register/', {'username':'new-owner', 'email':'OWNER@example.com',
            'password1':'Another-unique-pass-587!', 'password2':'Another-unique-pass-587!'})
        self.assertContains(response, 'An account already uses this email address.')
        self.assertFalse(User.objects.filter(username='new-owner').exists())

    def test_logo_validation_and_private_delivery(self):
        with TemporaryDirectory() as directory, override_settings(MEDIA_ROOT=directory):
            image = BytesIO()
            Image.new('RGB', (10, 10), 'green').save(image, format='PNG')
            response = self.client.post('/api/profile/', {'business_name':'Studio','logo':SimpleUploadedFile('logo.png', image.getvalue(), content_type='image/png')})
            self.assertEqual(response.status_code, 200, response.content)
            response = self.client.get('/business/logo/')
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response['Content-Type'], 'image/png')
            # Consume the test client's stream so it closes the response without
            # closing the PostgreSQL connection inside TestCase's transaction.
            self.assertTrue(b''.join(response.streaming_content))
            self.client.force_login(User.objects.create_user('another'))
            self.assertEqual(self.client.get('/business/logo/').status_code, 404)
            self.client.force_login(self.user)
            response = self.client.post('/api/profile/', {'business_name':'Studio','logo':SimpleUploadedFile('bad.svg', b'<svg onload="alert(1)"></svg>', content_type='image/svg+xml')})
            self.assertEqual(response.status_code, 400)

    @override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
    def test_password_reset_and_change_templates(self):
        self.client.logout()
        self.assertEqual(self.client.get('/accounts/password_reset/').status_code, 200)
        self.assertEqual(self.client.post('/accounts/password_reset/', {'email':'owner@example.com'}).status_code, 302)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('/accounts/reset/', mail.outbox[0].body)
        self.client.force_login(self.user)
        self.assertEqual(self.client.get('/accounts/password_change/').status_code, 200)
        self.assertEqual(self.client.post('/accounts/password_change/', {'old_password':'Long-unique-pass-987!',
            'new_password1':'New-long-unique-pass-541!', 'new_password2':'New-long-unique-pass-541!'}).status_code, 302)

    def test_malformed_requests_return_validation_errors(self):
        for payload in ['[]', '{bad', '{"customer": []}', '{"items":[{"quantity":{}}]}']:
            self.assertEqual(self.client.post('/api/invoices/', payload, content_type='application/json').status_code, 400)

    def test_profile_multipart_with_real_csrf(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.user)
        client.get('/')
        response = client.post('/api/profile/', {'business_name':'Saved Studio'}, HTTP_X_CSRFTOKEN=client.cookies['csrftoken'].value)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(BusinessProfile.objects.get(user=self.user).business_name, 'Saved Studio')
