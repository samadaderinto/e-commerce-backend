#!/usr/bin/env python3
"""
Security & Data Leak Testing Runner for ProAce Commerce.
Scans for sensitive information leaks, role boundary enforcement, and runs security regressions.
Outputs reports to: qa-reports/security/
"""

from __future__ import annotations

import argparse
import asyncio
import datetime
import os
import re
import subprocess
import sys
import time
from typing import Any, Dict, List

import httpx

if __package__:
    from .utils import print_banner, print_table, save_report
else:
    from utils import print_banner, print_table, save_report


class SecurityAuditor:
    def __init__(self, base_url: str) -> None:
        self.base_url = base_url.rstrip("/")
        self.findings: List[Dict[str, Any]] = []

    async def scan_sensitive_leaks(
        self, client: httpx.AsyncClient
    ) -> List[Dict[str, Any]]:
        """Verify error responses do not leak stack traces, database schema, or internal paths."""
        print("[*] Auditing API error handling for sensitive data exposure...")
        test_probes = [
            (
                "Malformed JSON payload",
                "POST",
                "/api/v1/auth/login/",
                "{bad-json",
                {400},
            ),
            (
                "Invalid query parameters",
                "GET",
                "/api/v1/products/?min_price=invalid_nan",
                None,
                {400},
            ),
            ("Nonexistent resource", "GET", "/api/v1/products/999999999/", None, {404}),
            (
                "Unauthenticated backoffice access",
                "GET",
                "/api/v1/admin/staff/orders/",
                None,
                {401, 403},
            ),
            (
                "Unauthenticated staff review",
                "GET",
                "/api/v1/admin/staff/payouts/",
                None,
                {401, 403},
            ),
        ]

        leak_patterns = [
            (r"Traceback \(most recent call last\):", "Python Stack Trace"),
            (r"ErrorDetail\(", "DRF ErrorDetail Python Representation"),
            (r"SELECT .* FROM", "Raw SQL Query"),
            (r"\/Users\/[a-zA-Z0-9_\-\/]+", "Local Server Filesystem Path"),
            (r"\/app\/[a-zA-Z0-9_\-\/]+", "Container Filesystem Path"),
            (r"psycopg\d*\.", "Database Adapter Exception"),
            (r"django\.db\.", "Django ORM Internal Module Leak"),
        ]

        results = []
        for name, method, path, payload, expected_statuses in test_probes:
            url = f"{self.base_url}{path}"
            headers = {"Content-Type": "application/json"}
            try:
                if method == "POST":
                    res = await client.post(url, content=payload, headers=headers)
                else:
                    res = await client.get(url, headers=headers)

                body = res.text
                detected_leaks = []
                for pattern, desc in leak_patterns:
                    if re.search(pattern, body, re.IGNORECASE):
                        detected_leaks.append(desc)

                status_ok = res.status_code in expected_statuses
                clean = not detected_leaks and status_ok
                results.append(
                    {
                        "probe": name,
                        "endpoint": path,
                        "status_code": res.status_code,
                        "clean": clean,
                        "reachable": True,
                        "status_ok": status_ok,
                        "expected_statuses": sorted(expected_statuses),
                        "leaks": detected_leaks,
                    }
                )
            except httpx.RequestError as error:
                results.append(
                    {
                        "probe": name,
                        "endpoint": path,
                        "status_code": 0,
                        "clean": False,
                        "reachable": False,
                        "status_ok": False,
                        "expected_statuses": sorted(expected_statuses),
                        "leaks": [],
                        "note": f"Request failed: {type(error).__name__}",
                    }
                )
        return results

    def run_regression_audit_tests(self) -> Dict[str, Any]:
        """Run existing security regression tests via pytest."""
        print("[*] Running backend security regression suites...")
        cmd = [
            sys.executable,
            "-m",
            "pytest",
            "server/notification/test_audit_regressions.py",
            "server/payment/test_audit_regressions.py",
            "server/core/test_activity.py",
            "-q",
        ]
        t0 = time.perf_counter()
        proc = subprocess.run(cmd, capture_output=True, text=True)
        duration = round(time.perf_counter() - t0, 2)

        return {
            "exit_code": proc.returncode,
            "duration_s": duration,
            "stdout": proc.stdout.strip(),
            "passed": proc.returncode == 0,
        }

    async def run(self) -> Dict[str, Any]:
        print_banner("STARTING SECURITY & DATA LEAK TEST", f"Target: {self.base_url}")
        async with httpx.AsyncClient(timeout=10.0) as client:
            leak_results = await self.scan_sensitive_leaks(client)

        regression_results = self.run_regression_audit_tests()
        return self.compile_report(leak_results, regression_results)

    def compile_report(
        self, leak_results: List[Dict[str, Any]], regression_results: Dict[str, Any]
    ) -> Dict[str, Any]:
        total_probes = len(leak_results)
        failed_probes = sum(1 for r in leak_results if not r["clean"])
        leaks_found = sum(1 for r in leak_results if r["leaks"])

        report_data = {
            "test_type": "security_check",
            "timestamp": datetime.datetime.now().isoformat(),
            "target_url": self.base_url,
            "sensitive_leak_probes": leak_results,
            "regression_audit_tests": regression_results,
            "total_probes": total_probes,
            "leaks_found": leaks_found,
            "failed_probes": failed_probes,
            "verdict": (
                "PASS"
                if total_probes == 5
                and failed_probes == 0
                and regression_results["passed"]
                else "FAIL"
            ),
        }

        # Terminal Print
        print_banner(
            "SECURITY & LEAK TEST RESULTS", f"Verdict: {report_data['verdict']}"
        )
        leak_rows = [
            [
                r["probe"],
                f"HTTP {r['status_code']}",
                (
                    "CLEAN"
                    if r["clean"]
                    else f"FAIL ({', '.join(r['leaks']) or r.get('note') or 'Unexpected status'})"
                ),
            ]
            for r in leak_results
        ]
        print_table(["Probe", "Status Code", "Sensitive Leak Evaluation"], leak_rows)

        print("\n--- Security Regression Suites ---")
        print(
            f"Pytest Exit Code: {regression_results['exit_code']} (Duration: {regression_results['duration_s']}s)"
        )
        print(
            f"Summary: {regression_results['stdout'].splitlines()[-1] if regression_results['stdout'] else 'No output'}"
        )

        # Markdown Report Generation
        md_content = self.generate_markdown(report_data)
        ts_path, latest_path = save_report(
            "security", "security-report", md_content, report_data
        )
        print(f"\n[+] Report saved to:")
        print(f"    - {ts_path}")
        print(f"    - {latest_path}")

        return report_data

    def generate_markdown(self, data: Dict[str, Any]) -> str:
        date_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        reg = data["regression_audit_tests"]

        probe_rows = []
        for r in data["sensitive_leak_probes"]:
            eval_str = (
                "CLEAN (Expected status, zero leaks)"
                if r["clean"]
                else f"FAIL: {', '.join(r['leaks']) or r.get('note') or 'Unexpected status'}"
            )
            probe_rows.append(
                f"| {r['probe']} | `{r['endpoint']}` | HTTP {r['status_code']} | {eval_str} |"
            )
        probe_table = "\n".join(probe_rows)

        return f"""# Security & Sensitive Data Leak Report — ProAce Commerce
**Date**: {date_str}  
**Target Environment**: `{data['target_url']}`  
**Overall Verdict**: **{data['verdict']}**

---

## 1. Sensitive Data Exposure & Error Envelope Audit

| Security Probe | Endpoint | Status Code | Leak Assessment |
| :--- | :--- | :--- | :--- |
{probe_table}

> **Guardrail Policy**: Error messages must never expose stack traces, raw SQL, database internal schemas, or Python `ErrorDetail(...)` representations.

---

## 2. Security & Regression Test Suites
- **Pytest Execution**: `{'PASS (0 failures)' if reg['passed'] else 'FAIL'}`
- **Execution Duration**: `{reg['duration_s']}s`
- **Output Summary**: `{reg['stdout'].splitlines()[-1] if reg['stdout'] else 'Completed'}`

---

## 3. Compliance Summary
- A PASS requires all five live probes to return their expected statuses without detected leaks and the regression suite to pass.
- Failed or unreachable probes do not establish endpoint safety or access-control enforcement.
- Generated automatically by `npm run test:security`.
"""


def main() -> None:
    parser = argparse.ArgumentParser(
        description="ProAce Commerce Security & Data Leak Runner"
    )
    parser.add_argument(
        "--url",
        default=os.getenv("TARGET_URL", "http://127.0.0.1:8000"),
        help="Target base URL",
    )
    args = parser.parse_args()

    auditor = SecurityAuditor(base_url=args.url)
    report = asyncio.run(auditor.run())
    if report["verdict"] != "PASS":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
