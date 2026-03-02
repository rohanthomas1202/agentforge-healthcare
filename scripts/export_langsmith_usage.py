"""Export total token usage and costs from LangSmith.

Usage:
    python scripts/export_langsmith_usage.py
    python scripts/export_langsmith_usage.py --csv  # Export to CSV
"""

import sys
import os
from datetime import datetime

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from langsmith import Client

# Claude Sonnet 4 pricing (per million tokens)
INPUT_RATE = 3.00
OUTPUT_RATE = 15.00

PROJECT_NAME = os.getenv("LANGCHAIN_PROJECT", "agentforge-healthcare")


def main():
    export_csv = "--csv" in sys.argv

    client = Client()

    print(f"Fetching runs from LangSmith project: {PROJECT_NAME}")
    print("=" * 60)

    runs = list(client.list_runs(
        project_name=PROJECT_NAME,
        is_root=True,
    ))

    total_input = 0
    total_output = 0
    total_tokens = 0
    total_runs = len(runs)
    total_latency_ms = 0
    tool_usage = {}
    daily_usage = {}
    errors = 0

    rows = []

    for run in runs:
        input_tok = run.prompt_tokens or 0
        output_tok = run.completion_tokens or 0
        run_tokens = run.total_tokens or (input_tok + output_tok)

        total_input += input_tok
        total_output += output_tok
        total_tokens += run_tokens

        # Latency
        if run.end_time and run.start_time:
            latency = (run.end_time - run.start_time).total_seconds() * 1000
            total_latency_ms += latency
        else:
            latency = 0

        # Errors
        if run.error:
            errors += 1

        # Daily aggregation
        day = run.start_time.strftime("%Y-%m-%d") if run.start_time else "unknown"
        if day not in daily_usage:
            daily_usage[day] = {"input": 0, "output": 0, "runs": 0, "cost": 0}
        daily_usage[day]["input"] += input_tok
        daily_usage[day]["output"] += output_tok
        daily_usage[day]["runs"] += 1
        daily_usage[day]["cost"] += (input_tok * INPUT_RATE + output_tok * OUTPUT_RATE) / 1_000_000

        # Collect row for CSV
        rows.append({
            "id": str(run.id),
            "date": day,
            "name": run.name or "",
            "input_tokens": input_tok,
            "output_tokens": output_tok,
            "total_tokens": run_tokens,
            "latency_ms": round(latency),
            "error": bool(run.error),
            "cost": round((input_tok * INPUT_RATE + output_tok * OUTPUT_RATE) / 1_000_000, 6),
        })

    # Calculate costs
    input_cost = total_input * INPUT_RATE / 1_000_000
    output_cost = total_output * OUTPUT_RATE / 1_000_000
    total_cost = input_cost + output_cost
    avg_latency = total_latency_ms / total_runs if total_runs else 0

    # Print summary
    print(f"\n{'TOTAL DEVELOPMENT USAGE':^60}")
    print("=" * 60)
    print(f"  Project:          {PROJECT_NAME}")
    print(f"  Total runs:       {total_runs:,}")
    print(f"  Errors:           {errors}")
    print(f"  Avg latency:      {avg_latency / 1000:.1f}s")
    print()
    print(f"  Input tokens:     {total_input:>12,}")
    print(f"  Output tokens:    {total_output:>12,}")
    print(f"  Total tokens:     {total_tokens:>12,}")
    print()
    print(f"  Input cost:       ${input_cost:>10.4f}  (@${INPUT_RATE}/M)")
    print(f"  Output cost:      ${output_cost:>10.4f}  (@${OUTPUT_RATE}/M)")
    print(f"  ─────────────────────────────────")
    print(f"  TOTAL COST:       ${total_cost:>10.4f}")
    print()

    # Daily breakdown
    if daily_usage:
        print(f"\n{'DAILY BREAKDOWN':^60}")
        print("=" * 60)
        print(f"  {'Date':<12} {'Runs':>6} {'Input':>10} {'Output':>10} {'Cost':>10}")
        print(f"  {'─' * 12} {'─' * 6} {'─' * 10} {'─' * 10} {'─' * 10}")
        for day in sorted(daily_usage.keys()):
            d = daily_usage[day]
            print(f"  {day:<12} {d['runs']:>6} {d['input']:>10,} {d['output']:>10,} ${d['cost']:>9.4f}")
        print(f"  {'─' * 12} {'─' * 6} {'─' * 10} {'─' * 10} {'─' * 10}")
        print(f"  {'TOTAL':<12} {total_runs:>6} {total_input:>10,} {total_output:>10,} ${total_cost:>9.4f}")

    # Per-query averages
    if total_runs > 0:
        print(f"\n{'PER-QUERY AVERAGES':^60}")
        print("=" * 60)
        print(f"  Avg input tokens:   {total_input / total_runs:,.0f}")
        print(f"  Avg output tokens:  {total_output / total_runs:,.0f}")
        print(f"  Avg total tokens:   {total_tokens / total_runs:,.0f}")
        print(f"  Avg cost/query:     ${total_cost / total_runs:.4f}")
        print(f"  Avg latency:        {avg_latency / 1000:.1f}s")

    # CSV export
    if export_csv:
        csv_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "data",
            f"langsmith_usage_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
        )
        os.makedirs(os.path.dirname(csv_path), exist_ok=True)

        import csv
        with open(csv_path, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=rows[0].keys() if rows else [])
            writer.writeheader()
            writer.writerows(rows)

        print(f"\nCSV exported to: {csv_path}")

    # Summary for COST_ANALYSIS.md
    print(f"\n{'COPY FOR COST_ANALYSIS.md':^60}")
    print("=" * 60)
    print(f"| Metric | Value |")
    print(f"|--------|-------|")
    print(f"| Total API calls | {total_runs:,} |")
    print(f"| Total input tokens | {total_input:,} |")
    print(f"| Total output tokens | {total_output:,} |")
    print(f"| Total tokens | {total_tokens:,} |")
    print(f"| Avg tokens/query | {total_tokens // max(total_runs, 1):,} |")
    print(f"| Avg latency | {avg_latency / 1000:.1f}s |")
    print(f"| **Total dev cost** | **${total_cost:.2f}** |")


if __name__ == "__main__":
    main()
