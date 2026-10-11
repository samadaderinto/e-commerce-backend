from __future__ import annotations

import datetime
import json
import math
import os
import pathlib
import sys
from typing import Any, Dict, List, Optional, Tuple

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
QA_REPORTS_DIR = REPO_ROOT / "qa-reports"

CATEGORY_DIRS = {
    "load": QA_REPORTS_DIR / "performance-testing" / "load",
    "stress": QA_REPORTS_DIR / "performance-testing" / "stress",
    "volume": QA_REPORTS_DIR / "performance-testing" / "volume",
    "audit": QA_REPORTS_DIR / "bug-audit",
}


def ensure_directories() -> None:
    """Ensure all required QA report directories exist."""
    for path in CATEGORY_DIRS.values():
        path.mkdir(parents=True, exist_ok=True)


def get_report_dir(category: str) -> pathlib.Path:
    ensure_directories()
    if category not in CATEGORY_DIRS:
        raise ValueError(f"Unknown QA report category: {category}. Valid: {list(CATEGORY_DIRS.keys())}")
    return CATEGORY_DIRS[category]


def compute_percentiles(latencies_ms: List[float]) -> Dict[str, float]:
    """Compute standard latency percentiles from a list of millisecond values."""
    if not latencies_ms:
        return {
            "count": 0,
            "min": 0.0,
            "p50": 0.0,
            "p90": 0.0,
            "p95": 0.0,
            "p99": 0.0,
            "max": 0.0,
            "avg": 0.0,
        }

    sorted_lats = sorted(latencies_ms)
    n = len(sorted_lats)

    def percentile(p: float) -> float:
        if n == 1:
            return sorted_lats[0]
        k = (n - 1) * (p / 100.0)
        f = math.floor(k)
        c = math.ceil(k)
        if f == c:
            return sorted_lats[int(k)]
        return sorted_lats[int(f)] * (c - k) + sorted_lats[int(c)] * (k - f)

    return {
        "count": n,
        "min": round(sorted_lats[0], 2),
        "p50": round(percentile(50), 2),
        "p90": round(percentile(90), 2),
        "p95": round(percentile(95), 2),
        "p99": round(percentile(99), 2),
        "max": round(sorted_lats[-1], 2),
        "avg": round(sum(sorted_lats) / n, 2),
    }


def save_report(
    category: str,
    prefix: str,
    markdown_content: str,
    data_payload: Optional[Dict[str, Any]] = None,
) -> Tuple[pathlib.Path, pathlib.Path]:
    """
    Saves a report in both timestamped format and 'latest' format.
    Returns (timestamped_md_path, latest_md_path).
    """
    target_dir = get_report_dir(category)
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d-%H%M%S")

    # Markdown paths
    ts_file = target_dir / f"{prefix}-{timestamp}.md"
    latest_file = target_dir / f"latest.md"

    ts_file.write_text(markdown_content, encoding="utf-8")
    latest_file.write_text(markdown_content, encoding="utf-8")

    # JSON raw metrics payload if provided
    if data_payload is not None:
        json_ts = target_dir / f"{prefix}-{timestamp}.json"
        json_latest = target_dir / f"latest.json"
        json_content = json.dumps(data_payload, indent=2, default=str)
        json_ts.write_text(json_content, encoding="utf-8")
        json_latest.write_text(json_content, encoding="utf-8")

    return ts_file, latest_file


def print_banner(title: str, subtitle: str = "") -> None:
    width = 72
    print("=" * width)
    print(f"  {title}".center(width))
    if subtitle:
        print(f"  {subtitle}".center(width))
    print("=" * width)


def print_table(headers: List[str], rows: List[List[Any]]) -> None:
    """Print a clean CLI table."""
    col_widths = [len(h) for h in headers]
    for row in rows:
        for idx, val in enumerate(row):
            col_widths[idx] = max(col_widths[idx], len(str(val)))

    header_str = " | ".join(f"{h:<{col_widths[i]}}" for i, h in enumerate(headers))
    sep_str = "-+-".join("-" * col_widths[i] for i in range(len(headers)))
    print(header_str)
    print(sep_str)
    for row in rows:
        print(" | ".join(f"{str(v):<{col_widths[i]}}" for i, v in enumerate(row)))
