"""Centralized input sanitization for agent tool parameters.

Provides consistent sanitization functions for all tool inputs to prevent
injection attacks, excessively long inputs, and malformed data. Each tool
should call the appropriate sanitizer at the start of its function body.

Existing per-tool sanitization (in fhir_helpers, fda_drug_safety, drug_recall,
allergy_checker) remains as defense-in-depth. This module provides the first
line of defense at the tool entry point.
"""

import re
import logging

logger = logging.getLogger(__name__)

# Max lengths for different input types
MAX_PATIENT_NAME_LENGTH = 200
MAX_DRUG_NAME_LENGTH = 200
MAX_FREE_TEXT_LENGTH = 2000
MAX_LIST_SIZE = 50

# Prompt injection patterns to strip from free text
_INJECTION_PATTERNS = [
    r"(?i)ignore\s+(?:all\s+)?(?:previous|above|prior)\s+instructions?",
    r"(?i)you\s+are\s+now\s+(?:a|an)\s+",
    r"(?i)system\s*:\s*",
    r"(?i)assistant\s*:\s*",
    r"(?i)human\s*:\s*",
    r"(?i)override\s+(?:safety|security|restriction)",
    r"(?i)disregard\s+(?:all\s+)?(?:safety|security|rules|instructions?)",
    r"(?i)pretend\s+(?:you\s+are|to\s+be)",
    r"(?i)jailbreak",
    r"(?i)do\s+anything\s+now",
    r"(?i)(?:forget|bypass)\s+(?:your|all)\s+(?:rules|instructions?|constraints?)",
    r"(?i)(?:output|reveal|show|print)\s+(?:your\s+)?(?:system\s+)?prompt",
]


def sanitize_patient_name(name: str) -> str:
    """Sanitize a patient name parameter.

    Strips injection characters, FHIR search modifiers, and caps length.
    Allows alphanumeric, spaces, hyphens, apostrophes, and periods
    (for names like "O'Brien", "St. James", "Mary-Jane").
    """
    if not name or not isinstance(name, str):
        return ""
    # Strip FHIR/SQL injection characters
    clean = re.sub(r"[^\w\s\-'.]+", "", name)
    # Collapse whitespace
    clean = " ".join(clean.split())
    return clean.strip()[:MAX_PATIENT_NAME_LENGTH]


def sanitize_drug_name(name: str) -> str:
    """Sanitize a drug/medication name parameter.

    Strips non-alpha characters (except spaces, hyphens, slashes for
    combo drugs like "amoxicillin/clavulanate"), removes dosage suffixes,
    and caps length.
    """
    if not name or not isinstance(name, str):
        return ""
    # Strip dosage suffix (e.g., "500 MG", "10mg")
    clean = re.sub(r"\s*\d+\s*(mg|mcg|ml|units?|%)\s*$", "", name, flags=re.IGNORECASE)
    # Allow only alphanumeric, spaces, hyphens, slashes, periods
    clean = re.sub(r"[^\w\s\-/.]+", "", clean)
    # Remove Lucene/query syntax
    clean = re.sub(r'[+&|!(){}[\]^"~*?:\\]', " ", clean)
    clean = " ".join(clean.split())
    return clean.strip()[:MAX_DRUG_NAME_LENGTH]


def sanitize_free_text(text: str) -> str:
    """Sanitize free-text input (symptoms, conditions, notes).

    Strips potential prompt injection patterns and caps length.
    Preserves normal medical text.
    """
    if not text or not isinstance(text, str):
        return ""
    clean = text
    for pattern in _INJECTION_PATTERNS:
        clean = re.sub(pattern, "", clean)
    # Collapse whitespace
    clean = " ".join(clean.split())
    return clean.strip()[:MAX_FREE_TEXT_LENGTH]


def sanitize_medication_list(medications: list) -> list:
    """Sanitize a list of medication names.

    Caps list size and applies drug name sanitization to each entry.
    """
    if not medications or not isinstance(medications, list):
        return []
    return [
        sanitize_drug_name(m)
        for m in medications[:MAX_LIST_SIZE]
        if isinstance(m, str) and m.strip()
    ]


def sanitize_symptom_list(symptoms: list) -> list:
    """Sanitize a list of symptom descriptions.

    Caps list size and applies free text sanitization to each entry.
    """
    if not symptoms or not isinstance(symptoms, list):
        return []
    return [
        sanitize_free_text(s)
        for s in symptoms[:MAX_LIST_SIZE]
        if isinstance(s, str) and s.strip()
    ]
