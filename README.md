# EIEAAS Invoicing

EIEAAS helps small businesses manage customers, create invoices and keep track of payments. The dashboard shows what has been paid, what is outstanding and which invoices need attention.

Built with Django, SQLite and vanilla JavaScript. The app uses email or username login, keeps each business's records separate, and calculates invoice totals on the server.

## Features

- Registration, login, POST logout, password changes and email password resets.
- Private business profiles, validated logo uploads, banking details and invoice defaults.
- Customer creation, editing, deletion, search and invoice history.
- Multiple invoice items, automatically generated numbers, drafts, duplication, editing, cancellation and status filters.
- Decimal calculations, partial/full payments, automatic paid and overdue status, and overpayment prevention.
- Database-backed dashboard, date-filtered reports, monthly cash revenue and top customers.
- Invoice previews with Print / Save as PDF and links to share invoice details by email or WhatsApp.
- Django admin, a demo dataset and an importer for records from the earlier browser-based version.

## Screenshots

The browser checks save desktop and mobile screenshots in `test-artifacts/`, along with a sample invoice PDF. These are generated locally and excluded from version control. See **Tests and checks** below to create them.

## Technology and architecture

Python 3.11+, Django 5.2 LTS, SQLite for local development, PostgreSQL for production, Django templates, vanilla JavaScript, WhiteNoise and Pillow. Playwright is an optional development dependency for browser checks.

```text
config/                  Settings, root URLs and WSGI entry point
billing/models.py        Database relationships
billing/forms.py         Server-side validation and owner-scoped choices
billing/services.py      Atomic invoice and payment calculations
billing/views.py         Authenticated pages, JSON endpoints and reports
billing/urls.py           Named application routes
billing/migrations/      Versioned database schema
billing/management/      Demo and legacy import commands
billing/tests/           Financial, account and isolation tests
templates/billing/       Application shell and invoice documents
templates/registration/  Login, registration and password pages
static/billing/          Stylesheets and browser interactions
assets/                  Illustrations and other static assets
```

Django renders the application shell and passes the initial data through `json_script`. JavaScript handles navigation, forms and modals, using authenticated endpoints to read and save records. Write requests include a CSRF token. Business records are stored in the database.

## Database overview

| Model | Purpose and relationships |
| --- | --- |
| BusinessProfile | One per Django user; contact, banking, logo, currency, tax, terms and numbering defaults |
| Customer | Belongs to a business; contact information, VAT number and notes |
| Invoice | Belongs to a business and customer; dates, status, financial totals and currency |
| InvoiceItem | Belongs to an invoice; description, quantity, price and rounded line total |
| Payment | Belongs to an invoice; amount, date, method, reference and notes |

Invoice numbers are unique per business. Customer deletion is protected while invoices reference it. Invoices with payments cannot be deleted or cancelled. Financial records are read-only in admin so staff cannot bypass service calculations; use the application for financial changes.

## Local installation

PowerShell, from the project directory:

```powershell
py -3.11 -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
.venv\Scripts\python -c "import secrets; print(secrets.token_urlsafe(48))"
```

If you do not already have a `.env` file, create one in the project root:

```dotenv
DJANGO_SECRET_KEY=paste-the-generated-secret-here
DJANGO_DEBUG=True
DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1
```

Keep an existing `.env` file and never commit it. Then:

```powershell
.venv\Scripts\python manage.py migrate
.venv\Scripts\python manage.py createsuperuser
.venv\Scripts\python manage.py runserver 8011
```

Open **http://127.0.0.1:8011/** and register an account. Django admin is available at `/admin/`. You can use a different port by changing the `runserver` argument.

On macOS/Linux use `python3 -m venv .venv` and `.venv/bin/python` in place of the Windows executable.

## Environment variables

| Variable | Purpose |
| --- | --- |
| `DJANGO_SECRET_KEY` | Required random secret; startup fails if missing |
| `DJANGO_DEBUG` | `True` locally; default `False` |
| `DJANGO_ALLOWED_HOSTS` | Comma-separated host names |
| `DJANGO_CSRF_TRUSTED_ORIGINS` | Comma-separated HTTPS origins for production |
| `DJANGO_HSTS_SECONDS` | HTTPS HSTS duration; defaults to one year in production |
| `DJANGO_HSTS_INCLUDE_SUBDOMAINS`, `DJANGO_HSTS_PRELOAD` | Optional HSTS policies; enable only after confirming domain-wide HTTPS readiness |
| `DJANGO_EMAIL_BACKEND` | Console backend locally; use `django.core.mail.backends.smtp.EmailBackend` for SMTP |
| `EMAIL_HOST`, `EMAIL_PORT` | SMTP host and port (default 587) |
| `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD` | SMTP credentials |
| `EMAIL_USE_TLS`, `DEFAULT_FROM_EMAIL` | SMTP TLS and sender address |
| `DEMO_PASSWORD` | Optional password for a newly seeded demo account |

Existing environment variables override `.env`. Local password-reset messages appear in the development server console; SMTP is needed for real email delivery.

## Demo data

```powershell
.venv\Scripts\python manage.py seed_demo
```

The command prints the `demo` account's generated password once. It creates a business, five customers, five invoices spanning the available statuses, multiple items and three payments. Rerunning it leaves an existing account untouched. Use `--username demo2` for another dataset. If a demo password is lost, run `python manage.py changepassword demo` with the virtual environment's Python.

## Tests and checks

```powershell
.venv\Scripts\python manage.py check
.venv\Scripts\python manage.py makemigrations --check --dry-run
.venv\Scripts\python manage.py test
.venv\Scripts\python manage.py collectstatic --noinput
```

Tests cover authentication, registration, password flows, private logos, customer creation, server totals, partial/final payments, invalid money, overdue logic, atomic edits, duplication, filters, print escaping, CSRF and cross-user read/write protection.

Optional browser workflow (start the development server first):

```powershell
.venv\Scripts\python -m pip install -r requirements-dev.txt
$env:PLAYWRIGHT_BROWSERS_PATH="$PWD\.playwright"
.venv\Scripts\python -m playwright install chromium
.venv\Scripts\python scripts/browser_smoke.py
```

The browser check registers isolated test accounts, creates records through the UI, checks payments/reports/printing, and captures desktop/mobile screenshots. It intentionally retains its test records under unique `browser_*` usernames; do not run it against production.

## Pages and endpoints

| Route | Behaviour |
| --- | --- |
| `/` | Authenticated application: dashboard, invoices/editor, customers, payments, reports, profile, settings |
| `/accounts/register/`, `/accounts/login/`, `/accounts/logout/` | Registration, login and POST logout |
| `/accounts/password_change/`, `/accounts/password_reset/` | Standard Django password flows |
| `/api/state/` | Current user's initial/display data |
| `/api/customers/`, `/api/customers/<id>/` | Search/create; view/update/delete and history |
| `/api/invoices/`, `/api/invoices/<id>/` | Search/create; view/update/delete |
| `/api/invoices/<id>/<action>/` | POST `duplicate`, `sent`, `paid` or `cancel` |
| `/api/payments/` | Search or record payment |
| `/api/reports/` | Financial report calculations |
| `/api/profile/`, `/api/settings/` | POST profile multipart form or settings JSON |
| `/business/logo/` | Authenticated user's private logo |
| `/invoices/<id>/print/` | Owner-protected printable document |

Updates use POST, deletions DELETE. Filters accept `q`, `start`, `end`, `status` and `method` where relevant. Dates use `YYYY-MM-DD`. API financial amounts are decimal strings. Invoice writes take `customer`, `issue_date`, `due_date`, `status`, `tax_rate`, `discount`, optional text fields and `items` containing `description`, `quantity`, `unit_price`. Browser-supplied totals and record ownership are ignored.

## Technical Decisions

- **Django ORM:** straightforward relationships and owner-scoped queries without custom SQL. Foreign keys and uniqueness constraints reinforce application validation.
- **Server-side validation:** Django forms validate every write. Customer/invoice choices are scoped to the logged-in business, and direct record URLs perform ownership checks.
- **Decimal for financial calculations:** each line rounds to cents with `ROUND_HALF_UP`; subtotal is the sum of rounded lines, tax is rounded on subtotal, and discount is an absolute amount after tax. Payments reduce the exact balance. The unsaved browser preview uses integer hundredths (`BigInt`).
- **User-level data isolation:** each business belongs to one user; all business endpoints derive that business from the session. Private logos use an authenticated route.
- **Django templates + JavaScript:** preserves the existing interface and modal workflows without introducing a frontend framework. Template escaping and explicit JavaScript escaping protect displayed user content.
- **SQLite locally:** keeps local setup simple. Financial writes use atomic transactions and serialize on the business row, including an initial write for SQLite. PostgreSQL can be adopted by changing `DATABASES`, installing its driver and migrating data; PostgreSQL support has not been tested.
- **Status and reports:** overdue is computed against today's local date, so no scheduled job is required. Drafts/cancelled invoices are excluded from invoiced/outstanding totals. Revenue means payments actually received. Date filters use issue dates for invoices and payment dates for revenue; outstanding is the current balance of invoices in that issue-date range, not a historical balance snapshot.
- **One currency per business:** an invoice snapshots its currency. Currency cannot change after invoices exist, avoiding misleading mixed-currency reports.

## Migrating original browser records

`invoicing.html` is the standalone browser-based version. Its records live in localStorage and are separate from the Django database. The importer requires an explicit export and an empty target account to keep existing records safe.

Open the original prototype in the same browser/origin where it was used. In its developer console, run:

```javascript
const data = localStorage.getItem('eieaas_invoicing_v1');
if (!data) throw new Error('No saved prototype data at this browser origin.');
const link = document.createElement('a');
link.href = URL.createObjectURL(new Blob([data], {type:'application/json'}));
link.download = 'invoicing-export.json';
link.click();
```

Register an empty Django account, then import:

```powershell
.venv\Scripts\python manage.py import_legacy invoicing-export.json --username yourname
```

The importer validates records, preserves invoice numbers, recalculates totals, and rolls back database changes on errors. Existing accounts with business records are rejected. Invalid legacy data (including overpayments previously accepted by the prototype's tolerance) must be corrected before importing. Keep a backup of the original export; it contains private business data.

## Deployment notes and limitations

1. Install requirements in an isolated environment and set a unique secret, `DJANGO_DEBUG=False`, allowed hosts and trusted HTTPS origins.
2. Run migrations, tests and `collectstatic --noinput`. WhiteNoise serves collected static assets. Run `check --deploy` against production settings.
3. Run `config.wsgi:application` with a production WSGI server (for example, a separately installed Waitress on Windows or Gunicorn on Linux), behind HTTPS. Do not use Django's development server for production.
4. Configure the proxy's HTTPS forwarding carefully; only trust forwarded headers from your own proxy. Secure cookies and HTTPS redirects are enabled when debug is off.
5. Persist and back up `db.sqlite3` and `media/`; logos are served through ownership-checked Django views. Never expose the media directory publicly. Consider PostgreSQL for higher write concurrency.
6. Configure SMTP for password-reset delivery. Email/WhatsApp buttons open the user's client with invoice text; PDF attachments remain manual. Marking an invoice sent records its status and does not deliver email.

`check --deploy` leaves the two optional HSTS subdomain/preload warnings until those domain-specific environment settings are enabled. Enable them only when the domain and its subdomains are ready for HTTPS.

This is a single-user-per-business application. Refunds, credit notes, overpayments, payment reversal, exchange rates, historical profile snapshots and automated invoice delivery are not implemented. Printed documents use current customer/business details and saved invoice amounts, terms and banking text. Financial records with payments are retained instead of offering a destructive delete. Large datasets may require pagination and database-level reporting aggregation; the current implementation favors readable code for small businesses.
