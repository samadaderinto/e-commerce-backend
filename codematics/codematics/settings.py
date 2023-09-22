"""
Django settings for codematics project.

Generated by 'django-admin startproject' using Django 4.1.4.

For more information on this file, see
https://docs.djangoproject.com/en/4.1/topics/settings/

For the full list of settings and their values, see
https://docs.djangoproject.com/en/4.1/ref/settings/
"""

from datetime import timedelta
import os
from pathlib import Path


# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent
SETTINGS_PATH = os.path.dirname(os.path.dirname(__file__))

# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/4.1/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = str(os.environ.get("SECRET_KEY"))

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = True

ENV_ALLOWED_HOST = str(os.environ.get("ENV_ALLOWED_HOST"))
ALLOWED_HOSTS = ["localhost", "127.0.0.1"]
# if ENV_ALLOWED_HOST:
#     ALLOWED_HOSTS = [ ENV_ALLOWED_HOST ]


# Application definition

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "event_notification.apps.EventNotificationConfig",
    "core.apps.CoreConfig",
    "product.apps.ProductConfig",
    "store.apps.StoreConfig",
    "staff.apps.StaffConfig",
    "payment.apps.PaymentConfig",
    "affiliates.apps.AffiliatesConfig",
    "cart.apps.CartConfig",
    
    
    "django_filters",
    "corsheaders",
    "rest_framework",
    'django_user_agents',
    "phonenumber_field",
  
    "rest_framework_simplejwt",
    "rest_framework_simplejwt.token_blacklist",
    "taggit",
    "stripe",
    "rest_framework_word_filter",
    "notifications",
    "dotenv",
    
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    'django_user_agents.middleware.UserAgentMiddleware',
]

ROOT_URLCONF = "codematics.urls"


TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [os.path.join(SETTINGS_PATH, 'templates')],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]


WSGI_APPLICATION = "codematics.wsgi.application"


# Database
# https://docs.djangoproject.com/en/4.1/ref/settings/#databases


DATABASE_PATH = os.path.join(BASE_DIR, "db.sqlite3")

# if postgres in not online use as default, to avoid errors and stuff
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": DATABASE_PATH,
    }
}

DB_USERNAME = str(os.environ.get("POSTGRES_USER"))
DB_PASSWORD = str(os.environ.get("POSTGRES_PASSWORD"))
DB_DATABASE = str(os.environ.get("POSTGRES_DB"))
DB_HOST = os.environ.get("POSTGRES_HOST")
DB_PORT = os.environ.get("POSTGRES_PORT")
DB_IS_AVAIL = all([DB_USERNAME, DB_PASSWORD, DB_DATABASE, DB_HOST, DB_PORT])
DB_IGNORE_SSL = os.environ.get("DB_ IGNORE_SSL") == "true"



# if DB_IS_AVAIL:
#     DATABASES = {
#         "default": {
#             "ENGINE": "django.db.backends.postgresql",
#             "NAME": DB_DATABASE,
#             "USER": DB_USERNAME,
#             "PASSWORD": DB_PASSWORD,
#             "HOST": DB_HOST,
#             "PORT": DB_PORT,
#         }
#     }


# if not DB_IGNORE_SSL:
#     DATABASES["default"]["OPTIONS"] = {"sslmode": "require"}


# Password validation
# https://docs.djangoproject.com/en/4.1/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]


# Internationalization
# https://docs.djangoproject.com/en/4.1/topics/i18n/

LANGUAGE_CODE = "en-us"

TIME_ZONE = "UTC"

USE_I18N = True

USE_TZ = True

# to change default timezone to that of user
# USE_L10N = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/4.1/howto/static-files/


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/4.0/howto/static-files/

STATIC_URL = "static/"
MEDIA_ROOT = os.path.join(BASE_DIR, "media")
MEDIA_URL = "/media/"

# Default primary key field type
# https://docs.djangoproject.com/en/4.1/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

AUTH_USER_MODEL = "core.User"
AUTH_PROFILE_MODULE = 'core.User'

CORS_ALLOW_METHODS = [
    "DELETE",
    "GET",
    "OPTIONS",
    "PATCH",
    "POST",
    "PUT",
]


CORS_ALLOWED_ORIGINS = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]

CORS_ORIGIN_WHITELIST = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]

REST_FRAMEWORK = {
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ],
    "DEFAULT_FILTER_BACKENDS": [
        "django_filters.rest_framework.DjangoFilterBackend",
    ],
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.LimitOffsetPagination",
    "PAGE_SIZE": 15,
}

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(days=7),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=1),
    "ROTATE_REFRESH_TOKENS": False,
    "BLACKLIST_AFTER_ROTATION": False,
    "UPDATE_LAST_LOGIN": True,
    "ALGORITHM": "HS256",
    "SIGNING_KEY": SECRET_KEY,
    "VERIFYING_KEY": "",
    "AUDIENCE": None,
    "ISSUER": None,
    "JSON_ENCODER": None,
    "JWK_URL": None,
    "LEEWAY": 0,
    "AUTH_HEADER_TYPES": ("Bearer",),
    "AUTH_HEADER_NAME": "HTTP_AUTHORIZATION",
    "USER_ID_FIELD": "id",
    "USER_ID_CLAIM": "user_id",
    "USER_AUTHENTICATION_RULE": "rest_framework_simplejwt.authentication.default_user_authentication_rule",
    "AUTH_TOKEN_CLASSES": ("rest_framework_simplejwt.tokens.AccessToken",),
    "TOKEN_TYPE_CLAIM": "token_type",
    "TOKEN_USER_CLASS": "rest_framework_simplejwt.models.TokenUser",
    "JTI_CLAIM": "jti",
    "SLIDING_TOKEN_REFRESH_EXP_CLAIM": "refresh_exp",
    "SLIDING_TOKEN_LIFETIME": timedelta(minutes=5),
    "SLIDING_TOKEN_REFRESH_LIFETIME": timedelta(days=1),
    "TOKEN_OBTAIN_SERIALIZER": "rest_framework_simplejwt.serializers.TokenObtainPairSerializer",
    "TOKEN_REFRESH_SERIALIZER": "rest_framework_simplejwt.serializers.TokenRefreshSerializer",
    "TOKEN_VERIFY_SERIALIZER": "rest_framework_simplejwt.serializers.TokenVerifySerializer",
    "TOKEN_BLACKLIST_SERIALIZER": "rest_framework_simplejwt.serializers.TokenBlacklistSerializer",
    "SLIDING_TOKEN_OBTAIN_SERIALIZER": "rest_framework_simplejwt.serializers.TokenObtainSlidingSerializer",
    "SLIDING_TOKEN_REFRESH_SERIALIZER": "rest_framework_simplejwt.serializers.TokenRefreshSlidingSerializer",
}


# EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
EMAIL_USE_TSL = True
EMAIL_HOST = str(os.environ.get("EMAIL_HOST"))
EMAIL_HOST_USER = str(os.environ.get("EMAIL_HOST_USER"))
EMAIL_HOST_PASSWORD = str(os.environ.get("EMAIL_HOST_PASSWORD"))
EMAIL_PORT = os.environ.get("EMAIL_HOST_PORT")
APPLICATION_EMAIL = str(os.environ.get("APPLICATION_EMAIL"))
DEFAULT_FROM_EMAIL = str(os.environ.get("DEFAULT_FROM_EMAIL"))

PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.PBKDF2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2SHA1PasswordHasher",
]

STRIPE_SECRET = str(os.environ.get("STRIPE_SECRET"))
PUBLISHER_KEY = str(os.environ.get("PUBLISHER_KEY"))


CRON_CLASSES = [
    "core.cron.set_product_visibility",
    "core.cron.deactivate_coupon"
]


PAYPAL_RECEIVER_EMAIL = str(
    os.environ.get("PAYPAL_RECEIVER_EMAIL")
)  

PAYPAL_TEST = True

USPS_USERNAME = str(os.environ.get("USPS_USERNAME"))

TAGGIT_CASE_INSENSITIVE = True

SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False
SECURE_SSL_REDIRECT = False



NOTIFICATIONS_NOTIFICATION_MODEL = "event_notification.Notification"
DJANGO_NOTIFICATIONS_CONFIG = {
    "USE_JSONFIELD": True,
    "SOFT_DELETE": True,
}


USER_AGENTS_CACHE = 'default'
AIRSHIP_KEY = str(os.environ.get("AIRSHIP_KEY"))
MASTER_SECRET = str(os.environ.get("MASTER_SECRET"))

