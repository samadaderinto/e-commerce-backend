#!/usr/bin/env python3
"""
Load Testing Runner for ProAce Commerce.
Simulates concurrent user browsing, search, and catalog queries.
Outputs reports to: qa-reports/performance-testing/load/
"""

from __future__ import annotations

import argparse
import asyncio
import datetime
import os
import random
import time
from typing import Any, Dict, List

import httpx

from catalog_workload import catalog_path, discover_catalog, route_api_request

from utils import (
    compute_percentiles,
    print_banner,
    print_table,
    save_report,
)


class LoadTester:
    def __init__(
        self,
        base_url: str,
        concurrency: int,
        duration_seconds: int,
        client_timeout: float = 10.0,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.concurrency = concurrency
        self.duration_seconds = duration_seconds
        self.client_timeout = client_timeout
        self.product_ids: List[str] = []
        self.max_page: int = 1
        self.results: List[Dict[str, Any]] = []

    async def warm_up_and_discover(self, client: httpx.AsyncClient) -> None:
        """Fetch active products to populate realistic detail URLs."""
        print(f"[*] Discovering sample catalog items from {self.base_url}...")
        fixtures = await discover_catalog(client, self.base_url)
        self.product_ids = fixtures["ids"]
        self.max_page = fixtures["pages"]
        self.categories = fixtures["categories"]
        self.search_term = fixtures["search"]

    async def worker(
        self, worker_id: int, stop_event: asyncio.Event, client: httpx.AsyncClient
    ) -> None:
        """Worker task that continuously issues realistic requests until stop_event is set."""
        while not stop_event.is_set():
            # Pick a scenario
            roll = random.random()
            if roll < 0.40:
                scenario = "Catalog Listing"
                page = random.randint(1, max(1, min(self.max_page, 5)))
                path = catalog_path(page=page)
            elif roll < 0.65:
                scenario = "Catalog Search"
                term = self.search_term
                path = catalog_path(search=term)
            elif roll < 0.85 and self.product_ids:
                scenario = "Product Detail"
                pid = random.choice(self.product_ids)
                path = f"/api/v1/products/{pid}/"
            else:
                scenario = "Category Filter"
                cat = random.choice(self.categories)
                path = catalog_path(category=cat)

            url = f"{self.base_url}{path}"
            t0 = time.perf_counter()
            status = 0
            error_msg = ""
            cache_status = "UNKNOWN"
            result_count: int | None = None
            try:
                res = await client.get(url)
                status = res.status_code
                cache_status = res.headers.get(
                    "X-Catalog-Cache",
                    "BYPASS" if scenario == "Product Detail" else "UNKNOWN",
                )
                if status == 200 and scenario != "Product Detail":
                    result_count = len(res.json().get("results", []))
                else:
                    result_count = None
            except httpx.TimeoutException:
                status = 408
                error_msg = "Timeout"
            except Exception as e:
                status = 599
                error_msg = str(e)
            latency_ms = (time.perf_counter() - t0) * 1000.0

            self.results.append(
                {
                    "worker": worker_id,
                    "scenario": scenario,
                    "path": path,
                    "status": status,
                    "latency_ms": latency_ms,
                    "error": error_msg,
                    "result_count": result_count,
                    "catalog_cache": cache_status,
                    "timestamp": time.time(),
                }
            )

            # Small realistic user think time (10ms - 50ms)
            await asyncio.sleep(random.uniform(0.01, 0.05))

    async def run(self) -> Dict[str, Any]:
        limits = httpx.Limits(
            max_keepalive_connections=self.concurrency,
            max_connections=self.concurrency * 2,
        )
        async with httpx.AsyncClient(
            timeout=self.client_timeout,
            limits=limits,
            event_hooks={"request": [route_api_request]},
        ) as client:
            await self.warm_up_and_discover(client)

            stop_event = asyncio.Event()
            print(
                f"[*] Starting Load Test with {self.concurrency} concurrent workers for {self.duration_seconds}s..."
            )
            start_time = time.perf_counter()

            tasks = [
                asyncio.create_task(self.worker(w, stop_event, client))
                for w in range(self.concurrency)
            ]

            await asyncio.sleep(self.duration_seconds)
            stop_event.set()
            await asyncio.gather(*tasks)

            total_duration = time.perf_counter() - start_time

        return self.compile_report(total_duration)

    def compile_report(self, total_duration: float) -> Dict[str, Any]:
        total_requests = len(self.results)
        if total_requests == 0:
            print("[!] No requests were recorded.")
            return {}

        success_count = sum(1 for r in self.results if r["status"] == 200)
        client_err_count = sum(
            1 for r in self.results if 400 <= r["status"] < 500 and not r.get("error")
        )
        server_err_count = sum(
            1 for r in self.results if r["status"] >= 500 and not r.get("error")
        )

        all_latencies = [r["latency_ms"] for r in self.results]
        overall_stats = compute_percentiles(all_latencies)
        rps = round(total_requests / total_duration, 2)
        error_rate = round(
            ((total_requests - success_count) / total_requests) * 100.0, 2
        )

        # Per scenario breakdown
        scenarios: Dict[str, List[float]] = {}
        scenario_status: Dict[str, Dict[int, int]] = {}
        for r in self.results:
            sc = r["scenario"]
            scenarios.setdefault(sc, []).append(r["latency_ms"])
            sc_dict = scenario_status.setdefault(sc, {})
            sc_dict[r["status"]] = sc_dict.get(r["status"], 0) + 1

        scenario_breakdown = {}
        for sc, lats in scenarios.items():
            stats = compute_percentiles(lats)
            stats["statuses"] = scenario_status[sc]
            stats["successful_latency_ms"] = compute_percentiles(
                [
                    r["latency_ms"]
                    for r in self.results
                    if r["scenario"] == sc and r["status"] == 200
                ]
            )
            stats["empty_responses"] = sum(
                r["result_count"] == 0 for r in self.results if r["scenario"] == sc
            )
            scenario_breakdown[sc] = stats

        report_data = {
            "test_type": "load",
            "verdict": "FAIL"
            if error_rate >= 1 or overall_stats["p95"] >= 450
            else "INCOMPLETE"
            if any(r["result_count"] == 0 for r in self.results)
            else "PASS",
            "successful_latency_ms": compute_percentiles(
                [r["latency_ms"] for r in self.results if r["status"] == 200]
            ),
            "timestamp": datetime.datetime.now().isoformat(),
            "target_url": self.base_url,
            "concurrency": self.concurrency,
            "duration_seconds": round(total_duration, 2),
            "total_requests": total_requests,
            "requests_per_second": rps,
            "success_count": success_count,
            "client_error_count": client_err_count,
            "transport_error_count": sum(bool(r.get("error")) for r in self.results),
            "server_error_count": server_err_count,
            "error_rate_pct": error_rate,
            "latency_stats_ms": overall_stats,
            "scenario_breakdown": scenario_breakdown,
            "catalog_cache_counts": {
                value: sum(r.get("catalog_cache") == value for r in self.results)
                for value in ("HIT", "MISS", "BYPASS", "UNKNOWN")
            },
        }

        # Terminal print
        print_banner(
            "LOAD TEST EXECUTION COMPLETE",
            f"Target: {self.base_url} | Duration: {total_duration:.1f}s",
        )
        print_table(
            ["Metric", "Value"],
            [
                ["Total Requests", total_requests],
                ["Throughput (RPS)", f"{rps} req/sec"],
                [
                    "Successful (HTTP 200)",
                    f"{success_count} ({success_count / total_requests * 100:.1f}%)",
                ],
                ["Client Errors (4xx)", client_err_count],
                ["Server Errors (5xx)", server_err_count],
                ["Error Rate", f"{error_rate}%"],
                ["p50 (Median) Latency", f"{overall_stats['p50']} ms"],
                ["p90 Latency", f"{overall_stats['p90']} ms"],
                ["p95 Latency", f"{overall_stats['p95']} ms"],
                ["p99 Latency", f"{overall_stats['p99']} ms"],
                ["Avg Latency", f"{overall_stats['avg']} ms"],
            ],
        )

        print("\n--- Per-Scenario Performance ---")
        scenario_rows = []
        for sc, stats in scenario_breakdown.items():
            scenario_rows.append(
                [
                    sc,
                    stats["count"],
                    f"{stats['p50']} ms",
                    f"{stats['p95']} ms",
                    f"{stats['max']} ms",
                ]
            )
        print_table(["Scenario", "Requests", "p50", "p95", "Max"], scenario_rows)

        # Markdown report generation
        md_content = self.generate_markdown(report_data)
        ts_path, latest_path = save_report(
            "load", "load-report", md_content, report_data
        )
        print("\n[+] Report saved to:")
        print(f"    - {ts_path}")
        print(f"    - {latest_path}")

        return report_data

    def generate_markdown(self, data: Dict[str, Any]) -> str:
        stats = data["latency_stats_ms"]
        date_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        status_eval = data["verdict"]

        rows = []
        for sc, s in data["scenario_breakdown"].items():
            rows.append(
                f"| {sc} | {s['count']} | {s['avg']} ms | {s['p50']} ms | {s['p95']} ms | {s['max']} ms | {s['statuses']} |"
            )
        scenario_table = "\n".join(rows)

        return f"""# Load Testing Report — ProAce Commerce
**Date**: {date_str}
**Target Environment**: `{data["target_url"]}`
**Test Profile**: Sustained Concurrency ({data["concurrency"]} Virtual Users, {data["duration_seconds"]}s)
**Catalog cache responses**: {data["catalog_cache_counts"]} (warm snapshots and uncached requests are mixed; this is not a cold-cache capacity measurement; UNKNOWN means the response/proxy did not expose the diagnostic header).
**Overall Verdict**: **{status_eval}** (Error Rate: {data["error_rate_pct"]}%, p95: {stats["p95"]}ms)

---

## 1. Executive Summary

| Metric | Measured Value | Standard Target | Status |
| :--- | :--- | :--- | :--- |
| **Total Requests** | **{data["total_requests"]}** | N/A | Completed |
| **Throughput** | **{data["requests_per_second"]} RPS** | > 20 RPS | {"PASS" if data["requests_per_second"] > 20 else "WARN"} |
| **Error Rate** | **{data["error_rate_pct"]}%** | < 1.0% | {"PASS" if data["error_rate_pct"] < 1.0 else "FAIL"} |
| **p50 Latency (Median)** | **{stats["p50"]} ms** | < 150 ms | {"PASS" if stats["p50"] < 150 else "WARN"} |
| **p95 Latency** | **{stats["p95"]} ms** | < 450 ms | {"PASS" if stats["p95"] < 450 else "WARN"} |
| **p99 Latency** | **{stats["p99"]} ms** | < 800 ms | {"PASS" if stats["p99"] < 800 else "WARN"} |
| **Max Latency** | **{stats["max"]} ms** | < 2000 ms | {"PASS" if stats["max"] < 2000 else "WARN"} |

---

## 2. Per-Scenario Breakdown

| Scenario | Request Count | Average | p50 (Median) | p95 | Max | HTTP statuses |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
{scenario_table}

---

## 3. Operational Observations & Diagnostics
- **Target Host**: `{data["target_url"]}`
- **Concurrency Level**: `{data["concurrency"]} concurrent workers`
- **Client Errors (4xx)**: `{data["client_error_count"]}`
- **Server Errors (5xx)**: `{data["server_error_count"]}`
- **Transport Errors**: `{data["transport_error_count"]}`
- Successful-only latency is recorded separately in JSON. Empty responses mark coverage incomplete.
- This is API timing; browser rendering and image loading are not measured.
- Generated automatically by `npm run test:load`.
"""


def main() -> None:
    parser = argparse.ArgumentParser(description="ProAce Commerce Load Testing Runner")
    parser.add_argument(
        "--url",
        default=os.getenv("TARGET_URL", "http://127.0.0.1:8000"),
        help="Target base URL",
    )
    parser.add_argument(
        "--concurrency",
        "-c",
        type=int,
        default=25,
        help="Number of concurrent workers (default: 25)",
    )
    parser.add_argument(
        "--duration",
        "-d",
        type=int,
        default=60,
        help="Test duration in seconds (default: 60)",
    )
    parser.add_argument(
        "--seed", type=int, default=2026, help="Repeatable scenario random seed"
    )
    args = parser.parse_args()
    if args.concurrency < 1 or args.duration < 1:
        parser.error("Concurrency and duration must be positive")
    random.seed(args.seed)

    tester = LoadTester(
        base_url=args.url, concurrency=args.concurrency, duration_seconds=args.duration
    )
    report = asyncio.run(tester.run())
    raise SystemExit(
        1
        if report["verdict"] == "FAIL"
        else 2
        if report["verdict"] == "INCOMPLETE"
        else 0
    )


if __name__ == "__main__":
    main()
