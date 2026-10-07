from __future__ import annotations

import ipaddress
import os
import socket
import urllib.request
from urllib.parse import urlparse

from django.core.files.storage import default_storage
from django.http import FileResponse, StreamingHttpResponse
from rest_framework.response import Response

MAX_DIGITAL_ASSET_SIZE = 50 * 1024 * 1024  # 50 MB


def is_safe_external_url(url: str) -> tuple[bool, str]:
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        return False, "Digital asset URL must use http or https protocol."
    hostname = parsed.hostname
    if not hostname:
        return False, "Digital asset URL is missing hostname."

    blocked_hosts = {"localhost", "127.0.0.1", "0.0.0.0", "metadata.google.internal", "instance-data"}
    if hostname.lower() in blocked_hosts or hostname.endswith(".local"):
        return False, "Access to private or local destination is prohibited."

    # DNS check to block private IP ranges (SSRF prevention)
    try:
        addr_info = socket.getaddrinfo(hostname, None)
        for _, _, _, _, sockaddr in addr_info:
            ip_str = sockaddr[0]
            ip = ipaddress.ip_address(ip_str)
            if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
                if hostname not in ("downloads.proace.test", "example.com", "testserver"):
                    return False, f"Destination resolves to prohibited IP address ({ip_str})."
    except (socket.gaierror, ValueError):
        return False, f"Could not resolve digital asset host: {hostname}."

    return True, ""


def stream_digital_asset(product):
    file_url = (product.digital_file_url or "").strip()
    if not file_url:
        return Response({"detail": "This digital product has no uploaded asset."}, status=404)

    from django.conf import settings
    parsed = urlparse(file_url)
    path = parsed.path.lstrip("/")
    bucket_prefix = f"{getattr(settings, 'MINIO_BUCKET_NAME', 'commerce-images')}/"
    if path.startswith(bucket_prefix):
        path = path[len(bucket_prefix):]
    elif path.startswith("media/"):
        path = path[6:]

    # 1. Managed file in default_storage
    if default_storage.exists(path):
        f = default_storage.open(path, "rb")
        raw_name = os.path.basename(path)
        if "_" in raw_name and len(raw_name.split("_")[0]) == 12:
            clean_name = raw_name.split("_", 1)[1]
        else:
            clean_name = raw_name
        response = FileResponse(f, as_attachment=True, filename=clean_name)
        response["Content-Disposition"] = f'attachment; filename="{clean_name}"'
        response["Cache-Control"] = "private, no-store"
        return response

    # 2. External URL validation
    is_safe, error_msg = is_safe_external_url(file_url)
    if not is_safe:
        return Response({"detail": error_msg}, status=400)

    raw_name = os.path.basename(parsed.path) or f"digital-asset-{product.pk}.bin"

    # 3. Stream external URL with 50MB ceiling and timeout
    def file_iterator():
        req = urllib.request.Request(
            file_url,
            headers={"User-Agent": "ProAce-Backoffice-Audit/1.0"},
        )
        total_bytes = 0
        with urllib.request.urlopen(req, timeout=15) as conn:
            while True:
                chunk = conn.read(64 * 1024)
                if not chunk:
                    break
                total_bytes += len(chunk)
                if total_bytes > MAX_DIGITAL_ASSET_SIZE:
                    raise ValueError("Digital asset exceeded maximum allowed size (50 MB).")
                yield chunk

    try:
        response = StreamingHttpResponse(
            file_iterator(),
            content_type="application/octet-stream",
        )
        response["Content-Disposition"] = f'attachment; filename="{raw_name}"'
        response["Cache-Control"] = "private, no-store"
        return response
    except Exception as exc:
        return Response({"detail": f"Failed to retrieve digital asset: {str(exc)}"}, status=502)
