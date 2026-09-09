# Invoice on Render

`render.yaml` defines only a separate **Free Invoice web service** from
`Mahure-Natasia/Invoice`, branch `main`, in Oregon. It does not create a database
or upgrade a workspace. Automatic deploys are off for explicit rollout control.
Never supply Saloon's database URL or change any Saloon resources.

Before creating any paid resource, obtain approval for its compute and storage
price. Provision Invoice's own PostgreSQL database in the same region, then set
its internal connection URL as `DATABASE_URL` on Invoice only. Production rejects
SQLite, missing database URLs, and known Saloon database identifiers.

`DJANGO_ENV=production` (or Render's `RENDER=true`) disables local `.env` loading.
Generate `DJANGO_SECRET_KEY` in Render; never commit it. Keep `DJANGO_DEBUG=False`.
Render's `RENDER_EXTERNAL_HOSTNAME` supplies the exact service host and HTTPS CSRF
origin. For custom domains set comma-separated `DJANGO_ALLOWED_HOSTS` and
`DJANGO_CSRF_TRUSTED_ORIGINS`. The Blueprint enables HSTS including subdomains
and preload for the dedicated service hostname.

Build: `bash build.sh` installs dependencies, checks production security settings,
and collects compressed, hashed static files with WhiteNoise. Startup:
`bash start.sh` migrates **Invoice's database only**, then starts Gunicorn on
`0.0.0.0:$PORT` (one worker, two threads). Free web services have no separate
pre-deploy command. `/health/` performs a read-only database probe and returns
200 when available or 503 without private error details.

Production business logos use `billing.storage.DatabaseStorage`, preserving the
existing authenticated logo route and persisting upload bytes in Invoice's own
PostgreSQL database instead of the Free service's temporary filesystem. Existing
local SQLite data and logos are not automatically imported. Build/start scripts
create no demo data or administrator accounts. Register through the app after
deployment; administrator access is a separate manual operation.

Email uses the existing `DJANGO_EMAIL_BACKEND`, `EMAIL_*` and `DEFAULT_FROM_EMAIL`
variables. Configure an email provider before relying on password-reset email
delivery; the default console backend does not deliver email.

## Verification

Run `python manage.py test --settings=config.test_settings --noinput` for isolated
regression tests and `python scripts/check_production.py` for production settings
validation (no database connections). GitHub Actions runs the production build,
migrations/tests against disposable PostgreSQL 18, and actual Gunicorn, health
and static-file HTTP checks on Linux. Gunicorn cannot start natively on Windows.
The CI database contains only disposable test data and never connects to Render.
Require successful checks before deployment.

For local migration smoke checks, use a disposable database via
`DJANGO_SQLITE_PATH`; do not overwrite the existing local business database.
SQLite testing alone does not verify PostgreSQL behavior.
