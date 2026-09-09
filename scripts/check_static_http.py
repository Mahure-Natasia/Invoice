"""Check actual Gunicorn/WhiteNoise delivery of a collected CSS asset."""
import os
import sys
import urllib.request
from pathlib import Path
import django

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()
from django.contrib.staticfiles.storage import staticfiles_storage
from django.conf import settings

css = next((settings.BASE_DIR / 'static' / 'billing').glob('*.css'))
path = staticfiles_storage.url('billing/' + css.name)
request = urllib.request.Request(
    'http://127.0.0.1:' + os.getenv('PORT', '10000') + path,
    headers={'X-Forwarded-Proto': 'https'})
with urllib.request.urlopen(request) as response:
    assert response.status == 200
    assert 'text/css' in response.headers['Content-Type']
    assert response.read()
print('PASS: Gunicorn and WhiteNoise serve production CSS.')
