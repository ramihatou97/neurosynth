"""
Anatomical Region Detector for NeuroSynth
==========================================
Detects and tags anatomical regions in extracted medical images
based on caption text, surrounding context, and image classification.

Version: 1.0
"""

import logging
import re
from dataclasses import dataclass, field
from typing import Optional

from neurosynth.models.visual import ImageType

from .anatomical_regions import (
    ALL_REGIONS,
    REGION_BY_ID,
    AnatomicalRegion,
    RegionCategory,
)

logger = logging.getLogger("RegionDetector")


@dataclass
class RegionMatch:
    """A detected anatomical region with confidence score."""

    region_id: str
    region_name: str
    category: RegionCategory
    confidence: float  # 0.0 - 1.0
    matched_keywords: list[str] = field(default_factory=list)
    source: str = "caption"  # "caption", "context", or "combined"


class AnatomicalRegionDetector:
    """
    Detect anatomical regions from image captions and context.

    Uses keyword matching with context-aware scoring to identify
    specific neuroanatomical regions, vascular territories, and
    surgical corridors.
    """

    # Image types that should have region tagging
    TAGGABLE_IMAGE_TYPES = {
        ImageType.ANATOMICAL,
        ImageType.IMAGING,
        ImageType.SURGICAL_STEP,
        ImageType.ILLUSTRATION,
    }

    def __init__(self, min_confidence: float = 0.3):
        """
        Initialize the region detector.

        Args:
            min_confidence: Minimum confidence threshold for region detection
        """
        self.min_confidence = min_confidence
        self._build_keyword_index()

    def _build_keyword_index(self):
        """Build inverted index from keywords to regions."""
        self.keyword_to_regions: dict[str, list[tuple[str, float]]] = {}

        for region in ALL_REGIONS:
            # Primary keywords get higher weight
            for keyword in region.keywords:
                keyword_lower = keyword.lower()
                if keyword_lower not in self.keyword_to_regions:
                    self.keyword_to_regions[keyword_lower] = []
                self.keyword_to_regions[keyword_lower].append((region.id, 1.0))

            # Aliases get slightly lower weight
            for alias in region.aliases:
                alias_lower = alias.lower()
                if alias_lower not in self.keyword_to_regions:
                    self.keyword_to_regions[alias_lower] = []
                self.keyword_to_regions[alias_lower].append((region.id, 0.8))

        # Pre-compile regex patterns for each keyword
        self.keyword_patterns: dict[str, re.Pattern] = {}
        for keyword in self.keyword_to_regions.keys():
            # Word boundary matching for keywords
            escaped = re.escape(keyword)
            self.keyword_patterns[keyword] = re.compile(
                rf"\b{escaped}\b", re.IGNORECASE
            )

    def detect_regions(
        self, caption: str, context: str = "", image_type: ImageType | None = None
    ) -> list[str]:
        """
        Analyze caption and context to detect specific anatomical regions.

        Args:
            caption: Figure caption text
            context: Surrounding text from PDF
            image_type: Classified image type (from ImageType enum)

        Returns:
            List of detected region IDs (e.g., ["mca", "temporal_lobe"])
        """
        # Filter by image type if provided
        if image_type is not None:
            if image_type not in self.TAGGABLE_IMAGE_TYPES:
                logger.debug(f"Skipping region detection for image type: {image_type}")
                return []

        # Get detailed matches with confidence
        matches = self.detect_regions_detailed(caption, context, image_type)

        # Return just the region IDs
        return [m.region_id for m in matches]

    def detect_regions_detailed(
        self, caption: str, context: str = "", image_type: ImageType | None = None
    ) -> list[RegionMatch]:
        """
        Detect regions with detailed confidence information.

        Args:
            caption: Figure caption text
            context: Surrounding text from PDF
            image_type: Classified image type

        Returns:
            List of RegionMatch objects with confidence scores
        """
        region_scores: dict[str, RegionMatch] = {}

        # Analyze caption (higher weight)
        self._analyze_text(caption, region_scores, weight=1.0, source="caption")

        # Analyze context (lower weight)
        if context:
            self._analyze_text(context, region_scores, weight=0.5, source="context")

        # Apply context-aware boosting
        self._apply_context_boosts(region_scores, caption, context)

        # Filter by minimum confidence and sort by score
        results = [
            match
            for match in region_scores.values()
            if match.confidence >= self.min_confidence
        ]
        results.sort(key=lambda m: m.confidence, reverse=True)

        # Limit to top 5 regions to avoid over-tagging
        return results[:5]

    def _analyze_text(
        self,
        text: str,
        region_scores: dict[str, RegionMatch],
        weight: float = 1.0,
        source: str = "caption",
    ):
        """
        Analyze text for anatomical keywords and update scores.

        Args:
            text: Text to analyze
            region_scores: Dict to update with matches
            weight: Weight multiplier for this text source
            source: Label for match source
        """
        if not text:
            return

        text_lower = text.lower()

        for keyword, pattern in self.keyword_patterns.items():
            matches = pattern.findall(text_lower)
            if not matches:
                continue

            # Get regions associated with this keyword
            for region_id, keyword_weight in self.keyword_to_regions[keyword]:
                base_score = keyword_weight * weight * 0.3  # Base score per match

                if region_id in region_scores:
                    # Add to existing score
                    region_scores[region_id].confidence += base_score
                    if keyword not in region_scores[region_id].matched_keywords:
                        region_scores[region_id].matched_keywords.append(keyword)
                    region_scores[region_id].source = "combined"
                else:
                    # Create new match
                    region = REGION_BY_ID.get(region_id)
                    if region:
                        region_scores[region_id] = RegionMatch(
                            region_id=region_id,
                            region_name=region.name,
                            category=region.category,
                            confidence=base_score,
                            matched_keywords=[keyword],
                            source=source,
                        )

    def _apply_context_boosts(
        self, region_scores: dict[str, RegionMatch], caption: str, context: str
    ):
        """
        Apply context-aware scoring boosts.

        For example:
        - "middle cerebral" + "artery" → boost MCA confidence
        - Multiple related regions → boost parent region
        """
        combined_text = f"{caption} {context}".lower()

        # Boost vascular regions when "artery" or "aneurysm" present
        vascular_context = any(
            term in combined_text
            for term in ["artery", "arterial", "aneurysm", "vascular", "vessel"]
        )
        if vascular_context:
            for region_id, match in region_scores.items():
                if match.category == RegionCategory.VASCULAR:
                    match.confidence *= 1.3

        # Boost surgical corridors when approach keywords present
        approach_context = any(
            term in combined_text
            for term in ["approach", "exposure", "craniotomy", "surgical"]
        )
        if approach_context:
            for region_id, match in region_scores.items():
                if match.category == RegionCategory.SURGICAL_CORRIDOR:
                    match.confidence *= 1.3

        # Boost spine regions when spine-related terms present
        spine_context = any(
            term in combined_text
            for term in ["vertebra", "disc", "spinal", "laminectomy", "foraminotomy"]
        )
        if spine_context:
            for region_id, match in region_scores.items():
                if match.category == RegionCategory.SPINE:
                    match.confidence *= 1.2

        # Boost cranial nerves when nerve-related terms present
        nerve_context = any(
            term in combined_text
            for term in ["nerve", "palsy", "neuropathy", "cranial nerve"]
        )
        if nerve_context:
            for region_id, match in region_scores.items():
                if match.category == RegionCategory.CRANIAL_NERVE:
                    match.confidence *= 1.2

        # Cap confidence at 1.0
        for match in region_scores.values():
            match.confidence = min(match.confidence, 1.0)


# Singleton instance for easy access
_detector_instance: AnatomicalRegionDetector | None = None


def get_region_detector() -> AnatomicalRegionDetector:
    """Get or create the singleton region detector instance."""
    global _detector_instance
    if _detector_instance is None:
        _detector_instance = AnatomicalRegionDetector()
    return _detector_instance
