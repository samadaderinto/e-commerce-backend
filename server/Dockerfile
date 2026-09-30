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
RUN pip install --upgrade pip && pip install -r requirements.txt \
    && if [ "$INSTALL_OBJECT_STORAGE" = "true" ]; then pip install -r requirements-storage.txt; fi

COPY . .
RUN chmod +x docker-entrypoint.sh \
    && mkdir -p /data /tmp/prometheus \
    && chown -R app:app /app /data /tmp/prometheus

USER app
EXPOSE 8000

ENTRYPOINT ["/app/docker-entrypoint.sh"]
CMD ["gunicorn", "-c", "gunicorn.conf.py", "codematics.wsgi:application"]
