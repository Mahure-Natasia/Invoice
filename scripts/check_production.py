"""Validate production settings without connecting to any database."""
import os
import secrets
import subprocess
import sys
from pathlib import Path

root = Path(__file__).resolve().parent.parent
env = {k: v for k, v in os.environ.items() if not k.startswith(
    ('DJANGO_', 'DATABASE_URL', 'RENDER_EXTERNAL_HOSTNAME'))}
env.update(DJANGO_ENV='production', DJANGO_DEBUG='False',
           DJANGO_SECRET_KEY=secrets.token_urlsafe(64),
           DJANGO_ALLOWED_HOSTS='invoice.example.com',
           DATABASE_URL='postgresql://invoice@localhost/invoice_test',
           DJANGO_HSTS_INCLUDE_SUBDOMAINS='True', DJANGO_HSTS_PRELOAD='True')


def check(changes, expected):
    result = subprocess.run(
        [sys.executable, 'manage.py', 'check', '--deploy', '--fail-level', 'WARNING'],
        cwd=root, env=env | changes, capture_output=True, text=True)
    assert (result.returncode == 0) == expected, result.stderr


check({}, True)
check({'DATABASE_URL': ''}, False)
check({'DATABASE_URL': 'sqlite:///db.sqlite3'}, False)
check({'DJANGO_DEBUG': 'True'}, False)
check({'DJANGO_SECRET_KEY': ''}, False)
check({'DJANGO_SECRET_KEY': 'weak'}, False)
check({'DJANGO_ALLOWED_HOSTS': ''}, False)
check({'DJANGO_ALLOWED_HOSTS': '*'}, False)
check({'DATABASE_URL': 'postgresql://saloon@localhost/saloon_ot4c'}, False)
check({'DATABASE_URL': 'postgresql://invoice@dpg-da14jt49v7es73aip03g-a/invoice'}, False)
check({'DJANGO_ALLOWED_HOSTS': '', 'RENDER_EXTERNAL_HOSTNAME': 'invoice-test.onrender.com'}, True)
print('PASS: production settings, required secrets/hosts/PostgreSQL, and Saloon rejection.')
