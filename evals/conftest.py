"""Pytest fixtures for the AgentForge Healthcare evaluation suite."""

from __future__ import annotations

import json
import os
import time
from pathlib import Path

import pytest
import requests

API_BASE_URL = os.getenv("EVAL_API_URL", "http://localhost:8004")
CHAT_TIMEOUT = 120  # seconds — agent may chain multiple tools


@pytest.fixture(scope="session")
def api_url() -> str:
    """Return the base URL for the API."""
    return API_BASE_URL


@pytest.fixture(scope="session")
def result_collector() -> list[dict]:
    """Session-scoped list to collect all eval results for the final report."""
    return []


@pytest.fixture(scope="session", autouse=True)
def check_api_health(api_url: str) -> None:
    """Verify the API is reachable before running any tests."""
    try:
        resp = requests.get(f"{api_url}/api/health", timeout=5)
        resp.raise_for_status()
        data = resp.json()
        assert data.get("status") == "ok", f"API unhealthy: {data}"
    except Exception as e:
        pytest.exit(f"API not reachable at {api_url}: {e}")


@pytest.fixture(scope="session", autouse=True)
def write_report(result_collector: list[dict]) -> None:
    """Write the evaluation report after all tests complete."""
    yield  # Run all tests first

    if not result_collector:
        return

    # Write raw results
    results_path = Path(__file__).parent / "results.json"
    with open(results_path, "w") as f:
        json.dump(result_collector, f, indent=2)

    # Print summary
    total = len(result_collector)
    passed = sum(1 for r in result_collector if r["passed"])
    failed = total - passed

    by_category: dict[str, dict] = {}
    latencies: list[float] = []

    for r in result_collector:
        cat = r["category"]
        if cat not in by_category:
            by_category[cat] = {"total": 0, "passed": 0, "latencies": []}
        by_category[cat]["total"] += 1
        if r["passed"]:
            by_category[cat]["passed"] += 1
        by_category[cat]["latencies"].append(r["latency"])
        latencies.append(r["latency"])

    latencies.sort()

    print("\n" + "=" * 70)
    print("AGENTFORGE HEALTHCARE — EVALUATION REPORT")
    print("=" * 70)
    print(f"\nOverall: {passed}/{total} passed ({100*passed/total:.0f}%)")
    print(f"Latency p50: {_percentile(latencies, 50):.1f}s | p95: {_percentile(latencies, 95):.1f}s")

    print(f"\n{'Category':<20} {'Passed':>8} {'Total':>8} {'Rate':>8} {'p50 Latency':>12}")
    print("-" * 60)
    for cat in ["happy_path", "edge_case", "adversarial", "multi_step"]:
        if cat in by_category:
            d = by_category[cat]
            rate = 100 * d["passed"] / d["total"] if d["total"] else 0
            p50 = _percentile(sorted(d["latencies"]), 50)
            print(f"{cat:<20} {d['passed']:>8} {d['total']:>8} {rate:>7.0f}% {p50:>10.1f}s")

    # Tool success rate
    tool_calls_total = sum(len(r.get("tool_calls", [])) for r in result_collector)
    tool_errors = sum(
        1 for r in result_collector
        for tc in r.get("tool_calls", [])
        if "error" in str(tc).lower()
    )
    tool_success = 100 * (tool_calls_total - tool_errors) / tool_calls_total if tool_calls_total else 100
    print(f"\nTool Success Rate: {tool_success:.0f}% ({tool_calls_total} calls)")

    # G4 target comparison
    print(f"\n{'G4 Target':<35} {'Actual':>10} {'Status':>8}")
    print("-" * 55)
    overall_rate = 100 * passed / total if total else 0
    _target_row("Eval pass rate >80%", f"{overall_rate:.0f}%", overall_rate > 80)
    _target_row("Tool success >95%", f"{tool_success:.0f}%", tool_success > 95)
    p50 = _percentile(latencies, 50)
    _target_row("Latency p50 <5s", f"{p50:.1f}s", p50 < 5)

    print("\n" + "=" * 70)
    print(f"Results saved to: {results_path}")


def send_chat(api_url: str, message: str) -> tuple[dict, float]:
    """Send a chat message and return (response_dict, elapsed_seconds)."""
    start = time.time()
    resp = requests.post(
        f"{api_url}/api/chat",
        json={"message": message},
        timeout=CHAT_TIMEOUT,
    )
    elapsed = time.time() - start
    resp.raise_for_status()
    return resp.json(), elapsed


def _percentile(sorted_vals: list[float], pct: int) -> float:
    """Calculate a percentile from a sorted list."""
    if not sorted_vals:
        return 0.0
    idx = int(len(sorted_vals) * pct / 100)
    idx = min(idx, len(sorted_vals) - 1)
    return sorted_vals[idx]


def _target_row(label: str, actual: str, met: bool) -> None:
    """Print a G4 target comparison row."""
    status = "PASS" if met else "FAIL"
    print(f"{label:<35} {actual:>10} {status:>8}")
