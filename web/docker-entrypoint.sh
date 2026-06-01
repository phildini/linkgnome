#!/bin/bash
set -e

litefs mount -config /etc/litefs.yml &

for i in 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15 16 17 18 19 20 21 22 23 24 25 26 27 28 29 30; do
    if mountpoint -q /data 2>/dev/null && [ -f /data/linkgnome.db ]; then
        break
    fi
    sleep 1
done

for i in 1 2 3 4 5; do
    if python manage.py migrate --noinput 2>/dev/null; then
        break
    fi
    sleep 2
done

if [ "$1" = "python" ] && [ "$2" = "manage.py" ] && [ "$3" = "qcluster" ]; then
    exec python manage.py qcluster
fi

exec gunicorn config.wsgi:application --bind 0.0.0.0:8080 --workers 1 --threads 4 --timeout 120 --access-logfile -
