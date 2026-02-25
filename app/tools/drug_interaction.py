"""Drug interaction check tool.

Checks for known drug-drug interactions between a list of medications.
Optionally fetches the patient's current medications from OpenEMR and
includes them in the interaction check.
"""

import json
from typing import List, Optional

from langchain_core.tools import tool

from app.fhir_client import fhir_client
from app.tools.drug_interactions_db import check_interactions, normalize_drug_name
from app.tools.fhir_helpers import extract_medication_request


@tool
async def drug_interaction_check(
    medications: List[str],
    patient_identifier: Optional[str] = None,
) -> str:
    """Check for potential drug-drug interactions between medications.

    This tool cross-references medications against a database of known clinically
    significant drug interactions and returns severity levels and recommendations.

    Use this tool when:
    - A user asks about drug interactions
    - A user mentions multiple medications
    - You need to verify medication safety
    - A patient's medication list needs review

    Args:
        medications: List of medication names to check (brand or generic names accepted).
        patient_identifier: Optional patient name or ID. If provided, the patient's current medications from their medical record will also be included in the interaction check.
    """
    try:
        all_medications = list(medications)  # Copy the input list

        # If patient provided, fetch their current medications too
        patient_meds_note = ""
        if patient_identifier:
            patient_meds = await _fetch_patient_medications(patient_identifier)
            if patient_meds:
                patient_meds_note = f"\nNote: Also included {len(patient_meds)} medication(s) from patient's medical record: {', '.join(patient_meds)}"
                # Add patient meds that aren't already in the list
                for med in patient_meds:
                    normalized_new = normalize_drug_name(med)
                    if not any(normalize_drug_name(m) == normalized_new for m in all_medications):
                        all_medications.append(med)

        if len(all_medications) < 2:
            return "At least 2 medications are needed to check for interactions. Please provide a list of medications."

        # Check interactions
        interactions = check_interactions(all_medications)

        # Format results
        return _format_results(all_medications, interactions, patient_meds_note)

    except Exception as e:
        return f"Error checking drug interactions: {str(e)}"


async def _fetch_patient_medications(identifier: str) -> list[str]:
    """Fetch a patient's current medications from OpenEMR FHIR API."""
    try:
        # Search for patient — split name into given+family for OpenEMR compatibility
        parts = identifier.strip().split()
        if len(parts) >= 2:
            patients = await fhir_client.search(
                "Patient", {"given": parts[0], "family": parts[-1]}
            )
        else:
            patients = await fhir_client.search("Patient", {"name": identifier})
        if not patients:
            return []

        patient_id = patients[0].get("id")

        # Get their medications
        med_requests = await fhir_client.search(
            "MedicationRequest", {"patient": patient_id}
        )

        meds = []
        for mr in med_requests:
            med_data = extract_medication_request(mr)
            if med_data.get("medication") and med_data["medication"] != "Unknown":
                meds.append(med_data["medication"])

        return meds
    except Exception:
        return []


def _format_results(
    medications: list[str], interactions: list[dict], patient_note: str
) -> str:
    """Format interaction check results into a readable string."""
    lines = []

    lines.append(f"=== DRUG INTERACTION CHECK ===")
    lines.append(f"Medications checked ({len(medications)}): {', '.join(medications)}")
    if patient_note:
        lines.append(patient_note)

    if not interactions:
        lines.append(f"\n✓ No known interactions found between these medications.")
        lines.append("Note: This check covers common clinically significant interactions.")
        lines.append("Always consult a pharmacist or physician for comprehensive review.")
        return "\n".join(lines)

    # Count by severity
    severity_counts = {}
    for i in interactions:
        sev = i["severity"]
        severity_counts[sev] = severity_counts.get(sev, 0) + 1

    lines.append(f"\n⚠ Found {len(interactions)} interaction(s):")
    for sev, count in sorted(severity_counts.items()):
        icon = {"contraindicated": "🚫", "high": "🔴", "moderate": "🟡", "low": "🟢"}.get(sev, "⚪")
        lines.append(f"  {icon} {sev.upper()}: {count}")

    # Detail each interaction
    for idx, interaction in enumerate(interactions, 1):
        sev = interaction["severity"]
        icon = {"contraindicated": "🚫", "high": "🔴", "moderate": "🟡", "low": "🟢"}.get(sev, "⚪")

        lines.append(f"\n--- Interaction {idx}: {interaction['drug_1']} + {interaction['drug_2']} ---")
        lines.append(f"  Severity: {icon} {sev.upper()}")
        lines.append(f"  Risk: {interaction['description']}")
        lines.append(f"  Mechanism: {interaction['mechanism']}")
        lines.append(f"  Recommendation: {interaction['recommendation']}")

    lines.append("\n⚕ IMPORTANT: This is an automated screening tool. Always verify")
    lines.append("interactions with a pharmacist or prescribing physician before")
    lines.append("making any changes to medication regimens.")

    return "\n".join(lines)
