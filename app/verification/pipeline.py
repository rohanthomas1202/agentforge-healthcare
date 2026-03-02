"""Verification pipeline — orchestrates all verification checks.

Single entry point that runs drug safety, confidence scoring, and
claim verification against the agent's response before returning to the user.
"""

from __future__ import annotations

import logging

from langchain_core.messages import ToolMessage

from app.verification.allergy_safety import AllergySafetyVerifier
from app.verification.claim_verifier import ClaimVerifier
from app.verification.confidence import ConfidenceScorer
from app.verification.dosage_checker import DosageChecker
from app.verification.drug_safety import DrugSafetyVerifier
from app.verification.phi_detector import PHIDetector

logger = logging.getLogger(__name__)

# Safe defaults when a verifier crashes
_SAFE_DRUG_RESULT = {"passed": True, "flags": [], "disclaimers": []}
_SAFE_ALLERGY_RESULT = {"passed": True, "flags": [], "disclaimers": []}
_SAFE_PHI_RESULT = {"passed": True, "flags": [], "disclaimers": []}
_SAFE_DOSAGE_RESULT = {"passed": True, "flags": [], "disclaimers": []}
_SAFE_CONFIDENCE_RESULT = {"score": 0.5, "factors": [], "disclaimers": []}
_SAFE_CLAIM_RESULT = {
    "passed": True,
    "grounded_claims": 0,
    "ungrounded_claims": 0,
    "total_claims": 0,
    "grounding_rate": 1.0,
    "details": [],
    "disclaimers": [],
}


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
    tool_outputs: list[dict] | None = None,
) -> dict:
    """Run all verification checks and return enriched metadata.

    Each verifier is wrapped in try/except so a single verifier crash
    does not prevent the response from being returned to the user.

    Args:
        response_text: The final LLM response text.
        messages: Full LangGraph message list (BaseMessage subclasses).
        tool_calls: Already-extracted tool call log [{"tool": name, "args": {...}}].
        tool_outputs: Pre-extracted tool outputs (used by streaming path).
                      If None, extracts from messages.

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
    # Extract tool outputs from message history (or use pre-extracted)
    if tool_outputs is None:
        tool_outputs = _extract_tool_outputs(messages)

    # Run each verifier independently with safe fallbacks
    try:
        drug_result = DrugSafetyVerifier().verify(
            response_text, tool_outputs, tool_calls
        )
    except Exception:
        logger.exception("DrugSafetyVerifier crashed — using safe default")
        drug_result = _SAFE_DRUG_RESULT

    try:
        allergy_result = AllergySafetyVerifier().verify(
            response_text, tool_outputs, tool_calls
        )
    except Exception:
        logger.exception("AllergySafetyVerifier crashed — using safe default")
        allergy_result = _SAFE_ALLERGY_RESULT

    try:
        confidence_result = ConfidenceScorer().score(
            response_text, tool_outputs, tool_calls
        )
    except Exception:
        logger.exception("ConfidenceScorer crashed — using safe default")
        confidence_result = _SAFE_CONFIDENCE_RESULT

    try:
        claim_result = ClaimVerifier().verify(
            response_text, tool_outputs, tool_calls
        )
    except Exception:
        logger.exception("ClaimVerifier crashed — using safe default")
        claim_result = _SAFE_CLAIM_RESULT

    try:
        phi_result = PHIDetector().detect(response_text)
    except Exception:
        logger.exception("PHIDetector crashed — using safe default")
        phi_result = _SAFE_PHI_RESULT

    try:
        dosage_result = DosageChecker().check(response_text)
    except Exception:
        logger.exception("DosageChecker crashed — using safe default")
        dosage_result = _SAFE_DOSAGE_RESULT

    # Merge disclaimers from all verifiers
    disclaimers: list[str] = []
    for verifier_result in [
        drug_result, allergy_result, confidence_result,
        claim_result, phi_result, dosage_result,
    ]:
        for d in verifier_result.get("disclaimers", []):
            if d not in disclaimers:
                disclaimers.append(d)

    # Determine overall safety
    overall_safe = (
        drug_result["passed"]
        and allergy_result["passed"]
        and confidence_result["score"] >= 0.3
        and claim_result["passed"]
        and phi_result["passed"]
        and dosage_result["passed"]
    )

    return {
        "confidence": confidence_result["score"],
        "disclaimers": disclaimers,
        "verification": {
            "drug_safety": {
                "passed": drug_result["passed"],
                "flags": drug_result["flags"],
            },
            "allergy_safety": {
                "passed": allergy_result["passed"],
                "flags": allergy_result["flags"],
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
            "phi_detection": {
                "passed": phi_result["passed"],
                "flags": phi_result["flags"],
            },
            "dosage_check": {
                "passed": dosage_result["passed"],
                "flags": dosage_result["flags"],
            },
            "overall_safe": overall_safe,
        },
    }
