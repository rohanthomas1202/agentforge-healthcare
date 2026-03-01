"""Drug recall monitor — queries openFDA for active drug recalls and enforcement actions.

Uses the openFDA Drug Enforcement API to check if medications have active
or recent recalls. Optionally cross-references with a patient's current
medications from OpenEMR to provide a patient-specific recall report.
"""

import logging
import re
from typing import Optional

import httpx
from langchain_core.tools import tool

from app.tools.fhir_helpers import (
    extract_patient_name,
    find_patient,
    get_patient_medications,
)
from app.tools.retry_utils import RetryableHTTPError, api_retry

logger = logging.getLogger(__name__)

OPENFDA_ENFORCEMENT_URL = "https://api.fda.gov/drug/enforcement.json"
FDA_TIMEOUT = 15.0
MAX_RESULTS = 5


def _sanitize_drug_name(name: str) -> str:
    """Normalize drug name: strip dosage, remove Lucene special characters."""
    name = re.sub(
        r"\s*\d+\s*(mg|mcg|ml|units?|%)\s*$", "", name, flags=re.IGNORECASE
    )
    # Remove Lucene/openFDA query syntax characters to prevent injection
    name = re.sub(r'[+\-&|!(){}[\]^"~*?:\\/]', " ", name)
    name = re.sub(r"\b(AND|OR|NOT)\b", " ", name, flags=re.IGNORECASE)
    return " ".join(name.split()).strip()


@tool
async def drug_recall_check(
    drug_name: Optional[str] = None,
    patient_identifier: Optional[str] = None,
) -> str:
    """Check for active FDA drug recalls and enforcement actions.

    Use this tool when:
    - A user asks if a medication has been recalled
    - A user wants to check recall status for a specific drug
    - A provider wants to check if any of a patient's medications have active recalls
    - A user asks about drug safety alerts or FDA enforcement actions

    Args:
        drug_name: Optional specific drug name to check for recalls.
        patient_identifier: Optional patient name or ID. If provided, checks all of
            the patient's current medications for active recalls.
    """
    try:
        if patient_identifier:
            return await _patient_recall_check(patient_identifier, drug_name)

        if not drug_name:
            return (
                "Please provide either a drug name or a patient identifier "
                "to check for recalls."
            )

        recalls = await _search_recalls(drug_name)
        return _format_recall_report(drug_name, recalls)

    except Exception as e:
        logger.error("Error checking drug recalls: %s", e, exc_info=True)
        return "Error checking drug recalls. Please try again or contact support."


async def _patient_recall_check(
    patient_identifier: str, extra_drug: Optional[str]
) -> str:
    """Check all of a patient's medications for recalls."""
    patient = await find_patient(patient_identifier)
    if not patient:
        return (
            f"No patient found matching '{patient_identifier}'. "
            "Please check the name or ID and try again."
        )

    patient_id = patient.get("id")
    patient_name = extract_patient_name(patient)
    medications = list(await get_patient_medications(patient_id))

    # Add extra drug if provided and not already in the list
    if extra_drug:
        norm_extra = _sanitize_drug_name(extra_drug).lower()
        if not any(_sanitize_drug_name(m).lower() == norm_extra for m in medications):
            medications.append(extra_drug)

    if not medications:
        return (
            f"=== DRUG RECALL CHECK: {patient_name} ===\n\n"
            "No medications found in patient's record.\n"
            "Provide a specific drug name to check for recalls."
        )

    # Check each medication for recalls
    all_results: dict[str, list[dict]] = {}
    for med in medications:
        clean_name = _sanitize_drug_name(med)
        recalls = await _search_recalls(clean_name)
        all_results[med] = recalls

    return _format_patient_recall_report(patient_name, medications, all_results)


async def _search_recalls(drug_name: str) -> list[dict]:
    """Query openFDA Drug Enforcement API for recalls (with retry)."""
    clean_name = _sanitize_drug_name(drug_name)
    if not clean_name:
        return []

    try:
        return await _search_recalls_inner(clean_name)
    except Exception as e:
        logger.warning("openFDA Enforcement API failed after retries for %s: %s", drug_name, e)
        return []


@api_retry
async def _search_recalls_inner(clean_name: str) -> list[dict]:
    """Inner fetch with retry — timeouts and 5xx are retried."""
    async with httpx.AsyncClient(timeout=FDA_TIMEOUT) as client:
        quoted_name = f'"{clean_name}"'
        resp = await client.get(
            OPENFDA_ENFORCEMENT_URL,
            params={
                "search": (
                    f"openfda.generic_name:{quoted_name}"
                    f"+OR+openfda.brand_name:{quoted_name}"
                ),
                "sort": "report_date:desc",
                "limit": str(MAX_RESULTS),
            },
        )
        if resp.status_code == 404:
            return []
        if resp.status_code >= 500:
            raise RetryableHTTPError(f"openFDA returned {resp.status_code}")
        resp.raise_for_status()
        data = resp.json()

    results = data.get("results", [])
    recalls: list[dict] = []
    for r in results[:MAX_RESULTS]:
        recalls.append({
            "recall_number": r.get("recall_number", "Unknown"),
            "status": r.get("status", "Unknown"),
            "classification": r.get("classification", "Unknown"),
            "reason": r.get("reason_for_recall", "Not specified"),
            "product_description": (
                r.get("product_description", "")[:300]
            ),
            "recalling_firm": r.get("recalling_firm", "Unknown"),
            "report_date": r.get("report_date", ""),
            "city": r.get("city", ""),
            "state": r.get("state", ""),
            "voluntary": r.get("voluntary_mandated", ""),
            "distribution": (
                r.get("distribution_pattern", "")[:200]
            ),
        })
    return recalls


def _format_recall_report(drug_name: str, recalls: list[dict]) -> str:
    """Format recall results for a single drug."""
    lines: list[str] = []
    lines.append(f"=== FDA DRUG RECALL CHECK: {drug_name.upper()} ===")

    if not recalls:
        lines.append(
            f"\nNo active recalls or recent enforcement actions found "
            f"for '{drug_name}'."
        )
        lines.append(
            "This does not guarantee no recalls exist — only that none were "
            "found in the FDA enforcement database for this drug name."
        )
        return "\n".join(lines)

    lines.append(f"\nFound {len(recalls)} recall/enforcement record(s):\n")

    for idx, recall in enumerate(recalls, 1):
        classification = recall["classification"]
        severity_icon = {
            "Class I": "MOST SERIOUS",
            "Class II": "MODERATE",
            "Class III": "LEAST SERIOUS",
        }.get(classification, "")

        lines.append(f"--- Recall {idx}: {recall['recall_number']} ---")
        lines.append(
            f"  Classification: {classification}"
            + (f" ({severity_icon})" if severity_icon else "")
        )
        lines.append(f"  Status: {recall['status']}")
        lines.append(f"  Reason: {recall['reason']}")
        if recall.get("product_description"):
            lines.append(f"  Product: {recall['product_description']}")
        lines.append(f"  Recalling Firm: {recall['recalling_firm']}")
        if recall.get("report_date"):
            date = recall["report_date"]
            formatted = f"{date[:4]}-{date[4:6]}-{date[6:8]}" if len(date) == 8 else date
            lines.append(f"  Report Date: {formatted}")
        if recall.get("distribution"):
            lines.append(f"  Distribution: {recall['distribution']}")
        if recall.get("voluntary"):
            lines.append(f"  Type: {recall['voluntary']}")
        lines.append("")

    lines.append("--- RECALL CLASSIFICATION GUIDE ---")
    lines.append(
        "  Class I: Dangerous or defective products that could cause "
        "serious health problems or death."
    )
    lines.append(
        "  Class II: Products that might cause a temporary health problem "
        "or pose a slight threat of a serious nature."
    )
    lines.append(
        "  Class III: Products unlikely to cause adverse health reaction "
        "but violate FDA regulations."
    )
    lines.append(
        "\nConsult your pharmacist or healthcare provider about "
        "any active recalls affecting your medications."
    )

    return "\n".join(lines)


def _format_patient_recall_report(
    patient_name: str,
    medications: list[str],
    results: dict[str, list[dict]],
) -> str:
    """Format a patient-wide recall check report."""
    lines: list[str] = []
    lines.append(f"=== DRUG RECALL CHECK: {patient_name.upper()} ===")
    lines.append(
        f"Medications checked ({len(medications)}): {', '.join(medications)}"
    )

    # Separate meds with and without recalls
    meds_with_recalls = {
        med: recalls for med, recalls in results.items() if recalls
    }
    meds_clear = [med for med in medications if not results.get(med)]

    if not meds_with_recalls:
        lines.append(
            "\nNo active recalls or enforcement actions found for any of "
            f"{patient_name}'s medications."
        )
        lines.append("\nAll medications checked:")
        for med in meds_clear:
            lines.append(f"  - {med}: No recalls found")
        return "\n".join(lines)

    # Medications with recalls
    lines.append(
        f"\nALERT: {len(meds_with_recalls)} medication(s) have recall records:\n"
    )
    for med, recalls in meds_with_recalls.items():
        lines.append(f"  {med}: {len(recalls)} recall record(s)")
        for recall in recalls:
            classification = recall["classification"]
            lines.append(
                f"    - {recall['recall_number']} ({classification}): "
                f"{recall['reason'][:100]}"
            )
        lines.append("")

    # Clear medications
    if meds_clear:
        lines.append(f"Medications with no recalls ({len(meds_clear)}):")
        for med in meds_clear:
            lines.append(f"  - {med}: No recalls found")

    lines.append(
        "\nIMPORTANT: Discuss any recall findings with the patient's "
        "pharmacist to determine if their specific product lot is affected."
    )

    return "\n".join(lines)
