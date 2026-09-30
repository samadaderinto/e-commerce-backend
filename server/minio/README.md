# Optional S3-compatible image storage

The default `server/compose.yaml` uses the persistent `media-data` volume for
local uploads, so the application does not depend on a MinIO image registry.
Use `OBJECT_STORAGE_ENABLED=true` only when connecting Django to an S3-compatible
provider that you operate or trust. The MinIO configuration below is retained as
legacy deployment guidance and is not started by the default Compose file.

Uploads still pass through the existing authenticated API for validation; Django

For an external S3-compatible provider, set `OBJECT_STORAGE_ENABLED=true`,
`MINIO_ENDPOINT_URL`, `MINIO_PUBLIC_URL`, `MINIO_BUCKET_NAME`,
`MINIO_ACCESS_KEY`, and `MINIO_SECRET_KEY` in the deployment secret manager.
`MINIO_PUBLIC_URL` must be reachable by browsers, without a bucket suffix. Use an
HTTPS endpoint for an HTTPS frontend. Create the bucket and its read/write policy
through the provider's supported tooling before starting the API.

Existing files are not automatically migrated. To keep their database paths,
copy the contents of `server/media/` into the bucket root (preserving `images/`).
Tests use in-memory storage and do not require Docker.

Storage configuration follows the
[django-storages S3 backend](https://django-storages.readthedocs.io/en/latest/backends/amazon-S3.html).
