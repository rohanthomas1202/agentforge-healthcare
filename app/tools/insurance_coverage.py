"""Insurance Formulary & Coverage Check tool.

Checks whether a medication is covered by a patient's insurance plan,
including tier, copay, prior authorization requirements, and generic
alternatives.

Uses custom tables in the OpenEMR MariaDB database:
  - insurance_plans: Available insurance plans
  - formulary_items: Drug coverage details per plan
  - coverage_checks: Audit log of coverage lookups

CRUD operations:
  - CREATE: Logs every coverage check for audit trail
  - READ:   Looks up formulary coverage for a medication
  - UPDATE: Formulary items can be updated (tier/copay changes)
  - DELETE: Discontinued drugs can be removed from formulary
"""

import logging
from typing import Optional

from langchain_core.tools import tool

from app.openemr_db import execute, fetch_all, fetch_one
from app.tools.fhir_helpers import find_patient

logger = logging.getLogger(__name__)

# Tier descriptions for user-friendly output
TIER_LABELS = {
    1: "Tier 1 (Generic) — Lowest copay",
    2: "Tier 2 (Preferred Brand) — Moderate copay",
    3: "Tier 3 (Non-Preferred Brand) — Higher copay",
    4: "Tier 4 (Specialty) — Highest copay",
}


@tool
async def insurance_coverage_check(
    patient_identifier: str,
    medication_name: str,
) -> str:
    """Check if a medication is covered by a patient's insurance plan.

    Returns coverage status, formulary tier, copay amount, prior authorization
    requirements, quantity limits, and generic alternatives if available.

    Use this tool when the user asks about:
    - Whether a medication is covered by insurance
    - Drug copay or out-of-pocket cost
    - Prior authorization requirements
    - Generic alternatives to a brand-name drug
    - Formulary tier for a medication
    - Insurance coverage for a prescription

    Args:
        patient_identifier: Patient name (e.g., "John Smith") or patient UUID.
        medication_name: Name of the medication to check (e.g., "Metformin", "Lipitor").
    """
    try:
        # Step 1: Find the patient
        patient = await find_patient(patient_identifier)
        if not patient:
            return f"No patient found matching '{patient_identifier}'."

        patient_id = patient.get("id")

        # Step 2: Get patient's insurance plan
        pid = await _get_patient_pid(patient_id)
        plan = await _get_patient_plan(pid) if pid else None

        if not plan:
            # Try to find any plan and note the assignment
            plan = await fetch_one(
                "SELECT * FROM insurance_plans WHERE active = 1 ORDER BY id LIMIT 1"
            )
            if not plan:
                return "No insurance plans found in the system. Please contact billing."

        plan_id = plan["id"]
        plan_name = plan["plan_name"]

        logger.info("Insurance coverage check for %s on plan %s, drug: %s",
                    patient_identifier, plan_name, medication_name)

        # Step 3: Search formulary for the medication (fuzzy match)
        formulary_item = await fetch_one(
            """
            SELECT * FROM formulary_items
            WHERE plan_id = %s AND LOWER(drug_name) LIKE %s
            LIMIT 1
            """,
            (plan_id, f"%{medication_name.lower()}%"),
        )

        # Step 4: Also check other plans for comparison
        other_plans = await fetch_all(
            """
            SELECT fi.*, ip.plan_name
            FROM formulary_items fi
            JOIN insurance_plans ip ON fi.plan_id = ip.id
            WHERE fi.plan_id != %s AND LOWER(fi.drug_name) LIKE %s AND ip.active = 1
            """,
            (plan_id, f"%{medication_name.lower()}%"),
        )

        # Step 5: Log the coverage check
        result_status = "covered" if formulary_item else "not_covered"
        if formulary_item and formulary_item.get("prior_auth_required"):
            result_status = "prior_auth"
        if formulary_item and formulary_item.get("step_therapy_required"):
            result_status = "step_therapy"

        if pid:
            await execute(
                """
                INSERT INTO coverage_checks (patient_pid, plan_id, drug_name, result, details)
                VALUES (%s, %s, %s, %s, %s)
                """,
                (pid, plan_id, medication_name, result_status,
                 f"Tier {formulary_item['tier']}" if formulary_item else "Not on formulary"),
            )

        # Step 6: Format response
        return _format_coverage_result(
            patient_identifier, plan_name, medication_name,
            formulary_item, other_plans
        )

    except Exception as e:
        logger.exception("Insurance coverage check failed")
        return f"Error checking insurance coverage: {str(e)}"


async def _get_patient_pid(fhir_patient_id: str) -> Optional[int]:
    """Resolve FHIR patient UUID to internal OpenEMR pid."""
    row = await fetch_one(
        "SELECT pid FROM patient_data WHERE uuid = UNHEX(REPLACE(%s, '-', '')) LIMIT 1",
        (fhir_patient_id,),
    )
    if row:
        return row["pid"]
    return None


async def _get_patient_plan(pid: int) -> Optional[dict]:
    """Get the insurance plan assigned to a patient."""
    # Check patient_insurance_plans mapping table
    row = await fetch_one(
        """
        SELECT ip.* FROM insurance_plans ip
        JOIN patient_insurance pi ON pi.plan_id = ip.id
        WHERE pi.patient_pid = %s AND ip.active = 1
        ORDER BY pi.id DESC LIMIT 1
        """,
        (pid,),
    )
    if row:
        return row

    # Fallback: check if there's a default plan assignment in insurance_data table
    row = await fetch_one(
        """
        SELECT ip.* FROM insurance_plans ip
        JOIN insurance_data id ON LOWER(ip.carrier) LIKE CONCAT('%%', LOWER(id.provider), '%%')
        WHERE id.pid = %s AND ip.active = 1
        LIMIT 1
        """,
        (pid,),
    )
    if row:
        return row

    # Last resort: assign first active plan
    return await fetch_one(
        "SELECT * FROM insurance_plans WHERE active = 1 ORDER BY id LIMIT 1"
    )


def _format_coverage_result(
    patient_name: str,
    plan_name: str,
    medication_name: str,
    formulary_item: Optional[dict],
    other_plans: list[dict],
) -> str:
    """Format coverage check results into a readable summary."""
    lines = [
        f"=== INSURANCE COVERAGE CHECK ===",
        f"Patient: {patient_name}",
        f"Insurance Plan: {plan_name}",
        f"Medication: {medication_name}",
        "",
    ]

    if formulary_item:
        tier = formulary_item["tier"]
        tier_label = TIER_LABELS.get(tier, f"Tier {tier}")
        copay = formulary_item.get("copay_amount")

        lines.append(f"--- COVERAGE STATUS: COVERED ---")
        lines.append(f"  Formulary Tier: {tier_label}")
        if copay is not None:
            lines.append(f"  Estimated Copay: ${copay:.2f}")

        if formulary_item.get("prior_auth_required"):
            lines.append(f"  ⚠ Prior Authorization: REQUIRED")
        else:
            lines.append(f"  Prior Authorization: Not required")

        if formulary_item.get("step_therapy_required"):
            lines.append(f"  ⚠ Step Therapy: REQUIRED (must try lower-tier alternatives first)")

        if formulary_item.get("quantity_limit"):
            lines.append(f"  Quantity Limit: {formulary_item['quantity_limit']}")

        if formulary_item.get("generic_alternative"):
            lines.append(f"  💡 Generic Alternative: {formulary_item['generic_alternative']} (may have lower copay)")

    else:
        lines.append(f"--- COVERAGE STATUS: NOT COVERED ---")
        lines.append(f"  '{medication_name}' is not on the formulary for {plan_name}.")
        lines.append(f"  Options:")
        lines.append(f"    1. Ask your provider about covered alternatives")
        lines.append(f"    2. Request a formulary exception from your insurer")
        lines.append(f"    3. Check if a generic equivalent is available")

    # Show coverage on other plans for comparison
    if other_plans:
        lines.append(f"\n--- OTHER PLAN COVERAGE ---")
        for op in other_plans[:3]:
            tier_label = TIER_LABELS.get(op["tier"], f"Tier {op['tier']}")
            copay_str = f"${op['copay_amount']:.2f}" if op.get("copay_amount") else "N/A"
            pa = " (PA required)" if op.get("prior_auth_required") else ""
            lines.append(f"  {op['plan_name']}: {tier_label} — Copay: {copay_str}{pa}")

    return "\n".join(lines)
