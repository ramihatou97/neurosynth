"""Search Strategy Configuration Module.

Defines STRICT / STANDARD / BROAD search strategies that control:
- Query expansion behavior
- Intent detection method
- Authority thresholds
- Result filtering
"""

from dataclasses import dataclass
from typing import Dict


@dataclass
class SearchStrategy:
    """Configuration for search behavior.

    Controls how queries are expanded, filtered, and scored.
    """

    name: str
    display_name: str
    description: str

    # === Query Expansion ===
    expand_synonyms: bool = True
    expand_orthographic: bool = True  # disc/disk, etc.
    max_expansions: int = 10

    # === Intent Detection ===
    use_intent_detection: bool = True
    use_ai_intent: bool = False  # Use Claude API for complex cases
    intent_confidence_threshold: float = 0.7  # Below this, use AI fallback

    # === Authority ===
    authority_threshold: int = 0  # Min authority to include (0-100)
    prefer_primary_sources: bool = True
    authority_boost_weight: float = 0.5  # How much authority affects score

    # === Section Detection ===
    use_section_detection: bool = True
    section_boost_weight: float = 1.0  # Boost for matching intent section

    # === Results ===
    max_results: int = 50
    min_relevance_score: float = 0.0

    # === Semantic Search ===
    use_semantic: bool = True
    semantic_threshold: float = 0.5


# Pre-defined strategies
STRICT = SearchStrategy(
    name="strict",
    display_name="🎯 Strict",
    description="Exact matches only. High precision, orthographic variants only.",
    # Query Expansion - Only orthographic (disc/disk) for STRICT
    expand_synonyms=False,
    expand_orthographic=True,  # Enable disc/disk, tumour/tumor variants
    max_expansions=2,  # Original + 1 orthographic variant
    # Intent Detection - DISABLED: rely on exact title matching
    use_intent_detection=False,
    use_ai_intent=False,
    # Authority - DISABLED: All neurosurgical references treated equally
    authority_threshold=0,  # No authority filtering
    prefer_primary_sources=False,
    authority_boost_weight=0.0,  # Authority doesn't affect ranking
    # Section Detection - ENABLED for precise targeting
    use_section_detection=True,
    section_boost_weight=1.5,  # High weight - prioritize exact section matches
    # Results
    max_results=30,  # Allow more results since filtering is tighter
    min_relevance_score=40.0,  # Slightly lower threshold
    # Semantic - DISABLED for keyword precision
    use_semantic=False,
    semantic_threshold=0.8,
)

STANDARD = SearchStrategy(
    name="standard",
    display_name="⚖️ Standard",
    description="Balanced search with intelligent expansion and ranking.",
    # Query Expansion - disabled synonyms for performance, only orthographic
    expand_synonyms=False,
    expand_orthographic=True,
    max_expansions=2,  # Just original + 1 variant
    # Intent Detection
    use_intent_detection=True,
    use_ai_intent=False,  # Lean detection only for speed
    intent_confidence_threshold=0.7,
    # Authority
    authority_threshold=0,
    prefer_primary_sources=True,
    authority_boost_weight=0.5,
    # Section Detection
    use_section_detection=True,
    section_boost_weight=1.0,
    # Results
    max_results=50,
    min_relevance_score=0.0,
    # Semantic
    use_semantic=True,
    semantic_threshold=0.5,
)

BROAD = SearchStrategy(
    name="broad",
    display_name="🌐 Broad",
    description="Maximum recall. Includes all matching sources.",
    # Query Expansion - disabled synonyms for performance, only orthographic
    expand_synonyms=False,
    expand_orthographic=True,
    max_expansions=2,  # Just original + 1 variant
    # Intent Detection
    use_intent_detection=True,
    use_ai_intent=False,  # Disabled for performance
    intent_confidence_threshold=0.5,
    # Authority
    authority_threshold=0,
    prefer_primary_sources=False,
    authority_boost_weight=0.3,
    # Section Detection
    use_section_detection=True,
    section_boost_weight=0.5,  # Less emphasis on section matching
    # Results
    max_results=100,
    min_relevance_score=0.0,
    # Semantic
    use_semantic=True,
    semantic_threshold=0.3,  # Lower threshold = more results
)


# Strategy lookup dictionary
STRATEGIES: dict[str, SearchStrategy] = {
    "strict": STRICT,
    "standard": STANDARD,
    "broad": BROAD,
}


def get_strategy(name: str) -> SearchStrategy:
    """Get a strategy by name.

    Args:
        name: Strategy name ('strict', 'standard', 'broad')

    Returns:
        SearchStrategy configuration

    Raises:
        KeyError if strategy not found
    """
    return STRATEGIES[name.lower()]


def get_strategy_names() -> list[str]:
    """Get list of available strategy names."""
    return list(STRATEGIES.keys())


def get_strategy_display_names() -> list[str]:
    """Get list of display names for UI."""
    return [s.display_name for s in STRATEGIES.values()]
