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
]
MIDDLEWARE = []
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
REST_FRAMEWORK = {
    'DEFAULT_PERMISSION_CLASSES': ['rest_framework.permissions.IsAuthenticated'],
    'DEFAULT_AUTHENTICATION_CLASSES': ['rest_framework_simplejwt.authentication.JWTAuthentication'],
}
