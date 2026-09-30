#!/usr/bin/env bash
set -euo pipefail
pip install -r requirements.lock.txt
python manage.py collectstatic --noinput
