#!/bin/bash
set -e

mkdir -p /data /var/lib/litefs

for i in 1 2 3 4 5; do
    if python manage.py migrate --noinput; then
        break
    fi
    echo "migrate attempt $i failed, retrying in 2s..."
    sleep 2
done

python manage.py qcluster &

exec gunicorn config.wsgi:application --bind 0.0.0.0:8080 --workers 1 --threads 4 --timeout 120 --access-logfile -
