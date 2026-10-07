#!/usr/bin/env python3
"""
Generate deploy/hostgator/.env from environment variables.
Used by GitHub Actions and local operators to compose production settings
with safe defaults without exposing secret values in build logs.
"""
import os
import sys


def main() -> None:
    output_path = os.path.join(os.path.dirname(__file__), ".env")

    public_domain = os.environ.get("PUBLIC_DOMAIN", "proaceintlshoppingmall.com").strip()
    secret_key = (
        os.environ.get("PROD_SECRET_KEY", "").strip()
        or os.environ.get("SECRET_KEY", "").strip()
    )
    postgres_password = (
        os.environ.get("PROD_POSTGRES_PASSWORD", "").strip()
        or os.environ.get("POSTGRES_PASSWORD", "").strip()
    )
    admin_password = (
        os.environ.get("PROD_ADMIN_PASSWORD", "").strip()
        or os.environ.get("DEFAULT_ADMIN_PASSWORD", "").strip()
    )
    tech_admin_password = (
        os.environ.get("PROD_TECHNICAL_ADMIN_PASSWORD", "").strip()
        or os.environ.get("TECHNICAL_ADMIN_PASSWORD", "").strip()
        or admin_password
    )
    observability_token = (
        os.environ.get("PROD_OBSERVABILITY_TOKEN", "").strip()
        or os.environ.get("OBSERVABILITY_TOKEN", "").strip()
    )

    admin_email = os.environ.get("PROD_ADMIN_EMAIL", "admin@proaceintl.com").strip()
    tech_admin_email = (
        os.environ.get("PROD_TECHNICAL_ADMIN_EMAIL", "").strip() or admin_email
    )

    env_map = {
        "PUBLIC_DOMAIN": public_domain,
        "COMMERCE_NETWORK": os.environ.get("COMMERCE_NETWORK", "commerce-network").strip(),
        "DJANGO_DEBUG": "false",
        "SECRET_KEY": secret_key,
        "ALLOWED_HOSTS": os.environ.get(
            "ALLOWED_HOSTS", f"{public_domain},www.{public_domain},api,client"
        ).strip(),
        "FRONTEND_URL": os.environ.get("FRONTEND_URL", f"https://{public_domain}").strip(),
        "CSRF_TRUSTED_ORIGINS": os.environ.get(
            "CSRF_TRUSTED_ORIGINS", f"https://{public_domain},https://www.{public_domain}"
        ).strip(),
        "SECURE_SSL_REDIRECT": "true",
        "SECURE_HSTS_SECONDS": "31536000",
        "API_URL": os.environ.get("API_URL", "http://api:8000/api/v1").strip(),
        "DEFAULT_ADMIN_EMAIL": admin_email,
        "DEFAULT_ADMIN_PASSWORD": admin_password,
        "TECHNICAL_ADMIN_EMAIL": tech_admin_email,
        "TECHNICAL_ADMIN_PASSWORD": tech_admin_password,
        "DEFAULT_ADMIN_FIRST_NAME": os.environ.get("PROD_ADMIN_FIRST_NAME", "ProAce").strip(),
        "DEFAULT_ADMIN_LAST_NAME": os.environ.get(
            "PROD_ADMIN_LAST_NAME", "Administrator"
        ).strip(),
        "DEFAULT_ADMIN_GENDER": os.environ.get("PROD_ADMIN_GENDER", "male").strip(),
        "DEFAULT_ADMIN_PHONE": os.environ.get("PROD_ADMIN_PHONE", "+13013251550").strip(),
        "POSTGRES_DB": os.environ.get("POSTGRES_DB", "commerce").strip(),
        "POSTGRES_USER": os.environ.get("POSTGRES_USER", "commerce").strip(),
        "POSTGRES_PASSWORD": postgres_password,
        "POSTGRES_EXPORTER_USER": os.environ.get("POSTGRES_USER", "commerce").strip(),
        "POSTGRES_EXPORTER_PASSWORD": postgres_password,
        "OBSERVABILITY_TOKEN": observability_token,
        "STRIPE_SECRET": os.environ.get("STRIPE_SECRET", "").strip(),
        "PUBLISHER_KEY": os.environ.get("PUBLISHER_KEY", "").strip(),
        "STRIPE_WALLET_PAYMENT_METHODS": os.environ.get(
            "STRIPE_WALLET_PAYMENT_METHODS", "cashapp"
        ).strip(),
        "STRIPE_CURRENCY": os.environ.get("STRIPE_CURRENCY", "usd").strip(),
        "OBJECT_STORAGE_ENABLED": os.environ.get("OBJECT_STORAGE_ENABLED", "false").strip(),
        "INSTALL_OBJECT_STORAGE": os.environ.get("INSTALL_OBJECT_STORAGE", "false").strip(),
        "ELASTICSEARCH_ENABLED": "true",
        "ELASTICSEARCH_JAVA_OPTS": os.environ.get(
            "ELASTICSEARCH_JAVA_OPTS", "-Xms512m -Xmx512m"
        ).strip(),
        "OTEL_TRACING_ENABLED": "true",
        "OTEL_EXPORTER_OTLP_ENDPOINT": "http://tempo:4318",
        "OTEL_SERVICE_NAME": "commerce-api",
        "OTEL_TRACES_SAMPLER_ARG": "0.05",
        "RESEND_API_KEY": os.environ.get("RESEND_API_KEY", "").strip(),
        "RESEND_FROM_EMAIL": os.environ.get(
            "RESEND_FROM_EMAIL", f"ProAce <{admin_email}>"
        ).strip(),
        "FCM_ENABLED": os.environ.get("FCM_ENABLED", "false").strip(),
        "FIREBASE_PROJECT_ID": os.environ.get("FIREBASE_PROJECT_ID", "").strip(),
        "FIREBASE_CREDENTIALS_JSON": os.environ.get("FIREBASE_CREDENTIALS_JSON", "").strip(),
        "SHIPPING_RATE_MODE": os.environ.get("SHIPPING_RATE_MODE", "live").strip(),
        "SHIPPING_SANDBOX": os.environ.get("SHIPPING_SANDBOX", "false").strip(),
        "USPS_CLIENT_ID": os.environ.get("USPS_CLIENT_ID", "").strip(),
        "USPS_CLIENT_SECRET": os.environ.get("USPS_CLIENT_SECRET", "").strip(),
        "FEDEX_API_KEY": os.environ.get("FEDEX_API_KEY", "").strip(),
        "FEDEX_SECRET_KEY": os.environ.get("FEDEX_SECRET_KEY", "").strip(),
        "FEDEX_ACCOUNT_NUMBER": os.environ.get("FEDEX_ACCOUNT_NUMBER", "").strip(),
        "DHL_API_KEY": os.environ.get("DHL_API_KEY", "").strip(),
        "DHL_API_SECRET": os.environ.get("DHL_API_SECRET", "").strip(),
        "UPS_CLIENT_ID": os.environ.get("UPS_CLIENT_ID", "").strip(),
        "UPS_CLIENT_SECRET": os.environ.get("UPS_CLIENT_SECRET", "").strip(),
        "UPS_ACCOUNT_NUMBER": os.environ.get("UPS_ACCOUNT_NUMBER", "").strip(),
        "CHECKOUT_TAX_RATE": "0",
        "REALTIME_REDIS_URL": os.environ.get("REALTIME_REDIS_URL", "").strip(),
        "GUNICORN_THREADS": os.environ.get("GUNICORN_THREADS", "32").strip(),
    }

    with open(output_path, "w", encoding="utf-8") as f:
        for k, v in env_map.items():
            f.write(f"{k}={v}\n")

    os.chmod(output_path, 0o600)
    print(f"Generated {output_path} successfully (mode 0600).")


if __name__ == "__main__":
    main()
