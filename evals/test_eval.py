"""Data-driven evaluation test suite for AgentForge Healthcare.

Loads 57 test cases from test_cases.json and runs each against the
live API, validating tool selection, response content, confidence,
verification safety, and latency.

Run: cd agentforge-healthcare && ./venv/Scripts/python.exe -m pytest evals/ -v --tb=short
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from evals.conftest import send_chat
from evals.helpers import run_all_assertions

# Load test cases from JSON
CASES_PATH = Path(__file__).parent / "test_cases.json"
with open(CASES_PATH) as f:
    TEST_CASES = json.load(f)


@pytest.mark.parametrize("case", TEST_CASES, ids=lambda c: c["id"])
def test_eval(case: dict, api_url: str, result_collector: list[dict]) -> None:
    """Run a single evaluation test case against the live API."""
    # Send the query
    result, elapsed = send_chat(api_url, case["query"])

    # Run all assertions
    failures = run_all_assertions(case, result, elapsed)

    # Collect result for report
    record = {
        "id": case["id"],
        "category": case["category"],
        "description": case["description"],
        "query": case["query"],
        "passed": len(failures) == 0,
        "failures": failures,
        "latency": elapsed,
        "confidence": result.get("confidence"),
        "tool_calls": result.get("tool_calls", []),
        "response_length": len(result.get("response", "")),
        "verification_safe": result.get("verification", {}).get("overall_safe"),
    }
    result_collector.append(record)

    # Assert
    if failures:
        failure_msg = f"\n[{case['id']}] {case['description']}\n"
        failure_msg += f"Query: {case['query']}\n"
        failure_msg += f"Latency: {elapsed:.1f}s | Confidence: {result.get('confidence')}\n"
        failure_msg += f"Tools: {[tc['tool'] for tc in result.get('tool_calls', [])]}\n"
        failure_msg += "Failures:\n"
        for f in failures:
            failure_msg += f"  - {f}\n"
        failure_msg += f"Response (first 300 chars): {result.get('response', '')[:300]}"
        pytest.fail(failure_msg)
