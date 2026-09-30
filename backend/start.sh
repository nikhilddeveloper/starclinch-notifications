#!/usr/bin/env bash
set -euo pipefail
python manage.py migrate --noinput
python manage.py seed_demo
python manage.py bootstrap_admin
exec gunicorn config.wsgi:application --bind "0.0.0.0:${PORT:-8000}" --workers 2 --threads 4 --timeout 120 --access-logfile -
