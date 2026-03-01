"""Helper functions for working with FHIR resources.

FHIR resources have deeply nested structures. These helpers extract
commonly needed fields into simpler formats for the agent to work with.
"""

import logging
import re
from typing import Any, Optional

logger = logging.getLogger(__name__)


def extract_patient_name(patient: dict) -> str:
    """Extract a human-readable name from a FHIR Patient resource."""
    names = patient.get("name", [])
    if not names:
        return "Unknown"
    name = names[0]
    given = " ".join(name.get("given", []))
    family = name.get("family", "")
    return f"{given} {family}".strip() or "Unknown"


def extract_patient_summary(patient: dict) -> dict[str, Any]:
    """Extract key fields from a FHIR Patient resource into a flat dict."""
    return {
        "id": patient.get("id"),
        "name": extract_patient_name(patient),
        "birth_date": patient.get("birthDate"),
        "gender": patient.get("gender"),
        "phone": _extract_telecom(patient, "phone"),
        "email": _extract_telecom(patient, "email"),
        "address": _extract_address(patient),
    }


def extract_condition(condition: dict) -> dict[str, Any]:
    """Extract key fields from a FHIR Condition resource."""
    code = condition.get("code", {})
    codings = code.get("coding", [])
    return {
        "id": condition.get("id"),
        "code": codings[0].get("code") if codings else None,
        "system": codings[0].get("system") if codings else None,
        "display": codings[0].get("display") if codings else code.get("text", "Unknown"),
        "clinical_status": _extract_nested_code(condition, "clinicalStatus"),
        "verification_status": _extract_nested_code(condition, "verificationStatus"),
        "onset": condition.get("onsetDateTime"),
    }


def extract_medication_request(med_request: dict) -> dict[str, Any]:
    """Extract key fields from a FHIR MedicationRequest resource."""
    med = med_request.get("medicationCodeableConcept", {})
    codings = med.get("coding", [])
    return {
        "id": med_request.get("id"),
        "medication": codings[0].get("display") if codings else med.get("text", "Unknown"),
        "medication_code": codings[0].get("code") if codings else None,
        "status": med_request.get("status"),
        "intent": med_request.get("intent"),
        "authored_on": med_request.get("authoredOn"),
        "dosage": _extract_dosage(med_request),
    }


def extract_allergy(allergy: dict) -> dict[str, Any]:
    """Extract key fields from a FHIR AllergyIntolerance resource."""
    code = allergy.get("code", {})
    codings = code.get("coding", [])

    # Determine substance name — OpenEMR may return data-absent-reason instead of actual code
    substance = "Unknown"
    if codings:
        first = codings[0]
        if first.get("system") != "http://terminology.hl7.org/CodeSystem/data-absent-reason":
            substance = first.get("display", code.get("text", "Unknown"))
        else:
            substance = code.get("text", "Unknown")
    else:
        substance = code.get("text", "Unknown")

    # Fallback: extract from narrative text (OpenEMR puts the name there)
    if substance == "Unknown":
        text_div = allergy.get("text", {}).get("div", "")
        if text_div:
            # Strip HTML tags from <div xmlns='...'>Name</div>
            clean = re.sub(r"<[^>]+>", "", text_div).strip()
            if clean:
                substance = clean

    return {
        "id": allergy.get("id"),
        "substance": substance,
        "type": allergy.get("type"),
        "category": allergy.get("category", []),
        "criticality": allergy.get("criticality"),
        "clinical_status": _extract_nested_code(allergy, "clinicalStatus"),
    }


def extract_observation(observation: dict) -> dict[str, Any]:
    """Extract key fields from a FHIR Observation resource (labs, vitals)."""
    code = observation.get("code", {})
    codings = code.get("coding", [])
    value = observation.get("valueQuantity", {})
    return {
        "id": observation.get("id"),
        "test_name": codings[0].get("display") if codings else code.get("text", "Unknown"),
        "test_code": codings[0].get("code") if codings else None,
        "value": value.get("value"),
        "unit": value.get("unit"),
        "status": observation.get("status"),
        "date": observation.get("effectiveDateTime"),
        "reference_range": _extract_reference_range(observation),
    }


def extract_practitioner(practitioner: dict) -> dict[str, Any]:
    """Extract key fields from a FHIR Practitioner resource."""
    names = practitioner.get("name", [])
    name = "Unknown"
    if names:
        n = names[0]
        prefix = " ".join(n.get("prefix", []))
        given = " ".join(n.get("given", []))
        family = n.get("family", "")
        name = f"{prefix} {given} {family}".strip()

    # Extract NPI from identifiers
    npi = None
    for identifier in practitioner.get("identifier", []):
        coding = identifier.get("type", {}).get("coding", [])
        for c in coding:
            if c.get("code") == "NPI":
                npi = identifier.get("value")
                break
        if npi:
            break
        # Also check system URI for NPI
        if "npi" in identifier.get("system", "").lower():
            npi = identifier.get("value")

    return {
        "id": practitioner.get("id"),
        "name": name,
        "npi": npi,
        "active": practitioner.get("active"),
        "phone": _extract_telecom(practitioner, "phone"),
        "email": _extract_telecom(practitioner, "email"),
        "address": _extract_address(practitioner),
    }


def extract_practitioner_role(role: dict) -> dict[str, Any]:
    """Extract key fields from a FHIR PractitionerRole resource."""
    # Extract specialty
    specialty = None
    for spec in role.get("specialty", []):
        codings = spec.get("coding", [])
        if codings:
            specialty = codings[0].get("display") or codings[0].get("code")
            break
        if spec.get("text"):
            specialty = spec["text"]
            break

    # Extract organization name
    org = role.get("organization", {})
    organization = org.get("display")

    # Extract practitioner reference
    pract = role.get("practitioner", {})
    practitioner_ref = pract.get("reference", "")
    practitioner_name = pract.get("display")

    return {
        "id": role.get("id"),
        "specialty": specialty,
        "organization": organization,
        "practitioner_ref": practitioner_ref,
        "practitioner_name": practitioner_name,
        "phone": _extract_telecom(role, "phone"),
        "email": _extract_telecom(role, "email"),
    }


def extract_appointment(appointment: dict) -> dict[str, Any]:
    """Extract key fields from a FHIR Appointment resource."""
    start = appointment.get("start", "")
    end = appointment.get("end", "")

    # Parse date and time from ISO format
    date = ""
    start_time = ""
    end_time = ""
    if start:
        if "T" in start:
            date = start.split("T")[0]
            start_time = start.split("T")[1][:5]  # HH:MM
        else:
            date = start
    if end and "T" in end:
        end_time = end.split("T")[1][:5]

    # Extract appointment type
    appt_type = None
    type_concept = appointment.get("appointmentType", {})
    codings = type_concept.get("coding", [])
    if codings:
        appt_type = codings[0].get("display") or codings[0].get("code")
    elif type_concept.get("text"):
        appt_type = type_concept["text"]

    # Extract participants
    provider_name = None
    provider_id = None
    patient_name = None
    location = None

    for participant in appointment.get("participant", []):
        actor = participant.get("actor", {})
        ref = actor.get("reference", "")
        display = actor.get("display", "")

        if ref.startswith("Practitioner/") or ref.startswith("Person/"):
            provider_name = display or ref
            provider_id = ref.split("/")[-1] if "/" in ref else ref
        elif ref.startswith("Patient/"):
            patient_name = display or ref
        elif ref.startswith("Location/"):
            location = display or ref

    return {
        "id": appointment.get("id"),
        "status": appointment.get("status"),
        "type": appt_type,
        "date": date,
        "start_time": start_time,
        "end_time": end_time,
        "provider_name": provider_name,
        "provider_id": provider_id,
        "patient_name": patient_name,
        "location": location,
        "comment": appointment.get("comment"),
    }


# --- Private helpers ---


def _extract_telecom(resource: dict, system: str) -> Optional[str]:
    """Extract a telecom value (phone/email) from a FHIR resource."""
    for telecom in resource.get("telecom", []):
        if telecom.get("system") == system:
            return telecom.get("value")
    return None


def _extract_address(resource: dict) -> Optional[str]:
    """Extract a formatted address from a FHIR resource."""
    addresses = resource.get("address", [])
    if not addresses:
        return None
    addr = addresses[0]
    parts = addr.get("line", []) + [
        addr.get("city", ""),
        addr.get("state", ""),
        addr.get("postalCode", ""),
    ]
    return ", ".join(p for p in parts if p)


def _extract_nested_code(resource: dict, field: str) -> Optional[str]:
    """Extract a coded value from a nested CodeableConcept field."""
    concept = resource.get(field, {})
    codings = concept.get("coding", [])
    if codings:
        return codings[0].get("code")
    return concept.get("text")


def _extract_dosage(med_request: dict) -> Optional[str]:
    """Extract dosage instructions from a MedicationRequest."""
    dosages = med_request.get("dosageInstruction", [])
    if dosages:
        dosage = dosages[0]
        text = dosage.get("text") or dosage.get("patientInstruction")
        if text:
            return text

    # OpenEMR puts dosage info in note field instead of dosageInstruction
    notes = med_request.get("note", [])
    if notes:
        return notes[0].get("text")

    return None


def _extract_reference_range(observation: dict) -> Optional[dict]:
    """Extract reference range from an Observation."""
    ranges = observation.get("referenceRange", [])
    if not ranges:
        return None
    ref = ranges[0]
    return {
        "low": ref.get("low", {}).get("value"),
        "high": ref.get("high", {}).get("value"),
        "unit": ref.get("low", {}).get("unit") or ref.get("high", {}).get("unit"),
        "text": ref.get("text"),
    }


# ── Shared patient/medication lookup helpers ─────────────────────────────────


_UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
    re.IGNORECASE,
)


def _sanitize_fhir_search_value(value: str) -> str:
    """Sanitize a value used in FHIR search parameters.

    Removes characters that could be interpreted as FHIR search modifiers
    or parameter separators (|, \\, $, :).
    """
    # Allow only alphanumeric, spaces, hyphens, apostrophes, and periods
    # (common in names like "O'Brien", "St. James", "Mary-Jane")
    sanitized = re.sub(r"[^\w\s\-'.]+", "", value)
    return sanitized.strip()[:200]  # Length cap for safety


async def find_patient(identifier: str) -> Optional[dict]:
    """Find a patient by name or UUID using the FHIR API.

    Search strategy:
    1. If identifier looks like a UUID, try direct resource fetch.
    2. If identifier has multiple words, try given+family search.
    3. Fall back to general name search.
    4. Fall back to family-only search.

    Args:
        identifier: Patient name (e.g., "John Smith") or UUID.

    Returns:
        FHIR Patient resource dict if found, else None.
    """
    from app.fhir_client import fhir_client

    identifier = identifier.strip()
    if not identifier:
        return None

    # Try as UUID (strict UUID format validation)
    if _UUID_RE.match(identifier):
        try:
            return await fhir_client.get_resource("Patient", identifier)
        except Exception:
            logger.debug("UUID lookup failed for %s", identifier)

    # Sanitize the identifier for search queries
    clean = _sanitize_fhir_search_value(identifier)
    if not clean:
        return None

    # Try given+family split
    parts = clean.split()
    if len(parts) >= 2:
        patients = await fhir_client.search(
            "Patient", {"given": parts[0], "family": parts[-1]}
        )
        if patients:
            return patients[0]

    # Try general name search
    patients = await fhir_client.search("Patient", {"name": clean})
    if patients:
        return patients[0]

    # Try family-only search
    patients = await fhir_client.search("Patient", {"family": clean})
    if patients:
        return patients[0]

    return None


async def get_patient_medications(patient_id: str) -> list[str]:
    """Fetch a patient's current medication names from OpenEMR.

    Args:
        patient_id: FHIR Patient resource ID.

    Returns:
        List of medication display names.
    """
    from app.fhir_client import fhir_client

    try:
        med_requests = await fhir_client.search(
            "MedicationRequest", {"patient": patient_id}
        )
        meds: list[str] = []
        for mr in med_requests:
            med_data = extract_medication_request(mr)
            if med_data.get("medication") and med_data["medication"] != "Unknown":
                meds.append(med_data["medication"])
        return meds
    except Exception as e:
        logger.warning("Failed to fetch medications for patient %s: %s", patient_id, e)
        return []


async def get_patient_allergies(patient_id: str) -> list[dict]:
    """Fetch a patient's allergy list from OpenEMR.

    Args:
        patient_id: FHIR Patient resource ID.

    Returns:
        List of extracted allergy dicts with substance, type, category, criticality.
    """
    from app.fhir_client import fhir_client

    try:
        resources = await fhir_client.search(
            "AllergyIntolerance", {"patient": patient_id}
        )
        return [extract_allergy(a) for a in resources]
    except Exception as e:
        logger.warning("Failed to fetch allergies for patient %s: %s", patient_id, e)
        return []


async def get_patient_conditions(patient_id: str) -> list[dict]:
    """Fetch a patient's active conditions from OpenEMR.

    Args:
        patient_id: FHIR Patient resource ID.

    Returns:
        List of extracted condition dicts with display, code, clinical_status.
    """
    from app.fhir_client import fhir_client

    try:
        resources = await fhir_client.search("Condition", {"patient": patient_id})
        return [extract_condition(c) for c in resources]
    except Exception as e:
        logger.warning("Failed to fetch conditions for patient %s: %s", patient_id, e)
        return []
