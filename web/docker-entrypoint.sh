#!/bin/bash
set -e

mkdir -p /data

for i in 1 2 3 4 5; do
    if python manage.py migrate --noinput; then
        break
    fi
    echo "migrate attempt $i failed, retrying in 2s..."
    sleep 2
done

if [ "$1" = "python" ] && [ "$2" = "manage.py" ] && [ "$3" = "qcluster" ]; then
    exec python manage.py qcluster
fi

exec gunicorn config.wsgi:application --bind 0.0.0.0:8080 --workers 1 --threads 4 --timeout 120 --access-logfile -
