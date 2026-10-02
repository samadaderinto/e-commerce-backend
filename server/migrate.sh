#!/bin/bash
set -euo pipefail

cd /app

/opt/venv/bin/python manage.py migrate --noinput
/opt/venv/bin/python manage.py ensure_default_admin