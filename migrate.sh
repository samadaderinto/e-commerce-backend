#!/bin/bash

DJANGO_SUPER_USER=${DJANGO_SUPER_USER:-"productace@proaceintl.com"}

/opt/venv/bin/python manage.py createsuperuser --email