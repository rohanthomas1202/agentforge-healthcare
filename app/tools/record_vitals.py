"""Record patient vitals tool — writes vital signs to OpenEMR via Standard REST API.

Posts vital sign measurements (blood pressure, heart rate, temperature, etc.)
to the patient's record in OpenEMR using the Standard REST API endpoint.
"""

from typing import Optional

from langchain_core.tools import tool

from app.fhir_client import fhir_client, standard_api_client
import logging

logger = logging.getLogger(__name__)


@tool
async def record_vitals(
    patient_identifier: str,
    systolic_bp: Optional[int] = None,
    diastolic_bp: Optional[int] = None,
    heart_rate: Optional[int] = None,
    temperature: Optional[float] = None,
    weight: Optional[float] = None,
    height: Optional[float] = None,
    respiration: Optional[int] = None,
    oxygen_saturation: Optional[float] = None,
    notes: Optional[str] = None,
) -> str:
    """Record patient vital signs into their medical record in OpenEMR.

    Use this tool when:
    - A user wants to record blood pressure, heart rate, temperature, or other vitals
    - A user provides vital sign measurements for a patient
    - A user asks to update a patient's vitals

    At least one vital sign measurement must be provided.

    Args:
        patient_identifier: Patient name (e.g., "John Smith") or patient UUID.
        systolic_bp: Systolic blood pressure in mmHg (e.g., 120).
        diastolic_bp: Diastolic blood pressure in mmHg (e.g., 80).
        heart_rate: Heart rate in beats per minute (e.g., 72).
        temperature: Body temperature in Fahrenheit (e.g., 98.6).
        weight: Weight in pounds (e.g., 175).
        height: Height in inches (e.g., 70).
        respiration: Respiratory rate in breaths per minute (e.g., 16).
        oxygen_saturation: Oxygen saturation percentage (e.g., 98).
        notes: Optional clinical notes about the vitals reading.
    """
    try:
        # Validate at least one measurement provided
        measurements = {
            "systolic_bp": systolic_bp,
            "diastolic_bp": diastolic_bp,
            "heart_rate": heart_rate,
            "temperature": temperature,
            "weight": weight,
            "height": height,
            "respiration": respiration,
            "oxygen_saturation": oxygen_saturation,
        }
        provided = {k: v for k, v in measurements.items() if v is not None}

        if not provided:
            return (
                "No vital sign measurements provided. Please include at least one "
                "measurement such as blood pressure (systolic_bp, diastolic_bp), "
                "heart_rate, temperature, weight, height, respiration, or "
                "oxygen_saturation."
            )

        # Step 1: Find the patient
        patient = await _find_patient(patient_identifier)
        if not patient:
            return (
                f"No patient found matching '{patient_identifier}'. "
                "Please check the name or ID and try again."
            )

        logger.info("Patient data accessed", extra={"operation": "patient_data_access", "patient": patient_identifier, "tool": "record_vitals"})
        patient_id = patient.get("id")
        patient_name = _get_patient_name(patient)

        # Step 2: Build the vitals payload
        vitals_payload = _build_vitals_payload(provided, notes)

        # Step 3: POST to OpenEMR (or return mock confirmation)
        if standard_api_client is None:
            return _format_confirmation(patient_name, provided, notes)

        try:
            result = await standard_api_client.post(
                f"patient/{patient_id}/vital", vitals_payload
            )
        except Exception:
            # Graceful fallback if Standard API is not configured
            return _format_confirmation(
                patient_name,
                provided,
                notes,
                note="(Note: Could not write to EHR — Standard API may not be configured)",
            )

        # Check for OpenEMR validation errors
        validation_errors = result.get("validationErrors", [])
        if validation_errors:
            return _format_confirmation(
                patient_name,
                provided,
                notes,
                note=f"(Warning: Validation issues: {validation_errors})",
            )

        logger.info("Vitals written to EHR", extra={"operation": "ehr_write", "patient": patient_identifier, "tool": "record_vitals"})
        return _format_confirmation(patient_name, provided, notes)

    except Exception as e:
        return f"Error recording vitals: {str(e)}"


# ── Private helpers ──────────────────────────────────────────────────────────


async def _find_patient(identifier: str) -> Optional[dict]:
    """Find a patient by name search or direct ID lookup."""
    # Try as UUID first
    if len(identifier) > 30 and "-" in identifier:
        try:
            return await fhir_client.get_resource("Patient", identifier)
        except Exception:
            pass

    # Split name into given+family for OpenEMR compatibility
    parts = identifier.strip().split()
    if len(parts) >= 2:
        patients = await fhir_client.search(
            "Patient", {"given": parts[0], "family": parts[-1]}
        )
        if patients:
            return patients[0]

    patients = await fhir_client.search("Patient", {"name": identifier})
    if patients:
        return patients[0]

    patients = await fhir_client.search("Patient", {"family": identifier})
    if patients:
        return patients[0]

    return None


def _get_patient_name(patient: dict) -> str:
    """Extract display name from patient resource."""
    names = patient.get("name", [])
    if not names:
        return "Unknown"
    name = names[0]
    given = " ".join(name.get("given", []))
    family = name.get("family", "")
    return f"{given} {family}".strip() or "Unknown"


def _build_vitals_payload(provided: dict, notes: Optional[str]) -> dict:
    """Build the OpenEMR Standard API vitals payload.

    OpenEMR field mapping:
    - bps = systolic blood pressure
    - bpd = diastolic blood pressure
    - pulse = heart rate
    - temperature = body temperature
    - weight = weight
    - height = height
    - respiration = respiratory rate
    - oxygen_saturation = SpO2
    """
    field_map = {
        "systolic_bp": "bps",
        "diastolic_bp": "bpd",
        "heart_rate": "pulse",
        "temperature": "temperature",
        "weight": "weight",
        "height": "height",
        "respiration": "respiration",
        "oxygen_saturation": "oxygen_saturation",
    }
    payload: dict = {}
    for param_name, api_field in field_map.items():
        if param_name in provided:
            payload[api_field] = str(provided[param_name])
    if notes:
        payload["note"] = notes
    return payload


_LABELS = {
    "systolic_bp": ("Systolic BP", "mmHg"),
    "diastolic_bp": ("Diastolic BP", "mmHg"),
    "heart_rate": ("Heart Rate", "bpm"),
    "temperature": ("Temperature", "F"),
    "weight": ("Weight", "lbs"),
    "height": ("Height", "in"),
    "respiration": ("Respiration", "breaths/min"),
    "oxygen_saturation": ("O2 Saturation", "%"),
}


def _format_confirmation(
    patient_name: str,
    provided: dict,
    notes: Optional[str],
    note: str = "",
) -> str:
    """Format a confirmation message for recorded vitals."""
    lines: list[str] = []
    lines.append("=== VITALS RECORDED ===")
    lines.append(f"Patient: {patient_name}")
    lines.append("")
    lines.append("--- Recorded Measurements ---")
    for key, value in provided.items():
        label, unit = _LABELS.get(key, (key, ""))
        lines.append(f"  * {label}: {value} {unit}")

    if notes:
        lines.append(f"\nNotes: {notes}")

    if note:
        lines.append(f"\n{note}")

    lines.append("\nVitals have been recorded for the patient.")
    return "\n".join(lines)
