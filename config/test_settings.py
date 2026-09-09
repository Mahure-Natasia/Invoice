"""Isolated tests; never use the local business database or production secrets."""
from tempfile import gettempdir
from pathlib import Path
from .settings import *

SECURE_SSL_REDIRECT = False
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False
PASSWORD_HASHERS = ['django.contrib.auth.hashers.MD5PasswordHasher']
MEDIA_ROOT = Path(gettempdir()) / 'invoice-test-media'
