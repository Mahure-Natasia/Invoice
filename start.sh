#!/usr/bin/env bash
set -euo pipefail
# Free web services do not support a separate pre-deploy command.
python manage.py migrate --noinput
exec gunicorn config.wsgi:application --config gunicorn.conf.py
