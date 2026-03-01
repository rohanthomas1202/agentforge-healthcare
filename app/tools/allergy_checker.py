"""Allergy-aware medication safety checker.

Cross-references a medication (or list of medications) against a patient's
documented allergies, using a drug-class mapping to catch class-level
contraindications (e.g., patient allergic to Penicillin → flag Amoxicillin).
"""

import logging
import re
from typing import Optional

from langchain_core.tools import tool

from app.tools.fhir_helpers import (
    extract_patient_name,
    find_patient,
    get_patient_allergies,
    get_patient_medications,
)

logger = logging.getLogger(__name__)

# ── Drug-to-class and cross-reactivity mappings ──────────────────────────────
#
# Maps allergy substances to the set of drug names that are contraindicated.
# Covers the most common drug-class cross-reactivity patterns seen in
# primary care. Each key is a normalized allergy name (lowercase), and the
# value contains the class name and a set of drug names that belong to it.

ALLERGY_DRUG_CLASS_MAP: dict[str, dict] = {
    "penicillin": {
        "class_name": "Penicillin-class antibiotics",
        "drugs": {
            "penicillin", "amoxicillin", "ampicillin", "augmentin",
            "amoxicillin/clavulanate", "piperacillin", "nafcillin",
            "oxacillin", "dicloxacillin", "piperacillin/tazobactam",
        },
        "cross_reactive_classes": ["cephalosporin"],
        "cross_reactivity_note": (
            "Patients with penicillin allergy have a 1-2% cross-reactivity "
            "risk with cephalosporins. Use with caution."
        ),
    },
    "cephalosporin": {
        "class_name": "Cephalosporin antibiotics",
        "drugs": {
            "cephalexin", "cefazolin", "ceftriaxone", "cefdinir",
            "cefuroxime", "cefepime", "ceftazidime", "cefpodoxime",
            "cefixime", "ceclor", "cefaclor",
        },
        "cross_reactive_classes": ["penicillin"],
        "cross_reactivity_note": (
            "Patients with cephalosporin allergy may have cross-reactivity "
            "with penicillins. Use with caution."
        ),
    },
    "sulfa drugs": {
        "class_name": "Sulfonamide antibiotics",
        "drugs": {
            "sulfamethoxazole", "trimethoprim/sulfamethoxazole", "bactrim",
            "sulfasalazine", "dapsone", "sulfadiazine",
        },
        "cross_reactive_classes": [],
        "cross_reactivity_note": "",
    },
    "sulfonamide": {
        "class_name": "Sulfonamide antibiotics",
        "drugs": {
            "sulfamethoxazole", "trimethoprim/sulfamethoxazole", "bactrim",
            "sulfasalazine", "dapsone", "sulfadiazine",
        },
        "cross_reactive_classes": [],
        "cross_reactivity_note": "",
    },
    "nsaids": {
        "class_name": "Non-steroidal anti-inflammatory drugs",
        "drugs": {
            "ibuprofen", "naproxen", "aspirin", "diclofenac", "celecoxib",
            "meloxicam", "indomethacin", "ketorolac", "piroxicam",
            "ketoprofen", "etodolac", "nabumetone", "advil", "motrin",
            "aleve",
        },
        "cross_reactive_classes": [],
        "cross_reactivity_note": "",
    },
    "aspirin": {
        "class_name": "Aspirin / Salicylates",
        "drugs": {"aspirin", "acetylsalicylic acid"},
        "cross_reactive_classes": ["nsaids"],
        "cross_reactivity_note": (
            "Aspirin-allergic patients may have cross-reactivity with "
            "other NSAIDs, especially in patients with asthma or nasal polyps."
        ),
    },
    "codeine": {
        "class_name": "Opioid analgesics",
        "drugs": {
            "codeine", "morphine", "hydrocodone", "oxycodone",
            "hydromorphone", "tramadol", "fentanyl", "meperidine",
        },
        "cross_reactive_classes": [],
        "cross_reactivity_note": (
            "Cross-reactivity between opioids varies. Codeine allergy does "
            "not necessarily preclude all opioids, but caution is warranted."
        ),
    },
    "amoxicillin": {
        "class_name": "Penicillin-class antibiotics",
        "drugs": {
            "amoxicillin", "penicillin", "ampicillin", "augmentin",
            "amoxicillin/clavulanate",
        },
        "cross_reactive_classes": ["cephalosporin"],
        "cross_reactivity_note": (
            "Amoxicillin is a penicillin-class antibiotic. "
            "Cross-reactivity with other penicillins is expected."
        ),
    },
    "carbamazepine": {
        "class_name": "Aromatic anticonvulsants",
        "drugs": {
            "carbamazepine", "oxcarbazepine", "phenytoin", "eslicarbazepine",
        },
        "cross_reactive_classes": [],
        "cross_reactivity_note": (
            "Patients allergic to carbamazepine have approximately 25-30% "
            "cross-reactivity risk with oxcarbazepine."
        ),
    },
    "iodine contrast": {
        "class_name": "Iodinated contrast media",
        "drugs": {
            "iohexol", "iopamidol", "iodixanol", "ioversol",
            "iopromide", "diatrizoate",
        },
        "cross_reactive_classes": [],
        "cross_reactivity_note": (
            "Iodine contrast allergy is a reaction to the contrast agent, "
            "not to iodine itself. Premedication protocols may allow safe use."
        ),
    },
    "morphine": {
        "class_name": "Opioid analgesics",
        "drugs": {
            "morphine", "codeine", "hydrocodone", "oxycodone",
            "hydromorphone", "fentanyl", "meperidine",
        },
        "cross_reactive_classes": [],
        "cross_reactivity_note": (
            "Cross-reactivity between opioids varies by chemical structure. "
            "Codeine and morphine share a phenanthrene core. "
            "Fentanyl has a different structure and may be tolerated."
        ),
    },
    "fluoroquinolone": {
        "class_name": "Fluoroquinolone antibiotics",
        "drugs": {
            "ciprofloxacin", "levofloxacin", "moxifloxacin",
            "ofloxacin", "norfloxacin", "gemifloxacin",
        },
        "cross_reactive_classes": [],
        "cross_reactivity_note": (
            "Cross-reactivity within fluoroquinolones is common. "
            "Patients allergic to one should avoid all quinolones."
        ),
    },
    "ciprofloxacin": {
        "class_name": "Fluoroquinolone antibiotics",
        "drugs": {
            "ciprofloxacin", "levofloxacin", "moxifloxacin",
            "ofloxacin", "norfloxacin", "gemifloxacin",
        },
        "cross_reactive_classes": [],
        "cross_reactivity_note": (
            "Ciprofloxacin is a fluoroquinolone. Cross-reactivity with "
            "other fluoroquinolones is expected."
        ),
    },
    "levofloxacin": {
        "class_name": "Fluoroquinolone antibiotics",
        "drugs": {
            "ciprofloxacin", "levofloxacin", "moxifloxacin",
            "ofloxacin", "norfloxacin", "gemifloxacin",
        },
        "cross_reactive_classes": [],
        "cross_reactivity_note": (
            "Levofloxacin is a fluoroquinolone. Cross-reactivity with "
            "other fluoroquinolones is expected."
        ),
    },
    "ace inhibitor": {
        "class_name": "ACE inhibitors",
        "drugs": {
            "lisinopril", "enalapril", "ramipril", "captopril",
            "benazepril", "fosinopril", "quinapril", "perindopril",
        },
        "cross_reactive_classes": [],
        "cross_reactivity_note": (
            "ACE inhibitor angioedema is a class effect. "
            "Patients who experienced angioedema with one ACE inhibitor "
            "should avoid all ACE inhibitors."
        ),
    },
    "lisinopril": {
        "class_name": "ACE inhibitors",
        "drugs": {
            "lisinopril", "enalapril", "ramipril", "captopril",
            "benazepril", "fosinopril", "quinapril", "perindopril",
        },
        "cross_reactive_classes": [],
        "cross_reactivity_note": (
            "Lisinopril is an ACE inhibitor. Cross-reactivity with "
            "other ACE inhibitors is expected, especially for angioedema."
        ),
    },
}


def normalize_substance(substance: str) -> str:
    """Normalize an allergy substance name for lookup."""
    return substance.strip().lower()


def _normalize_drug(drug_name: str) -> str:
    """Normalize a drug name: lowercase, strip dosage suffixes."""
    name = drug_name.strip().lower()
    name = re.sub(r"\s*\d+\s*(mg|mcg|ml|units?|%)\s*$", "", name)
    return name.strip()


def check_allergy_conflicts(
    allergies: list[dict], medications: list[str]
) -> list[dict]:
    """Check a list of medications against patient allergies.

    Args:
        allergies: List of extracted allergy dicts (from fhir_helpers.extract_allergy).
        medications: List of medication names to check.

    Returns:
        List of conflict dicts, each with:
            - allergy: the allergy substance
            - medication: the flagged medication
            - severity: "DIRECT" | "CLASS" | "CROSS-REACTIVE"
            - class_name: drug class name
            - note: clinical note about the conflict
    """
    conflicts: list[dict] = []

    for allergy in allergies:
        substance = normalize_substance(allergy.get("substance", ""))
        criticality = allergy.get("criticality", "unknown")
        if not substance or substance == "unknown":
            continue

        # Check if this allergy has a known drug-class mapping
        class_info = ALLERGY_DRUG_CLASS_MAP.get(substance)

        for med in medications:
            norm_med = _normalize_drug(med)
            if not norm_med:
                continue

            # Direct name match (allergy substance == medication name)
            if substance == norm_med:
                conflicts.append({
                    "allergy": allergy.get("substance", substance),
                    "medication": med,
                    "severity": "DIRECT",
                    "criticality": criticality,
                    "class_name": class_info["class_name"] if class_info else "N/A",
                    "note": f"Direct match: patient is allergic to {substance}.",
                })
                continue

            if not class_info:
                continue

            # Class-level match (medication is in the same drug class)
            if norm_med in class_info["drugs"]:
                conflicts.append({
                    "allergy": allergy.get("substance", substance),
                    "medication": med,
                    "severity": "CLASS",
                    "criticality": criticality,
                    "class_name": class_info["class_name"],
                    "note": (
                        f"{med} belongs to {class_info['class_name']}, "
                        f"same class as documented allergy to {substance}."
                    ),
                })
                continue

            # Cross-reactive class check
            for cross_class in class_info.get("cross_reactive_classes", []):
                cross_info = ALLERGY_DRUG_CLASS_MAP.get(cross_class)
                if cross_info and norm_med in cross_info["drugs"]:
                    conflicts.append({
                        "allergy": allergy.get("substance", substance),
                        "medication": med,
                        "severity": "CROSS-REACTIVE",
                        "criticality": criticality,
                        "class_name": cross_info["class_name"],
                        "note": (
                            f"{med} is in {cross_info['class_name']}, which "
                            f"has cross-reactivity with {class_info['class_name']}. "
                            f"{class_info.get('cross_reactivity_note', '')}"
                        ),
                    })
                    break

    return conflicts


@tool
async def allergy_check(
    patient_identifier: str,
    medications: Optional[list[str]] = None,
) -> str:
    """Check if medications are safe for a patient given their documented allergies.

    Cross-references medications against the patient's allergy list, including
    drug-class and cross-reactivity checks (e.g., Penicillin allergy flags
    Amoxicillin as a class-level conflict).

    Use this tool when:
    - A user asks if a specific medication is safe for a patient
    - Before prescribing or recommending a medication
    - A user asks about allergy-drug conflicts
    - You need to verify medication safety against a patient's allergy list

    Args:
        patient_identifier: Patient name or ID to check allergies for.
        medications: Optional list of specific medications to check. If not provided,
            checks the patient's current medications against their allergies.
    """
    try:
        patient = await find_patient(patient_identifier)
        if not patient:
            return (
                f"No patient found matching '{patient_identifier}'. "
                "Please check the name or ID and try again."
            )

        patient_id = patient.get("id")
        patient_name = extract_patient_name(patient)

        # Fetch allergies
        allergies = await get_patient_allergies(patient_id)
        if not allergies:
            return (
                f"=== ALLERGY SAFETY CHECK: {patient_name} ===\n\n"
                "No allergies on record (NKA - No Known Allergies).\n"
                "No allergy-based medication contraindications identified.\n\n"
                "Note: Always confirm allergy status verbally with the patient."
            )

        # Get medications to check (cap at 50 to prevent abuse)
        MAX_MEDICATIONS = 50
        MAX_MED_NAME_LEN = 200
        meds_to_check = list(medications) if medications else []
        meds_to_check = [m[:MAX_MED_NAME_LEN] for m in meds_to_check[:MAX_MEDICATIONS]]
        current_meds: list[str] = []
        if not meds_to_check:
            current_meds = await get_patient_medications(patient_id)
            meds_to_check = current_meds

        if not meds_to_check:
            return (
                f"=== ALLERGY SAFETY CHECK: {patient_name} ===\n\n"
                f"Documented allergies: "
                f"{', '.join(a.get('substance', 'Unknown') for a in allergies)}\n\n"
                "No medications provided or on record to check.\n"
                "Provide specific medication names to check against allergies."
            )

        # Run the check
        conflicts = check_allergy_conflicts(allergies, meds_to_check)

        return _format_allergy_report(
            patient_name, allergies, meds_to_check, current_meds, conflicts
        )

    except Exception as e:
        return f"Error checking allergy safety: {str(e)}"


def _format_allergy_report(
    patient_name: str,
    allergies: list[dict],
    medications_checked: list[str],
    current_meds: list[str],
    conflicts: list[dict],
) -> str:
    """Format the allergy safety check report."""
    lines: list[str] = []
    lines.append(f"=== ALLERGY SAFETY CHECK: {patient_name.upper()} ===")

    # Documented allergies
    lines.append(f"\n--- Documented Allergies ({len(allergies)}) ---")
    for a in allergies:
        crit = f" [Criticality: {a['criticality']}]" if a.get("criticality") else ""
        cat = f" ({', '.join(a['category'])})" if a.get("category") else ""
        lines.append(f"  - {a.get('substance', 'Unknown')}{cat}{crit}")

    # Medications checked
    source = "current medications" if current_meds else "specified medications"
    lines.append(
        f"\n--- Medications Checked ({len(medications_checked)}, from {source}) ---"
    )
    for med in medications_checked:
        lines.append(f"  - {med}")

    # Results
    if not conflicts:
        lines.append("\n--- RESULT: NO CONFLICTS FOUND ---")
        lines.append(
            "No allergy-based contraindications identified for the checked medications."
        )
    else:
        direct = [c for c in conflicts if c["severity"] == "DIRECT"]
        class_level = [c for c in conflicts if c["severity"] == "CLASS"]
        cross = [c for c in conflicts if c["severity"] == "CROSS-REACTIVE"]

        lines.append(
            f"\n--- RESULT: {len(conflicts)} CONFLICT(S) FOUND ---"
        )

        if direct:
            lines.append(f"\n  DIRECT ALLERGY MATCH ({len(direct)}):")
            for c in direct:
                lines.append(f"    ALERT: {c['medication']}")
                lines.append(f"      Allergy: {c['allergy']}")
                lines.append(f"      {c['note']}")

        if class_level:
            lines.append(f"\n  DRUG CLASS CONFLICT ({len(class_level)}):")
            for c in class_level:
                lines.append(f"    WARNING: {c['medication']}")
                lines.append(f"      Allergy: {c['allergy']}")
                lines.append(f"      Drug Class: {c['class_name']}")
                lines.append(f"      {c['note']}")

        if cross:
            lines.append(f"\n  CROSS-REACTIVITY RISK ({len(cross)}):")
            for c in cross:
                lines.append(f"    CAUTION: {c['medication']}")
                lines.append(f"      Allergy: {c['allergy']}")
                lines.append(f"      Cross-reactive Class: {c['class_name']}")
                lines.append(f"      {c['note']}")

    # Disclaimer
    lines.append("\n--- IMPORTANT ---")
    lines.append(
        "This check covers documented allergies and known drug-class "
        "cross-reactivity patterns. It does not replace clinical judgment."
    )
    lines.append(
        "Always verify allergy history with the patient and consult "
        "a pharmacist for comprehensive drug allergy evaluation."
    )

    return "\n".join(lines)
