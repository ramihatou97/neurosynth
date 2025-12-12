"""Hybrid Intent Classification Module.

Combines fast lean keyword-based detection with optional AI fallback:
1. First tries lean detection (fast, free, works offline)
2. Falls back to Claude API for ambiguous queries (if enabled)
"""

from dataclasses import dataclass
from enum import Enum
from typing import List, Optional

from .query_intent_lean import IntentDetector as LeanIntentDetector
from .query_intent_lean import IntentResult as LeanIntentResult
from .query_intent_lean import QueryIntent, get_intent_detector


@dataclass
class HybridIntentResult:
    """Result of hybrid intent classification."""

    original_query: str
    cleaned_query: str
    intent: QueryIntent
    suggested_sections: list[str]
    confidence: float  # 0.0 - 1.0
    source: str  # "lean" or "ai"
    reasoning: str = ""

    @property
    def is_specific(self) -> bool:
        """Check if intent is specific (not GENERAL)."""
        return self.intent != QueryIntent.GENERAL


class HybridIntentClassifier:
    """Unified intent classifier with lean + AI fallback."""

    def __init__(self, database=None, api_key: str | None = None):
        """Initialize classifier.

        Args:
            database: Optional database for caching AI results
            api_key: Optional Anthropic API key for AI fallback
        """
        self.lean_detector = get_intent_detector()
        self.database = database
        self.api_key = api_key
        self._ai_classifier = None

    def _get_ai_classifier(self):
        """Lazy-load AI classifier."""
        if self._ai_classifier is None and self.api_key:
            try:
                from reference_library.ai.query_intent import QueryIntentClassifier

                self._ai_classifier = QueryIntentClassifier(
                    api_key=self.api_key, database=self.database
                )
            except ImportError:
                pass
        return self._ai_classifier

    def classify(
        self, query: str, use_ai: bool = False, confidence_threshold: float = 0.7
    ) -> HybridIntentResult:
        """Classify query intent.

        Args:
            query: Search query string
            use_ai: Whether to use AI fallback for ambiguous queries
            confidence_threshold: Confidence below which AI is used

        Returns:
            HybridIntentResult with intent classification
        """
        if not query or not query.strip():
            return HybridIntentResult(
                original_query=query,
                cleaned_query=query,
                intent=QueryIntent.GENERAL,
                suggested_sections=[],
                confidence=0.0,
                source="lean",
                reasoning="Empty query",
            )

        # 1. Try lean detection first (always)
        lean_result = self.lean_detector.detect(query)

        # Calculate confidence based on intent type
        # GENERAL = low confidence, specific intents = high confidence
        lean_confidence = 0.9 if lean_result.intent != QueryIntent.GENERAL else 0.5

        # 2. If confident enough OR AI disabled, return lean result
        if not use_ai or lean_confidence >= confidence_threshold:
            return HybridIntentResult(
                original_query=lean_result.original_query,
                cleaned_query=lean_result.cleaned_query,
                intent=lean_result.intent,
                suggested_sections=lean_result.suggested_sections,
                confidence=lean_confidence,
                source="lean",
                reasoning=f"Keyword match: {lean_result.intent.value}",
            )

        # 3. Use AI for ambiguous GENERAL intent
        ai_classifier = self._get_ai_classifier()
        if ai_classifier is None:
            # No AI available, return lean result
            return HybridIntentResult(
                original_query=lean_result.original_query,
                cleaned_query=lean_result.cleaned_query,
                intent=lean_result.intent,
                suggested_sections=lean_result.suggested_sections,
                confidence=lean_confidence,
                source="lean",
                reasoning="AI unavailable, using keyword detection",
            )

        try:
            ai_result = ai_classifier.classify(query)

            # Map AI intent to our QueryIntent enum
            mapped_intent = self._map_ai_intent(ai_result.intent)

            return HybridIntentResult(
                original_query=query,
                cleaned_query=lean_result.cleaned_query,  # Use lean's cleaned query
                intent=mapped_intent,
                suggested_sections=lean_result.suggested_sections,
                confidence=ai_result.confidence,
                source="ai",
                reasoning=ai_result.reasoning,
            )
        except Exception as e:
            # AI failed, return lean result
            return HybridIntentResult(
                original_query=lean_result.original_query,
                cleaned_query=lean_result.cleaned_query,
                intent=lean_result.intent,
                suggested_sections=lean_result.suggested_sections,
                confidence=lean_confidence,
                source="lean",
                reasoning=f"AI error ({e}), using keyword detection",
            )

    def _map_ai_intent(self, ai_intent: str) -> QueryIntent:
        """Map AI intent string to QueryIntent enum."""
        mapping = {
            "SURGICAL_TECHNIQUE": QueryIntent.TECHNIQUE,
            "CLINICAL_KNOWLEDGE": QueryIntent.GENERAL,  # Map to GENERAL for now
            "MIXED": QueryIntent.GENERAL,
        }
        return mapping.get(ai_intent, QueryIntent.GENERAL)


# Module-level singleton
_hybrid_classifier: HybridIntentClassifier | None = None


def get_hybrid_classifier(
    database=None, api_key: str | None = None
) -> HybridIntentClassifier:
    """Get singleton HybridIntentClassifier."""
    global _hybrid_classifier
    if _hybrid_classifier is None:
        _hybrid_classifier = HybridIntentClassifier(database=database, api_key=api_key)
    return _hybrid_classifier
