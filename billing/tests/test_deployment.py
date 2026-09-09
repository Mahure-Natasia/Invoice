from unittest.mock import patch
from django.db import OperationalError
from django.core.files.base import ContentFile
from django.test import TestCase, override_settings
from billing.storage import DatabaseStorage
from billing.tests import test_accounts


class DeploymentTests(TestCase):
    def test_health_checks_database_without_login(self):
        self.assertEqual(self.client.get('/health/').json(), {'status': 'ok'})
        with patch('config.health.connection.cursor', side_effect=OperationalError('private detail')):
            response = self.client.get('/health/')
        self.assertEqual(response.status_code, 503)
        self.assertNotContains(response, 'private detail', status_code=503)

    def test_uploaded_logo_survives_storage_instance_recreation(self):
        storage = DatabaseStorage()
        name = storage.save('logos/logo.png', ContentFile(b'logo bytes'))
        reopened = DatabaseStorage()
        with reopened.open(name) as content:
            self.assertEqual(content.read(), b'logo bytes')
        self.assertEqual(reopened.size(name), 10)
        reopened.delete(name)
        self.assertFalse(storage.exists(name))
        with self.assertRaises(FileNotFoundError):
            storage.open(name)


@override_settings(STORAGES={
    'default': {'BACKEND': 'billing.storage.DatabaseStorage'},
    'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'},
})
class DatabaseLogoTests(test_accounts.AccountTests):
    """Exercise existing account/logo isolation flows with production storage."""
