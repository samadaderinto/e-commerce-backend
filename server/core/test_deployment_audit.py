"""Deployment guards that never invoke Docker or delete real backups."""

from __future__ import annotations

import gzip
from pathlib import Path
import shutil
import subprocess

import pytest
import yaml


ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize(
    "failure", ["none", "dump", "empty", "compress", "validate", "rename"]
)
def test_backup_publishes_and_prunes_only_after_validation(
    tmp_path: Path, failure: str,
) -> None:
    commands = tmp_path / "bin"
    commands.mkdir()
    backups = tmp_path / "backups"
    backups.mkdir()
    old_backup = backups / "postgres-old.sql.gz"
    old_backup.write_bytes(b"existing backup")
    events = tmp_path / "events"
    real_gzip = shutil.which("gzip")
    real_mv = shutil.which("mv")
    assert real_gzip is not None and real_mv is not None
    scripts = {
        "docker": """#!/bin/bash
if [ "$FAILURE" = dump ]; then
    printf 'partial dump'
    exit 7
fi
if [ "$FAILURE" != empty ]; then printf 'SELECT 1;\\n'; fi
""",
        "gzip": """#!/bin/bash
if [ "$1" = -9 ] && [ "$FAILURE" = compress ]; then exit 8; fi
if [ "$1" = -t ]; then
    echo validate >> "$EVENTS"
    if [ "$FAILURE" = validate ]; then exit 9; fi
fi
exec "$REAL_GZIP" "$@"
""",
        "mv": """#!/bin/bash
echo rename >> "$EVENTS"
if [ "$FAILURE" = rename ]; then exit 10; fi
exec "$REAL_MV" "$@"
""",
        "find": """#!/bin/bash
echo retention >> "$EVENTS"
""",
        "date": "#!/bin/bash\nprintf '20261020T120000Z\\n'\n",
    }
    for name, source in scripts.items():
        executable = commands / name
        executable.write_text(source)
        executable.chmod(0o700)
    result = subprocess.run(
        ["/bin/bash", str(ROOT / "deploy/hostgator/backup.sh")],
        env={
            "PATH": f"{commands}:/usr/bin:/bin",
            "HOSTGATOR_BACKUP_DIR": str(backups),
            "HOSTGATOR_ENV_FILE": str(tmp_path / "unused.env"),
            "FAILURE": failure,
            "EVENTS": str(events),
            "REAL_GZIP": real_gzip,
            "REAL_MV": real_mv,
        },
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )
    recorded = events.read_text().splitlines() if events.exists() else []
    published = backups / "postgres-20261020T120000Z.sql.gz"
    assert old_backup.read_bytes() == b"existing backup"
    assert not list(backups.glob(".postgres-*"))
    if failure == "none":
        assert result.returncode == 0, result.stderr
        assert gzip.decompress(published.read_bytes()) == b"SELECT 1;\n"
        assert published.stat().st_mode & 0o777 == 0o600
        assert recorded == ["validate", "rename", "retention"]
        assert "Database backup written" in result.stdout
    else:
        assert result.returncode != 0
        assert not published.exists()
        assert "retention" not in recorded
        assert "Database backup written" not in result.stdout


def test_ci_storefront_uses_isolated_settings() -> None:
    workflow = yaml.safe_load((ROOT / ".github/workflows/ci-cd.yml").read_text())
    steps = workflow["jobs"]["test"]["steps"]
    command = next(
        step["run"] for step in steps
        if step.get("name") == "Storefront API integration tests"
    )
    assert command == (
        "pipenv run python manage.py test storefront "
        "--settings=codematics.test_settings --noinput"
    )
