"""Dosage limit verification layer — flags mentions that exceed FDA max daily doses.

Extracts dosage mentions from the agent's response (e.g., "5000 mg of
acetaminophen") and compares against a built-in table of FDA maximum
recommended daily doses for common medications.
"""

import re


# FDA maximum recommended daily doses (mg/day) for common medications.
# Source: FDA-approved prescribing information (selected subset).
MAX_DAILY_DOSES: dict[str, float] = {
    "acetaminophen": 4000,
    "ibuprofen": 3200,
    "naproxen": 1500,
    "aspirin": 4000,
    "metformin": 2550,
    "lisinopril": 80,
    "atorvastatin": 80,
    "simvastatin": 40,
    "amlodipine": 10,
    "losartan": 100,
    "omeprazole": 40,
    "pantoprazole": 80,
    "metoprolol": 450,
    "atenolol": 200,
    "warfarin": 15,
    "sertraline": 200,
    "fluoxetine": 80,
    "escitalopram": 20,
    "gabapentin": 3600,
    "pregabalin": 600,
    "amoxicillin": 3000,
    "azithromycin": 500,
    "ciprofloxacin": 1500,
    "hydrochlorothiazide": 50,
    "furosemide": 600,
    "prednisone": 80,
    "albuterol": 32,  # oral; inhaler limits differ
    "montelukast": 10,
}

# Patterns to extract dosage mentions from text
_DOSAGE_PATTERNS = [
    # "5000 mg of acetaminophen" / "5000mg acetaminophen"
    r"(\d+(?:\.\d+)?)\s*(?:mg|milligrams?)\s+(?:of\s+)?([A-Za-z]+)",
    # "acetaminophen 5000 mg" / "acetaminophen 5000mg"
    r"([A-Za-z]+)\s+(\d+(?:\.\d+)?)\s*(?:mg|milligrams?)",
    # "take 5000 mg acetaminophen"
    r"take\s+(\d+(?:\.\d+)?)\s*(?:mg|milligrams?)\s+(?:of\s+)?([A-Za-z]+)",
]


class DosageChecker:
    """Check response text for dosage mentions that exceed FDA max daily limits."""

    def check(self, response_text: str) -> dict:
        """Scan response text for dosage mentions and flag excessive ones.

        Returns:
            {
                "passed": bool,
                "flags": [
                    {"drug": str, "mentioned_mg": float, "max_mg": float, "note": str}
                ],
                "disclaimers": list[str],
            }
        """
        mentions = self._extract_dosages(response_text)
        flags: list[dict] = []

        for drug, mg in mentions:
            drug_lower = drug.lower()
            if drug_lower in MAX_DAILY_DOSES:
                max_mg = MAX_DAILY_DOSES[drug_lower]
                if mg > max_mg:
                    flags.append({
                        "drug": drug,
                        "mentioned_mg": mg,
                        "max_mg": max_mg,
                        "note": (
                            f"{mg:.0f} mg exceeds FDA max daily dose of "
                            f"{max_mg:.0f} mg for {drug}."
                        ),
                    })

        passed = len(flags) == 0

        disclaimers: list[str] = []
        if flags:
            drug_list = ", ".join(f["drug"] for f in flags)
            disclaimers.append(
                f"DOSAGE WARNING: Mentioned dosage(s) for {drug_list} exceed "
                "FDA maximum recommended daily limits. Verify with a pharmacist "
                "or prescriber before acting on this information."
            )

        return {
            "passed": passed,
            "flags": flags,
            "disclaimers": disclaimers,
        }

    def _extract_dosages(self, text: str) -> list[tuple[str, float]]:
        """Extract (drug_name, mg_amount) pairs from text."""
        results: list[tuple[str, float]] = []
        seen: set[str] = set()

        for pattern in _DOSAGE_PATTERNS:
            for match in re.finditer(pattern, text, re.IGNORECASE):
                groups = match.groups()
                # Determine which group is the number and which is the name
                if groups[0][0].isdigit():
                    mg_str, drug = groups[0], groups[1]
                else:
                    drug, mg_str = groups[0], groups[1]

                try:
                    mg = float(mg_str)
                except ValueError:
                    continue

                key = f"{drug.lower()}:{mg}"
                if key not in seen:
                    seen.add(key)
                    results.append((drug, mg))

        return results
