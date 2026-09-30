# MinIO image storage

From the repository root:

```sh
.venv/bin/python -m pip install -r server/requirements.txt
docker compose --env-file server/.env -f server/compose.yaml up -d
.venv/bin/python server/manage.py runserver --settings=codematics.storefront_settings
```

`server/.env` holds local settings and is ignored by Git. `server/.env.example`
documents every MinIO setting. Replace the example passwords for deployment.
The console is at http://127.0.0.1:9001; use the root credentials from `.env`.
The initialization service creates the bucket and a separate application user
whose read/write/delete permissions are limited to that bucket. Anonymous access
allows image reads only. Do not put private documents in this image bucket.

Uploads still pass through the existing authenticated API for validation; Django
stores the contents in MinIO instead of `server/media`. Image URLs point directly
to MinIO. Replacements, explicit deletes, and parent cascades remove old objects
after the database transaction commits. Failed database transactions preserve old
images. As with any separate object store, failed database saves after an upload
can leave an unreferenced object; storage cleanup failures are logged by django-cleanup.

Use `MINIO_ENDPOINT_URL=http://minio:9000` for Django inside the Compose network.
`MINIO_PUBLIC_URL` must be reachable by browsers, without a bucket suffix. Use an
HTTPS public endpoint for an HTTPS frontend. Docker stores objects in the named
`minio-data` volume; `docker compose down` retains it, `down -v` removes it.

Existing files are not automatically migrated. To keep their database paths,
copy the contents of `server/media/` into the bucket root (preserving `images/`).
Tests use in-memory storage and do not require Docker.

Storage configuration follows the
[django-storages S3 backend](https://django-storages.readthedocs.io/en/latest/backends/amazon-S3.html).
