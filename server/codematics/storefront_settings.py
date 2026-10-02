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
    'core', 'store', 'product', 'cart', 'payment', 'affiliates', 'notification', 'storefront',
    'django_cleanup.apps.CleanupConfig',
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
if DATABASE_ENGINE not in {'postgres', 'postgresql'}:
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
    'TITLE': 'ProAce Commerce API',
    'DESCRIPTION': (
        'OpenAPI documentation for the ProAce customer storefront and merchant API. '
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
EMAIL_BACKEND = 'notification.email_backend.ResendEmailBackend'
RESEND_API_KEY = os.environ.get('RESEND_API_KEY', '')
RESEND_FROM_EMAIL = os.environ.get(
    'RESEND_FROM_EMAIL',
    'ProAce <notifications@example.com>',
)
DEFAULT_FROM_EMAIL = RESEND_FROM_EMAIL
APPLICATION_EMAIL = RESEND_FROM_EMAIL
FRONTEND_URL = os.environ.get('FRONTEND_URL', 'http://localhost:3000')
FCM_ENABLED = os.environ.get('FCM_ENABLED', 'false').lower() == 'true'
FIREBASE_PROJECT_ID = os.environ.get('FIREBASE_PROJECT_ID', '')
FIREBASE_CREDENTIALS_JSON = os.environ.get('FIREBASE_CREDENTIALS_JSON', '')
if FCM_ENABLED and not (FIREBASE_PROJECT_ID and (
    FIREBASE_CREDENTIALS_JSON or os.environ.get('GOOGLE_APPLICATION_CREDENTIALS')
)):
    raise ImproperlyConfigured(
        'Set FIREBASE_PROJECT_ID and Firebase credentials when FCM_ENABLED=true.'
    )
STRIPE_WALLET_PAYMENT_METHODS = os.environ.get('STRIPE_WALLET_PAYMENT_METHODS', 'cashapp')
STRIPE_CURRENCY = os.environ.get('STRIPE_CURRENCY', 'usd')
SESSION_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SECURE = not DEBUG
SECURE_CONTENT_TYPE_NOSNIFF = True
PASSWORD_RESET_TIMEOUT = 3600
MEDIA_ROOT = BASE_DIR / 'media'

configure_observability(globals())
