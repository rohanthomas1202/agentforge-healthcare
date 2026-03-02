"""Clinical trials search tool — queries ClinicalTrials.gov for recruiting studies.

Uses the ClinicalTrials.gov API v2 to find actively recruiting clinical trials
based on medical conditions. Optionally cross-references with a patient's
active conditions from OpenEMR to find personally relevant trials.
"""

import logging
import re
from typing import Optional

import httpx
from langchain_core.tools import tool

from app.agent.input_sanitizer import sanitize_free_text, sanitize_patient_name
from app.tools.fhir_helpers import (
    extract_patient_name,
    find_patient,
    get_patient_conditions,
)
from app.tools.retry_utils import RetryableHTTPError, api_retry

logger = logging.getLogger(__name__)

CTGOV_API_URL = "https://clinicaltrials.gov/api/v2/studies"
CTGOV_TIMEOUT = 15.0
MAX_RESULTS = 5


def _sanitize_query(text: str) -> str:
    """Remove dosage suffixes, special characters, and normalize whitespace."""
    text = re.sub(r"\s*\d+\s*(mg|mcg|ml|units?|%)\s*$", "", text, flags=re.IGNORECASE)
    text = re.sub(r"[^\w\s\-]", "", text)
    return text.strip()


@tool
async def clinical_trials_search(
    condition: str,
    patient_identifier: Optional[str] = None,
    location: Optional[str] = None,
) -> str:
    """Search ClinicalTrials.gov for actively recruiting clinical trials related to
    a medical condition.

    Use this tool when:
    - A user asks about clinical trials for a specific condition or disease
    - A user wants to know about research studies they might be eligible for
    - A provider wants to find trials relevant to a patient's conditions
    - A user asks about experimental treatments or ongoing research

    Args:
        condition: Medical condition or disease to search for (e.g., "Type 2 Diabetes",
            "atrial fibrillation", "breast cancer").
        patient_identifier: Optional patient name or ID. If provided, searches for
            trials matching the patient's active conditions from their medical record.
        location: Optional location to filter trials by (e.g., "Austin, TX", "Texas").
    """
    try:
        condition = sanitize_free_text(condition)
        if patient_identifier:
            patient_identifier = sanitize_patient_name(patient_identifier)
        if location:
            location = sanitize_free_text(location)

        # If patient provided, get their conditions and search for each
        if patient_identifier:
            return await _patient_trials_search(
                patient_identifier, condition, location
            )

        # Direct condition search
        trials = await _search_trials(condition, location)
        return _format_trials_report(condition, trials, location)

    except Exception as e:
        logger.error("Error searching clinical trials: %s", e, exc_info=True)
        return "Error searching clinical trials. Please try again or contact support."


async def _patient_trials_search(
    patient_identifier: str, condition_hint: str, location: Optional[str]
) -> str:
    """Search trials based on a patient's active conditions."""
    patient = await find_patient(patient_identifier)
    if not patient:
        return (
            f"No patient found matching '{patient_identifier}'. "
            "Please check the name or ID and try again."
        )

    patient_id = patient.get("id")
    patient_name = extract_patient_name(patient)
    conditions = await get_patient_conditions(patient_id)

    if not conditions:
        # Fall back to the condition hint
        trials = await _search_trials(condition_hint, location)
        return _format_trials_report(condition_hint, trials, location, patient_name)

    # Search trials for each of the patient's conditions (cap at 5 to avoid
    # excessive API calls for patients with many documented conditions)
    MAX_CONDITIONS_TO_SEARCH = 5
    all_results: list[dict] = []
    conditions_searched: list[str] = []
    for cond in conditions[:MAX_CONDITIONS_TO_SEARCH]:
        display = cond.get("display", "")
        if not display or display == "Unknown":
            continue
        conditions_searched.append(display)
        trials = await _search_trials(display, location)
        for trial in trials:
            trial["matched_condition"] = display
            if not any(t["nct_id"] == trial["nct_id"] for t in all_results):
                all_results.append(trial)

    return _format_patient_trials_report(
        patient_name, conditions_searched, all_results, location
    )


async def _search_trials(
    condition: str, location: Optional[str] = None
) -> list[dict]:
    """Query ClinicalTrials.gov API v2 for recruiting studies (with retry)."""
    clean_condition = _sanitize_query(condition)
    if not clean_condition:
        return []

    try:
        return await _search_trials_inner(clean_condition, location)
    except Exception as e:
        logger.warning("ClinicalTrials.gov API failed after retries: %s", e)
        return []


@api_retry
async def _search_trials_inner(
    clean_condition: str, location: Optional[str] = None
) -> list[dict]:
    """Inner fetch with retry — timeouts and 5xx are retried."""
    params: dict = {
        "query.cond": clean_condition,
        "filter.overallStatus": "RECRUITING",
        "pageSize": str(MAX_RESULTS),
        "format": "json",
    }
    if location:
        params["query.locn"] = _sanitize_query(location)

    async with httpx.AsyncClient(timeout=CTGOV_TIMEOUT) as client:
        resp = await client.get(CTGOV_API_URL, params=params)
        if resp.status_code == 404:
            return []
        if resp.status_code >= 500:
            raise RetryableHTTPError(f"ClinicalTrials.gov returned {resp.status_code}")
        resp.raise_for_status()
        data = resp.json()

    studies = data.get("studies", [])
    results: list[dict] = []
    for study in studies[:MAX_RESULTS]:
        proto = study.get("protocolSection", {})
        ident = proto.get("identificationModule", {})
        status = proto.get("statusModule", {})
        design = proto.get("designModule", {})
        eligibility = proto.get("eligibilityModule", {})
        desc = proto.get("descriptionModule", {})
        contacts = proto.get("contactsLocationsModule", {})
        arms = proto.get("armsInterventionsModule", {})
        sponsor = proto.get("sponsorCollaboratorsModule", {})

        # Extract locations
        locations: list[str] = []
        for loc in contacts.get("locations", [])[:3]:
            city = loc.get("city", "")
            state_ = loc.get("state", "")
            country = loc.get("country", "")
            parts = [p for p in [city, state_, country] if p]
            if parts:
                locations.append(", ".join(parts))

        # Extract interventions
        interventions: list[str] = []
        for iv in arms.get("interventions", [])[:3]:
            name = iv.get("name", "")
            if name:
                interventions.append(name)

        # Extract conditions
        conds_module = proto.get("conditionsModule", {})
        conditions = conds_module.get("conditions", [])

        # Extract lead sponsor
        lead_sponsor = ""
        if sponsor.get("leadSponsor"):
            lead_sponsor = sponsor["leadSponsor"].get("name", "")

        results.append({
            "nct_id": ident.get("nctId", "Unknown"),
            "title": ident.get("briefTitle", "Untitled Study"),
            "conditions": conditions[:5],
            "interventions": interventions,
            "phase": ", ".join(design.get("phases", ["N/A"])),
            "enrollment": design.get("enrollmentInfo", {}).get(
                "count", "Unknown"
            ),
            "study_type": design.get("studyType", "Unknown"),
            "start_date": status.get("startDateStruct", {}).get("date", ""),
            "completion_date": status.get(
                "primaryCompletionDateStruct", {}
            ).get("date", ""),
            "sponsor": lead_sponsor,
            "locations": locations,
            "min_age": eligibility.get("minimumAge", "N/A"),
            "max_age": eligibility.get("maximumAge", "N/A"),
            "sex": eligibility.get("sex", "ALL"),
            "summary": (desc.get("briefSummary", "") or "")[:300],
        })

    return results


def _format_trials_report(
    condition: str,
    trials: list[dict],
    location: Optional[str] = None,
    patient_name: Optional[str] = None,
) -> str:
    """Format clinical trials results into a readable report."""
    lines: list[str] = []
    lines.append(f"=== CLINICAL TRIALS SEARCH: {condition.upper()} ===")
    if patient_name:
        lines.append(f"Patient: {patient_name}")
    if location:
        lines.append(f"Location filter: {location}")

    if not trials:
        lines.append(
            f"\nNo actively recruiting trials found for '{condition}'."
        )
        lines.append(
            "Try broadening the search term or removing the location filter."
        )
        lines.append(
            "You can also search at https://clinicaltrials.gov for more options."
        )
        return "\n".join(lines)

    lines.append(f"\nFound {len(trials)} actively recruiting trial(s):\n")

    for idx, trial in enumerate(trials, 1):
        lines.append(f"--- Trial {idx}: {trial['nct_id']} ---")
        lines.append(f"  Title: {trial['title']}")
        if trial.get("conditions"):
            lines.append(f"  Conditions: {', '.join(trial['conditions'])}")
        if trial.get("interventions"):
            lines.append(f"  Interventions: {', '.join(trial['interventions'])}")
        lines.append(f"  Phase: {trial['phase']}")
        lines.append(f"  Study Type: {trial['study_type']}")
        lines.append(f"  Enrollment: {trial['enrollment']} participants")
        lines.append(f"  Sponsor: {trial['sponsor'] or 'Unknown'}")
        if trial.get("locations"):
            lines.append(f"  Locations: {'; '.join(trial['locations'])}")
        lines.append(
            f"  Eligibility: Ages {trial['min_age']} - {trial['max_age']}, "
            f"Sex: {trial['sex']}"
        )
        if trial.get("start_date"):
            lines.append(f"  Started: {trial['start_date']}")
        if trial.get("summary"):
            lines.append(f"  Summary: {trial['summary']}...")
        lines.append(
            f"  Link: https://clinicaltrials.gov/study/{trial['nct_id']}"
        )
        lines.append("")

    lines.append("--- IMPORTANT ---")
    lines.append(
        "Clinical trial participation requires evaluation by the study team. "
        "Discuss eligibility with your healthcare provider before enrolling."
    )

    return "\n".join(lines)


def _format_patient_trials_report(
    patient_name: str,
    conditions_searched: list[str],
    trials: list[dict],
    location: Optional[str] = None,
) -> str:
    """Format patient-specific clinical trials report."""
    lines: list[str] = []
    lines.append(f"=== CLINICAL TRIALS FOR PATIENT: {patient_name.upper()} ===")
    lines.append(
        f"Conditions searched: {', '.join(conditions_searched)}"
    )
    if location:
        lines.append(f"Location filter: {location}")

    if not trials:
        lines.append(
            "\nNo actively recruiting trials found for this patient's conditions."
        )
        lines.append(
            "Try searching for specific conditions or check "
            "https://clinicaltrials.gov directly."
        )
        return "\n".join(lines)

    lines.append(f"\nFound {len(trials)} relevant trial(s):\n")

    for idx, trial in enumerate(trials, 1):
        lines.append(f"--- Trial {idx}: {trial['nct_id']} ---")
        lines.append(f"  Matched Condition: {trial.get('matched_condition', 'N/A')}")
        lines.append(f"  Title: {trial['title']}")
        if trial.get("interventions"):
            lines.append(f"  Interventions: {', '.join(trial['interventions'])}")
        lines.append(f"  Phase: {trial['phase']}")
        lines.append(f"  Enrollment: {trial['enrollment']} participants")
        lines.append(f"  Sponsor: {trial['sponsor'] or 'Unknown'}")
        if trial.get("locations"):
            lines.append(f"  Locations: {'; '.join(trial['locations'])}")
        lines.append(
            f"  Eligibility: Ages {trial['min_age']} - {trial['max_age']}, "
            f"Sex: {trial['sex']}"
        )
        if trial.get("summary"):
            lines.append(f"  Summary: {trial['summary']}...")
        lines.append(
            f"  Link: https://clinicaltrials.gov/study/{trial['nct_id']}"
        )
        lines.append("")

    lines.append("--- IMPORTANT ---")
    lines.append(
        "Clinical trial eligibility depends on many factors. "
        "Discuss these options with the patient's healthcare provider."
    )

    return "\n".join(lines)
