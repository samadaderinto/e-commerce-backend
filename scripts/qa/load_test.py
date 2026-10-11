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
import sys
import time
from typing import Any, Dict, List

import httpx

from utils import (
    compute_percentiles,
    get_report_dir,
    print_banner,
    print_table,
    save_report,
)


class LoadTester:
    def __init__(self, base_url: str, concurrency: int, duration_seconds: int, client_timeout: float = 10.0):
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
        try:
            res = await client.get(f"{self.base_url}/api/v1/products/?page=1&page_size=12")
            if res.status_code == 200:
                data = res.json()
                count = data.get("count", 12)
                self.max_page = max(1, (count + 11) // 12)
                items = data.get("results", data if isinstance(data, list) else [])
                self.product_ids = [str(item["id"]) for item in items if "id" in item]
                print(f"[+] Found {len(self.product_ids)} catalog products ({count} total, {self.max_page} pages).")
        except Exception as exc:
            print(f"[!] Warning: catalog discovery failed ({exc}). Falling back to generic routes.")

    async def worker(self, worker_id: int, stop_event: asyncio.Event, client: httpx.AsyncClient) -> None:
        """Worker task that continuously issues realistic requests until stop_event is set."""
        search_terms = ["shoes", "jacket", "shirt", "pro", "running", "cotton", "black", "audio"]
        
        while not stop_event.is_set():
            # Pick a scenario
            roll = random.random()
            if roll < 0.40:
                scenario = "Catalog Listing"
                page = random.randint(1, max(1, min(self.max_page, 5)))
                path = f"/api/v1/products/?page={page}&page_size=12"
            elif roll < 0.65:
                scenario = "Elasticsearch Search"
                term = random.choice(search_terms)
                path = f"/api/v1/products/?search={term}"
            elif roll < 0.85 and self.product_ids:
                scenario = "Product Detail"
                pid = random.choice(self.product_ids)
                path = f"/api/v1/products/{pid}/"
            else:
                scenario = "Category Filter"
                cat = random.choice(["apparel", "electronics", "footwear", "accessories"])
                path = f"/api/v1/products/?category={cat}"

            url = f"{self.base_url}{path}"
            t0 = time.perf_counter()
            status = 0
            error_msg = ""
            try:
                res = await client.get(url)
                status = res.status_code
            except httpx.TimeoutException:
                status = 408
                error_msg = "Timeout"
            except Exception as e:
                status = 599
                error_msg = str(e)
            latency_ms = (time.perf_counter() - t0) * 1000.0

            self.results.append({
                "worker": worker_id,
                "scenario": scenario,
                "path": path,
                "status": status,
                "latency_ms": latency_ms,
                "error": error_msg,
                "timestamp": time.time(),
            })

            # Small realistic user think time (10ms - 50ms)
            await asyncio.sleep(random.uniform(0.01, 0.05))

    async def run(self) -> Dict[str, Any]:
        limits = httpx.Limits(max_keepalive_connections=self.concurrency, max_connections=self.concurrency * 2)
        async with httpx.AsyncClient(timeout=self.client_timeout, limits=limits) as client:
            await self.warm_up_and_discover(client)

            stop_event = asyncio.Event()
            print(f"[*] Starting Load Test with {self.concurrency} concurrent workers for {self.duration_seconds}s...")
            start_time = time.perf_counter()

            tasks = [
                asyncio.create_task(self.worker(w, stop_event, client))
                for w in range(self.concurrency)
            ]

            await asyncio.sleep(self.duration_seconds)
            stop_event.set()
            await asyncio.gather(*tasks, return_exceptions=True)

            total_duration = time.perf_counter() - start_time

        return self.compile_report(total_duration)

    def compile_report(self, total_duration: float) -> Dict[str, Any]:
        total_requests = len(self.results)
        if total_requests == 0:
            print("[!] No requests were recorded.")
            return {}

        success_count = sum(1 for r in self.results if 200 <= r["status"] < 400)
        client_err_count = sum(1 for r in self.results if 400 <= r["status"] < 500)
        server_err_count = sum(1 for r in self.results if r["status"] >= 500)

        all_latencies = [r["latency_ms"] for r in self.results]
        overall_stats = compute_percentiles(all_latencies)
        rps = round(total_requests / total_duration, 2)
        error_rate = round(((client_err_count + server_err_count) / total_requests) * 100.0, 2)

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
            scenario_breakdown[sc] = stats

        report_data = {
            "test_type": "load",
            "timestamp": datetime.datetime.now().isoformat(),
            "target_url": self.base_url,
            "concurrency": self.concurrency,
            "duration_seconds": round(total_duration, 2),
            "total_requests": total_requests,
            "requests_per_second": rps,
            "success_count": success_count,
            "client_error_count": client_err_count,
            "server_error_count": server_err_count,
            "error_rate_pct": error_rate,
            "latency_stats_ms": overall_stats,
            "scenario_breakdown": scenario_breakdown,
        }

        # Terminal print
        print_banner("LOAD TEST EXECUTION COMPLETE", f"Target: {self.base_url} | Duration: {total_duration:.1f}s")
        print_table(
            ["Metric", "Value"],
            [
                ["Total Requests", total_requests],
                ["Throughput (RPS)", f"{rps} req/sec"],
                ["Successful (2xx/3xx)", f"{success_count} ({success_count/total_requests*100:.1f}%)"],
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
            scenario_rows.append([
                sc,
                stats["count"],
                f"{stats['p50']} ms",
                f"{stats['p95']} ms",
                f"{stats['max']} ms",
            ])
        print_table(["Scenario", "Requests", "p50", "p95", "Max"], scenario_rows)

        # Markdown report generation
        md_content = self.generate_markdown(report_data)
        ts_path, latest_path = save_report("load", "load-report", md_content, report_data)
        print(f"\n[+] Report saved to:")
        print(f"    - {ts_path}")
        print(f"    - {latest_path}")

        return report_data

    def generate_markdown(self, data: Dict[str, Any]) -> str:
        stats = data["latency_stats_ms"]
        date_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        status_eval = "PASS" if data["error_rate_pct"] < 1.0 and stats["p95"] < 450 else "WARN"

        rows = []
        for sc, s in data["scenario_breakdown"].items():
            rows.append(f"| {sc} | {s['count']} | {s['avg']} ms | {s['p50']} ms | {s['p95']} ms | {s['max']} ms |")
        scenario_table = "\n".join(rows)

        return f"""# Load Testing Report — ProAce Commerce
**Date**: {date_str}  
**Target Environment**: `{data['target_url']}`  
**Test Profile**: Sustained Concurrency ({data['concurrency']} Virtual Users, {data['duration_seconds']}s)  
**Overall Verdict**: **{status_eval}** (Error Rate: {data['error_rate_pct']}%, p95: {stats['p95']}ms)

---

## 1. Executive Summary

| Metric | Measured Value | Standard Target | Status |
| :--- | :--- | :--- | :--- |
| **Total Requests** | **{data['total_requests']}** | N/A | Completed |
| **Throughput** | **{data['requests_per_second']} RPS** | > 20 RPS | {'PASS' if data['requests_per_second'] > 20 else 'WARN'} |
| **Error Rate** | **{data['error_rate_pct']}%** | < 1.0% | {'PASS' if data['error_rate_pct'] < 1.0 else 'FAIL'} |
| **p50 Latency (Median)** | **{stats['p50']} ms** | < 150 ms | {'PASS' if stats['p50'] < 150 else 'WARN'} |
| **p95 Latency** | **{stats['p95']} ms** | < 450 ms | {'PASS' if stats['p95'] < 450 else 'WARN'} |
| **p99 Latency** | **{stats['p99']} ms** | < 800 ms | {'PASS' if stats['p99'] < 800 else 'WARN'} |
| **Max Latency** | **{stats['max']} ms** | < 2000 ms | {'PASS' if stats['max'] < 2000 else 'WARN'} |

---

## 2. Per-Scenario Breakdown

| Scenario | Request Count | Average | p50 (Median) | p95 | Max |
| :--- | :--- | :--- | :--- | :--- | :--- |
{scenario_table}

---

## 3. Operational Observations & Diagnostics
- **Target Host**: `{data['target_url']}`
- **Concurrency Level**: `{data['concurrency']} concurrent workers`
- **Client Errors (4xx)**: `{data['client_error_count']}`
- **Server Errors (5xx)**: `{data['server_error_count']}`
- Generated automatically by `npm run test:load`.
"""


def main() -> None:
    parser = argparse.ArgumentParser(description="ProAce Commerce Load Testing Runner")
    parser.add_argument("--url", default=os.getenv("TARGET_URL", "http://127.0.0.1:8000"), help="Target base URL")
    parser.add_argument("--concurrency", "-c", type=int, default=25, help="Number of concurrent workers (default: 25)")
    parser.add_argument("--duration", "-d", type=int, default=15, help="Test duration in seconds (default: 15)")
    args = parser.parse_args()

    tester = LoadTester(base_url=args.url, concurrency=args.concurrency, duration_seconds=args.duration)
    asyncio.run(tester.run())


if __name__ == "__main__":
    main()
