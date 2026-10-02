"""Test settings using SQLite, isolated from the main development database."""
import os

from .settings import *  # noqa: F403

SECRET_KEY = 'merchant-tests-only-not-for-deployment'
SIMPLE_JWT = {**SIMPLE_JWT, 'SIGNING_KEY': SECRET_KEY}  # noqa: F405
DEBUG = False
ALLOWED_HOSTS = ['testserver', 'localhost']
INSTALLED_APPS = [
    'django.contrib.auth', 'django.contrib.contenttypes', 'django.contrib.sessions',
    'rest_framework', 'taggit', 'core', 'store', 'product', 'cart', 'payment',
    'notification.apps.EventNotificationConfig',
    'observability.apps.ObservabilityConfig',
    'affiliates',
    'drf_spectacular',
    'storefront',
]
try:
    import django_cleanup  # noqa: F401
    INSTALLED_APPS.append('django_cleanup.apps.CleanupConfig')
except ImportError:
    pass
MIDDLEWARE = []
STORAGES = {
    'default': {'BACKEND': 'django.core.files.storage.InMemoryStorage'},
    'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'},
}
MEDIA_URL = '/media/'
ROOT_URLCONF = 'store.test_urls'
TEST_DATABASE_PATH = os.environ.get("SQLITE_TEST_DATABASE_PATH") or os.path.join(BASE_DIR, "test.sqlite3")  # noqa: F405
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': TEST_DATABASE_PATH,
        'TEST': {'NAME': TEST_DATABASE_PATH},
    }
}
PASSWORD_HASHERS = ['django.contrib.auth.hashers.MD5PasswordHasher']
CACHES = {'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'}}
EMAIL_BACKEND = 'django.core.mail.backends.locmem.EmailBackend'
DEFAULT_FROM_EMAIL = 'Proace <hello@proace.test>'
RESEND_API_KEY = 're_test_key'
RESEND_FROM_EMAIL = DEFAULT_FROM_EMAIL
FRONTEND_URL = 'http://testserver'
REST_FRAMEWORK = {
    'DEFAULT_PERMISSION_CLASSES': ['rest_framework.permissions.IsAuthenticated'],
    'DEFAULT_AUTHENTICATION_CLASSES': ['rest_framework_simplejwt.authentication.JWTAuthentication'],
    'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema',
    'EXCEPTION_HANDLER': 'utils.exceptions.custom_exception_handler',
}
