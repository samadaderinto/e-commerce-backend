#!/usr/bin/env python3
"""Read-only volume sampling with explicit coverage and response validation."""

from __future__ import annotations

import argparse
import asyncio
import datetime
import os
import time
from typing import Any

import httpx

from catalog_workload import (
    catalog_path,
    discover_catalog,
    route_api_request,
    result_count,
)
from utils import compute_percentiles, save_report


class VolumeTester:
    def __init__(self, base_url: str, client_timeout: float = 15.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.client_timeout = client_timeout

    async def sample(self, client: httpx.AsyncClient, path: str) -> dict[str, Any]:
        latencies: list[float] = []
        statuses: list[int] = []
        counts: list[int] = []
        sizes: list[int] = []
        for _ in range(3):
            started = time.perf_counter()
            try:
                response = await client.get(self.base_url + path)
                statuses.append(response.status_code)
                counts.append(result_count(response))
                sizes.append(len(response.content))
            except (httpx.HTTPError, ValueError, TypeError) as exc:
                statuses.append(599)
                counts.append(0)
                sizes.append(0)
                print(f"Sample failed: {type(exc).__name__}")
            latencies.append((time.perf_counter() - started) * 1000)
        stats = compute_percentiles(latencies)
        return {
            "path": path,
            "statuses": statuses,
            "result_counts": counts,
            "payload_kb": round(max(sizes) / 1024, 2),
            "avg_latency_ms": stats["avg"],
            "p95_ms": stats["p95"],
        }

    async def run(self) -> dict[str, Any]:
        async with httpx.AsyncClient(
            timeout=self.client_timeout, event_hooks={"request": [route_api_request]}
        ) as client:
            fixtures = await discover_catalog(client, self.base_url)
            # Probe only populated pages; preserve the requested-depth coverage separately.
            pages = sorted({min(page, fixtures["pages"]) for page in [1, 2, 5, 10, 20]})
            pagination = []
            for page in pages:
                sample = await self.sample(client, catalog_path(page=page))
                pagination.append({"page": page, **sample})
            from urllib.parse import quote

            category = quote(fixtures["categories"][0])
            queries = [
                ("Baseline", "/api/v1/products/"),
                ("Category", f"/api/v1/products/?category={category}"),
                ("Price range", catalog_path(min_price=10, max_price=150)),
                (
                    "Category and price",
                    f"/api/v1/products/?category={category}&min_price=20&max_price=100",
                ),
                ("Catalog search", catalog_path(search=fixtures["search"])),
            ]
            filters = []
            for name, path in queries:
                filters.append({"query_name": name, **await self.sample(client, path)})
        rows = pagination + filters
        failed = any(status != 200 for row in rows for status in row["statuses"])
        slow = any(row["p95_ms"] >= 450 for row in rows)
        incomplete = (
            fixtures["count"] < 1000
            or fixtures["pages"] < 20
            or any(count == 0 for row in rows for count in row["result_counts"])
        )
        verdict = "FAIL" if failed or slow else "INCOMPLETE" if incomplete else "PASS"
        data = {
            "test_type": "volume",
            "timestamp": datetime.datetime.now().isoformat(),
            "target_url": self.base_url,
            "verdict": verdict,
            "visible_product_count": fixtures["count"],
            "available_pages": fixtures["pages"],
            "pagination_results": pagination,
            "filter_results": filters,
            "limitations": "Visible API dataset only. No database query plans or index utilization measured. Empty samples do not establish populated-query performance.",
        }
        paths = save_report(
            "volume", "volume-report", self.generate_markdown(data), data
        )
        print(f"Volume verdict: {verdict}; reports: {paths}")
        return data

    def generate_markdown(self, data: dict[str, Any]) -> str:
        rows = []
        for row in data["pagination_results"] + data["filter_results"]:
            name = row.get("query_name", f"Page {row.get('page')}")
            rows.append(
                f"| {name} | `{row['path']}` | {row['statuses']} | "
                f"{row['result_counts']} | {row['avg_latency_ms']} ms | {row['p95_ms']} ms |"
            )
        table = "\n".join(rows)
        return f"""# Volume performance report
Date: {data["timestamp"]}
Target: {data["target_url"]}
Verdict: **{data["verdict"]}**

Visible products: {data["visible_product_count"]}; populated pages: {data["available_pages"]}.
Target coverage: at least 1,000 visible products and page 20; p95 < 450 ms and HTTP 200 for every sample.

| Scenario | Path | HTTP statuses | Result counts | Average | p95 |
| --- | --- | --- | --- | --- | --- |
{table}

{data["limitations"]}
"""


def main() -> None:
    parser = argparse.ArgumentParser(description="Read-only catalog volume sampling")
    parser.add_argument(
        "--url", default=os.getenv("TARGET_URL", "http://127.0.0.1:8000")
    )
    args = parser.parse_args()
    report = asyncio.run(VolumeTester(args.url).run())
    raise SystemExit(
        1
        if report["verdict"] == "FAIL"
        else 2
        if report["verdict"] == "INCOMPLETE"
        else 0
    )


if __name__ == "__main__":
    main()
