"""Offline guards for the local worker command and its rollback override."""

from pathlib import Path

import yaml


def test_local_worker_concurrency_is_explicit_and_overridable() -> None:
    root = Path(__file__).resolve().parents[1]
    services = yaml.safe_load((root / "compose.yaml").read_text())["services"]
    command = services["notification-worker"]["command"]

    assert command == [
        "celery", "-A", "codematics", "worker", "--loglevel=INFO",
        "--concurrency", "${CELERY_WORKER_CONCURRENCY:-2}",
    ]
    assert "--concurrency" not in services["celery-beat"]["command"]
    assert services["notification-worker"]["environment"]["RUN_MIGRATIONS"] == "false"
    assert "CELERY_WORKER_CONCURRENCY=2" in (root / ".env.example").read_text()
