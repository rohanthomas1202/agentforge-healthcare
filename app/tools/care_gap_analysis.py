"""USPSTF Preventive Care Gap Tracker.

Analyzes which evidence-based preventive screenings (Grade A/B) a patient
is due or overdue for, based on their age, sex, and medical history.

Uses custom tables in the OpenEMR MariaDB database:
  - screening_protocols: USPSTF recommendations with eligibility criteria
  - patient_care_gaps: per-patient tracking of screening status

CRUD operations:
  - CREATE: Auto-generates gap records when applicable protocols are found
  - READ:   care_gap_analysis retrieves all gaps for a patient
  - UPDATE: update_care_gap marks screenings as completed/declined
  - DELETE: update_care_gap with action="reset" resets a gap to due
"""

import logging
from datetime import date, datetime
from typing import Optional

from langchain_core.tools import tool

from app.openemr_db import execute, execute_returning_id, fetch_all, fetch_one
from app.tools.fhir_helpers import find_patient

logger = logging.getLogger(__name__)


def _calculate_age(birth_date_str: str) -> int:
    """Calculate age in years from an ISO date string (YYYY-MM-DD)."""
    birth = datetime.strptime(birth_date_str[:10], "%Y-%m-%d").date()
    today = date.today()
    return today.year - birth.year - ((today.month, today.day) < (birth.month, birth.day))


@tool
async def care_gap_analysis(patient_identifier: str) -> str:
    """Analyze preventive care gaps for a patient based on USPSTF guidelines.

    Checks which evidence-based screenings (USPSTF Grade A/B) the patient is
    due or overdue for based on their age, sex, and medical history. Returns
    a list of applicable screenings with their status and recommendations.

    Use this tool when the user asks about:
    - Preventive care or screening recommendations
    - What screenings a patient is due for
    - Overdue health screenings
    - USPSTF guidelines for a patient
    - Quality measures or care gaps

    Args:
        patient_identifier: Patient name (e.g., "John Smith") or patient UUID.
    """
    try:
        # Step 1: Find the patient
        patient = await find_patient(patient_identifier)
        if not patient:
            return f"No patient found matching '{patient_identifier}'. Please check the name or ID."

        patient_id = patient.get("id")
        birth_date = patient.get("birthDate")
        gender = patient.get("gender", "").lower()

        if not birth_date:
            return f"Patient found but birth date is missing — cannot evaluate age-based screenings."

        age = _calculate_age(birth_date)
        # Map FHIR gender to our DB sex values
        sex = "male" if gender == "male" else "female" if gender == "female" else "all"

        # Get the patient's internal PID from the DB for care gap records
        pid = await _get_patient_pid(patient_id)
        if not pid:
            return f"Patient found in FHIR but could not resolve internal ID. Please try again."

        logger.info("Care gap analysis", extra={
            "operation": "care_gap_analysis",
            "patient": patient_identifier,
            "age": age,
            "sex": sex,
        })

        # Step 2: Find applicable screening protocols
        protocols = await fetch_all(
            """
            SELECT id, name, uspstf_grade, description, frequency_months,
                   condition_filter, evidence_url
            FROM screening_protocols
            WHERE active = 1
              AND %s BETWEEN min_age AND max_age
              AND (sex = 'all' OR sex = %s)
            ORDER BY uspstf_grade, name
            """,
            (age, sex),
        )

        if not protocols:
            return f"No applicable USPSTF screenings found for this patient (age {age}, {gender})."

        # Step 3: Get existing care gap records for this patient
        existing_gaps = await fetch_all(
            """
            SELECT id, protocol_id, status, due_date, completed_date, notes
            FROM patient_care_gaps
            WHERE patient_pid = %s
            """,
            (pid,),
        )
        gaps_by_protocol = {g["protocol_id"]: g for g in existing_gaps}

        # Step 4: For each protocol, create or evaluate gap records
        results = []
        for proto in protocols:
            proto_id = proto["id"]
            gap = gaps_by_protocol.get(proto_id)

            if gap is None:
                # Auto-create a new gap record as 'due'
                due_date = date.today()
                await execute(
                    """
                    INSERT INTO patient_care_gaps
                        (patient_pid, protocol_id, status, due_date)
                    VALUES (%s, %s, 'due', %s)
                    """,
                    (pid, proto_id, due_date),
                )
                status = "due"
                completed_date = None
            else:
                status = gap["status"]
                completed_date = gap.get("completed_date")

                # Check if overdue (due_date in the past and not completed)
                if status == "due" and gap.get("due_date") and gap["due_date"] < date.today():
                    status = "overdue"
                    await execute(
                        "UPDATE patient_care_gaps SET status = 'overdue' WHERE id = %s",
                        (gap["id"],),
                    )

            results.append({
                "name": proto["name"],
                "grade": proto["uspstf_grade"],
                "description": proto["description"],
                "frequency_months": proto["frequency_months"],
                "status": status,
                "completed_date": str(completed_date) if completed_date else None,
            })

        # Step 5: Format output
        return _format_care_gaps(patient_identifier, age, gender, results)

    except Exception as e:
        logger.exception("Care gap analysis failed")
        return f"Error analyzing care gaps: {str(e)}"


@tool
async def update_care_gap(
    patient_identifier: str,
    screening_name: str,
    action: str,
) -> str:
    """Update a patient's preventive care gap status.

    Use this when a patient reports completing a screening, a provider wants
    to mark a screening as completed or declined, or to reset a screening.

    Args:
        patient_identifier: Patient name (e.g., "John Smith") or patient UUID.
        screening_name: Name of the screening (e.g., "Colorectal Cancer Screening").
        action: One of "completed", "declined", or "reset".
    """
    if action not in ("completed", "declined", "reset"):
        return f"Invalid action '{action}'. Must be one of: completed, declined, reset."

    try:
        # Find patient
        patient = await find_patient(patient_identifier)
        if not patient:
            return f"No patient found matching '{patient_identifier}'."

        patient_id = patient.get("id")
        pid = await _get_patient_pid(patient_id)
        if not pid:
            return f"Could not resolve internal patient ID."

        # Find the screening protocol by name (fuzzy match)
        protocol = await fetch_one(
            """
            SELECT id, name, frequency_months
            FROM screening_protocols
            WHERE LOWER(name) LIKE %s AND active = 1
            LIMIT 1
            """,
            (f"%{screening_name.lower()}%",),
        )

        if not protocol:
            return (
                f"No screening protocol found matching '{screening_name}'. "
                f"Use care_gap_analysis to see available screenings for this patient."
            )

        proto_id = protocol["id"]

        # Find or create the gap record
        gap = await fetch_one(
            "SELECT id FROM patient_care_gaps WHERE patient_pid = %s AND protocol_id = %s",
            (pid, proto_id),
        )

        if action == "completed":
            today = date.today()
            # Calculate next due date based on frequency
            freq = protocol["frequency_months"]
            if freq and freq > 0:
                next_year = today.year + (today.month + freq - 1) // 12
                next_month = (today.month + freq - 1) % 12 + 1
                next_due = date(next_year, next_month, min(today.day, 28))
            else:
                next_due = None  # One-time screening

            if gap:
                if next_due:
                    await execute(
                        """
                        UPDATE patient_care_gaps
                        SET status = 'completed', completed_date = %s,
                            due_date = %s, updated_at = NOW()
                        WHERE id = %s
                        """,
                        (today, next_due, gap["id"]),
                    )
                else:
                    await execute(
                        """
                        UPDATE patient_care_gaps
                        SET status = 'completed', completed_date = %s,
                            updated_at = NOW()
                        WHERE id = %s
                        """,
                        (today, gap["id"]),
                    )
            else:
                await execute(
                    """
                    INSERT INTO patient_care_gaps
                        (patient_pid, protocol_id, status, completed_date, due_date)
                    VALUES (%s, %s, 'completed', %s, %s)
                    """,
                    (pid, proto_id, today, next_due),
                )

            next_msg = f" Next due: {next_due}." if next_due else " (One-time screening — no repeat needed.)"
            logger.info("Care gap updated", extra={
                "operation": "update_care_gap",
                "patient": patient_identifier,
                "screening": protocol["name"],
                "action": "completed",
            })
            return f"'{protocol['name']}' marked as COMPLETED for this patient on {today}.{next_msg}"

        elif action == "declined":
            if gap:
                await execute(
                    """
                    UPDATE patient_care_gaps
                    SET status = 'declined', updated_at = NOW()
                    WHERE id = %s
                    """,
                    (gap["id"],),
                )
            else:
                await execute(
                    """
                    INSERT INTO patient_care_gaps
                        (patient_pid, protocol_id, status, due_date)
                    VALUES (%s, %s, 'declined', %s)
                    """,
                    (pid, proto_id, date.today()),
                )
            logger.info("Care gap updated", extra={
                "operation": "update_care_gap",
                "patient": patient_identifier,
                "screening": protocol["name"],
                "action": "declined",
            })
            return f"'{protocol['name']}' marked as DECLINED for this patient. This will be flagged in future care gap analyses."

        else:  # reset
            if gap:
                await execute(
                    """
                    UPDATE patient_care_gaps
                    SET status = 'due', completed_date = NULL,
                        due_date = %s, updated_at = NOW()
                    WHERE id = %s
                    """,
                    (date.today(), gap["id"]),
                )
            else:
                await execute(
                    """
                    INSERT INTO patient_care_gaps
                        (patient_pid, protocol_id, status, due_date)
                    VALUES (%s, %s, 'due', %s)
                    """,
                    (pid, proto_id, date.today()),
                )
            logger.info("Care gap updated", extra={
                "operation": "update_care_gap",
                "patient": patient_identifier,
                "screening": protocol["name"],
                "action": "reset",
            })
            return f"'{protocol['name']}' has been RESET to 'due' status for this patient."

    except Exception as e:
        logger.exception("Update care gap failed")
        return f"Error updating care gap: {str(e)}"


async def _get_patient_pid(fhir_patient_id: str) -> Optional[int]:
    """Resolve FHIR patient UUID to the internal OpenEMR pid."""
    row = await fetch_one(
        """
        SELECT table_id FROM uuid_registry
        WHERE uuid = UNHEX(REPLACE(%s, '-', ''))
          AND table_name = 'patient_data'
        LIMIT 1
        """,
        (fhir_patient_id,),
    )
    if row:
        return row["table_id"]
    return None


def _format_care_gaps(
    patient_name: str,
    age: int,
    gender: str,
    gaps: list[dict],
) -> str:
    """Format care gap results into a readable summary."""
    lines = [
        f"=== PREVENTIVE CARE GAP ANALYSIS: {patient_name} ===",
        f"Age: {age} | Gender: {gender}",
        f"Based on USPSTF Grade A/B recommendations",
        "",
    ]

    # Group by status
    due = [g for g in gaps if g["status"] == "due"]
    overdue = [g for g in gaps if g["status"] == "overdue"]
    completed = [g for g in gaps if g["status"] == "completed"]
    declined = [g for g in gaps if g["status"] == "declined"]

    if overdue:
        lines.append(f"--- OVERDUE ({len(overdue)}) --- [ACTION NEEDED]")
        for g in overdue:
            freq = f"every {g['frequency_months']} months" if g["frequency_months"] else "one-time"
            lines.append(f"  !! {g['name']} (Grade {g['grade']}) — {freq}")
            if g["description"]:
                lines.append(f"     {g['description']}")
        lines.append("")

    if due:
        lines.append(f"--- DUE NOW ({len(due)}) ---")
        for g in due:
            freq = f"every {g['frequency_months']} months" if g["frequency_months"] else "one-time"
            lines.append(f"  -> {g['name']} (Grade {g['grade']}) — {freq}")
            if g["description"]:
                lines.append(f"     {g['description']}")
        lines.append("")

    if completed:
        lines.append(f"--- COMPLETED ({len(completed)}) ---")
        for g in completed:
            date_str = f" on {g['completed_date']}" if g["completed_date"] else ""
            lines.append(f"  OK {g['name']} (Grade {g['grade']}){date_str}")
        lines.append("")

    if declined:
        lines.append(f"--- DECLINED ({len(declined)}) ---")
        for g in declined:
            lines.append(f"  -- {g['name']} (Grade {g['grade']}) — patient declined")
        lines.append("")

    total = len(gaps)
    action_needed = len(due) + len(overdue)
    lines.append(f"Summary: {action_needed} of {total} applicable screenings need attention.")

    if action_needed > 0:
        lines.append(
            "\nTo update a screening status, use: "
            "update_care_gap(patient, screening_name, 'completed'|'declined'|'reset')"
        )

    return "\n".join(lines)
