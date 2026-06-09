#!/bin/bash
set -e

export PATH="/app/web/.venv/bin:$PATH"

python manage.py migrate --noinput
python manage.py createcachetable

python manage.py qcluster &

exec gunicorn config.wsgi:application --bind 0.0.0.0:8080 --workers 1 --threads 4 --timeout 120 --access-logfile -
