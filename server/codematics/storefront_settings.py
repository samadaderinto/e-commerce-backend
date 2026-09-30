"""Runnable first-party commerce API, without optional legacy integrations."""
from .settings import *  # noqa: F403
from django.core.exceptions import ImproperlyConfigured

DEBUG = os.environ.get('DJANGO_DEBUG', 'true').lower() == 'true'
SECRET_KEY = os.environ.get('SECRET_KEY', 'local-proace-development-key-do-not-deploy')
if not DEBUG and SECRET_KEY == 'local-proace-development-key-do-not-deploy':
    raise ImproperlyConfigured('Set SECRET_KEY before running with DJANGO_DEBUG=false.')
ALLOWED_HOSTS = os.environ.get('ALLOWED_HOSTS', '127.0.0.1,localhost,testserver').split(',')
INSTALLED_APPS = [
    'django.contrib.auth', 'django.contrib.contenttypes', 'django.contrib.sessions',
    'rest_framework', 'rest_framework_simplejwt.token_blacklist',
    'drf_spectacular', 'taggit',
    'core', 'store', 'product', 'cart', 'payment', 'storefront',
]
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]
ROOT_URLCONF = 'storefront.urls'
DATABASES = {'default': {
    'ENGINE': 'django.db.backends.sqlite3',
    'NAME': os.environ.get('SQLITE_DATABASE_PATH', str(BASE_DIR / 'storefront.sqlite3')),
    'OPTIONS': {'timeout': 20},
}}
REST_FRAMEWORK = {
    'DEFAULT_PERMISSION_CLASSES': ['rest_framework.permissions.IsAuthenticated'],
    'DEFAULT_AUTHENTICATION_CLASSES': ['rest_framework_simplejwt.authentication.JWTAuthentication'],
    'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema',
    'DEFAULT_THROTTLE_CLASSES': ['rest_framework.throttling.ScopedRateThrottle'],
    'DEFAULT_THROTTLE_RATES': {'auth': '10/minute'},
    'DEFAULT_RENDERER_CLASSES': ['rest_framework.renderers.JSONRenderer'],
}
SPECTACULAR_SETTINGS = {
    'TITLE': 'Proace Commerce API',
    'DESCRIPTION': (
        'OpenAPI documentation for the Proace customer storefront and merchant API. '
        'Authenticated endpoints use a JWT bearer access token.'
    ),
    'VERSION': '1.0.0',
    'SERVE_INCLUDE_SCHEMA': False,
    'COMPONENT_SPLIT_REQUEST': True,
}
SIMPLE_JWT = {
    **SIMPLE_JWT,
    'SIGNING_KEY': SECRET_KEY,
    'ACCESS_TOKEN_LIFETIME': timedelta(minutes=15),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=7),
    'ROTATE_REFRESH_TOKENS': False,
    'CHECK_REVOKE_TOKEN': True,
}
EMAIL_BACKEND = os.environ.get('EMAIL_BACKEND', 'django.core.mail.backends.console.EmailBackend')
EMAIL_PORT = int(os.environ.get('EMAIL_PORT', '587'))
EMAIL_USE_TLS = os.environ.get('EMAIL_USE_TLS', 'true').lower() == 'true'
DEFAULT_FROM_EMAIL = os.environ.get('DEFAULT_FROM_EMAIL', 'Proace <hello@proace.example>')
FRONTEND_URL = os.environ.get('FRONTEND_URL', 'http://localhost:3000')
SESSION_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SECURE = not DEBUG
SECURE_CONTENT_TYPE_NOSNIFF = True
PASSWORD_RESET_TIMEOUT = 3600
MEDIA_ROOT = BASE_DIR / 'media'
MEDIA_URL = '/media/'
