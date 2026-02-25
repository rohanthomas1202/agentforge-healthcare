"""Shared assertion helpers for the evaluation framework."""

from __future__ import annotations


def assert_tools_used(result: dict, expected_tools: list[str], allow_extra: bool = False) -> list[str]:
    """Validate that the expected tools were called.

    Returns a list of failure messages (empty = pass).
    """
    failures = []
    actual_tools = [tc["tool"] for tc in result.get("tool_calls", [])]

    for tool in expected_tools:
        if tool not in actual_tools:
            failures.append(f"Expected tool '{tool}' not called. Actual: {actual_tools}")

    if not allow_extra and expected_tools:
        extra = set(actual_tools) - set(expected_tools)
        if extra:
            failures.append(f"Unexpected extra tools called: {extra}")

    return failures


def assert_response_contains(result: dict, patterns: list[str]) -> list[str]:
    """Check that the response contains ALL of the given patterns (case-insensitive).

    Returns a list of failure messages.
    """
    failures = []
    response = result.get("response", "").lower()

    for pattern in patterns:
        if pattern.lower() not in response:
            failures.append(f"Response missing required text: '{pattern}'")

    return failures


def assert_response_contains_any(result: dict, patterns: list[str]) -> list[str]:
    """Check that the response contains AT LEAST ONE of the given patterns (case-insensitive).

    Returns a list of failure messages.
    """
    if not patterns:
        return []

    response = result.get("response", "").lower()

    for pattern in patterns:
        if pattern.lower() in response:
            return []  # At least one found — pass

    return [f"Response missing all of: {patterns}"]


def assert_response_not_contains(result: dict, patterns: list[str]) -> list[str]:
    """Check that the response does NOT contain any of the given patterns.

    Returns a list of failure messages.
    """
    failures = []
    response = result.get("response", "").lower()

    for pattern in patterns:
        if pattern.lower() in response:
            failures.append(f"Response contains forbidden text: '{pattern}'")

    return failures


def assert_confidence_range(result: dict, min_val: float, max_val: float) -> list[str]:
    """Validate confidence is within the expected range.

    Returns a list of failure messages.
    """
    confidence = result.get("confidence")
    if confidence is None:
        return []  # No confidence score — skip check

    failures = []
    if confidence < min_val:
        failures.append(f"Confidence {confidence:.2f} below minimum {min_val}")
    if confidence > max_val:
        failures.append(f"Confidence {confidence:.2f} above maximum {max_val}")

    return failures


def assert_verification_safe(result: dict) -> list[str]:
    """Check that the verification pipeline marked the response as safe.

    Returns a list of failure messages.
    """
    verification = result.get("verification", {})
    overall_safe = verification.get("overall_safe")

    if overall_safe is None:
        return []  # No verification data — skip

    if not overall_safe:
        return ["Verification marked response as UNSAFE"]

    return []


def assert_latency(elapsed: float, max_seconds: float) -> list[str]:
    """Check that the response time is within acceptable bounds.

    Returns a list of failure messages.
    """
    if elapsed > max_seconds:
        return [f"Latency {elapsed:.1f}s exceeds max {max_seconds}s"]
    return []


def assert_has_disclaimer(result: dict) -> list[str]:
    """Check that at least one disclaimer is present.

    Returns a list of failure messages.
    """
    disclaimers = result.get("disclaimers", [])
    if not disclaimers:
        return ["No disclaimers present in response"]
    return []


def run_all_assertions(case: dict, result: dict, elapsed: float) -> list[str]:
    """Run all applicable assertions for a test case.

    Returns a list of all failure messages (empty = all passed).
    """
    failures = []

    # Tool selection
    expected_tools = case.get("expected_tools", [])
    if expected_tools:
        failures.extend(assert_tools_used(
            result, expected_tools, case.get("allow_extra_tools", False)
        ))

    # Response content — must contain all
    must_contain = case.get("response_must_contain", [])
    if must_contain:
        failures.extend(assert_response_contains(result, must_contain))

    # Response content — must contain any
    must_contain_any = case.get("response_must_contain_any", [])
    if must_contain_any:
        failures.extend(assert_response_contains_any(result, must_contain_any))

    # Second "any" group (for cases needing two independent OR checks)
    must_contain_any2 = case.get("response_must_contain_any2", [])
    if must_contain_any2:
        failures.extend(assert_response_contains_any(result, must_contain_any2))

    # Response content — must NOT contain
    must_not_contain = case.get("response_must_not_contain", [])
    if must_not_contain:
        failures.extend(assert_response_not_contains(result, must_not_contain))

    # Confidence range
    min_conf = case.get("min_confidence")
    max_conf = case.get("max_confidence")
    if min_conf is not None and max_conf is not None:
        failures.extend(assert_confidence_range(result, min_conf, max_conf))

    # Verification safety
    if case.get("verification_safe") is True:
        failures.extend(assert_verification_safe(result))

    # Latency
    max_latency = case.get("max_latency_seconds", 15)
    failures.extend(assert_latency(elapsed, max_latency))

    return failures
