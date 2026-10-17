import os
from pathlib import Path
import subprocess
import sys


def test_disabled_object_storage_cannot_silently_persist_uploads_locally() -> None:
    environment = os.environ.copy()
    environment['OBJECT_STORAGE_ENABLED'] = 'false'
    result = subprocess.run(
        [sys.executable, '-c', 'import codematics.settings'],
        cwd=Path(__file__).resolve().parents[1],
        env=environment,
        capture_output=True,
        text=True,
        timeout=20,
        check=False,
    )
    assert result.returncode != 0
    assert 'MinIO/S3 object storage is required' in result.stderr
