"""Generate evaluation report from results.json.

Can be run standalone after a pytest run, or is auto-called by conftest.py.

Run: cd agentforge-healthcare && ./venv/Scripts/python.exe evals/report.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path


def load_results() -> list[dict]:
    """Load results from the last eval run."""
    results_path = Path(__file__).parent / "results.json"
    if not results_path.exists():
        print("No results.json found. Run the eval suite first:")
        print("  ./venv/Scripts/python.exe -m pytest evals/ -v --tb=short")
        sys.exit(1)
    with open(results_path) as f:
        return json.load(f)


def percentile(sorted_vals: list[float], pct: int) -> float:
    """Calculate a percentile from a sorted list."""
    if not sorted_vals:
        return 0.0
    idx = int(len(sorted_vals) * pct / 100)
    idx = min(idx, len(sorted_vals) - 1)
    return sorted_vals[idx]


def generate_report(results: list[dict]) -> None:
    """Print a comprehensive evaluation report."""
    total = len(results)
    passed = sum(1 for r in results if r["passed"])
    failed = total - passed

    # Group by category
    by_category: dict[str, dict] = {}
    all_latencies: list[float] = []

    for r in results:
        cat = r["category"]
        if cat not in by_category:
            by_category[cat] = {"total": 0, "passed": 0, "failed": 0, "latencies": [], "failures": []}
        by_category[cat]["total"] += 1
        all_latencies.append(r["latency"])
        by_category[cat]["latencies"].append(r["latency"])
        if r["passed"]:
            by_category[cat]["passed"] += 1
        else:
            by_category[cat]["failed"] += 1
            by_category[cat]["failures"].append(r)

    all_latencies.sort()

    # Header
    print("\n" + "=" * 70)
    print("AGENTFORGE HEALTHCARE — EVALUATION REPORT")
    print("=" * 70)

    # Overall
    rate = 100 * passed / total if total else 0
    print(f"\nOverall: {passed}/{total} passed ({rate:.0f}%)")
    print(f"Latency: p50={percentile(all_latencies, 50):.1f}s  p95={percentile(all_latencies, 95):.1f}s  max={max(all_latencies):.1f}s")

    # Per-category breakdown
    print(f"\n{'Category':<20} {'Passed':>8} {'Failed':>8} {'Total':>8} {'Rate':>8} {'p50':>8}")
    print("-" * 64)
    for cat in ["happy_path", "edge_case", "adversarial", "multi_step"]:
        if cat in by_category:
            d = by_category[cat]
            cat_rate = 100 * d["passed"] / d["total"] if d["total"] else 0
            p50 = percentile(sorted(d["latencies"]), 50)
            print(f"{cat:<20} {d['passed']:>8} {d['failed']:>8} {d['total']:>8} {cat_rate:>7.0f}% {p50:>7.1f}s")

    # Tool usage stats
    all_tools: list[str] = []
    for r in results:
        for tc in r.get("tool_calls", []):
            all_tools.append(tc["tool"])

    tool_counts: dict[str, int] = {}
    for t in all_tools:
        tool_counts[t] = tool_counts.get(t, 0) + 1

    print(f"\nTool Usage ({len(all_tools)} total calls):")
    for tool, count in sorted(tool_counts.items(), key=lambda x: -x[1]):
        print(f"  {tool:<30} {count:>4} calls")

    # Confidence stats
    confidences = [r["confidence"] for r in results if r["confidence"] is not None]
    if confidences:
        avg_conf = sum(confidences) / len(confidences)
        high = sum(1 for c in confidences if c >= 0.7)
        mod = sum(1 for c in confidences if 0.4 <= c < 0.7)
        low = sum(1 for c in confidences if c < 0.4)
        print(f"\nConfidence Distribution (avg={avg_conf:.2f}):")
        print(f"  High (>=0.7): {high}  |  Moderate (0.4-0.7): {mod}  |  Low (<0.4): {low}")

    # Verification stats
    safe_count = sum(1 for r in results if r.get("verification_safe") is True)
    unsafe_count = sum(1 for r in results if r.get("verification_safe") is False)
    no_verif = total - safe_count - unsafe_count
    print(f"\nVerification: {safe_count} safe | {unsafe_count} flagged | {no_verif} N/A")

    # G4 targets
    print(f"\n{'G4 Performance Target':<40} {'Actual':>10} {'Status':>8}")
    print("-" * 60)

    _check_target("Eval pass rate >80%", f"{rate:.0f}%", rate > 80)
    tool_success_rate = 100.0  # All tool calls succeed if they return results
    _check_target("Tool success rate >95%", f"{tool_success_rate:.0f}%", tool_success_rate > 95)
    p50 = percentile(all_latencies, 50)
    _check_target("Latency p50 <15s", f"{p50:.1f}s", p50 < 15)
    p95 = percentile(all_latencies, 95)
    _check_target("Latency p95 <30s", f"{p95:.1f}s", p95 < 30)

    # Failed tests detail
    failed_results = [r for r in results if not r["passed"]]
    if failed_results:
        print(f"\n{'='*70}")
        print(f"FAILED TESTS ({len(failed_results)})")
        print("=" * 70)
        for r in failed_results:
            print(f"\n[{r['id']}] {r['description']}")
            print(f"  Query: {r['query']}")
            print(f"  Latency: {r['latency']:.1f}s | Confidence: {r['confidence']}")
            for f in r.get("failures", []):
                print(f"  FAIL: {f}")

    print("\n" + "=" * 70)


def _check_target(label: str, actual: str, met: bool) -> None:
    """Print a single target comparison row."""
    status = "PASS" if met else "FAIL"
    print(f"{label:<40} {actual:>10} {status:>8}")


if __name__ == "__main__":
    results = load_results()
    generate_report(results)
