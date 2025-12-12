"""
Visual Region Detector for NeuroSynth
======================================
Uses BiomedCLIP visual embeddings to detect anatomical regions
by comparing images to region exemplar centroids.

This complements the keyword-based AnatomicalRegionDetector
to improve region tagging from ~7.8% to 35-50% coverage.

Version: 1.0
"""

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import numpy as np

logger = logging.getLogger("VisualRegionDetector")


@dataclass
class RegionCentroid:
    """Centroid embedding for an anatomical region."""

    region_id: str
    region_name: str
    centroid: np.ndarray
    exemplar_count: int
    text_embedding: np.ndarray | None = None  # Text-based fallback


@dataclass
class VisualRegionMatch:
    """A visually detected anatomical region with confidence score."""

    region_id: str
    region_name: str
    similarity: float  # Cosine similarity to centroid (0.0 - 1.0)
    source: str = "visual"  # "visual", "text_embedding", or "hybrid"


# Region definitions with text descriptions for text-based embeddings
# These descriptions are used when no exemplar images are available
REGION_TEXT_DESCRIPTIONS = {
    # Spine regions
    "cervical_spine": "cervical spine vertebrae C1-C7 neck region lateral view",
    "thoracic_spine": "thoracic spine vertebrae T1-T12 dorsal spine",
    "lumbar_spine": "lumbar spine vertebrae L1-L5 lower back sagittal view",
    "sacral_spine": "sacrum sacral spine S1-S5 coccyx",
    # Vascular regions
    "mca": "middle cerebral artery MCA angiogram cerebral vasculature",
    "aca": "anterior cerebral artery ACA interhemispheric fissure",
    "ica": "internal carotid artery ICA cavernous segment",
    "basilar": "basilar artery vertebrobasilar system posterior circulation",
    "pca": "posterior cerebral artery PCA occipital lobe supply",
    # Brain regions
    "frontal_lobe": "frontal lobe prefrontal cortex MRI brain",
    "temporal_lobe": "temporal lobe mesial temporal structures hippocampus",
    "parietal_lobe": "parietal lobe sensory cortex postcentral gyrus",
    "occipital_lobe": "occipital lobe visual cortex calcarine fissure",
    "cerebellum": "cerebellum cerebellar hemispheres vermis",
    "brainstem": "brainstem midbrain pons medulla",
    # Skull base
    "anterior_fossa": "anterior cranial fossa cribriform plate planum sphenoidale",
    "middle_fossa": "middle cranial fossa sphenoid wing temporal bone",
    "posterior_fossa": "posterior fossa foramen magnum cerebellopontine angle",
    "cerebellopontine_angle": "cerebellopontine angle CPA acoustic neuroma",
    # Surgical corridors
    "pterional": "pterional approach frontotemporal craniotomy sylvian fissure",
    "retrosigmoid": "retrosigmoid approach lateral suboccipital craniotomy",
    "transsphenoidal": "transsphenoidal approach endonasal pituitary sella",
    "far_lateral": "far lateral approach transcondylar foramen magnum",
}


class VisualRegionDetector:
    """
    Detect anatomical regions using BiomedCLIP visual similarity.

    Uses text embeddings of region descriptions as fallback when
    exemplar images are not available, then compares image embeddings
    to these text embeddings for region detection.
    """

    def __init__(
        self,
        exemplar_dir: Path | None = None,
        similarity_threshold: float = 0.25,  # CLIP similarities are typically 0.15-0.35
        max_regions: int = 3,
    ):
        """
        Initialize the visual region detector.

        Args:
            exemplar_dir: Path to directory with region exemplar images
            similarity_threshold: Minimum cosine similarity for detection
            max_regions: Maximum number of regions to return per image
        """
        self.threshold = similarity_threshold
        self.max_regions = max_regions
        self.centroids: dict[str, RegionCentroid] = {}
        self._embedder = None
        self._initialized = False
        self.exemplar_dir = exemplar_dir

    @property
    def embedder(self):
        """Lazy-load BiomedCLIP embedder."""
        if self._embedder is None:
            try:
                from src.services.model_manager import get_model_manager

                self._embedder = get_model_manager().get_biomed_clip()
                logger.info("BiomedCLIP retrieved from ModelManager")
            except Exception as e:
                logger.warning(f"Failed to load BiomedCLIP: {e}")
        return self._embedder

    def initialize(self) -> bool:
        """
        Initialize region centroids from exemplars or text descriptions.

        Returns:
            True if initialization successful
        """
        if self._initialized:
            return True

        if not self.embedder:
            logger.error("Cannot initialize: BiomedCLIP not available")
            return False

        # Try to load from exemplar images first
        if self.exemplar_dir and self.exemplar_dir.exists():
            self._load_from_exemplars()

        # Fall back to text embeddings for missing regions
        self._load_from_text_descriptions()

        self._initialized = bool(self.centroids)
        logger.info(f"Initialized {len(self.centroids)} region centroids")
        return self._initialized

    def _load_from_exemplars(self):
        """Load region centroids from exemplar images."""
        if not self.exemplar_dir:
            return

        for region_dir in self.exemplar_dir.iterdir():
            if not region_dir.is_dir():
                continue

            region_id = region_dir.name
            image_files = list(region_dir.glob("*.jpg")) + list(
                region_dir.glob("*.png")
            )

            if not image_files:
                continue

            # Embed all exemplar images
            embeddings = []
            for img_path in image_files[:10]:  # Max 10 exemplars per region
                try:
                    emb = self.embedder.embed_image(img_path)
                    if emb.size > 0:
                        embeddings.append(emb[0])
                except Exception as e:
                    logger.debug(f"Failed to embed {img_path}: {e}")

            if embeddings:
                # Compute centroid as mean of embeddings
                centroid = np.mean(embeddings, axis=0)
                centroid = centroid / np.linalg.norm(centroid)  # Normalize

                region_name = region_id.replace("_", " ").title()
                self.centroids[region_id] = RegionCentroid(
                    region_id=region_id,
                    region_name=region_name,
                    centroid=centroid,
                    exemplar_count=len(embeddings),
                )
                logger.debug(f"Loaded {len(embeddings)} exemplars for {region_id}")

    def _load_from_text_descriptions(self):
        """Create text-based centroids for regions without exemplars."""
        for region_id, description in REGION_TEXT_DESCRIPTIONS.items():
            if region_id in self.centroids:
                # Add text embedding as fallback
                try:
                    text_emb = self.embedder.embed_text(description)
                    if text_emb.size > 0:
                        self.centroids[region_id].text_embedding = text_emb[0]
                except Exception:
                    pass
            else:
                # Create centroid from text only
                try:
                    text_emb = self.embedder.embed_text(description)
                    if text_emb.size > 0:
                        region_name = region_id.replace("_", " ").title()
                        self.centroids[region_id] = RegionCentroid(
                            region_id=region_id,
                            region_name=region_name,
                            centroid=text_emb[0],
                            exemplar_count=0,
                            text_embedding=text_emb[0],
                        )
                except Exception as e:
                    logger.debug(f"Failed text embedding for {region_id}: {e}")

    def detect_regions(
        self,
        image_path: Path | None = None,
        image_embedding: np.ndarray | None = None,
    ) -> list[VisualRegionMatch]:
        """
        Detect anatomical regions in an image using visual similarity.

        Args:
            image_path: Path to image file
            image_embedding: Pre-computed image embedding (optional)

        Returns:
            List of VisualRegionMatch objects sorted by similarity
        """
        if not self._initialized:
            if not self.initialize():
                return []

        # Get image embedding
        if image_embedding is None and image_path:
            if not self.embedder:
                return []
            try:
                emb = self.embedder.embed_image(image_path)
                if emb.size == 0:
                    return []
                image_embedding = emb[0]
            except Exception as e:
                logger.debug(f"Failed to embed image: {e}")
                return []

        if image_embedding is None:
            return []

        # Compare to all region centroids
        matches = []
        for region_id, centroid in self.centroids.items():
            similarity = self._cosine_similarity(image_embedding, centroid.centroid)

            if similarity >= self.threshold:
                source = "visual" if centroid.exemplar_count > 0 else "text_embedding"
                matches.append(
                    VisualRegionMatch(
                        region_id=region_id,
                        region_name=centroid.region_name,
                        similarity=float(similarity),
                        source=source,
                    )
                )

        # Sort by similarity and limit
        matches.sort(key=lambda m: m.similarity, reverse=True)
        return matches[: self.max_regions]

    def detect_regions_from_embedding(
        self,
        embedding: np.ndarray,
    ) -> list[str]:
        """
        Simplified interface returning just region IDs.

        Args:
            embedding: Pre-computed image embedding

        Returns:
            List of region IDs
        """
        matches = self.detect_regions(image_embedding=embedding)
        return [m.region_id for m in matches]

    def _cosine_similarity(self, a: np.ndarray, b: np.ndarray) -> float:
        """Compute cosine similarity between two vectors."""
        norm_a = np.linalg.norm(a)
        norm_b = np.linalg.norm(b)
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return float(np.dot(a, b) / (norm_a * norm_b))


# Singleton instance
_visual_detector: VisualRegionDetector | None = None


def get_visual_region_detector(
    exemplar_dir: Path | None = None,
) -> VisualRegionDetector:
    """Get or create the singleton visual region detector."""
    global _visual_detector
    if _visual_detector is None:
        _visual_detector = VisualRegionDetector(exemplar_dir=exemplar_dir)
    return _visual_detector
