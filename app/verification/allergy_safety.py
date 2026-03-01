"""Allergy safety verifier — checks if the LLM response recommends medications
that conflict with a patient's documented allergies.

Works by extracting patient allergy data from tool outputs and checking if the
response recommends any contraindicated medications without proper warnings.
"""

import re

from app.tools.allergy_checker import ALLERGY_DRUG_CLASS_MAP, normalize_substance


class AllergySafetyVerifier:
    """Verify allergy-related claims in the LLM response."""

    def verify(
        self,
        response_text: str,
        tool_outputs: list[dict],
        tool_calls: list[dict],
    ) -> dict:
        """Check for allergy safety issues in the response.

        Returns:
            {
                "passed": bool,
                "flags": [{"allergy": str, "drug": str, "issue": str}],
                "disclaimers": list[str],
            }
        """
        flags: list[dict] = []
        disclaimers: list[str] = []

        # Extract allergy information from tool outputs
        patient_allergies = self._extract_allergies_from_outputs(tool_outputs)
        if not patient_allergies:
            return {"passed": True, "flags": [], "disclaimers": []}

        # Extract medication recommendations from the response
        response_lower = response_text.lower()

        for allergy_substance in patient_allergies:
            norm = _normalize_substance(allergy_substance)
            class_info = ALLERGY_DRUG_CLASS_MAP.get(norm)
            if not class_info:
                continue

            # Check if any drugs in this class are mentioned positively
            for drug in class_info["drugs"]:
                pattern = r"\b" + re.escape(drug) + r"\b"
                if not re.search(pattern, response_lower):
                    continue

                # Drug is mentioned — check if it's a recommendation without warning
                if self._is_recommended_without_warning(
                    response_text, drug, allergy_substance
                ):
                    flags.append({
                        "allergy": allergy_substance,
                        "drug": drug,
                        "class": class_info["class_name"],
                        "issue": (
                            f"Response mentions {drug} but patient has "
                            f"documented allergy to {allergy_substance} "
                            f"({class_info['class_name']}). "
                            "No allergy warning was included."
                        ),
                    })

        if flags:
            drug_pairs = [
                f"{f['drug']} (allergy: {f['allergy']})" for f in flags
            ]
            disclaimers.append(
                "ALLERGY SAFETY ALERT: Potential allergy conflict detected — "
                f"{', '.join(drug_pairs)}. "
                "Verify allergy status before administering."
            )

        return {
            "passed": len(flags) == 0,
            "flags": flags,
            "disclaimers": disclaimers,
        }

    def _extract_allergies_from_outputs(
        self, tool_outputs: list[dict]
    ) -> list[str]:
        """Extract allergy substance names from tool outputs."""
        allergies: list[str] = []
        for output in tool_outputs:
            text = output.get("output", "")
            # Look for allergy sections in patient_summary output
            if "Allergies" in text:
                # Parse allergy lines like "  • Penicillin [Criticality: high]"
                for match in re.finditer(
                    r"[•\-]\s*(.+?)(?:\s*\[|$)", text, re.MULTILINE
                ):
                    substance = match.group(1).strip()
                    if substance and substance not in ("No known allergies (NKA).",):
                        # Remove category info in parentheses
                        substance = re.sub(r"\s*\(.*?\)\s*$", "", substance)
                        allergies.append(substance)

            # Also parse allergy_check output
            if "Documented Allergies" in text:
                for match in re.finditer(
                    r"-\s*(.+?)(?:\s*\(|$)", text, re.MULTILINE
                ):
                    substance = match.group(1).strip()
                    if substance and substance != "Unknown":
                        allergies.append(substance)

        return list(set(allergies))

    def _is_recommended_without_warning(
        self, response_text: str, drug: str, allergy: str
    ) -> bool:
        """Check if a drug is recommended in the response without allergy warning."""
        text_lower = response_text.lower()

        # Warning phrases that indicate the response properly flags the issue
        warning_phrases = [
            "allerg", "contraindicated", "avoid", "do not",
            "should not", "cannot take", "not recommended",
            "cross-react", "class conflict", "caution",
            "allergic", "sensitivity",
        ]

        # Find sentences mentioning the drug
        sentences = re.split(r"[.!?\n]", text_lower)
        for idx, sentence in enumerate(sentences):
            if re.search(r"\b" + re.escape(drug) + r"\b", sentence):
                # If the sentence also contains a warning, it's properly flagged
                if any(wp in sentence for wp in warning_phrases):
                    return False
                # Check if allergy is mentioned nearby (within 2 sentences)
                # This is a loose check to avoid false positives
                context = " ".join(
                    sentences[max(0, idx - 1): min(len(sentences), idx + 2)]
                )
                if any(wp in context for wp in warning_phrases):
                    return False

        # If the drug is mentioned without any warning context, flag it
        # But only if it seems like a recommendation (not just listing)
        recommend_phrases = [
            "prescribe", "recommend", "take", "start", "try",
            "consider", "use", "administer",
        ]
        for sentence in sentences:
            if re.search(r"\b" + re.escape(drug) + r"\b", sentence):
                if any(rp in sentence for rp in recommend_phrases):
                    return True

        return False
