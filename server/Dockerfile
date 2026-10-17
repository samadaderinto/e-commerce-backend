FROM cgr.dev/chainguard/minio-client@sha256:fc78c525b3227e4d256ed1fc285ee08976688c7ac870f3daed73469d5da750ba AS minio-client

FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    DJANGO_SETTINGS_MODULE=codematics.storefront_settings

WORKDIR /app

RUN groupadd --system app && useradd --system --gid app --home-dir /app --shell /usr/sbin/nologin app

COPY requirements.txt ./
COPY requirements-storage.txt ./
ARG INSTALL_OBJECT_STORAGE=false
COPY --from=minio-client /usr/bin/mc /usr/local/bin/mc
RUN apt-get update && apt-get install -y --no-install-recommends ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && pip install --upgrade pip && pip install -r requirements.txt \
    && if [ "$INSTALL_OBJECT_STORAGE" = "true" ]; then pip install -r requirements-storage.txt; fi

COPY requirements-stream.txt ./
ARG INSTALL_STREAM_POOL=false
RUN if [ "$INSTALL_STREAM_POOL" = "true" ]; then pip install -r requirements-stream.txt; fi

COPY . .
RUN chmod +x docker-entrypoint.sh \
    && mkdir -p /app/media /data /tmp/prometheus \
    && chown -R app:app /app /data /tmp/prometheus

USER app
EXPOSE 8000

ENTRYPOINT ["/bin/sh", "/app/docker-entrypoint.sh"]
CMD ["gunicorn", "-c", "gunicorn.conf.py", "codematics.wsgi:application"]
