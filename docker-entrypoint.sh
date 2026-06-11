#!/usr/bin/env sh
set -e

python manage.py migrate --noinput
exec gunicorn comitatus.wsgi --bind 0.0.0.0:8080 --workers 2 --timeout 120
