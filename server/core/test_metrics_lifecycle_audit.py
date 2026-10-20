"""Offline entrypoint lifecycle tests without Django or container startup."""

from __future__ import annotations

from pathlib import Path
import subprocess
import sys

import pytest
import yaml


ROOT = Path(__file__).resolve().parents[2]
ENTRYPOINT = ROOT / "server/docker-entrypoint.sh"


def run_entrypoint(
    command: list[str], environment: dict[str, str],
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["/bin/sh", str(ENTRYPOINT), *command],
        env={
            "PATH": "/usr/bin:/bin",
            "RUN_MIGRATIONS": "false",
            "RUN_COLLECTSTATIC": "false",
            **environment,
        },
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )


def test_configured_metrics_get_fresh_directories_without_touching_prior_files(
    tmp_path: Path,
) -> None:
    prior = tmp_path / "prior-metrics"
    prior.mkdir()
    fixture = prior / "counter_123.db"
    fixture.write_bytes(b"preserve existing metrics")
    directories: list[Path] = []
    try:
        for _ in range(2):
            result = run_entrypoint(
                ["/bin/sh", "-c", 'printf "%s" "$PROMETHEUS_MULTIPROC_DIR"'],
                {"PROMETHEUS_MULTIPROC_DIR": str(prior)},
            )
            assert result.returncode == 0, result.stderr
            directory = Path(result.stdout)
            assert directory.parent == Path("/tmp")
            assert directory.name.startswith("proace-metrics.")
            directories.append(directory)
            assert directory.is_dir()
            assert not list(directory.iterdir())
            assert directory.stat().st_mode & 0o777 == 0o700
        assert directories[0] != directories[1]
        assert fixture.read_bytes() == b"preserve existing metrics"
        assert list(prior.iterdir()) == [fixture]
    finally:
        # Only remove the exact empty directories allocated by these invocations.
        for directory in directories:
            directory.rmdir()


@pytest.mark.parametrize("configured", [False, True])
def test_disabled_metrics_remove_environment_keys(configured: bool) -> None:
    environment = {"PROMETHEUS_MULTIPROC_DIR": ""} if configured else {}
    result = run_entrypoint(
        ["/bin/sh", "-c", 'printf "%s" "${PROMETHEUS_MULTIPROC_DIR-unset}"'],
        environment,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout == "unset"


def test_disabled_metrics_use_in_memory_values() -> None:
    result = run_entrypoint(
        [sys.executable, "-c", (
            "from prometheus_client.values import ValueClass; "
            "assert not ValueClass._multiprocess"
        )],
        {"PROMETHEUS_MULTIPROC_DIR": "", "prometheus_multiproc_dir": ""},
    )
    assert result.returncode == 0, result.stderr


def test_metrics_allocation_failure_prevents_command_start(tmp_path: Path) -> None:
    executable = tmp_path / "mktemp"
    executable.write_text("#!/bin/sh\nexit 17\n")
    executable.chmod(0o700)
    result = run_entrypoint(
        ["/bin/sh", "-c", "printf command-started"],
        {"PATH": str(tmp_path), "PROMETHEUS_MULTIPROC_DIR": "/unused"},
    )
    assert result.returncode == 17
    assert result.stdout == ""


def test_compose_enables_storage_and_isolates_metrics_consumers() -> None:
    compose = yaml.safe_load((ROOT / "server/compose.yaml").read_text())
    services = compose["services"]
    assert services["api"]["environment"]["OBJECT_STORAGE_ENABLED"] == (
        "${OBJECT_STORAGE_ENABLED:-true}"
    )
    for name in ("api", "notification-stream", "notification-worker", "celery-beat"):
        mounts = services[name]["volumes"]
        assert not any(mount.startswith("prometheus-multiproc:") for mount in mounts)
    for name in ("api", "notification-stream"):
        assert services[name]["environment"]["PROMETHEUS_MULTIPROC_DIR"]
    for name in ("notification-worker", "celery-beat"):
        assert services[name]["environment"]["PROMETHEUS_MULTIPROC_DIR"] == ""
    assert "prometheus-multiproc" in compose["volumes"]
