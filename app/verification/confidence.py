"""Confidence scorer — rates response reliability from 0.0 to 1.0.

Analyzes tool outputs, data richness, and response language to compute
a deterministic confidence score without any LLM calls.
"""

import re

# Phrases in tool outputs indicating missing or empty data
_ERROR_PHRASES = [
    "error",
    "no patient found",
    "not found",
    "no results",
    "no conditions on record",
    "no medications on record",
    "no known allergies",
    "no immunization records",
    "no recent lab results",
    "no providers found",
    "no appointments",
    "no available slots",
    "no upcoming appointments",
    "unavailable",
    "at least 2 medications are needed",
    "try a broader search",
    "check the spelling",
]

# Phrases in the response indicating uncertainty
_HEDGING_PHRASES = [
    "i'm not sure",
    "i cannot confirm",
    "i don't have enough",
    "i was unable to",
    "the data is incomplete",
    "no information available",
    "could not find",
    "i couldn't find",
    "unable to retrieve",
    "there may be",
    "i believe",
    "it's possible",
    "might be",
    "i don't have access",
    "not available in",
    "no data",
]


class ConfidenceScorer:
    """Compute a deterministic confidence score for the agent response."""

    def score(
        self,
        response_text: str,
        tool_outputs: list[dict],
        tool_calls: list[dict],
    ) -> dict:
        """Compute a confidence score and factor breakdown.

        Returns:
            {
                "score": float (0.0–1.0),
                "factors": {
                    "tools_used": float,
                    "data_richness": float,
                    "response_hedging": float,
                    "tool_error_rate": float,
                },
                "disclaimers": list[str],
            }
        """
        f_tools = self._score_tools_used(tool_outputs, tool_calls)
        f_richness = self._score_data_richness(tool_outputs)
        f_hedging = self._score_hedging(response_text)
        f_errors = self._score_tool_errors(tool_outputs)

        # Weighted average
        score = (
            f_tools * 0.30
            + f_richness * 0.30
            + f_hedging * 0.20
            + f_errors * 0.20
        )
        score = max(0.0, min(1.0, score))

        factors = {
            "tools_used": round(f_tools, 2),
            "data_richness": round(f_richness, 2),
            "response_hedging": round(f_hedging, 2),
            "tool_error_rate": round(f_errors, 2),
        }

        disclaimers: list[str] = []
        if score < 0.3:
            disclaimers.append(
                "LOW CONFIDENCE: This response has limited data backing. "
                "Please verify information with your healthcare provider."
            )
        elif score < 0.6:
            disclaimers.append(
                "MODERATE CONFIDENCE: Some data was unavailable or incomplete. "
                "Important details may be missing."
            )

        return {
            "score": round(score, 2),
            "factors": factors,
            "disclaimers": disclaimers,
        }

    def _score_tools_used(
        self, tool_outputs: list[dict], tool_calls: list[dict]
    ) -> float:
        """Score based on whether tools were called and succeeded."""
        if not tool_calls:
            # No tools needed (general question) — neutral
            return 0.5

        if not tool_outputs:
            # Tools called but no output captured
            return 0.3

        # At least some tools ran
        return 1.0

    def _score_data_richness(self, tool_outputs: list[dict]) -> float:
        """Proportion of tool outputs containing substantive data."""
        if not tool_outputs:
            return 0.5  # No tools needed, neutral

        good = 0
        for output in tool_outputs:
            text = output["output"].lower()
            error_count = sum(1 for phrase in _ERROR_PHRASES if phrase in text)
            has_data = len(output["output"]) > 100
            # A long output with only a few error phrases is still good data
            # (e.g., patient summary with "no immunization records" is still rich)
            if has_data and error_count <= 2:
                good += 1
            elif has_data and len(output["output"]) > 500:
                # Very long output is likely rich even with some error phrases
                good += 0.7

        return min(1.0, good / len(tool_outputs)) if tool_outputs else 0.5

    def _score_hedging(self, response_text: str) -> float:
        """Score based on uncertainty language in the response."""
        text_lower = response_text.lower()
        hedging_count = sum(
            1 for phrase in _HEDGING_PHRASES if phrase in text_lower
        )
        # Each hedging phrase reduces score by 0.15
        return max(0.2, 1.0 - hedging_count * 0.15)

    def _score_tool_errors(self, tool_outputs: list[dict]) -> float:
        """Score based on fraction of tool outputs without errors."""
        if not tool_outputs:
            return 0.5  # Neutral when no tools used

        error_count = 0
        for output in tool_outputs:
            text = output["output"].lower()
            phrase_hits = sum(1 for phrase in _ERROR_PHRASES if phrase in text)
            has_data = len(output["output"]) > 200
            # Only count as error if it's a short output dominated by error phrases
            # or has 3+ error indicators
            if phrase_hits >= 3 or (phrase_hits > 0 and not has_data):
                error_count += 1

        return 1.0 - (error_count / len(tool_outputs))
