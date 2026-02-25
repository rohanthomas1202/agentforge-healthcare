"""Medical claim verifier — hallucination detection via grounding checks.

Extracts factual claims from the LLM response and verifies each one
is supported by actual tool output data.
"""

import re
from typing import Optional

# Regex patterns for extractable medical claims
_CLAIM_PATTERNS = [
    # "Patient has [condition]"
    r"(?:patient|they|he|she)\s+(?:has|have|is diagnosed with|suffers from)\s+([^.,;!?\n]+)",
    # "currently taking [medication]"
    r"(?:currently|is|are)\s+(?:taking|prescribed|on)\s+([^.,;!?\n]+)",
    # "allergic to [substance]"
    r"(?:allergic|allergy)\s+to\s+([^.,;!?\n]+)",
    # Specific measurements
    r"(?:blood pressure|bp|heart rate|temperature|weight|bmi|a1c|hba1c)\s+(?:is|was|of)\s+([\d./]+[^.,;!?\n]*)",
    # Severity claims
    r"(?:severity|risk)\s+(?:is|level:?\s*)\s*(contraindicated|high|moderate|low)",
    # Bold items from markdown (e.g., **Metformin 500 MG**)
    r"\*\*([A-Z][a-zA-Z\s]+\d+\s*(?:MG|mg|mcg|ML|ml)[^*]*)\*\*",
    # Conditions listed (e.g., **Type 2 diabetes mellitus**)
    r"\*\*([A-Z][a-zA-Z\s]+(?:mellitus|hypertension|disease|disorder|syndrome|failure|asthma|anxiety|fibrillation)[^*]*)\*\*",
    # "Date of Birth:" or "Gender:" factual claims
    r"(?:Date of Birth|DOB|Gender|Contact|Address):\*?\*?\s*([^\n]+)",
    # Drug interaction results
    r"(?:interaction|interacts?)\s+(?:between|with)\s+([^.,;!?\n]+)",
]

# Common stop words to exclude from key-term matching
_STOP_WORDS = frozenset({
    "this", "that", "with", "from", "have", "been", "they", "their",
    "which", "about", "should", "would", "could", "also", "very",
    "currently", "patient", "taking", "prescribed", "some", "more",
    "than", "will", "there", "here", "into", "when", "what", "your",
    "does", "were", "being", "each", "other", "most", "only", "over",
    "such", "after", "before", "between", "these", "those", "then",
    "them", "just", "like", "well", "however", "following", "include",
    "includes", "including", "based", "note", "please",
})


class ClaimVerifier:
    """Verify that medical claims in the response are grounded in tool outputs."""

    def verify(
        self,
        response_text: str,
        tool_outputs: list[dict],
        tool_calls: list[dict],
    ) -> dict:
        """Verify claims in the response against tool outputs.

        Returns:
            {
                "passed": bool,
                "grounded_claims": int,
                "ungrounded_claims": int,
                "total_claims": int,
                "grounding_rate": float,
                "details": [{"claim": str, "grounded": bool, "source_tool": str|None}],
                "disclaimers": list[str],
            }
        """
        # If no tools were called, be lenient — this is a general knowledge query
        if not tool_outputs:
            return {
                "passed": True,
                "grounded_claims": 0,
                "ungrounded_claims": 0,
                "total_claims": 0,
                "grounding_rate": 1.0,
                "details": [],
                "disclaimers": [],
            }

        # Extract claims from the response
        claims = self._extract_claims(response_text)
        if not claims:
            return {
                "passed": True,
                "grounded_claims": 0,
                "ungrounded_claims": 0,
                "total_claims": 0,
                "grounding_rate": 1.0,
                "details": [],
                "disclaimers": [],
            }

        # Check each claim against tool outputs
        details: list[dict] = []
        grounded = 0
        ungrounded = 0

        for claim in claims:
            is_grounded, source = self._is_claim_grounded(claim, tool_outputs)
            details.append({
                "claim": claim,
                "grounded": is_grounded,
                "source_tool": source,
            })
            if is_grounded:
                grounded += 1
            else:
                ungrounded += 1

        total = grounded + ungrounded
        rate = grounded / total if total > 0 else 1.0
        passed = rate >= 0.5 or total == 0

        disclaimers: list[str] = []
        if ungrounded > 0 and rate < 0.7:
            disclaimers.append(
                f"GROUNDING WARNING: {ungrounded} claim(s) in this response "
                "could not be verified against medical records data. "
                "These may be general knowledge rather than patient-specific facts."
            )

        return {
            "passed": passed,
            "grounded_claims": grounded,
            "ungrounded_claims": ungrounded,
            "total_claims": total,
            "grounding_rate": round(rate, 2),
            "details": details,
            "disclaimers": disclaimers,
        }

    def _extract_claims(self, text: str) -> list[str]:
        """Extract factual medical claims from response text."""
        claims: list[str] = []
        seen: set[str] = set()

        for pattern in _CLAIM_PATTERNS:
            for match in re.finditer(pattern, text, re.IGNORECASE):
                claim = match.group(1).strip() if match.lastindex else match.group(0).strip()
                # Skip very short or very long matches (likely noise)
                if len(claim) < 3 or len(claim) > 200:
                    continue
                claim_lower = claim.lower()
                if claim_lower not in seen:
                    seen.add(claim_lower)
                    claims.append(claim)

        return claims

    def _is_claim_grounded(
        self, claim: str, tool_outputs: list[dict]
    ) -> tuple[bool, Optional[str]]:
        """Check if a claim is supported by tool output.

        A claim is grounded if >= 60% of its key terms appear in at least
        one tool's output.
        """
        claim_lower = claim.lower().strip()

        # Extract key terms (words > 3 chars, excluding stop words)
        key_terms = [
            w
            for w in re.findall(r"[a-z]+", claim_lower)
            if len(w) > 3 and w not in _STOP_WORDS
        ]

        if not key_terms:
            return True, None  # No verifiable content

        # Check each tool output for term matches
        for output in tool_outputs:
            output_lower = output["output"].lower()
            matches = sum(1 for term in key_terms if term in output_lower)
            if matches >= len(key_terms) * 0.6:
                return True, output["tool_name"]

        return False, None
