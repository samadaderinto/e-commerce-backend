"""Offline dependencies with an explicitly isolated PostgreSQL audit database."""
from copy import deepcopy

from django.core.exceptions import ImproperlyConfigured

from .test_settings import *  # noqa: F403
from .settings import DATABASES as application_databases

DATABASES = deepcopy(application_databases)
test_database = 'test_proace_audit_47_49'
database = DATABASES['default']
if database['ENGINE'] != 'django.db.backends.postgresql':
    raise ImproperlyConfigured('Concurrency audits require PostgreSQL.')
if database['NAME'] == test_database:
    raise ImproperlyConfigured('The audit database must differ from the application database.')
database['TEST'] = {'NAME': test_database}
database['CONN_MAX_AGE'] = 0
