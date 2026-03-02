"""FDA drug safety tool — queries openFDA for drug safety intelligence.

Fetches boxed warnings, contraindications, drug interactions, adverse
reactions from FDA-approved labels, plus top reported adverse events from
the FDA Adverse Event Reporting System (FAERS). Optionally cross-references
with a patient's current medications from OpenEMR.
"""

import os
import re
from datetime import date
from typing import Optional

import httpx
from langchain_core.tools import tool

from app.agent.input_sanitizer import sanitize_drug_name, sanitize_patient_name
from app.fhir_client import fhir_client
from app.tools.fhir_helpers import extract_medication_request
from app.tools.retry_utils import RetryableHTTPError, api_retry
import logging

logger = logging.getLogger(__name__)

OPENFDA_LABEL_URL = "https://api.fda.gov/drug/label.json"
OPENFDA_EVENT_URL = "https://api.fda.gov/drug/event.json"
MAX_SECTION_CHARS = 500
FDA_TIMEOUT = 15.0


@tool
async def fda_drug_safety(
    drug_name: str,
    patient_identifier: Optional[str] = None,
    store_in_ehr: bool = False,
) -> str:
    """Look up FDA safety information for a medication including boxed warnings,
    contraindications, drug interactions, and adverse reactions.

    Use this tool when:
    - A user asks about FDA warnings or safety data for a drug
    - A user wants to know side effects or adverse reactions for a medication
    - A user asks about contraindications or boxed warnings
    - You need to check if a patient's medications have relevant FDA safety alerts

    Args:
        drug_name: Generic medication name to look up (e.g., "warfarin", "metformin").
        patient_identifier: Optional patient name or ID. If provided, cross-references
            FDA drug interaction data with the patient's current medications from OpenEMR.
        store_in_ehr: If True and patient_identifier is provided, stores the safety
            report as a clinical note in the patient's OpenEMR record.
    """
    try:
        drug_name = sanitize_drug_name(drug_name)
        if patient_identifier:
            patient_identifier = sanitize_patient_name(patient_identifier)

        # Step 1: Fetch FDA label data
        label_data = await _fetch_fda_label(drug_name)

        # Step 2: Fetch adverse event data
        adverse_events = await _fetch_adverse_events(drug_name)

        # Step 3: Optionally cross-reference with patient medications
        patient_meds: list[str] = []
        patient_name: Optional[str] = None
        patient_id: Optional[str] = None
        cross_ref_results: list[str] = []
        if patient_identifier:
            logger.info("Patient data accessed", extra={"operation": "patient_data_access", "patient": patient_identifier, "tool": "fda_drug_safety"})
            patient_meds, patient_name, patient_id = await _fetch_patient_meds(
                patient_identifier
            )
            if patient_meds and label_data.get("found"):
                cross_ref_results = _cross_reference_meds(label_data, patient_meds)

        # Step 4: Optionally store in EHR
        ehr_note = ""
        if store_in_ehr and patient_id:
            ehr_note = await _store_safety_report_in_ehr(
                patient_id, drug_name, label_data
            )

        # Step 5: Format and return
        return _format_safety_report(
            drug_name,
            label_data,
            adverse_events,
            patient_name,
            patient_meds,
            cross_ref_results,
            ehr_note,
        )

    except Exception as e:
        return f"Error retrieving FDA safety data for '{drug_name}': {str(e)}"


# ── Private helpers ──────────────────────────────────────────────────────────


def _sanitize_fda_query(name: str) -> str:
    """Sanitize a drug name for use in openFDA Lucene queries."""
    # Strip dosage suffixes
    name = re.sub(
        r"\s*\d+\s*(mg|mcg|ml|units?|%)\s*$", "", name, flags=re.IGNORECASE
    )
    # Remove Lucene special characters to prevent query injection
    name = re.sub(r'[+\-&|!(){}[\]^"~*?:\\/]', " ", name)
    name = re.sub(r"\b(AND|OR|NOT)\b", " ", name, flags=re.IGNORECASE)
    return " ".join(name.split()).strip()


def _strip_html(text: str) -> str:
    """Remove HTML tags from FDA label text."""
    return re.sub(r"<[^>]+>", "", text).strip()


def _truncate(text: str, max_chars: int = MAX_SECTION_CHARS) -> str:
    """Truncate text to max_chars, appending '...' if truncated."""
    if len(text) <= max_chars:
        return text
    return text[:max_chars].rsplit(" ", 1)[0] + "..."


async def _fetch_fda_label(drug_name: str) -> dict:
    """Fetch drug label safety data from openFDA (with retry on transient failures)."""
    try:
        return await _fetch_fda_label_inner(drug_name)
    except Exception as e:
        logger.warning("FDA label fetch failed after retries: %s", e)
        return {"found": False, "error": "FDA API unavailable after retries"}


@api_retry
async def _fetch_fda_label_inner(drug_name: str) -> dict:
    """Inner fetch with retry — timeouts and 5xx are retried."""
    async with httpx.AsyncClient(timeout=FDA_TIMEOUT) as client:
        resp = await client.get(
            OPENFDA_LABEL_URL,
            params={
                "search": f"openfda.generic_name:{drug_name}",
                "limit": "1",
            },
        )
        if resp.status_code == 404:
            return {"found": False}
        if resp.status_code >= 500:
            raise RetryableHTTPError(f"FDA API returned {resp.status_code}")
        resp.raise_for_status()
        data = resp.json()

    results = data.get("results", [])
    if not results:
        return {"found": False}

    label = results[0]

    def _extract_field(field_name: str) -> str:
        raw = label.get(field_name, [])
        if isinstance(raw, list):
            text = "\n".join(raw)
        else:
            text = str(raw)
        return _truncate(_strip_html(text))

    warnings_text = _extract_field("warnings_and_cautions")
    if not warnings_text:
        warnings_text = _extract_field("warnings")

    return {
        "found": True,
        "boxed_warning": _extract_field("boxed_warning"),
        "contraindications": _extract_field("contraindications"),
        "warnings": warnings_text,
        "drug_interactions": _extract_field("drug_interactions"),
        "adverse_reactions": _extract_field("adverse_reactions"),
    }


async def _fetch_adverse_events(drug_name: str) -> list[dict]:
    """Fetch top adverse events from FDA FAERS database (with retry)."""
    try:
        return await _fetch_adverse_events_inner(drug_name)
    except Exception as e:
        logger.warning("FDA adverse events fetch failed after retries: %s", e)
        return []


@api_retry
async def _fetch_adverse_events_inner(drug_name: str) -> list[dict]:
    """Inner fetch with retry — timeouts and 5xx are retried."""
    async with httpx.AsyncClient(timeout=FDA_TIMEOUT) as client:
        resp = await client.get(
            OPENFDA_EVENT_URL,
            params={
                "search": f"patient.drug.openfda.generic_name:{drug_name.upper()}",
                "count": "patient.reaction.reactionmeddrapt.exact",
            },
        )
        if resp.status_code == 404:
            return []
        if resp.status_code >= 500:
            raise RetryableHTTPError(f"FDA FAERS API returned {resp.status_code}")
        resp.raise_for_status()
        data = resp.json()

    results = data.get("results", [])
    return [{"reaction": r["term"], "count": r["count"]} for r in results[:10]]


async def _fetch_patient_meds(
    identifier: str,
) -> tuple[list[str], Optional[str], Optional[str]]:
    """Fetch a patient's current medications from OpenEMR."""
    try:
        # Search for patient (same pattern as drug_interaction.py)
        parts = identifier.strip().split()
        if len(parts) >= 2:
            patients = await fhir_client.search(
                "Patient", {"given": parts[0], "family": parts[-1]}
            )
        else:
            patients = await fhir_client.search("Patient", {"name": identifier})
        if not patients:
            return [], None, None

        patient = patients[0]
        patient_id = patient.get("id")

        # Extract display name
        names = patient.get("name", [{}])
        given = " ".join(names[0].get("given", []))
        family = names[0].get("family", "")
        patient_name = f"{given} {family}".strip()

        # Get their medications
        med_requests = await fhir_client.search(
            "MedicationRequest", {"patient": patient_id}
        )
        meds = []
        for mr in med_requests:
            med_data = extract_medication_request(mr)
            if med_data.get("medication") and med_data["medication"] != "Unknown":
                meds.append(med_data["medication"])

        return meds, patient_name, patient_id
    except Exception:
        return [], None, None


def _cross_reference_meds(label_data: dict, patient_meds: list[str]) -> list[str]:
    """Check if patient's current meds appear in FDA drug interaction text."""
    interaction_text = label_data.get("drug_interactions", "").lower()
    if not interaction_text:
        return []

    flagged = []
    for med in patient_meds:
        # Extract base drug name (remove dosage like "500mg", "20mg")
        base_name = re.sub(
            r"\s*\d+\s*(mg|mcg|ml|units?|%)\s*$", "", med, flags=re.IGNORECASE
        )
        if base_name.lower() in interaction_text:
            flagged.append(med)
    return flagged


async def _store_safety_report_in_ehr(
    patient_id: str, drug_name: str, label_data: dict
) -> str:
    """Store safety report in OpenEMR as encounter + SOAP note."""
    if os.getenv("USE_MOCK_DATA", "").lower() in ("true", "1", "yes"):
        return "(EHR storage skipped — mock mode)"

    try:
        from app.fhir_client import standard_api_client

        if standard_api_client is None:
            return "(EHR storage not available — Standard API client not configured)"

        # Create encounter
        encounter = await standard_api_client.post(
            f"patient/{patient_id}/encounter",
            {
                "date": date.today().isoformat(),
                "reason": f"FDA Drug Safety Review: {drug_name}",
                "facility_id": "1",
                "class_code": "AMB",
            },
        )
        encounter_id = encounter.get("uuid", encounter.get("id"))
        if not encounter_id:
            return "(EHR storage failed — could not create encounter)"

        # Build SOAP note
        subjective = f"FDA safety review requested for {drug_name}."
        objective = label_data.get("boxed_warning", "No boxed warning.")
        assessment = label_data.get("contraindications", "See FDA label.")
        plan = "Review FDA safety data. Monitor for adverse effects."

        await standard_api_client.post(
            f"patient/{patient_id}/encounter/{encounter_id}/soap_note",
            {
                "subjective": subjective,
                "objective": objective,
                "assessment": assessment,
                "plan": plan,
            },
        )
        return f"(Safety report saved to EHR — encounter {encounter_id})"
    except Exception as e:
        return f"(EHR storage failed: {str(e)})"


def _format_safety_report(
    drug_name: str,
    label_data: dict,
    adverse_events: list[dict],
    patient_name: Optional[str],
    patient_meds: list[str],
    cross_ref_results: list[str],
    ehr_note: str,
) -> str:
    """Format the complete FDA safety report."""
    lines: list[str] = []
    lines.append(f"=== FDA DRUG SAFETY REPORT: {drug_name.upper()} ===")

    if not label_data.get("found"):
        error = label_data.get("error", "")
        lines.append(
            f"\nNo FDA label data found for '{drug_name}'."
            + (f" ({error})" if error else "")
        )
        lines.append(
            "This may be an over-the-counter product, a non-US drug, "
            "or the name may be misspelled."
        )
        lines.append(
            "Try using the generic name (e.g., 'acetaminophen' instead of 'Tylenol')."
        )
        return "\n".join(lines)

    # Boxed Warning (most critical)
    if label_data.get("boxed_warning"):
        lines.append("\n--- BOXED WARNING (BLACK BOX) ---")
        lines.append(label_data["boxed_warning"])

    # Contraindications
    if label_data.get("contraindications"):
        lines.append("\n--- CONTRAINDICATIONS ---")
        lines.append(label_data["contraindications"])

    # Warnings
    if label_data.get("warnings"):
        lines.append("\n--- WARNINGS & PRECAUTIONS ---")
        lines.append(label_data["warnings"])

    # Drug Interactions
    if label_data.get("drug_interactions"):
        lines.append("\n--- DRUG INTERACTIONS (FDA Label) ---")
        lines.append(label_data["drug_interactions"])

    # Adverse Reactions
    if label_data.get("adverse_reactions"):
        lines.append("\n--- ADVERSE REACTIONS ---")
        lines.append(label_data["adverse_reactions"])

    # FAERS Adverse Events
    if adverse_events:
        lines.append("\n--- TOP REPORTED ADVERSE EVENTS (FAERS) ---")
        for idx, event in enumerate(adverse_events, 1):
            lines.append(
                f"  {idx}. {event['reaction']} ({event['count']:,} reports)"
            )

    # Patient cross-reference
    if patient_name:
        lines.append(f"\n--- PATIENT CROSS-REFERENCE: {patient_name} ---")
        lines.append(
            f"Current medications: "
            f"{', '.join(patient_meds) if patient_meds else 'None found'}"
        )
        if cross_ref_results:
            lines.append(
                "\n  ALERT: The following patient medications appear in "
                "FDA drug interaction data:"
            )
            for med in cross_ref_results:
                lines.append(f"    - {med}")
            lines.append(
                "  Review the drug interactions section above for details."
            )
        else:
            lines.append(
                "  No patient medications found in FDA drug interaction text."
            )

    # EHR storage note
    if ehr_note:
        lines.append(f"\n{ehr_note}")

    # Disclaimer
    lines.append("\n--- IMPORTANT ---")
    lines.append(
        "This report is based on FDA-approved labeling and FAERS post-market data."
    )
    lines.append(
        "Always consult a pharmacist or physician for clinical decision-making."
    )

    return "\n".join(lines)
