#!/usr/bin/env sh
set -e

db_path="${DATABASE_PATH:-data/db.sqlite3}"
db_dir=$(dirname "$db_path")
mkdir -p "$db_dir"

python manage.py migrate --noinput
exec gunicorn comitatus.wsgi --bind 0.0.0.0:8080 --workers 2 --timeout 120
