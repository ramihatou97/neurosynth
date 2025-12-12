"""Lean Intent Detection module.

Classifies user queries into intents (Technique, Complication, etc.)
based on keyword matching at the END of the query.
"""

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Set


class QueryIntent(Enum):
    """User intent categories."""

    GENERAL = "general"
    TECHNIQUE = "technique"
    COMPLICATION = "complication"
    ANATOMY = "anatomy"
    INDICATION = "indication"
    OUTCOME = "outcome"


@dataclass
class IntentResult:
    """Result of intent detection."""

    original_query: str
    cleaned_query: str  # Query with intent keywords removed
    intent: QueryIntent
    suggested_sections: list[str]  # Section headers to prioritize


class IntentDetector:
    """Simple keyword-based intent detector."""

    # Keywords that signal specific intents
    # Only matched at the END of the query
    INTENT_KEYWORDS: dict[QueryIntent, set[str]] = {
        QueryIntent.TECHNIQUE: {
            "technique",
            "techniques",
            "procedure",
            "procedures",
            "steps",
            "operative",
            "surgery",
            "surgical",
            "approach",
            "approaches",
            "how to",
            "method",
            "methods",
        },
        QueryIntent.COMPLICATION: {
            "complication",
            "complications",
            "risk",
            "risks",
            "avoidance",
            "prevention",
            "management",
            "safety",
            "pitfalls",
            "hazards",
            "adverse events",
            "failure",
        },
        QueryIntent.ANATOMY: {
            "anatomy",
            "anatomical",
            "structure",
            "structures",
            "course",
            "relationship",
            "relationships",
            "nerve",
            "artery",
            "vein",
            "location",
            "position",
        },
        QueryIntent.INDICATION: {
            "indication",
            "indications",
            "contraindication",
            "contraindications",
            "selection",
            "patient selection",
            "criteria",
            "when to",
            "decision",
        },
        QueryIntent.OUTCOME: {
            "outcome",
            "outcomes",
            "prognosis",
            "results",
            "survival",
            "recurrence",
            "recovery",
            "follow-up",
        },
    }

    # Strong keywords that trigger intent regardless of position
    STRONG_KEYWORDS: dict[QueryIntent, set[str]] = {
        QueryIntent.TECHNIQUE: {"how to", "surgical steps", "operative steps"},
        QueryIntent.COMPLICATION: {
            "complication",
            "complications",
            "pitfall",
            "pitfalls",
            "morbidity",
            "mortality",
            "adverse event",
            "adverse events",
        },
        QueryIntent.INDICATION: {
            "indication",
            "indications",
            "contraindication",
            "contraindications",
            "patient selection",
            "selection criteria",
            "when to",
        },
        QueryIntent.ANATOMY: {"anatomy", "anatomical", "landmark", "landmarks"},
        QueryIntent.OUTCOME: {"outcome", "outcomes", "prognosis", "survival rate"},
    }

    # Map intents to likely section headers in textbooks
    SECTION_MAP: dict[QueryIntent, list[str]] = {
        QueryIntent.TECHNIQUE: [
            "Surgical Technique",
            "Operative Technique",
            "Procedure",
            "Surgical Steps",
            "Operative Nuances",
            "Technique",
        ],
        QueryIntent.COMPLICATION: [
            "Complications",
            "Complication Avoidance",
            "Postoperative Management",
            "Avoidance of Complications",
            "Risks",
        ],
        QueryIntent.ANATOMY: [
            "Surgical Anatomy",
            "Anatomy",
            "Relevant Anatomy",
            "Anatomical Considerations",
        ],
        QueryIntent.INDICATION: [
            "Indications",
            "Patient Selection",
            "Clinical Presentation",
            "Contraindications",
            "Decision Making",
        ],
        QueryIntent.OUTCOME: ["Outcomes", "Results", "Prognosis", "Long-term Results"],
    }

    # Keywords that should NOT be stripped even if they match an intent
    # e.g., "pterional approach" -> "approach" is part of the name
    PROTECTED_PHRASES: set[str] = {"approach", "approaches"}

    def detect(self, query: str) -> IntentResult:
        """Detect intent and return cleaned query."""
        query = query.strip()
        query_lower = query.lower()

        best_intent = QueryIntent.GENERAL
        cleaned_query = query
        longest_match_len = 0

        # 1. Check STRONG keywords anywhere in the query
        for intent, keywords in self.STRONG_KEYWORDS.items():
            for keyword in keywords:
                pattern = r"\b" + re.escape(keyword) + r"\b"
                if re.search(pattern, query_lower):
                    # Found strong keyword - this wins
                    # We still want to clean the query if possible, but maybe not?
                    # For "contraindications for surgery", if we strip "contraindications", we get "for surgery".
                    # Let's keep the original query as cleaned for now, or try to strip the keyword.

                    # Simple strip: remove the keyword
                    cleaned = re.sub(pattern, "", query_lower).strip()
                    # Clean up extra spaces/prepositions
                    cleaned = re.sub(r"\s+(for|of|in|to)\s*$", "", cleaned).strip()
                    cleaned = re.sub(r"^\s*(for|of|in|to)\s+", "", cleaned).strip()

                    if not cleaned:
                        cleaned = query  # Fallback if everything removed

                    return IntentResult(
                        original_query=query,
                        cleaned_query=cleaned,
                        intent=intent,
                        suggested_sections=self.SECTION_MAP.get(intent, []),
                    )

        # 2. Check END keywords (Standard Logic)
        for intent, keywords in self.INTENT_KEYWORDS.items():
            for keyword in keywords:
                # Check if query ends with this keyword
                # Ensure word boundary
                pattern = r"\b" + re.escape(keyword) + r"$"
                match = re.search(pattern, query_lower)

                if match:
                    # Found a match at the end
                    # Check if it's a protected phrase that shouldn't be stripped
                    # Logic: If it's "approach", we only strip it if the user explicitly
                    # asks for "approaches to X" (start) or "X approaches" (end).
                    # But "pterional approach" is a specific entity.

                    # For MVP: "approach" is tricky.
                    # If query is "pterional approach", intent IS technique,
                    # but we shouldn't strip "approach" because "pterional" is too vague?
                    # Actually, "pterional" usually implies the approach.
                    # But let's follow the plan: "pterional approach" -> "pterional approach" (don't strip)

                    if keyword in self.PROTECTED_PHRASES:
                        # Don't strip, but DO set intent
                        if len(keyword) > longest_match_len:
                            longest_match_len = len(keyword)
                            best_intent = intent
                            # cleaned_query remains original
                    else:
                        # Strip it
                        if len(keyword) > longest_match_len:
                            longest_match_len = len(keyword)
                            best_intent = intent
                            # Remove keyword from end
                            cleaned_query = query[: match.start()].strip()

        return IntentResult(
            original_query=query,
            cleaned_query=cleaned_query,
            intent=best_intent,
            suggested_sections=self.SECTION_MAP.get(best_intent, []),
        )


# Module-level singleton
_detector: IntentDetector | None = None


def get_intent_detector() -> IntentDetector:
    """Get singleton IntentDetector."""
    global _detector
    if _detector is None:
        _detector = IntentDetector()
    return _detector
