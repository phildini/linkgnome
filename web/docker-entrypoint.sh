#!/bin/bash
set -e

litefs mount -config /etc/litefs.yml &

for i in 1 2 3 4 5 6 7 8 9 10; do
    if mountpoint -q /data 2>/dev/null; then
        break
    fi
    sleep 1
done

mkdir -p /data /var/lib/litefs

python manage.py migrate --noinput

if [ "$1" = "python" ] && [ "$2" = "manage.py" ] && [ "$3" = "qcluster" ]; then
    exec python manage.py qcluster
fi

exec gunicorn config.wsgi:application --bind 0.0.0.0:8080 --workers 1 --threads 4 --timeout 120 --access-logfile -
