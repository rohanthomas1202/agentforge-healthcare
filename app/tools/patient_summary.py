"""Patient summary tool — aggregates patient data from multiple FHIR endpoints.

Queries OpenEMR's FHIR API for demographics, conditions, medications,
allergies, immunizations, and recent encounters to build a complete picture.
"""

import json
from typing import List, Optional

from langchain_core.tools import tool

from app.fhir_client import fhir_client
from app.tools.fhir_helpers import (
    extract_allergy,
    extract_condition,
    extract_medication_request,
    extract_observation,
    extract_patient_name,
    extract_patient_summary,
)


@tool
async def patient_summary(patient_identifier: str) -> str:
    """Get a comprehensive summary of a patient's medical record including demographics, conditions, medications, allergies, and recent lab results.

    Use this tool when the user asks about a patient's medical history, health record,
    current conditions, or medication list. You can search by patient name or patient ID.

    Args:
        patient_identifier: Patient name (e.g., "John Smith") or patient UUID to look up.
    """
    try:
        # Step 1: Find the patient (search by name or get by ID)
        patient = await _find_patient(patient_identifier)
        if not patient:
            return f"No patient found matching '{patient_identifier}'. Please check the name or ID and try again."

        patient_id = patient.get("id")
        demographics = extract_patient_summary(patient)

        # Step 2: Fetch all clinical data in parallel-ish (sequential for simplicity)
        conditions = await _get_conditions(patient_id)
        medications = await _get_medications(patient_id)
        allergies = await _get_allergies(patient_id)
        immunizations = await _get_immunizations(patient_id)
        observations = await _get_recent_observations(patient_id)

        # Step 3: Build the summary
        summary = _format_summary(
            demographics, conditions, medications, allergies, immunizations, observations
        )
        return summary

    except Exception as e:
        return f"Error retrieving patient data: {str(e)}. The medical records system may be temporarily unavailable."


async def _find_patient(identifier: str) -> Optional[dict]:
    """Find a patient by name search or direct ID lookup."""
    # First try as UUID (if it looks like one)
    if len(identifier) > 30 and "-" in identifier:
        try:
            return await fhir_client.get_resource("Patient", identifier)
        except Exception:
            pass

    # If the identifier has multiple words, try given+family search
    parts = identifier.strip().split()
    if len(parts) >= 2:
        patients = await fhir_client.search(
            "Patient", {"given": parts[0], "family": parts[-1]}
        )
        if patients:
            return patients[0]

    # Try as a general name search (works for single names)
    patients = await fhir_client.search("Patient", {"name": identifier})
    if patients:
        return patients[0]

    # Try searching by family name only
    patients = await fhir_client.search("Patient", {"family": identifier})
    if patients:
        return patients[0]

    return None


async def _get_conditions(patient_id: str) -> list[dict]:
    """Get patient's active conditions/diagnoses."""
    try:
        resources = await fhir_client.search("Condition", {"patient": patient_id})
        return [extract_condition(c) for c in resources]
    except Exception:
        return []


async def _get_medications(patient_id: str) -> list[dict]:
    """Get patient's current medications."""
    try:
        resources = await fhir_client.search(
            "MedicationRequest", {"patient": patient_id}
        )
        return [extract_medication_request(m) for m in resources]
    except Exception:
        return []


async def _get_allergies(patient_id: str) -> list[dict]:
    """Get patient's allergies and intolerances."""
    try:
        resources = await fhir_client.search(
            "AllergyIntolerance", {"patient": patient_id}
        )
        return [extract_allergy(a) for a in resources]
    except Exception:
        return []


async def _get_immunizations(patient_id: str) -> list[dict]:
    """Get patient's immunization records."""
    try:
        resources = await fhir_client.search("Immunization", {"patient": patient_id})
        results = []
        for imm in resources:
            vaccine = imm.get("vaccineCode", {})
            codings = vaccine.get("coding", [])
            results.append({
                "vaccine": codings[0].get("display") if codings else vaccine.get("text", "Unknown"),
                "date": imm.get("occurrenceDateTime"),
                "status": imm.get("status"),
            })
        return results
    except Exception:
        return []


async def _get_recent_observations(patient_id: str) -> list[dict]:
    """Get patient's recent lab results and vitals."""
    try:
        resources = await fhir_client.search("Observation", {"patient": patient_id})
        return [extract_observation(o) for o in resources[:10]]  # Limit to 10 most recent
    except Exception:
        return []


def _format_summary(
    demographics: dict,
    conditions: list,
    medications: list,
    allergies: list,
    immunizations: list,
    observations: list,
) -> str:
    """Format all patient data into a readable summary string."""
    lines = []

    # Demographics
    lines.append(f"=== PATIENT SUMMARY: {demographics.get('name', 'Unknown')} ===")
    lines.append(f"Date of Birth: {demographics.get('birth_date', 'Unknown')}")
    lines.append(f"Gender: {demographics.get('gender', 'Unknown')}")
    if demographics.get("phone"):
        lines.append(f"Phone: {demographics['phone']}")
    if demographics.get("email"):
        lines.append(f"Email: {demographics['email']}")
    if demographics.get("address"):
        lines.append(f"Address: {demographics['address']}")
    lines.append(f"Patient ID: {demographics.get('id', 'Unknown')}")

    # Active Conditions
    lines.append(f"\n--- Active Conditions ({len(conditions)}) ---")
    if conditions:
        for c in conditions:
            status = f" [{c['clinical_status']}]" if c.get("clinical_status") else ""
            code = f" (ICD-10: {c['code']})" if c.get("code") else ""
            lines.append(f"  • {c.get('display', 'Unknown')}{code}{status}")
            if c.get("onset"):
                lines.append(f"    Onset: {c['onset']}")
    else:
        lines.append("  No conditions on record.")

    # Medications
    lines.append(f"\n--- Current Medications ({len(medications)}) ---")
    if medications:
        for m in medications:
            status = f" [{m['status']}]" if m.get("status") else ""
            lines.append(f"  • {m.get('medication', 'Unknown')}{status}")
            if m.get("dosage"):
                lines.append(f"    Dosage: {m['dosage']}")
    else:
        lines.append("  No medications on record.")

    # Allergies
    lines.append(f"\n--- Allergies ({len(allergies)}) ---")
    if allergies:
        for a in allergies:
            crit = f" [Criticality: {a['criticality']}]" if a.get("criticality") else ""
            lines.append(f"  • {a.get('substance', 'Unknown')}{crit}")
            if a.get("category"):
                lines.append(f"    Category: {', '.join(a['category'])}")
    else:
        lines.append("  No known allergies (NKA).")

    # Immunizations
    lines.append(f"\n--- Immunizations ({len(immunizations)}) ---")
    if immunizations:
        for i in immunizations:
            date = f" ({i['date']})" if i.get("date") else ""
            lines.append(f"  • {i.get('vaccine', 'Unknown')}{date}")
    else:
        lines.append("  No immunization records.")

    # Recent Lab Results
    lines.append(f"\n--- Recent Lab Results / Vitals ({len(observations)}) ---")
    if observations:
        for o in observations:
            value_str = ""
            if o.get("value") is not None:
                value_str = f": {o['value']} {o.get('unit', '')}"
                ref = o.get("reference_range")
                if ref and ref.get("low") is not None and ref.get("high") is not None:
                    value_str += f" (ref: {ref['low']}-{ref['high']} {ref.get('unit', '')})"
            date = f" [{o['date']}]" if o.get("date") else ""
            lines.append(f"  • {o.get('test_name', 'Unknown')}{value_str}{date}")
    else:
        lines.append("  No recent lab results or vitals.")

    return "\n".join(lines)
