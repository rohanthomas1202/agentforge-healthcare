"""Lab Results Trend Analyzer tool.

Retrieves and analyzes lab results for a patient, comparing against
standard reference ranges and identifying trends over time.

Uses custom tables in the OpenEMR MariaDB database:
  - lab_reference_ranges: Standard reference ranges for common lab tests
  - patient_lab_results: Patient lab result history

CRUD operations:
  - CREATE: New lab results are recorded in patient_lab_results
  - READ:   lab_results_analysis retrieves and analyzes results
  - UPDATE: Reference ranges can be updated (age/sex-specific)
  - DELETE: Old results can be archived/removed
"""

import logging
from datetime import date, datetime
from typing import Optional

from langchain_core.tools import tool

from app.openemr_db import fetch_all, fetch_one
from app.tools.fhir_helpers import find_patient

logger = logging.getLogger(__name__)


@tool
async def lab_results_analysis(
    patient_identifier: str,
    test_type: str = "",
) -> str:
    """Analyze a patient's lab results with trends and clinical interpretation.

    Retrieves lab values from the EHR, compares against reference ranges,
    identifies trends (improving/worsening/stable), and flags critical values.

    Use this tool when the user asks about:
    - Lab results or lab values for a patient
    - Blood test results or blood work
    - HbA1c, glucose, cholesterol, kidney function, liver function
    - Whether lab values are normal or abnormal
    - Trends in lab results over time
    - Critical or concerning lab values

    Args:
        patient_identifier: Patient name (e.g., "John Smith") or patient UUID.
        test_type: Optional filter — e.g., "metabolic", "renal", "hematology",
                   "lipid", or a specific test name like "HbA1c". Leave empty for all.
    """
    try:
        # Step 1: Find the patient
        patient = await find_patient(patient_identifier)
        if not patient:
            return f"No patient found matching '{patient_identifier}'."

        patient_id = patient.get("id")
        birth_date = patient.get("birthDate")
        gender = patient.get("gender", "").lower()

        age = _calculate_age(birth_date) if birth_date else None
        sex = "male" if gender == "male" else "female" if gender == "female" else "all"

        # Step 2: Resolve internal PID
        pid = await _get_patient_pid(patient_id)
        if not pid:
            return f"Patient found but could not resolve internal ID for lab lookup."

        logger.info(
            "Lab results analysis for %s (pid=%s, test_type=%s)",
            patient_identifier, pid, test_type or "all",
        )

        # Step 3: Fetch lab results from our custom table
        if test_type:
            results = await fetch_all(
                """
                SELECT lr.*, rr.normal_low, rr.normal_high,
                       rr.critical_low, rr.critical_high, rr.unit AS ref_unit,
                       rr.category, rr.clinical_significance
                FROM patient_lab_results lr
                LEFT JOIN lab_reference_ranges rr
                    ON lr.loinc_code = rr.loinc_code
                    AND (rr.sex = 'all' OR rr.sex = %s)
                WHERE lr.patient_pid = %s
                  AND (LOWER(lr.test_name) LIKE %s
                       OR LOWER(rr.category) LIKE %s
                       OR lr.loinc_code = %s)
                ORDER BY lr.test_name, lr.result_date DESC
                """,
                (sex, pid, f"%{test_type.lower()}%", f"%{test_type.lower()}%", test_type),
            )
        else:
            results = await fetch_all(
                """
                SELECT lr.*, rr.normal_low, rr.normal_high,
                       rr.critical_low, rr.critical_high, rr.unit AS ref_unit,
                       rr.category, rr.clinical_significance
                FROM patient_lab_results lr
                LEFT JOIN lab_reference_ranges rr
                    ON lr.loinc_code = rr.loinc_code
                    AND (rr.sex = 'all' OR rr.sex = %s)
                WHERE lr.patient_pid = %s
                ORDER BY lr.test_name, lr.result_date DESC
                """,
                (sex, pid),
            )

        if not results:
            filter_msg = f" matching '{test_type}'" if test_type else ""
            return (
                f"No lab results found for {patient_identifier}{filter_msg}. "
                f"Lab results may not yet be recorded in the system."
            )

        # Step 4: Group results by test and analyze
        grouped = _group_by_test(results)
        analyzed = []
        for test_name, entries in grouped.items():
            analysis = _analyze_test(test_name, entries, age)
            analyzed.append(analysis)

        # Step 5: Format output
        return _format_lab_report(patient_identifier, age, gender, analyzed, test_type)

    except Exception as e:
        logger.exception("Lab results analysis failed")
        return f"Error analyzing lab results: {str(e)}"


def _calculate_age(birth_date_str: str) -> int:
    """Calculate age in years from an ISO date string."""
    birth = datetime.strptime(birth_date_str[:10], "%Y-%m-%d").date()
    today = date.today()
    return today.year - birth.year - ((today.month, today.day) < (birth.month, birth.day))


async def _get_patient_pid(fhir_patient_id: str) -> Optional[int]:
    """Resolve FHIR patient UUID to internal OpenEMR pid."""
    row = await fetch_one(
        "SELECT pid FROM patient_data WHERE uuid = UNHEX(REPLACE(%s, '-', '')) LIMIT 1",
        (fhir_patient_id,),
    )
    if row:
        return row["pid"]

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


def _group_by_test(results: list[dict]) -> dict[str, list[dict]]:
    """Group lab result rows by test name, preserving order."""
    grouped: dict[str, list[dict]] = {}
    for r in results:
        name = r["test_name"]
        if name not in grouped:
            grouped[name] = []
        grouped[name].append(r)
    return grouped


def _analyze_test(test_name: str, entries: list[dict], age: Optional[int]) -> dict:
    """Analyze a single lab test's results: status, trend, flags."""
    latest = entries[0]  # Already sorted DESC by date
    value = latest.get("value")
    unit = latest.get("unit") or latest.get("ref_unit") or ""
    normal_low = latest.get("normal_low")
    normal_high = latest.get("normal_high")
    critical_low = latest.get("critical_low")
    critical_high = latest.get("critical_high")
    category = latest.get("category") or "general"
    significance = latest.get("clinical_significance")

    # Determine status
    status = "normal"
    if value is not None and normal_low is not None and normal_high is not None:
        val = float(value)
        if critical_low is not None and val <= float(critical_low):
            status = "critical_low"
        elif critical_high is not None and val >= float(critical_high):
            status = "critical_high"
        elif val < float(normal_low):
            status = "low"
        elif val > float(normal_high):
            status = "high"

    # Compute trend if multiple results exist
    trend = None
    if len(entries) >= 2:
        values = []
        for e in entries:
            v = e.get("value")
            if v is not None:
                values.append(float(v))
        if len(values) >= 2:
            # Compare latest to previous
            diff = values[0] - values[1]
            pct = abs(diff / values[1]) * 100 if values[1] != 0 else 0
            if pct < 5:
                trend = "stable"
            elif diff > 0:
                trend = "increasing"
            else:
                trend = "decreasing"

    # Build history
    history = []
    for e in entries[:5]:  # Last 5 results
        history.append({
            "value": e.get("value"),
            "unit": e.get("unit") or unit,
            "date": str(e.get("result_date")) if e.get("result_date") else None,
        })

    return {
        "test_name": test_name,
        "loinc_code": latest.get("loinc_code"),
        "category": category,
        "latest_value": value,
        "unit": unit,
        "latest_date": str(latest.get("result_date")) if latest.get("result_date") else None,
        "status": status,
        "normal_range": f"{normal_low}-{normal_high}" if normal_low is not None else None,
        "critical_range": _format_critical(critical_low, critical_high),
        "trend": trend,
        "history": history,
        "clinical_significance": significance,
    }


def _format_critical(low, high) -> Optional[str]:
    """Format critical range string."""
    parts = []
    if low is not None:
        parts.append(f"<{low}")
    if high is not None:
        parts.append(f">{high}")
    return " or ".join(parts) if parts else None


def _format_lab_report(
    patient_name: str,
    age: Optional[int],
    gender: str,
    analyses: list[dict],
    test_filter: str,
) -> str:
    """Format lab analysis results into a readable clinical summary."""
    lines = [
        f"=== LAB RESULTS ANALYSIS: {patient_name} ===",
    ]
    if age:
        lines.append(f"Age: {age} | Gender: {gender}")
    if test_filter:
        lines.append(f"Filter: {test_filter}")
    lines.append("")

    # Separate by severity
    critical = [a for a in analyses if a["status"].startswith("critical")]
    abnormal = [a for a in analyses if a["status"] in ("high", "low")]
    normal = [a for a in analyses if a["status"] == "normal"]

    if critical:
        lines.append(f"--- CRITICAL VALUES ({len(critical)}) --- [IMMEDIATE ATTENTION] ---")
        for a in critical:
            flag = "CRITICALLY LOW" if a["status"] == "critical_low" else "CRITICALLY HIGH"
            lines.append(f"  !! {a['test_name']}: {a['latest_value']} {a['unit']} [{flag}]")
            if a["normal_range"]:
                lines.append(f"     Normal range: {a['normal_range']} {a['unit']}")
            if a["trend"]:
                lines.append(f"     Trend: {a['trend']}")
            if a["clinical_significance"]:
                lines.append(f"     Note: {a['clinical_significance']}")
        lines.append("")

    if abnormal:
        lines.append(f"--- ABNORMAL VALUES ({len(abnormal)}) ---")
        for a in abnormal:
            flag = "HIGH" if a["status"] == "high" else "LOW"
            lines.append(f"  ** {a['test_name']}: {a['latest_value']} {a['unit']} [{flag}]")
            if a["normal_range"]:
                lines.append(f"     Normal range: {a['normal_range']} {a['unit']}")
            if a["trend"]:
                lines.append(f"     Trend: {a['trend']}")
            if a["clinical_significance"]:
                lines.append(f"     Note: {a['clinical_significance']}")
        lines.append("")

    if normal:
        lines.append(f"--- NORMAL VALUES ({len(normal)}) ---")
        for a in normal:
            lines.append(f"  OK {a['test_name']}: {a['latest_value']} {a['unit']}")
            if a["normal_range"]:
                lines.append(f"     Normal range: {a['normal_range']} {a['unit']}")
            if a["trend"]:
                lines.append(f"     Trend: {a['trend']}")
        lines.append("")

    # Show history for abnormal/critical tests
    flagged = critical + abnormal
    if flagged:
        lines.append("--- RESULT HISTORY (flagged tests) ---")
        for a in flagged:
            if len(a["history"]) > 1:
                lines.append(f"  {a['test_name']}:")
                for h in a["history"]:
                    lines.append(f"    {h['date']}: {h['value']} {h['unit']}")
        lines.append("")

    # Summary
    total = len(analyses)
    lines.append(
        f"Summary: {len(critical)} critical, {len(abnormal)} abnormal, "
        f"{len(normal)} normal out of {total} tests."
    )

    if critical:
        lines.append(
            "\n⚠ CRITICAL values detected — immediate clinical review recommended."
        )

    return "\n".join(lines)
