"""The security runner must never pass unavailable or incorrect endpoints."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from unittest.mock import AsyncMock, patch

import httpx
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from scripts.qa import security_test

SecurityAuditor = security_test.SecurityAuditor
main = security_test.main


def scan(mode: str) -> list[dict[str, object]]:
    def respond(request: httpx.Request) -> httpx.Response:
        if mode == "offline":
            raise httpx.ConnectError("Unavailable", request=request)
        if mode in {"404", "200"}:
            return httpx.Response(int(mode), text="Unexpected response")
        expected = (
            401
            if "/admin/staff/" in request.url.path
            else 404 if request.url.path.endswith("/999999999/") else 400
        )
        return httpx.Response(
            expected,
            text=(
                'ErrorDetail(string="unsafe", code="invalid")'
                if mode == "leak"
                else "Clean denial"
            ),
        )

    async def run() -> list[dict[str, object]]:
        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
            return await SecurityAuditor("http://testserver").scan_sensitive_leaks(
                client
            )

    return asyncio.run(run())


@pytest.mark.parametrize("mode", ["offline", "404", "200", "leak", "healthy"])
def test_report_requires_expected_live_statuses_and_no_leaks(mode: str) -> None:
    auditor = SecurityAuditor("http://testserver")
    rows = scan(mode)
    regressions = {"exit_code": 0, "duration_s": 0, "stdout": "Passed", "passed": True}
    with patch.object(
        security_test, "save_report", return_value=("not-written", "not-written")
    ):
        report = auditor.compile_report(rows, regressions)
    assert report["verdict"] == ("PASS" if mode == "healthy" else "FAIL")
    assert report["leaks_found"] == (5 if mode == "leak" else 0)
    if mode == "offline":
        assert all(not row["reachable"] and not row["clean"] for row in rows)
    if mode == "healthy":
        protected = [
            row["endpoint"] for row in rows if "/admin/" in str(row["endpoint"])
        ]
        assert protected == [
            "/api/v1/admin/staff/orders/",
            "/api/v1/admin/staff/payouts/",
        ]


@pytest.mark.parametrize("verdict", ["FAIL", "PASS"])
def test_cli_exits_nonzero_for_failed_report(verdict: str) -> None:
    with patch("sys.argv", ["security_test.py"]), patch.object(
        SecurityAuditor, "run", new=AsyncMock(return_value={"verdict": verdict})
    ):
        if verdict == "FAIL":
            with pytest.raises(SystemExit) as error:
                main()
            assert error.value.code == 1
        else:
            main()
