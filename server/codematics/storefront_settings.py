"""Runnable first-party commerce API, without optional legacy integrations."""
from .settings import *  # noqa: F403
from django.core.exceptions import ImproperlyConfigured

DEBUG = os.environ.get('DJANGO_DEBUG', 'true').lower() == 'true'
SECRET_KEY = os.environ.get('SECRET_KEY', 'local-proace-development-key-do-not-deploy')
if not DEBUG and SECRET_KEY == 'local-proace-development-key-do-not-deploy':
    raise ImproperlyConfigured('Set SECRET_KEY before running with DJANGO_DEBUG=false.')
ALLOWED_HOSTS = os.environ.get('ALLOWED_HOSTS', '127.0.0.1,localhost,testserver').split(',')
INSTALLED_APPS = [
    'django.contrib.admin', 'django.contrib.auth', 'django.contrib.contenttypes',
    'django.contrib.sessions', 'django.contrib.messages', 'django.contrib.staticfiles',
    'rest_framework', 'rest_framework_simplejwt.token_blacklist',
    'corsheaders',
    'drf_spectacular', 'taggit',
    'core', 'store', 'product', 'cart', 'payment', 'affiliates', 'notification',
    'observability', 'staff', 'storefront',
    'django_cleanup.apps.CleanupConfig',
]
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
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
    'DEFAULT_AUTHENTICATION_CLASSES': ['core.access.BackofficeJWTAuthentication'],
    'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema',
    'DEFAULT_THROTTLE_CLASSES': ['rest_framework.throttling.ScopedRateThrottle'],
    'DEFAULT_THROTTLE_RATES': {'auth': '10/minute'},
    'DEFAULT_RENDERER_CLASSES': ['rest_framework.renderers.JSONRenderer'],
}
SWAGGER_API_DESCRIPTION = """# ProAce Multi-Vendor Commerce REST API

Welcome to the official API documentation for the **ProAce Commerce Platform**.
This API powers the Next.js customer storefront, merchant store management portal, admin moderation dashboards, and automated fulfillment workflows.

---

### Core Capabilities
* **Storefront & Catalog**: Public product discovery, category hierarchies, brand filters, variants, and specifications.
* **Customer Cart & Bag**: Line-item calculation, promotional discounts, and guest-to-account cart synchronization.
* **Fulfillment & Checkout**: Shipping rate lookups, Stripe payment intent creation, and instant store credit checkout.
* **Orders & Real-Time Tracking**: Full lifecycle status transitions (`pending` &rarr; `confirmed` &rarr; `shipped` &rarr; `delivered`), integrated carrier tracking timelines, and refund requests.
* **Customer Digital Wallet**: Store credit refunds, deposits, and transparent audit ledgers.
* **Multi-Vendor Merchant Engine**: Store profiles, automated seller tier calculation, escrow hold periods, and payout disbursements.
* **Event Notifications & Alerts**: Real-time customer activity feeds and web push notifications.
* **System Observability**: Prometheus metrics export and health check probes (`/health/live/`, `/health/ready/`, `/health/status/`).

---

### Authentication & Authorization
Authenticated endpoints require a JSON Web Token (JWT) in the `Authorization` header:

```http
Authorization: Bearer <your_access_token>
```

1. **Obtain Tokens**: Submit credentials to `POST /api/v1/auth/login/` for an access token (15m lifetime) and refresh token (7d lifetime).
2. **Refresh Access**: Call `POST /api/v1/auth/refresh/` using your refresh token when access expires.
3. **Logout**: Call `POST /api/v1/auth/logout/` to invalidate the refresh token session.

---

### Rate Limiting
Sensitive endpoints are protected with throttling policies:
* **Authentication (`/api/v1/auth/*`)**: 10 requests per minute per IP. Excess calls receive HTTP `429 Too Many Requests`.

---

### Support & Resources
* **Technical Contact**: [developer@proace.local](mailto:developer@proace.local)
* **Frontend Web App**: [http://localhost:3000](http://localhost:3000)
* **Grafana Observability Portal**: [http://localhost:3002](http://localhost:3002)
"""

SPECTACULAR_SETTINGS = {
    'TITLE': 'ProAce Multi-Vendor Commerce API',
    'DESCRIPTION': SWAGGER_API_DESCRIPTION.strip(),
    'VERSION': '1.0.0',
    'SERVE_INCLUDE_SCHEMA': False,
    'COMPONENT_SPLIT_REQUEST': True,
    'CONTACT': {
        'name': 'ProAce Platform Engineering',
        'email': 'developer@proace.local',
        'url': 'https://proace.local',
    },
    'LICENSE': {
        'name': 'MIT License',
        'url': 'https://opensource.org/licenses/MIT',
    },
    'TAGS': [
        {'name': 'Authentication & Account', 'description': 'User registration, JWT login, token rotation, and profile management.'},
        {'name': 'Storefront Catalog', 'description': 'Public product listings, category filters, specifications, and store showcases.'},
        {'name': 'Customer Cart & Bag', 'description': 'Shopping cart management and line item quantity adjustments.'},
        {'name': 'Checkout & Payments', 'description': 'Shipping rate calculation, Stripe session creation, and wallet checkout.'},
        {'name': 'Orders & Fulfillment', 'description': 'Order lifecycle, live carrier tracking events, and refund processing.'},
        {'name': 'Customer Wallet', 'description': 'Digital store credit balances and transaction audit trails.'},
        {'name': 'Merchant Stores', 'description': 'Store profiles, vendor tiers, verification status, and public showcase.'},
        {'name': 'Merchant Financials', 'description': 'Sales earnings ledgers, platform fee splits, and withdrawal payouts.'},
        {'name': 'Promotions & Coupons', 'description': 'Discount codes and coupon redemptions.'},
        {'name': 'Notifications', 'description': 'In-app notification feed, read tracking, and push devices.'},
        {'name': 'Staff & Moderation', 'description': 'Vendor verification, staff accounts, and dispute resolution.'},
        {'name': 'System & Observability', 'description': 'Health check probes and Prometheus metrics.'},
    ],
    'SWAGGER_UI_SETTINGS': {
        'deepLinking': True,
        'persistAuthorization': True,
        'displayRequestDuration': True,
        'docExpansion': 'list',
        'filter': True,
        'defaultModelsExpandDepth': 2,
        'defaultModelExpandDepth': 2,
        'showCommonExtensions': True,
    },
    'REDOC_UI_SETTINGS': {
        'expandResponses': '200,201',
        'hideDownloadButton': False,
        'pathInMiddlePanel': True,
    },
}
SIMPLE_JWT = {
    **SIMPLE_JWT,
    'SIGNING_KEY': SECRET_KEY,
    'ACCESS_TOKEN_LIFETIME': timedelta(minutes=15),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=7),
    'ROTATE_REFRESH_TOKENS': False,
    'CHECK_REVOKE_TOKEN': True,
}
RESEND_API_KEY = os.environ.get('RESEND_API_KEY', '')
RESEND_FROM_EMAIL = os.environ.get(
    'RESEND_FROM_EMAIL',
    'ProAce <admin@proaceintl.com>',
)
DEFAULT_FROM_EMAIL = RESEND_FROM_EMAIL
APPLICATION_EMAIL = RESEND_FROM_EMAIL
default_email_backend = (
    'notification.email_backend.ResendEmailBackend'
    if (RESEND_API_KEY or not DEBUG)
    else 'django.core.mail.backends.console.EmailBackend'
)
EMAIL_BACKEND = os.environ.get('EMAIL_BACKEND', default_email_backend)
CELERY_TASK_ALWAYS_EAGER = os.environ.get(
    'CELERY_TASK_ALWAYS_EAGER',
    'false',
).lower() == 'true'
CELERY_TASK_EAGER_PROPAGATES = CELERY_TASK_ALWAYS_EAGER
FRONTEND_URL = os.environ.get('FRONTEND_URL', 'http://localhost:3000')
CORS_ALLOWED_ORIGINS = [origin.strip() for origin in os.environ.get('CORS_ALLOWED_ORIGINS', FRONTEND_URL).split(',') if origin.strip()]
CSRF_TRUSTED_ORIGINS = [
    origin.strip()
    for origin in os.environ.get('CSRF_TRUSTED_ORIGINS', '').split(',')
    if origin.strip()
]
if not DEBUG:
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
    SECURE_SSL_REDIRECT = os.environ.get('SECURE_SSL_REDIRECT', 'true').lower() == 'true'
    SECURE_HSTS_SECONDS = int(os.environ.get('SECURE_HSTS_SECONDS', '31536000'))
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
FCM_ENABLED = os.environ.get('FCM_ENABLED', 'false').lower() == 'true'
FIREBASE_PROJECT_ID = os.environ.get('FIREBASE_PROJECT_ID', '')
FIREBASE_CREDENTIALS_JSON = os.environ.get('FIREBASE_CREDENTIALS_JSON', '')
if FCM_ENABLED and not (FIREBASE_PROJECT_ID and (
    FIREBASE_CREDENTIALS_JSON or os.environ.get('GOOGLE_APPLICATION_CREDENTIALS')
)):
    raise ImproperlyConfigured(
        'Set FIREBASE_PROJECT_ID and Firebase credentials when FCM_ENABLED=true.'
    )
STRIPE_WALLET_PAYMENT_METHODS = os.environ.get('STRIPE_WALLET_PAYMENT_METHODS', 'card,cashapp')
STRIPE_CURRENCY = os.environ.get('STRIPE_CURRENCY', 'usd')
STRIPE_WEBHOOK_SECRET = os.environ.get('STRIPE_WEBHOOK_SECRET', '').strip()
GOOGLE_CLIENT_ID = os.environ.get('GOOGLE_CLIENT_ID', '').strip()
APPLE_CLIENT_ID = os.environ.get('APPLE_CLIENT_ID', '').strip()
SESSION_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SECURE = not DEBUG
SESSION_COOKIE_SAMESITE = 'Lax'
CSRF_COOKIE_SAMESITE = 'Lax'
SECURE_CONTENT_TYPE_NOSNIFF = True
PASSWORD_RESET_TIMEOUT = 3600
MEDIA_ROOT = BASE_DIR / 'media'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STORAGES = {
    **STORAGES,
    'staticfiles': {'BACKEND': 'whitenoise.storage.CompressedManifestStaticFilesStorage'},
}
REFUND_WINDOW_DAYS = int(os.environ.get('REFUND_WINDOW_DAYS', '7'))
PLATFORM_FEE_PERCENT = Decimal(os.environ.get('PLATFORM_FEE_PERCENT', '4.00'))

configure_observability(globals())
