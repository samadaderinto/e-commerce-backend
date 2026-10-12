"""Public-only, bounded downloads and private original asset boundaries."""

import socket
from io import BytesIO
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.files.storage import default_storage
from django.http import Http404
from django.test import RequestFactory, override_settings
from PIL import Image

from staff.digital_assets import PublicRedirectHandler, _public_connection, is_safe_external_url, stream_digital_asset
from utils.digital_previews import create_digital_preview
from utils.public_media import serve_public_media


def addresses(ip: str) -> list[tuple]:
    return [(socket.AF_INET, socket.SOCK_STREAM, 6, '', (ip, 443))]


def test_dns_rebinding_is_checked_at_connection_and_private_ips_never_connected() -> None:
    with patch('staff.digital_assets.socket.getaddrinfo', side_effect=[addresses('1.1.1.1'), addresses('127.0.0.1')]), patch('staff.digital_assets.socket.create_connection') as connect:
        assert is_safe_external_url('https://provider.test/file.pdf')[0]
        with pytest.raises(ValueError):
            _public_connection(('provider.test', 443), 15)
        connect.assert_not_called()


def test_public_connection_pins_numeric_address() -> None:
    with patch('staff.digital_assets.socket.getaddrinfo', return_value=addresses('1.1.1.1')), patch('staff.digital_assets.socket.create_connection') as connect:
        _public_connection(('provider.test', 443), 15)
        connect.assert_called_once_with(('1.1.1.1', 443), 15, None)


def test_redirect_cannot_switch_to_ftp_or_private_destination() -> None:
    for url in ('ftp://provider.test/file', 'http://127.0.0.1/private'):
        with pytest.raises(ValueError):
            PublicRedirectHandler().redirect_request(None, None, 302, '', {}, url)


def test_provider_download_failure_is_reported_before_success_headers() -> None:
    with patch('staff.digital_assets.default_storage.exists', return_value=False), patch('staff.digital_assets.is_safe_external_url', return_value=(True, '')), patch('staff.digital_assets.urllib.request.build_opener') as opener:
        opener.return_value.open.side_effect = RuntimeError('SECRET network internals')
        response = stream_digital_asset(SimpleNamespace(pk=1, digital_file_url='https://provider.test/file.pdf'))
    assert response.status_code == 502
    assert 'SECRET' not in str(response.data)


def test_oversized_download_is_rejected_before_returning_a_success() -> None:
    connection = MagicMock()
    connection.__enter__.return_value = connection
    connection.read.side_effect = [b'x' * 20, b'']
    with patch('staff.digital_assets.default_storage.exists', return_value=False), patch('staff.digital_assets.is_safe_external_url', return_value=(True, '')), patch('staff.digital_assets.urllib.request.build_opener') as opener, patch('staff.digital_assets.MAX_DIGITAL_ASSET_SIZE', 10):
        opener.return_value.open.return_value = connection
        response = stream_digital_asset(SimpleNamespace(pk=1, digital_file_url='https://provider.test/file.pdf'))
    assert response.status_code == 502


def test_debug_media_cannot_serve_digital_originals() -> None:
    with pytest.raises(Http404):
        serve_public_media(RequestFactory().get('/media/digital_products/private.pdf'), 'digital_products/private.pdf')


def test_public_preview_is_a_distinct_watermarked_reduced_asset() -> None:
    source = BytesIO()
    Image.new('RGB', (2048, 2048), 'purple').save(source, format='PNG')
    uploaded = SimpleUploadedFile('original.png', source.getvalue(), content_type='image/png')
    with TemporaryDirectory() as directory, override_settings(MEDIA_ROOT=directory):
        path = create_digital_preview(uploaded, 10, 20)
        assert path.startswith('images/digital-previews/10/20/')
        with default_storage.open(path, 'rb') as file, Image.open(file) as preview:
            assert preview.size == (1024, 1024)
            assert len(set(preview.getdata())) > 1
        assert uploaded.tell() == 0
