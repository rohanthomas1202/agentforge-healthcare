"""Drug safety verifier — cross-checks LLM response against the interaction DB.

Detects contradictions where the LLM claims drugs are safe to combine
but the interaction database says otherwise.
"""

import re

from app.tools.drug_interactions_db import (
    INTERACTIONS,
    DRUG_NAME_ALIASES,
    normalize_drug_name,
)

# Phrases indicating the LLM claims safety / no interaction
_SAFETY_PHRASES = [
    "safe to take together",
    "safe to combine",
    "safe combination",
    "no known interaction",
    "no significant interaction",
    "no interaction",
    "no concerning interaction",
    "generally safe",
    "compatible",
    "can be taken together",
    "no issues",
    "no major interaction",
    "no clinically significant",
]

# Phrases indicating the LLM correctly flags a risk
_RISK_PHRASES = [
    "interaction",
    "risk",
    "caution",
    "dangerous",
    "contraindicated",
    "avoid",
    "warning",
    "severe",
    "high risk",
    "bleeding",
    "serotonin syndrome",
    "monitor",
    "concern",
    "alert",
]


class DrugSafetyVerifier:
    """Verify drug-related claims in the LLM response against the interaction DB."""

    def __init__(self) -> None:
        # Build a set of all known drug names (generic + aliases)
        self._known_drugs: set[str] = set()
        for pair in INTERACTIONS:
            self._known_drugs.update(pair)
        self._known_drugs.update(DRUG_NAME_ALIASES.keys())

    def verify(
        self,
        response_text: str,
        tool_outputs: list[dict],
        tool_calls: list[dict],
    ) -> dict:
        """Check for drug safety contradictions.

        Returns:
            {
                "passed": bool,
                "flags": [{"drugs": [d1, d2], "issue": str, "severity": str}],
                "disclaimers": list[str],
            }
        """
        flags: list[dict] = []
        disclaimers: list[str] = []

        # 1. Extract all drug names mentioned in the response
        mentioned_drugs = self._extract_drugs(response_text)
        if len(mentioned_drugs) < 2:
            return {"passed": True, "flags": [], "disclaimers": []}

        # 2. Check all pairs against the interaction DB
        drug_list = list(mentioned_drugs)
        for i in range(len(drug_list)):
            for j in range(i + 1, len(drug_list)):
                d1, d2 = drug_list[i], drug_list[j]
                pair = frozenset({d1, d2})
                if pair not in INTERACTIONS:
                    continue

                interaction = INTERACTIONS[pair]
                severity = interaction["severity"]

                # 3. Check if the response contradicts the DB
                if self._response_contradicts(response_text, d1, d2):
                    flags.append({
                        "drugs": [d1, d2],
                        "issue": (
                            f"Response suggests {d1} and {d2} are safe, "
                            f"but database shows {severity} severity interaction: "
                            f"{interaction['description']}"
                        ),
                        "severity": severity,
                    })

        # 4. Check if drugs are mentioned but interaction tool was never called
        interaction_tool_used = any(
            tc.get("tool") == "drug_interaction_check" for tc in tool_calls
        )
        if not interaction_tool_used and len(mentioned_drugs) >= 2:
            # Check if any of the mentioned pairs actually have interactions
            unchecked_interactions = []
            for i in range(len(drug_list)):
                for j in range(i + 1, len(drug_list)):
                    pair = frozenset({drug_list[i], drug_list[j]})
                    if pair in INTERACTIONS:
                        sev = INTERACTIONS[pair]["severity"]
                        if sev in ("contraindicated", "high"):
                            unchecked_interactions.append(
                                (drug_list[i], drug_list[j], sev)
                            )

            for d1, d2, sev in unchecked_interactions:
                flags.append({
                    "drugs": [d1, d2],
                    "issue": (
                        f"Drug interaction check was not performed, "
                        f"but {d1} and {d2} have a {sev} severity interaction in the database."
                    ),
                    "severity": sev,
                })

        # 5. Build disclaimers for critical flags
        critical_flags = [
            f for f in flags if f["severity"] in ("contraindicated", "high")
        ]
        if critical_flags:
            drug_pairs = [
                f"{f['drugs'][0]} and {f['drugs'][1]}" for f in critical_flags
            ]
            disclaimers.append(
                "SAFETY ALERT: Potential drug interaction concern detected "
                f"({', '.join(drug_pairs)}). "
                "Please consult a pharmacist or healthcare provider for guidance."
            )

        passed = len(critical_flags) == 0
        return {"passed": passed, "flags": flags, "disclaimers": disclaimers}

    def _extract_drugs(self, text: str) -> set[str]:
        """Find all known drug names mentioned in text, normalized to generic."""
        text_lower = text.lower()
        found: set[str] = set()
        for drug in self._known_drugs:
            pattern = r"\b" + re.escape(drug) + r"\b"
            if re.search(pattern, text_lower):
                found.add(normalize_drug_name(drug))
        return found

    def _response_contradicts(
        self, response_text: str, drug1: str, drug2: str
    ) -> bool:
        """Return True if response says these drugs are safe but DB says they interact."""
        text_lower = response_text.lower()

        # Find sentences mentioning both drugs
        sentences = re.split(r"[.!?\n]", text_lower)
        relevant = []
        for s in sentences:
            p1 = r"\b" + re.escape(drug1) + r"\b"
            p2 = r"\b" + re.escape(drug2) + r"\b"
            if re.search(p1, s) and re.search(p2, s):
                relevant.append(s)

        if not relevant:
            return False

        for sentence in relevant:
            claims_safe = any(phrase in sentence for phrase in _SAFETY_PHRASES)
            acknowledges_risk = any(phrase in sentence for phrase in _RISK_PHRASES)
            if claims_safe and not acknowledges_risk:
                return True

        return False
