#!/usr/bin/env python3
"""Sync selected GitHub Actions environment values into a Render service."""
import json
import os
from urllib.error import HTTPError
from urllib.parse import quote
from urllib.request import Request, urlopen


RENDER_ENV_KEYS = [
    "API_URL",
    "DJANGO_SETTINGS_MODULE",
    "DJANGO_DEBUG",
    "SECRET_KEY",
    "ALLOWED_HOSTS",
    "FRONTEND_URL",
    "DATABASE_ENGINE",
    "POSTGRES_HOST",
    "POSTGRES_PORT",
    "POSTGRES_DB",
    "POSTGRES_USER",
    "POSTGRES_PASSWORD",
    "DB_REQUIRE_SSL",
    "CACHE_URL",
    "OBSERVABILITY_TOKEN",
    "OBJECT_STORAGE_ENABLED",
    "MINIO_ENDPOINT_URL",
    "MINIO_PUBLIC_URL",
    "MINIO_BUCKET_NAME",
    "MINIO_REGION",
    "MINIO_ACCESS_KEY",
    "MINIO_SECRET_KEY",
    "OTEL_TRACING_ENABLED",
    "OTEL_EXPORTER_OTLP_ENDPOINT",
    "OTEL_SERVICE_NAME",
    "OTEL_TRACES_SAMPLER_ARG",
    "ELASTICSEARCH_ENABLED",
    "ELASTICSEARCH_URL",
    "ELASTICSEARCH_PRODUCTS_INDEX",
    "KAFKA_BOOTSTRAP_SERVERS",
    "KAFKA_LOGGING_ENABLED",
    "KAFKA_LOG_TOPIC",
    "CELERY_BROKER_URL",
    "NOTIFICATION_DELIVERY_MAX_ATTEMPTS",
    "NOTIFICATION_DELIVERY_STALE_SECONDS",
    "EMAIL_BACKEND",
    "EMAIL_HOST",
    "EMAIL_HOST_USER",
    "EMAIL_HOST_PASSWORD",
    "EMAIL_PORT",
    "EMAIL_USE_TLS",
    "DEFAULT_FROM_EMAIL",
    "APPLICATION_EMAIL",
    "FCM_ENABLED",
    "FIREBASE_PROJECT_ID",
    "FIREBASE_CREDENTIALS_JSON",
]


def render_request(method, path, payload=None):
    token = os.environ["RENDER_API_KEY"]
    body = None if payload is None else json.dumps(payload).encode("utf-8")
    request = Request(
        f"https://api.render.com/v1{path}",
        data=body,
        method=method,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
    )
    try:
        with urlopen(request, timeout=30) as response:
            return response.read()
    except HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace")
        raise SystemExit(f"Render API {method} {path} failed: {error.code} {detail}") from error


def main():
    services = {
        "API": os.environ["RENDER_SERVICE_ID"],
        "notification worker": os.environ["RENDER_WORKER_SERVICE_ID"],
    }
    total_synced = 0
    for service_name, service_id in services.items():
        synced = 0
        for key in RENDER_ENV_KEYS:
            value = os.environ.get(key)
            if value is None or value == "":
                continue
            render_request(
                "PUT",
                f"/services/{quote(service_id)}/env-vars/{quote(key)}",
                {"value": value},
            )
            synced += 1
        total_synced += synced
        print(f"Synced {synced} Render environment variables to {service_name}.")
    print(f"Synced {total_synced} Render environment variables.")


if __name__ == "__main__":
    main()
