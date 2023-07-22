#!/bin/bash

APP_PORT = ${PORT:-8000}
cd /app/
/opt/venv/bin/gunicorn --worker-tmp-dir /dev/shm backend.wsgi:apllication --bind "0.0.0.0:${APP_PORT}"