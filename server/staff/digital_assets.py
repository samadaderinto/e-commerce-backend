from __future__ import annotations

import ipaddress
import http.client
import logging
import os
import socket
import tempfile
import urllib.request
from typing import Any
from urllib.parse import urlparse

from django.core.files.storage import default_storage
from django.http import FileResponse
from rest_framework.response import Response

MAX_DIGITAL_ASSET_SIZE = 50 * 1024 * 1024  # 50 MB
logger = logging.getLogger(__name__)


def _public_connection(address: tuple[str, int], timeout: Any = None, source_address: Any = None) -> socket.socket:
    """Validate and pin the resolved IP used by HTTP and TLS connections."""
    host, port = address
    addresses = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    if not addresses or any(not ipaddress.ip_address(row[4][0]).is_global for row in addresses):
        raise ValueError('Private digital asset destination is prohibited.')
    # The HTTP host and TLS server name remain the original hostname. Only the
    # TCP destination is pinned, preventing a second DNS lookup from rebinding.
    return socket.create_connection((addresses[0][4][0], port), timeout, source_address)


def _http_connection(host: str, **kwargs: Any) -> http.client.HTTPConnection:
    connection = http.client.HTTPConnection(host, **kwargs)
    connection._create_connection = _public_connection
    return connection


def _https_connection(host: str, **kwargs: Any) -> http.client.HTTPSConnection:
    connection = http.client.HTTPSConnection(host, **kwargs)
    connection._create_connection = _public_connection
    return connection


class PublicHTTPHandler(urllib.request.HTTPHandler):
    def http_open(self, request: urllib.request.Request) -> Any:
        return self.do_open(_http_connection, request)


class PublicHTTPSHandler(urllib.request.HTTPSHandler):
    def https_open(self, request: urllib.request.Request) -> Any:
        return self.do_open(_https_connection, request)


class PublicRedirectHandler(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request: Any, file: Any, code: int, message: str, headers: Any, new_url: str) -> Any:
        safe, _ = is_safe_external_url(new_url)
        if not safe:
            raise ValueError('Unsafe digital asset redirect.')
        return super().redirect_request(request, file, code, message, headers, new_url)


def is_safe_external_url(url: str) -> tuple[bool, str]:
    try:
        parsed = urlparse(url)
        port = parsed.port
    except ValueError:
        return False, 'Invalid digital asset URL.'
    if parsed.scheme not in ("http", "https"):
        return False, "Digital asset URL must use http or https protocol."
    hostname = parsed.hostname
    if not hostname:
        return False, "Digital asset URL is missing hostname."
    if parsed.username or parsed.password:
        return False, 'Digital asset URLs cannot include credentials.'

    blocked_hosts = {"localhost", "127.0.0.1", "0.0.0.0", "metadata.google.internal", "instance-data"}
    if hostname.lower() in blocked_hosts or hostname.endswith(".local"):
        return False, "Access to private or local destination is prohibited."

    # DNS check to block private IP ranges (SSRF prevention)
    try:
        addr_info = socket.getaddrinfo(hostname, None)
        for _, _, _, _, sockaddr in addr_info:
            ip_str = sockaddr[0]
            ip = ipaddress.ip_address(ip_str)
            if not ip.is_global:
                return False, 'Destination resolves to a prohibited network.'
    except (socket.gaierror, ValueError):
        return False, 'Could not resolve the digital asset destination.'

    return True, ""


def stream_digital_asset(product: Any) -> FileResponse | Response:
    file_url = (product.digital_file_url or "").strip()
    if not file_url:
        return Response({"detail": "This digital product has no uploaded asset."}, status=404)

    from django.conf import settings
    try:
        parsed = urlparse(file_url)
    except ValueError:
        return Response({'detail': 'Invalid digital asset URL.'}, status=400)
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
        response["Cache-Control"] = "private, no-store"
        return response

    # 2. External URL validation
    is_safe, error_msg = is_safe_external_url(file_url)
    if not is_safe:
        return Response({"detail": error_msg}, status=400)

    raw_name = os.path.basename(parsed.path) or f"digital-asset-{product.pk}.bin"

    # Complete the bounded fetch before sending headers so provider failures
    # become a clean API error rather than a truncated successful download.
    asset = tempfile.SpooledTemporaryFile(max_size=5 * 1024 * 1024)
    try:
        req = urllib.request.Request(
            file_url,
            headers={"User-Agent": "ProAce-Backoffice-Audit/1.0"},
        )
        opener = urllib.request.build_opener(
            urllib.request.ProxyHandler({}), PublicHTTPHandler(), PublicHTTPSHandler(), PublicRedirectHandler(),
        )
        total_bytes = 0
        with opener.open(req, timeout=15) as conn:
            while True:
                chunk = conn.read(64 * 1024)
                if not chunk:
                    break
                total_bytes += len(chunk)
                if total_bytes > MAX_DIGITAL_ASSET_SIZE:
                    raise ValueError("Digital asset exceeded maximum allowed size (50 MB).")
                asset.write(chunk)
        asset.seek(0)
        response = FileResponse(asset, as_attachment=True, filename=raw_name, content_type='application/octet-stream')
        response["Cache-Control"] = "private, no-store"
        return response
    except Exception as exc:
        asset.close()
        logger.warning('Digital asset retrieval failed for product %s (%s)', product.pk, type(exc).__name__)
        return Response({'detail': 'Unable to retrieve the digital asset. Please try again.'}, status=502)
