import os
from pathlib import Path
from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent
PRODUCTION = os.getenv('DJANGO_ENV') == 'production' or os.getenv('RENDER', '').lower() == 'true'
# A small .env reader keeps local setup dependency-free; process variables win.
if not PRODUCTION and (BASE_DIR / '.env').exists():
    for line in (BASE_DIR / '.env').read_text().splitlines():
        if line.strip() and not line.lstrip().startswith('#') and '=' in line:
            key, value = line.split('=', 1)
            os.environ.setdefault(key.strip(), value.strip().strip('\"\''))
DEBUG = os.getenv('DJANGO_DEBUG', 'False').lower() == 'true'
SECRET_KEY = os.getenv('DJANGO_SECRET_KEY')
if not SECRET_KEY:
    raise ImproperlyConfigured('Set DJANGO_SECRET_KEY in your environment or .env.')
ALLOWED_HOSTS = os.getenv('DJANGO_ALLOWED_HOSTS', 'localhost,127.0.0.1,testserver').split(',')
INSTALLED_APPS = ['django.contrib.admin', 'django.contrib.auth', 'django.contrib.contenttypes',
                  'django.contrib.sessions', 'django.contrib.messages', 'django.contrib.staticfiles', 'billing']
MIDDLEWARE = ['django.middleware.security.SecurityMiddleware', 'whitenoise.middleware.WhiteNoiseMiddleware',
              'django.contrib.sessions.middleware.SessionMiddleware', 'django.middleware.common.CommonMiddleware',
              'django.middleware.csrf.CsrfViewMiddleware', 'django.contrib.auth.middleware.AuthenticationMiddleware',
              'django.contrib.messages.middleware.MessageMiddleware', 'django.middleware.clickjacking.XFrameOptionsMiddleware']
ROOT_URLCONF = 'config.urls'
TEMPLATES = [{'BACKEND': 'django.template.backends.django.DjangoTemplates', 'DIRS': [BASE_DIR / 'templates'],
              'APP_DIRS': True, 'OPTIONS': {'context_processors': ['django.template.context_processors.request',
              'django.contrib.auth.context_processors.auth', 'django.contrib.messages.context_processors.messages']}}]
WSGI_APPLICATION = 'config.wsgi.application'
import dj_database_url
DATABASE_URL = os.getenv('DATABASE_URL', '')
DATABASES = {'default': dj_database_url.parse(DATABASE_URL, conn_max_age=60, conn_health_checks=True)} if DATABASE_URL else {
    'default': {'ENGINE': 'django.db.backends.sqlite3',
                'NAME': os.getenv('DJANGO_SQLITE_PATH', str(BASE_DIR / 'db.sqlite3')),
                'OPTIONS': {'timeout': 20}}}
AUTH_PASSWORD_VALIDATORS = [{'NAME': 'django.contrib.auth.password_validation.' + name} for name in
    ['UserAttributeSimilarityValidator', 'MinimumLengthValidator', 'CommonPasswordValidator', 'NumericPasswordValidator']]
LANGUAGE_CODE = 'en-za'
TIME_ZONE = 'Africa/Johannesburg'
USE_I18N = True
USE_TZ = True
STATIC_URL = '/static/'
STATICFILES_DIRS = [BASE_DIR / 'static', ('assets', BASE_DIR / 'assets')]
STATIC_ROOT = BASE_DIR / 'staticfiles'
STORAGES = {'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
            'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage' if DEBUG else 'whitenoise.storage.CompressedManifestStaticFilesStorage'}}
MEDIA_ROOT = BASE_DIR / 'media'
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
LOGIN_URL = '/accounts/login/'
LOGIN_REDIRECT_URL = '/'
LOGOUT_REDIRECT_URL = LOGIN_URL
EMAIL_BACKEND = os.getenv('DJANGO_EMAIL_BACKEND', 'django.core.mail.backends.console.EmailBackend')
EMAIL_HOST = os.getenv('EMAIL_HOST', '')
EMAIL_PORT = int(os.getenv('EMAIL_PORT', '587'))
EMAIL_HOST_USER = os.getenv('EMAIL_HOST_USER', '')
EMAIL_HOST_PASSWORD = os.getenv('EMAIL_HOST_PASSWORD', '')
EMAIL_USE_TLS = os.getenv('EMAIL_USE_TLS', 'True').lower() == 'true'
DEFAULT_FROM_EMAIL = os.getenv('DEFAULT_FROM_EMAIL', 'invoices@localhost')
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SECURE = not DEBUG
SECURE_SSL_REDIRECT = not DEBUG
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_HSTS_SECONDS = int(os.getenv('DJANGO_HSTS_SECONDS', '0' if DEBUG else '31536000'))
SECURE_HSTS_INCLUDE_SUBDOMAINS = os.getenv('DJANGO_HSTS_INCLUDE_SUBDOMAINS', 'False').lower() == 'true'
SECURE_HSTS_PRELOAD = os.getenv('DJANGO_HSTS_PRELOAD', 'False').lower() == 'true'
CSRF_TRUSTED_ORIGINS = [x for x in os.getenv('DJANGO_CSRF_TRUSTED_ORIGINS', '').split(',') if x]

# Render terminates HTTPS before forwarding requests to Gunicorn.
if PRODUCTION:
    if DEBUG:
        raise ImproperlyConfigured('DJANGO_DEBUG must be False in production.')
    if not DATABASE_URL or DATABASES['default']['ENGINE'] != 'django.db.backends.postgresql':
        raise ImproperlyConfigured('Production requires a separate Invoice PostgreSQL DATABASE_URL.')
    # Never run Invoice migrations against the protected Saloon database.
    db = DATABASES['default']
    if any('saloon' in str(db.get(key, '')).lower() for key in ('NAME', 'USER', 'HOST')) or 'dpg-da14jt49v7es73aip03g' in str(db.get('HOST', '')):
        raise ImproperlyConfigured('The Saloon database is off-limits to Invoice.')
    if len(SECRET_KEY) < 50 or len(set(SECRET_KEY)) < 5 or SECRET_KEY.startswith('django-insecure-'):
        raise ImproperlyConfigured('Production requires a strong generated DJANGO_SECRET_KEY.')
    ALLOWED_HOSTS = [h.strip() for h in os.getenv('DJANGO_ALLOWED_HOSTS', '').split(',') if h.strip()]
    render_host = os.getenv('RENDER_EXTERNAL_HOSTNAME', '')
    if render_host:
        ALLOWED_HOSTS.append(render_host)
        CSRF_TRUSTED_ORIGINS.append('https://' + render_host)
    if not ALLOWED_HOSTS or '*' in ALLOWED_HOSTS:
        raise ImproperlyConfigured('Set explicit production hosts or RENDER_EXTERNAL_HOSTNAME.')
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
    SECURE_REDIRECT_EXEMPT = [r'^health/$']
    STORAGES['default'] = {'BACKEND': 'billing.storage.DatabaseStorage'}
