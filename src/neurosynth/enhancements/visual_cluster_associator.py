"""
Enhanced Visual Cluster Associator v3.1
========================================
Associates images with text content using multiple scoring methods:
- Spatial proximity with actual bbox distance
- Neurosurgical keyword relevance scoring (5-category weighted)
- Context analysis (references, demonstratives)
- Cross-reference linking

ALL WEIGHTS ARE CENTRALIZED IN config.py
Do not hardcode weights in this module.

Version: 3.1 (weight centralization)
"""

import logging
import math
import re
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any

from .config import ImageCategory, NeuroSynthEnhancedConfig

logger = logging.getLogger(__name__)


# =============================================================================
# DATA STRUCTURES
# =============================================================================


@dataclass
class TextBlock:
    """A block of text with position and metadata."""

    text: str
    bbox: tuple[float, float, float, float]
    page_number: int
    block_type: str = "paragraph"  # paragraph, heading, caption, list
    font_size: float = 12.0
    is_bold: bool = False
    is_italic: bool = False

    @property
    def center(self) -> tuple[float, float]:
        x0, y0, x1, y1 = self.bbox
        return ((x0 + x1) / 2, (y0 + y1) / 2)

    @property
    def area(self) -> float:
        x0, y0, x1, y1 = self.bbox
        return (x1 - x0) * (y1 - y0)


@dataclass
class ImageBlock:
    """An image with position and metadata."""

    image_id: str
    bbox: tuple[float, float, float, float]
    page_number: int
    category: ImageCategory = ImageCategory.UNKNOWN
    caption: str | None = None
    figure_id: str | None = None

    @property
    def center(self) -> tuple[float, float]:
        x0, y0, x1, y1 = self.bbox
        return ((x0 + x1) / 2, (y0 + y1) / 2)

    @property
    def area(self) -> float:
        x0, y0, x1, y1 = self.bbox
        return (x1 - x0) * (y1 - y0)


@dataclass
class AssociationScore:
    """Detailed association score breakdown."""

    total_score: float
    spatial_score: float
    keyword_score: float
    context_score: float
    caption_boost: float

    # Details
    distance_pixels: float = 0.0
    keywords_matched: list[str] = field(default_factory=list)
    keyword_categories: dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "total": round(self.total_score, 3),
            "spatial": round(self.spatial_score, 3),
            "keyword": round(self.keyword_score, 3),
            "context": round(self.context_score, 3),
            "caption_boost": round(self.caption_boost, 3),
            "distance_px": round(self.distance_pixels, 1),
            "keywords": self.keywords_matched[:10],
            "categories": self.keyword_categories,
        }


@dataclass
class Association:
    """A scored association between image and text."""

    image: ImageBlock
    text_block: TextBlock
    score: AssociationScore
    association_type: str = "proximity"  # proximity, caption, reference
    confidence: float = 0.0

    def to_dict(self) -> dict:
        return {
            "image_id": self.image.image_id,
            "text_preview": self.text_block.text[:100],
            "page": self.image.page_number,
            "score": self.score.to_dict(),
            "type": self.association_type,
            "confidence": round(self.confidence, 3),
        }


# =============================================================================
# SPATIAL PROXIMITY CALCULATOR
# =============================================================================


class SpatialProximityCalculator:
    """
    Calculate spatial proximity between images and text blocks.
    Uses actual bbox distance, not just center-to-center.
    """

    def __init__(self, max_distance: float = 500.0):
        self.max_distance = max_distance

    def calculate_distance(
        self,
        bbox1: tuple[float, float, float, float],
        bbox2: tuple[float, float, float, float],
    ) -> float:
        """
        Calculate minimum distance between two bboxes.
        Returns 0 if bboxes overlap.
        """
        x0_1, y0_1, x1_1, y1_1 = bbox1
        x0_2, y0_2, x1_2, y1_2 = bbox2

        # Calculate gaps in each dimension
        dx = max(0, max(x0_1, x0_2) - min(x1_1, x1_2))
        dy = max(0, max(y0_1, y0_2) - min(y1_1, y1_2))

        # Euclidean distance
        return math.sqrt(dx * dx + dy * dy)

    def calculate_score(
        self,
        image_bbox: tuple[float, float, float, float],
        text_bbox: tuple[float, float, float, float],
    ) -> tuple[float, float]:
        """
        Calculate proximity score (0-1, higher = closer).

        Returns:
            (score, distance_in_pixels)
        """
        distance = self.calculate_distance(image_bbox, text_bbox)

        if distance == 0:
            return 1.0, 0.0

        if distance >= self.max_distance:
            return 0.0, distance

        # Linear decay with distance
        score = 1.0 - (distance / self.max_distance)

        return score, distance

    def calculate_vertical_relationship(
        self,
        image_bbox: tuple[float, float, float, float],
        text_bbox: tuple[float, float, float, float],
    ) -> str:
        """Determine if text is above, below, or beside image."""
        img_y_center = (image_bbox[1] + image_bbox[3]) / 2
        txt_y_center = (text_bbox[1] + text_bbox[3]) / 2

        img_x_center = (image_bbox[0] + image_bbox[2]) / 2
        txt_x_center = (text_bbox[0] + text_bbox[2]) / 2

        vertical_diff = txt_y_center - img_y_center
        horizontal_diff = abs(txt_x_center - img_x_center)

        if horizontal_diff > abs(vertical_diff) * 1.5:
            return "beside"
        elif vertical_diff < 0:
            return "above"
        else:
            return "below"


# =============================================================================
# NEUROSURGICAL KEYWORD SCORER
# =============================================================================


class NeurosurgicalKeywordScorer:
    """
    Score text relevance using neurosurgical keyword matching.

    Uses centralized weights from KeywordWeightConfig:
    - anatomy:     0.25
    - pathology:   0.25
    - procedure:   0.30  ← highest (surgical actions most relevant)
    - imaging:     0.15
    - instruments: 0.05  ← lowest (least discriminative)

    Context multipliers:
    - caption:  1.5x
    - heading:  1.3x
    - body:     1.0x
    """

    def __init__(self, config: NeuroSynthEnhancedConfig = None):
        cfg = config or NeuroSynthEnhancedConfig()
        self.keywords = cfg.keywords
        self.weights = cfg.keyword_weights

        # Build keyword lookup: keyword -> category
        self._keyword_to_category: dict[str, str] = {}
        for category, kw_list in self.keywords.get_all_keywords().items():
            for kw in kw_list:
                self._keyword_to_category[kw.lower()] = category

        # Pre-compile patterns for multi-word keywords
        self._patterns: dict[str, re.Pattern] = {}
        for kw in self._keyword_to_category:
            if " " in kw:
                self._patterns[kw] = re.compile(
                    r"\b" + re.escape(kw) + r"\b", re.IGNORECASE
                )

    def score_text(
        self, text: str, context_type: str = "body"
    ) -> tuple[float, dict[str, Any]]:
        """
        Score text for neurosurgical relevance.

        Args:
            text: Text to score
            context_type: "caption", "heading", or "body"

        Returns:
            (score, details_dict)

        Scoring algorithm:
        1. Find all matching keywords
        2. Group by category and count
        3. For each category: score = weight × (1 - 0.5^count)
           (diminishing returns for multiple keywords in same category)
        4. Apply context multiplier
        5. Normalize to 0-1
        """
        if not text:
            return 0.0, {"keywords": [], "categories": {}}

        text_lower = text.lower()

        # Find matching keywords
        matches: list[str] = []
        category_counts: dict[str, int] = defaultdict(int)

        # Check multi-word patterns first
        for kw, pattern in self._patterns.items():
            if pattern.search(text_lower):
                category = self._keyword_to_category[kw]
                matches.append(kw)
                category_counts[category] += 1

        # Check single-word keywords
        words = set(re.findall(r"\b\w+\b", text_lower))
        for word in words:
            if word in self._keyword_to_category:
                category = self._keyword_to_category[word]
                if word not in matches:
                    matches.append(word)
                    category_counts[category] += 1

        if not matches:
            return 0.0, {"keywords": [], "categories": {}}

        # Calculate weighted score using centralized weights
        score = 0.0
        for category, count in category_counts.items():
            weight = self.weights.get_weight(category)
            # Diminishing returns: 1 keyword = 0.5×weight, 2 = 0.75×weight, etc.
            category_score = weight * (1.0 - 0.5**count)
            score += category_score

        # Apply context multiplier from config
        if context_type == "caption":
            score *= self.weights.caption_context_boost
        elif context_type == "heading":
            score *= self.weights.heading_context_boost
        else:
            score *= self.weights.body_context_boost

        # Normalize to 0-1
        score = min(score, 1.0)

        details = {
            "keywords": matches,
            "categories": dict(category_counts),
            "context_type": context_type,
            "raw_score_before_context": score
            / (
                self.weights.caption_context_boost
                if context_type == "caption"
                else (
                    self.weights.heading_context_boost
                    if context_type == "heading"
                    else 1.0
                )
            ),
        }

        return score, details

    def get_category_for_keyword(self, keyword: str) -> str | None:
        """Get category for a specific keyword."""
        return self._keyword_to_category.get(keyword.lower())

    def get_weight_for_keyword(self, keyword: str) -> float:
        """Get weight for a specific keyword based on its category."""
        category = self.get_category_for_keyword(keyword)
        if category:
            return self.weights.get_weight(category)
        return 0.0


# =============================================================================
# CONTEXT ANALYZER
# =============================================================================


class ContextAnalyzer:
    """
    Analyze surrounding context for image-text association.
    Detects figure references and demonstrative phrases.
    """

    def __init__(self):
        # Figure reference patterns
        self.figure_ref_pattern = re.compile(
            r"(?:fig(?:ure)?|image|plate)\.?\s*(\d+(?:[.\-]\d+)?(?:[a-z])?)",
            re.IGNORECASE,
        )

        # Demonstrative patterns suggesting nearby visual
        self.demonstrative_patterns = [
            re.compile(
                r"\b(this|these|the following|above|below)\s+(?:image|figure|diagram|photo)",
                re.I,
            ),
            re.compile(r"\bas\s+(?:shown|seen|illustrated|depicted)\b", re.I),
            re.compile(r"\b(?:shows?|depicts?|illustrates?|demonstrates?)\b", re.I),
        ]

    def analyze_context(
        self, text: str, image_figure_id: str | None = None
    ) -> tuple[float, dict[str, Any]]:
        """
        Analyze text context for visual association cues.

        Returns:
            (score, details)
        """
        score = 0.0
        details = {
            "references_found": [],
            "demonstratives": [],
            "direct_reference": False,
        }

        # Check for figure references
        refs = self.figure_ref_pattern.findall(text)
        if refs:
            details["references_found"] = refs
            score += 0.2

            # Check for direct reference to this figure
            if image_figure_id:
                for ref in refs:
                    if ref == image_figure_id or ref.startswith(image_figure_id):
                        details["direct_reference"] = True
                        score += 0.5
                        break

        # Check for demonstrative patterns
        for pattern in self.demonstrative_patterns:
            if pattern.search(text):
                details["demonstratives"].append(pattern.pattern)
                score += 0.1

        return min(score, 1.0), details


# =============================================================================
# ENHANCED VISUAL CLUSTER ASSOCIATOR
# =============================================================================


class EnhancedVisualClusterAssociator:
    """
    Associate images with relevant text content using multiple scoring methods.

    Scoring formula (weights from config.association_weights):

    total = (spatial × 0.50) + (keyword × 0.30) + (context × 0.20) + boosts

    Where:
    - spatial:  Proximity score (0-1, closer = higher)
    - keyword:  Neurosurgical keyword relevance (uses 5-category weights)
    - context:  Reference/demonstrative detection
    - boosts:   Caption boost (0.15), direct reference boost (0.20)
    """

    def __init__(self, config: NeuroSynthEnhancedConfig = None):
        self.config = config or NeuroSynthEnhancedConfig()

        # Get weights from centralized config
        self.assoc_weights = self.config.association_weights

        # Initialize sub-components
        self.proximity_calc = SpatialProximityCalculator()
        self.keyword_scorer = NeurosurgicalKeywordScorer(config)
        self.context_analyzer = ContextAnalyzer()

    @property
    def SPATIAL_WEIGHT(self) -> float:
        """Spatial proximity weight (from config)."""
        return self.assoc_weights.spatial_weight

    @property
    def KEYWORD_WEIGHT(self) -> float:
        """Keyword relevance weight (from config)."""
        return self.assoc_weights.keyword_weight

    @property
    def CONTEXT_WEIGHT(self) -> float:
        """Context analysis weight (from config)."""
        return self.assoc_weights.context_weight

    @property
    def CAPTION_BOOST(self) -> float:
        """Caption boost value (from config)."""
        return self.assoc_weights.caption_boost

    @property
    def DIRECT_REF_BOOST(self) -> float:
        """Direct reference boost value (from config)."""
        return self.assoc_weights.direct_ref_boost

    def associate_image_with_text(
        self, image: ImageBlock, text_blocks: list[TextBlock], top_n: int = 5
    ) -> list[Association]:
        """
        Find best text associations for an image.

        Args:
            image: Image to associate
            text_blocks: List of text blocks to consider
            top_n: Number of top associations to return

        Returns:
            List of Association objects, sorted by score descending
        """
        associations = []

        for text_block in text_blocks:
            # Skip if different page
            if text_block.page_number != image.page_number:
                continue

            score = self._calculate_association_score(image, text_block)

            if score.total_score >= self.assoc_weights.min_association_score:
                assoc = Association(
                    image=image,
                    text_block=text_block,
                    score=score,
                    association_type=self._determine_type(text_block, score),
                    confidence=self._calculate_confidence(score),
                )
                associations.append(assoc)

        # Sort by score descending
        associations.sort(key=lambda a: a.score.total_score, reverse=True)

        return associations[:top_n]

    def associate_all_on_page(
        self, images: list[ImageBlock], text_blocks: list[TextBlock], page_number: int
    ) -> dict[str, list[Association]]:
        """
        Associate all images on a page with text.

        Returns:
            Dict mapping image_id to list of associations
        """
        page_images = [img for img in images if img.page_number == page_number]
        page_texts = [txt for txt in text_blocks if txt.page_number == page_number]

        results = {}
        for image in page_images:
            results[image.image_id] = self.associate_image_with_text(image, page_texts)

        return results

    def find_best_match(
        self, image: ImageBlock, text_blocks: list[TextBlock]
    ) -> Association | None:
        """Find single best text match for an image."""
        associations = self.associate_image_with_text(image, text_blocks, top_n=1)
        return associations[0] if associations else None

    def _calculate_association_score(
        self, image: ImageBlock, text_block: TextBlock
    ) -> AssociationScore:
        """
        Calculate detailed association score using centralized weights.

        Formula:
        total = (spatial × SPATIAL_WEIGHT) +
                (keyword × KEYWORD_WEIGHT) +
                (context × CONTEXT_WEIGHT) +
                caption_boost + direct_ref_boost
        """

        # 1. Spatial proximity
        spatial_score, distance = self.proximity_calc.calculate_score(
            image.bbox, text_block.bbox
        )

        # 2. Determine context type for keyword scoring
        context_type = self._determine_context_type(text_block)

        # 3. Keyword relevance (uses 5-category weights internally)
        keyword_score, keyword_details = self.keyword_scorer.score_text(
            text_block.text, context_type
        )

        # 4. Context analysis
        context_score, context_details = self.context_analyzer.analyze_context(
            text_block.text, image.figure_id
        )

        # 5. Calculate boosts
        caption_boost = 0.0
        if context_type == "caption":
            caption_boost = self.CAPTION_BOOST

        if context_details.get("direct_reference"):
            caption_boost += self.DIRECT_REF_BOOST

        # 6. Calculate weighted total
        total = (
            spatial_score * self.SPATIAL_WEIGHT
            + keyword_score * self.KEYWORD_WEIGHT
            + context_score * self.CONTEXT_WEIGHT
            + caption_boost
        )

        return AssociationScore(
            total_score=min(total, 1.0),
            spatial_score=spatial_score,
            keyword_score=keyword_score,
            context_score=context_score,
            caption_boost=caption_boost,
            distance_pixels=distance,
            keywords_matched=keyword_details.get("keywords", []),
            keyword_categories=keyword_details.get("categories", {}),
        )

    def _determine_context_type(self, text_block: TextBlock) -> str:
        """Determine context type from text block properties."""
        if text_block.block_type == "caption":
            return "caption"
        if text_block.block_type == "heading":
            return "heading"
        if text_block.is_bold and len(text_block.text) < 100:
            return "heading"
        if text_block.is_italic and "fig" in text_block.text.lower():
            return "caption"
        return "body"

    def _determine_type(self, text_block: TextBlock, score: AssociationScore) -> str:
        """Determine association type."""
        if text_block.block_type == "caption":
            return "caption"
        if score.caption_boost >= self.DIRECT_REF_BOOST:
            return "reference"
        return "proximity"

    def _calculate_confidence(self, score: AssociationScore) -> float:
        """Calculate confidence in association."""
        # High spatial + high keyword = high confidence
        if score.spatial_score > 0.7 and score.keyword_score > 0.3:
            return min(score.total_score * 1.2, 1.0)

        # Caption boost increases confidence
        if score.caption_boost > 0:
            return min(score.total_score * 1.1, 1.0)

        return score.total_score

    def explain_score(self, score: AssociationScore) -> str:
        """Generate human-readable explanation of a score."""
        lines = [
            f"Total Score: {score.total_score:.3f}",
            "",
            "Components (weights from config):",
            f"  Spatial:  {score.spatial_score:.3f} × {self.SPATIAL_WEIGHT:.2f} = {score.spatial_score * self.SPATIAL_WEIGHT:.3f}",
            f"  Keyword:  {score.keyword_score:.3f} × {self.KEYWORD_WEIGHT:.2f} = {score.keyword_score * self.KEYWORD_WEIGHT:.3f}",
            f"  Context:  {score.context_score:.3f} × {self.CONTEXT_WEIGHT:.2f} = {score.context_score * self.CONTEXT_WEIGHT:.3f}",
            f"  Boost:    {score.caption_boost:.3f}",
            "",
            f"Keywords matched ({len(score.keywords_matched)}):",
        ]

        for cat, count in score.keyword_categories.items():
            weight = self.config.keyword_weights.get_weight(cat)
            lines.append(f"  {cat}: {count} keywords (weight: {weight:.2f})")

        return "\n".join(lines)


# =============================================================================
# CLUSTER BUILDER
# =============================================================================


@dataclass
class ImageTextCluster:
    """A cluster of related images and text."""

    cluster_id: str
    images: list[ImageBlock] = field(default_factory=list)
    text_blocks: list[TextBlock] = field(default_factory=list)
    primary_topic: str = ""
    keywords: set[str] = field(default_factory=set)
    page_span: tuple[int, int] = (0, 0)

    def to_dict(self) -> dict:
        return {
            "cluster_id": self.cluster_id,
            "images": [img.image_id for img in self.images],
            "text_count": len(self.text_blocks),
            "topic": self.primary_topic,
            "keywords": list(self.keywords)[:20],
            "pages": f"{self.page_span[0]}-{self.page_span[1]}",
        }


class ClusterBuilder:
    """
    Build clusters of related images and text.
    """

    def __init__(self, config: NeuroSynthEnhancedConfig = None):
        self.config = config or NeuroSynthEnhancedConfig()
        self.associator = EnhancedVisualClusterAssociator(config)
        self.keyword_scorer = NeurosurgicalKeywordScorer(config)

    def build_clusters(
        self,
        images: list[ImageBlock],
        text_blocks: list[TextBlock],
        min_cluster_score: float = 0.3,
    ) -> list[ImageTextCluster]:
        """
        Build clusters from images and text.
        """
        clusters = []
        used_images: set[str] = set()
        used_texts: set[int] = set()

        # Sort images by page and position
        sorted_images = sorted(images, key=lambda i: (i.page_number, i.bbox[1]))

        for i, image in enumerate(sorted_images):
            if image.image_id in used_images:
                continue

            # Find associated text
            associations = self.associator.associate_image_with_text(
                image, text_blocks, top_n=10
            )

            # Filter by score
            good_assocs = [
                a for a in associations if a.score.total_score >= min_cluster_score
            ]

            if not good_assocs:
                continue

            # Create cluster
            cluster = ImageTextCluster(
                cluster_id=f"cluster_{i:03d}",
                images=[image],
                text_blocks=[a.text_block for a in good_assocs],
            )

            # Extract keywords
            all_keywords: set[str] = set()
            for assoc in good_assocs:
                all_keywords.update(assoc.score.keywords_matched)
            cluster.keywords = all_keywords

            # Determine topic by most frequent category
            if all_keywords:
                category_counts: dict[str, int] = defaultdict(int)
                for kw in all_keywords:
                    cat = self.keyword_scorer.get_category_for_keyword(kw)
                    if cat:
                        category_counts[cat] += 1

                if category_counts:
                    cluster.primary_topic = max(
                        category_counts, key=category_counts.get
                    )

            cluster.page_span = (image.page_number, image.page_number)

            # Mark as used
            used_images.add(image.image_id)
            for text_block in cluster.text_blocks:
                used_texts.add(id(text_block))

            clusters.append(cluster)

        return clusters


# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================


def print_weight_summary(config: NeuroSynthEnhancedConfig = None):
    """Print all weights used in association scoring."""
    cfg = config or NeuroSynthEnhancedConfig()
    cfg.print_weights_summary()


# =============================================================================
# EXAMPLE USAGE
# =============================================================================

if __name__ == "__main__":
    # Create config and print weights
    config = NeuroSynthEnhancedConfig()
    print_weight_summary(config)

    # Example scoring
    scorer = NeurosurgicalKeywordScorer(config)

    test_text = (
        "Figure 3. Pterional craniotomy approach showing the "
        "sylvian fissure and MCA bifurcation after dural opening."
    )

    score, details = scorer.score_text(test_text, context_type="caption")

    print(f"\nTest text: {test_text[:60]}...")
    print(f"Score: {score:.3f}")
    print(f"Keywords: {details['keywords']}")
    print(f"Categories: {details['categories']}")
