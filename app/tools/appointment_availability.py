"""Appointment availability tool — checks schedules and open time slots.

Queries OpenEMR's FHIR Appointment endpoint to find booked appointments,
then calculates available time slots for a given provider and date.
"""

from datetime import datetime, timedelta
from typing import Optional

from langchain_core.tools import tool

from app.fhir_client import fhir_client
from app.tools.fhir_helpers import extract_appointment, extract_practitioner

# Business hours configuration
BUSINESS_START_HOUR = 9   # 9 AM
BUSINESS_END_HOUR = 17    # 5 PM
SLOT_DURATION_MINUTES = 30


@tool
async def appointment_availability(
    provider_name: Optional[str] = None,
    date: Optional[str] = None,
    patient_name: Optional[str] = None,
) -> str:
    """Check appointment availability for a provider on a specific date, or look up a patient's existing appointments.

    Use this tool when:
    - A user wants to find available appointment time slots
    - A user asks about a doctor's availability on a specific date
    - A user wants to see their upcoming or past appointments
    - A user needs to know when a provider has openings

    Args:
        provider_name: Name of the healthcare provider (e.g., "Dr. Wilson"). If not provided, shows all appointments on the date.
        date: Date to check in YYYY-MM-DD format (e.g., "2026-02-25"). Defaults to today.
        patient_name: Optional patient name to look up their existing appointments instead.
    """
    try:
        # Default to today
        if not date:
            date = datetime.now().strftime("%Y-%m-%d")

        # Validate date format
        try:
            target_date = datetime.strptime(date, "%Y-%m-%d")
        except ValueError:
            return f"Invalid date format: '{date}'. Please use YYYY-MM-DD format (e.g., 2026-02-25)."

        # If patient specified, look up their appointments
        if patient_name:
            results = await _get_patient_appointments(patient_name, date)
            if results is None:
                return f"No patient found matching '{patient_name}'."
            return _format_patient_appointments(results, patient_name, date)

        # Get all appointments on the target date
        appointments = await _get_appointments_on_date(date)

        # If provider specified, filter and show their availability
        if provider_name:
            provider = await _find_provider(provider_name)
            if not provider:
                return (
                    f"No provider found matching '{provider_name}'. "
                    "Use the provider search tool to find available providers."
                )

            provider_id = provider.get("id")
            provider_appointments = [
                a for a in appointments
                if a.get("provider_id") == provider_id
            ]

            available_slots = _calculate_available_slots(provider_appointments, target_date)
            return _format_availability(provider, provider_appointments, available_slots, date)
        else:
            return _format_date_summary(appointments, date)

    except Exception as e:
        return f"Error checking appointment availability: {str(e)}"


async def _find_provider(name: str) -> Optional[dict]:
    """Find a provider by name.

    Note: OpenEMR's FHIR 'name' param returns 500, so we use family/given instead.
    """
    clean_name = name.strip()
    for prefix in ["Dr.", "Dr ", "dr.", "dr "]:
        if clean_name.lower().startswith(prefix):
            clean_name = clean_name[len(prefix):].strip()

    parts = clean_name.split()

    if len(parts) >= 2:
        practitioners = await fhir_client.search(
            "Practitioner", {"given": parts[0], "family": parts[-1]}
        )
        if practitioners:
            return extract_practitioner(practitioners[0])

    # Try family name, then given name
    practitioners = await fhir_client.search("Practitioner", {"family": clean_name})
    if not practitioners:
        practitioners = await fhir_client.search("Practitioner", {"given": clean_name})

    if practitioners:
        return extract_practitioner(practitioners[0])

    return None


async def _get_appointments_on_date(date: str) -> list[dict]:
    """Fetch all appointments on a specific date."""
    try:
        resources = await fhir_client.search("Appointment", {"date": date})
        return [extract_appointment(a) for a in resources]
    except Exception:
        return []


async def _get_patient_appointments(patient_name: str, date: str) -> Optional[list[dict]]:
    """Fetch appointments for a specific patient from the given date onwards."""
    # Find patient
    parts = patient_name.strip().split()
    if len(parts) >= 2:
        patients = await fhir_client.search(
            "Patient", {"given": parts[0], "family": parts[-1]}
        )
    else:
        patients = await fhir_client.search("Patient", {"name": patient_name})

    if not patients:
        return None

    patient_id = patients[0].get("id")

    try:
        resources = await fhir_client.search(
            "Appointment", {"patient": patient_id, "date": f"ge{date}"}
        )
        return [extract_appointment(a) for a in resources]
    except Exception:
        return []


def _calculate_available_slots(booked: list[dict], target_date: datetime) -> list[dict]:
    """Calculate available time slots given booked appointments."""
    all_slots = []
    current = target_date.replace(hour=BUSINESS_START_HOUR, minute=0, second=0)
    end_time = target_date.replace(hour=BUSINESS_END_HOUR, minute=0, second=0)

    while current < end_time:
        slot_end = current + timedelta(minutes=SLOT_DURATION_MINUTES)
        all_slots.append({
            "start": current.strftime("%H:%M"),
            "end": slot_end.strftime("%H:%M"),
            "available": True,
        })
        current = slot_end

    # Mark booked slots as unavailable
    for appt in booked:
        appt_start = appt.get("start_time", "")
        appt_end = appt.get("end_time", "")
        if not appt_start:
            continue
        for slot in all_slots:
            if _times_overlap(slot["start"], slot["end"], appt_start, appt_end):
                slot["available"] = False

    return all_slots


def _times_overlap(s1_start: str, s1_end: str, s2_start: str, s2_end: str) -> bool:
    """Check if two time ranges overlap (HH:MM format)."""
    try:
        a_start = _parse_time(s1_start)
        a_end = _parse_time(s1_end)
        b_start = _parse_time(s2_start)
        b_end = _parse_time(s2_end)
        return a_start < b_end and b_start < a_end
    except (ValueError, TypeError):
        return False


def _parse_time(time_str: str) -> int:
    """Convert HH:MM to minutes since midnight for comparison."""
    if not time_str or ":" not in time_str:
        return 0
    parts = time_str.split(":")
    return int(parts[0]) * 60 + int(parts[1])


def _format_availability(
    provider: dict, appointments: list[dict], slots: list[dict], date: str
) -> str:
    """Format provider availability with booked and open slots."""
    lines = []
    lines.append("=== APPOINTMENT AVAILABILITY ===")
    lines.append(f"Provider: {provider.get('name', 'Unknown')}")
    lines.append(f"Date: {date}")
    lines.append(f"Business Hours: {BUSINESS_START_HOUR}:00 AM - {BUSINESS_END_HOUR - 12}:00 PM")
    lines.append(f"Slot Duration: {SLOT_DURATION_MINUTES} minutes\n")

    # Show booked appointments
    if appointments:
        lines.append(f"--- Booked Appointments ({len(appointments)}) ---")
        for appt in appointments:
            time_str = f"{appt.get('start_time', '?')} - {appt.get('end_time', '?')}"
            status = f" [{appt.get('status', '')}]" if appt.get("status") else ""
            appt_type = f" ({appt.get('type', '')})" if appt.get("type") else ""
            patient = f" - {appt.get('patient_name', '')}" if appt.get("patient_name") else ""
            lines.append(f"  • {time_str}{appt_type}{patient}{status}")
        lines.append("")

    # Show available slots
    available = [s for s in slots if s["available"]]
    unavailable_count = len(slots) - len(available)

    lines.append(f"--- Available Slots ({len(available)}/{len(slots)}) ---")
    if available:
        for slot in available:
            lines.append(f"  ✓ {slot['start']} - {slot['end']}")
    else:
        lines.append("  No available slots on this date.")
        lines.append("  Try another date or a different provider.")

    lines.append(
        f"\nTotal slots: {len(slots)} | Available: {len(available)} | Booked: {unavailable_count}"
    )
    lines.append("\nTo schedule an appointment, please contact the provider's office directly")
    lines.append("or ask your healthcare provider to book through the EHR system.")

    return "\n".join(lines)


def _format_patient_appointments(
    appointments: list[dict], patient_name: str, date: str
) -> str:
    """Format a patient's appointment listing."""
    lines = []
    lines.append("=== PATIENT APPOINTMENTS ===")
    lines.append(f"Patient: {patient_name}")
    lines.append(f"Showing appointments from: {date}\n")

    if not appointments:
        lines.append("No upcoming appointments found.")
        lines.append("Use the provider search tool to find a provider, then check their availability.")
        return "\n".join(lines)

    for idx, appt in enumerate(appointments, 1):
        lines.append(f"--- Appointment {idx} ---")
        lines.append(f"  Date: {appt.get('date', 'Unknown')}")
        lines.append(f"  Time: {appt.get('start_time', '?')} - {appt.get('end_time', '?')}")
        if appt.get("type"):
            lines.append(f"  Type: {appt['type']}")
        if appt.get("status"):
            lines.append(f"  Status: {appt['status']}")
        if appt.get("provider_name"):
            lines.append(f"  Provider: {appt['provider_name']}")
        if appt.get("location"):
            lines.append(f"  Location: {appt['location']}")
        if appt.get("comment"):
            lines.append(f"  Notes: {appt['comment']}")
        lines.append("")

    lines.append(f"Total: {len(appointments)} appointment(s)")

    return "\n".join(lines)


def _format_date_summary(appointments: list[dict], date: str) -> str:
    """Format a general appointment summary for a date."""
    lines = []
    lines.append("=== APPOINTMENT SCHEDULE ===")
    lines.append(f"Date: {date}\n")

    if not appointments:
        lines.append("No appointments scheduled for this date.")
        lines.append("All provider slots should be available.")
        lines.append("\nSpecify a provider name to see their available time slots.")
        return "\n".join(lines)

    # Group by provider
    by_provider: dict[str, list] = {}
    for appt in appointments:
        prov = appt.get("provider_name", "Unassigned")
        by_provider.setdefault(prov, []).append(appt)

    for provider, appts in by_provider.items():
        lines.append(f"--- {provider} ({len(appts)} appointment(s)) ---")
        for appt in sorted(appts, key=lambda a: a.get("start_time", "")):
            time_str = f"{appt.get('start_time', '?')} - {appt.get('end_time', '?')}"
            status = f" [{appt.get('status', '')}]" if appt.get("status") else ""
            lines.append(f"  • {time_str}{status}")
        lines.append("")

    lines.append(
        f"Total: {len(appointments)} appointment(s) across {len(by_provider)} provider(s)"
    )
    lines.append("\nSpecify a provider name to see their available time slots.")

    return "\n".join(lines)
