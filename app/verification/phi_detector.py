"""PHI Detection verification layer — scans LLM responses for PHI leakage.

Detects Protected Health Information patterns in the agent's response text
and flags them. Critical patterns (SSN) cause the check to fail; moderate
patterns (phone, email, address, DOB, MRN) generate warnings only.
"""

import re


# Severity levels:
#   critical  → causes passed=False (response should be blocked/redacted)
#   high      → strong warning, does NOT block
#   moderate  → informational warning
_PHI_PATTERNS = [
    {
        "name": "SSN",
        "pattern": r"\b\d{3}-\d{2}-\d{4}\b",
        "severity": "critical",
        "description": "Social Security Number detected",
    },
    {
        "name": "MRN",
        "pattern": r"\b(?:MRN|Medical Record Number|medical record #)[:\s]*[\w\-]{4,20}\b",
        "severity": "high",
        "description": "Medical Record Number reference detected",
    },
    {
        "name": "Phone",
        "pattern": r"\b(?:\+1[\s.-]?)?\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4}\b",
        "severity": "moderate",
        "description": "Phone number detected",
    },
    {
        "name": "Email",
        "pattern": r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b",
        "severity": "moderate",
        "description": "Email address detected",
    },
    {
        "name": "Street Address",
        "pattern": r"\b\d{1,5}\s+(?:[A-Z][a-z]+\s+){1,3}(?:St|Street|Ave|Avenue|Blvd|Boulevard|Dr|Drive|Rd|Road|Ln|Lane|Way|Ct|Court|Pl|Place)\b",
        "severity": "moderate",
        "description": "Street address detected",
    },
    {
        "name": "Labeled DOB",
        "pattern": r"(?:DOB|Date of Birth|born on)[:\s]+\d{4}[-/]\d{2}[-/]\d{2}",
        "severity": "moderate",
        "description": "Labeled date of birth detected",
    },
]


class PHIDetector:
    """Scan agent responses for Protected Health Information patterns."""

    def detect(self, response_text: str) -> dict:
        """Scan response text for PHI patterns.

        Returns:
            {
                "passed": bool,         # False only if critical PHI found
                "flags": [
                    {"pattern": str, "severity": str, "description": str, "match": str}
                ],
                "disclaimers": list[str],
            }
        """
        flags: list[dict] = []
        has_critical = False

        for spec in _PHI_PATTERNS:
            for match in re.finditer(spec["pattern"], response_text, re.IGNORECASE):
                matched_text = match.group(0)
                flags.append({
                    "pattern": spec["name"],
                    "severity": spec["severity"],
                    "description": spec["description"],
                    "match": _redact(matched_text),
                })
                if spec["severity"] == "critical":
                    has_critical = True

        disclaimers: list[str] = []
        if has_critical:
            disclaimers.append(
                "CRITICAL: Response contains what appears to be a Social Security "
                "Number or other critical PHI. This data should not be shared."
            )
        elif flags:
            disclaimers.append(
                "PHI NOTICE: Response may contain patient-identifiable information "
                "(phone, email, address, or DOB). Ensure this is appropriate for "
                "the context."
            )

        return {
            "passed": not has_critical,
            "flags": flags,
            "disclaimers": disclaimers,
        }


def _redact(text: str) -> str:
    """Partially redact a matched value for safe logging."""
    if len(text) <= 4:
        return "***"
    return text[:2] + "***" + text[-2:]
