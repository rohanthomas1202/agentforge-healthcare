"""Symptom lookup tool — maps symptoms to possible medical conditions.

Takes a list of patient symptoms and returns possible conditions with
ICD-10 codes, urgency levels, and clinical recommendations.
"""

from typing import List

from langchain_core.tools import tool

from app.tools.symptom_conditions_db import lookup_symptoms


@tool
async def symptom_lookup(symptoms: List[str]) -> str:
    """Look up possible medical conditions based on reported symptoms.

    This tool maps symptoms to known conditions, providing ICD-10 codes,
    urgency levels, and clinical guidance. Use this when a user describes
    symptoms and wants to understand what conditions might be relevant.

    IMPORTANT: This tool provides educational information only and should
    NEVER be used as a substitute for professional medical diagnosis.

    Args:
        symptoms: List of symptoms the patient is experiencing (e.g., ["chest pain", "shortness of breath", "fatigue"]).
    """
    try:
        if not symptoms:
            return "No symptoms provided. Please describe the symptoms you'd like to look up."

        results = lookup_symptoms(symptoms)
        return _format_results(results)

    except Exception as e:
        return f"Error looking up symptoms: {str(e)}"


def _format_results(results: list[dict]) -> str:
    """Format symptom lookup results into a readable string."""
    lines = []
    lines.append("=== SYMPTOM ANALYSIS ===")

    # Determine overall urgency
    urgency_order = {"emergency": 0, "urgent": 1, "soon": 2, "routine": 3, "unknown": 4}
    highest_urgency = min(
        (r["highest_urgency"] for r in results),
        key=lambda u: urgency_order.get(u, 99),
    )

    if highest_urgency == "emergency":
        lines.append("\n🚨 EMERGENCY CONDITIONS POSSIBLE — Some of these symptoms may indicate")
        lines.append("a life-threatening condition. If experiencing severe symptoms, call 911")
        lines.append("or go to the nearest emergency room IMMEDIATELY.")
    elif highest_urgency == "urgent":
        lines.append("\n⚠ URGENT: Some possible conditions require prompt medical evaluation.")
        lines.append("Please see a healthcare provider within 24 hours.")

    for result in results:
        symptom = result["symptom"]
        lines.append(f"\n{'='*50}")
        lines.append(f"SYMPTOM: {symptom.upper()}")
        lines.append(f"{'='*50}")

        if not result["matched"]:
            lines.append(f"  This symptom was not found in our database.")
            lines.append(f"  Please consult a healthcare provider for proper evaluation.")
            continue

        conditions = result["conditions"]
        lines.append(f"Possible conditions ({len(conditions)}):\n")

        for idx, condition in enumerate(conditions, 1):
            urgency = condition["urgency"]
            icon = {
                "emergency": "🚨",
                "urgent": "⚠",
                "soon": "📋",
                "routine": "ℹ",
            }.get(urgency, "•")

            likelihood = condition.get("likelihood", "")
            likelihood_label = {
                "must_rule_out": " [MUST RULE OUT]",
                "very_common": " [Very Common]",
                "common": " [Common]",
                "less_common": " [Less Common]",
            }.get(likelihood, "")

            lines.append(f"  {idx}. {icon} {condition['condition']}{likelihood_label}")
            lines.append(f"     ICD-10: {condition['icd10']}")
            lines.append(f"     Urgency: {urgency.upper()}")
            lines.append(f"     Key indicators: {condition['red_flags']}")
            lines.append(f"     Clinical note: {condition['notes']}")
            lines.append("")

    # Always add disclaimer
    lines.append("=" * 50)
    lines.append("⚕ MEDICAL DISCLAIMER")
    lines.append("=" * 50)
    lines.append("This information is for EDUCATIONAL PURPOSES ONLY and does NOT")
    lines.append("constitute a medical diagnosis. Conditions are listed by clinical")
    lines.append("likelihood and do not represent a definitive diagnosis.")
    lines.append("")
    lines.append("ALWAYS consult a qualified healthcare provider for:")
    lines.append("  • Proper evaluation and diagnosis")
    lines.append("  • Appropriate testing and imaging")
    lines.append("  • Treatment recommendations")
    lines.append("")
    lines.append("If you are experiencing a medical emergency, call 911 immediately.")

    return "\n".join(lines)
