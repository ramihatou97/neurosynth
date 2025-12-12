"""
Late Fusion Ranker (Phase 3)
============================
Combines Text Relevance (Qdrant/BM25) with Visual Similarity (BiomedCLIP).

Formula:
    Score = (alpha * TextScore) + ((1 - alpha) * VisualScore)

Where:
    - TextScore is the relevance of the image's surrounding text/caption to the query.
    - VisualScore is the direct cosine similarity of the image to the query.
    - Alpha is a tunable weight (default 0.7 favoring text).
"""

from dataclasses import dataclass
from typing import List


@dataclass
class VisualCandidate:
    image_id: str
    text_score: float
    visual_score: float
    combined_score: float = 0.0


class LateFusionRanker:
    """
    Ranks visual search candidates using Late Fusion.
    """

    def __init__(self, alpha: float = 0.7):
        self.alpha = alpha

    def rank(self, candidates: list[VisualCandidate]) -> list[VisualCandidate]:
        """
        Compute combined scores and re-rank candidates.
        """
        for cand in candidates:
            # Simple linear combination
            cand.combined_score = (self.alpha * cand.text_score) + (
                (1 - self.alpha) * cand.visual_score
            )

        # Sort descending
        return sorted(candidates, key=lambda x: x.combined_score, reverse=True)

    def set_alpha(self, alpha: float):
        """Update weighting factor."""
        if not 0.0 <= alpha <= 1.0:
            raise ValueError("Alpha must be between 0.0 and 1.0")
        self.alpha = alpha
