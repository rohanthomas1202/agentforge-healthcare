"""Verification pipeline — orchestrates all verification checks.

Single entry point that runs drug safety, confidence scoring, and
claim verification against the agent's response before returning to the user.
"""

from langchain_core.messages import ToolMessage

from app.verification.drug_safety import DrugSafetyVerifier
from app.verification.confidence import ConfidenceScorer
from app.verification.claim_verifier import ClaimVerifier


def _extract_tool_outputs(messages: list) -> list[dict]:
    """Extract tool name and output text from ToolMessage objects."""
    outputs = []
    for msg in messages:
        if isinstance(msg, ToolMessage):
            outputs.append({
                "tool_name": getattr(msg, "name", "unknown"),
                "output": msg.content if isinstance(msg.content, str) else str(msg.content),
                "tool_call_id": getattr(msg, "tool_call_id", ""),
            })
    return outputs


def run_verification_pipeline(
    response_text: str,
    messages: list,
    tool_calls: list[dict],
) -> dict:
    """Run all verification checks and return enriched metadata.

    Args:
        response_text: The final LLM response text.
        messages: Full LangGraph message list (BaseMessage subclasses).
        tool_calls: Already-extracted tool call log [{"tool": name, "args": {...}}].

    Returns:
        {
            "confidence": float,
            "disclaimers": list[str],
            "verification": {
                "drug_safety": {...},
                "confidence_scoring": {...},
                "claim_verification": {...},
                "overall_safe": bool,
            },
        }
    """
    # Extract tool outputs from message history
    tool_outputs = _extract_tool_outputs(messages)

    # Run all three verifiers
    drug_result = DrugSafetyVerifier().verify(
        response_text, tool_outputs, tool_calls
    )
    confidence_result = ConfidenceScorer().score(
        response_text, tool_outputs, tool_calls
    )
    claim_result = ClaimVerifier().verify(
        response_text, tool_outputs, tool_calls
    )

    # Merge disclaimers from all verifiers
    disclaimers: list[str] = []
    for d in drug_result.get("disclaimers", []):
        if d not in disclaimers:
            disclaimers.append(d)
    for d in confidence_result.get("disclaimers", []):
        if d not in disclaimers:
            disclaimers.append(d)
    for d in claim_result.get("disclaimers", []):
        if d not in disclaimers:
            disclaimers.append(d)

    # Determine overall safety
    overall_safe = (
        drug_result["passed"]
        and confidence_result["score"] >= 0.3
        and claim_result["passed"]
    )

    return {
        "confidence": confidence_result["score"],
        "disclaimers": disclaimers,
        "verification": {
            "drug_safety": {
                "passed": drug_result["passed"],
                "flags": drug_result["flags"],
            },
            "confidence_scoring": {
                "score": confidence_result["score"],
                "factors": confidence_result["factors"],
            },
            "claim_verification": {
                "passed": claim_result["passed"],
                "grounded_claims": claim_result["grounded_claims"],
                "ungrounded_claims": claim_result["ungrounded_claims"],
                "total_claims": claim_result["total_claims"],
                "grounding_rate": claim_result["grounding_rate"],
                "details": claim_result["details"],
            },
            "overall_safe": overall_safe,
        },
    }
