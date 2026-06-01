#!/bin/bash
set -e

if [ "$1" = "python" ] && [ "$2" = "manage.py" ] && [ "$3" = "qcluster" ]; then
    exec python manage.py qcluster
fi

exec gunicorn config.wsgi:application --bind 0.0.0.0:8080 --workers 1 --threads 4 --timeout 120 --access-logfile -
