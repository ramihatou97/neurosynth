import logging
from typing import Dict, List, Optional, Tuple

import numpy as np

from neurosynth.ai.biomed_searcher import BiomedCLIPSearcher

logger = logging.getLogger("ModalityClassifier")


class ModalityClassifier:
    """Zero-Shot Classifier for Medical Images."""

    # Categories mapped to "prompts" or descriptions that CLIP understands
    CATEGORIES = {
        "radiology": "a radiological scan like MRI, CT, or X-ray",
        "surgical": "an intraoperative photograph of a surgery",
        "microscopic": "a histology slide or microscopic view",
        "diagram": "a medical illustration, diagram, or schematic drawing",
        "graph": "a chart, graph, or data table",
        "equipment": "medical equipment or surgical instruments on a tray",
    }

    def __init__(self, searcher: BiomedCLIPSearcher):
        self.searcher = searcher
        self.labels = list(self.CATEGORIES.keys())
        self.prompts = list(self.CATEGORIES.values())

        # Pre-compute text features for the fixed categories
        logger.info("Pre-computing classification centroids...")
        self.text_features = self.searcher.embed_text(self.prompts)
        # Transpose for easier dot product (N_categories x D) -> (D x N_categories)
        self.text_features_T = self.text_features.T

    def classify(self, image_vector: np.ndarray) -> tuple[str, float]:
        """Classify a single image vector."""
        if image_vector.ndim == 1:
            image_vector = image_vector.reshape(1, -1)

        # Robustness: Ensure vector is normalized
        norm = np.linalg.norm(image_vector, axis=1, keepdims=True)
        if norm[0, 0] > 0:
            image_vector = image_vector / norm

        scores = np.dot(
            image_vector, self.text_features_T
        )  # (1 x D) dot (D x N) = (1 x N)
        scores = scores.flatten()

        exp_scores = np.exp(scores * 100)  # Softmax with temperature scaling
        probs = exp_scores / np.sum(exp_scores)
        best_idx = np.argmax(probs)
        return self.labels[best_idx], float(probs[best_idx])

    def classify_batch(self, image_vectors: np.ndarray) -> list[dict[str, float]]:
        """Classify a batch of image vectors."""
        if len(image_vectors) == 0:
            return []

        # (B x D) dot (D x N) = (B x N)
        logits = image_vectors @ self.text_features_T
        best_indices = np.argmax(logits, axis=1)

        results = []
        for i, idx in enumerate(best_indices):
            results.append({"label": self.labels[idx], "score": float(logits[i, idx])})
        return results
