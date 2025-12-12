"""
Figure Request Parser for 2-Pass Synthesis (Priority 5)
========================================================
Parses LLM figure requests from Pass 1 output and resolves them
to actual figures for Pass 2 synthesis.

Pass 1 Output Format:
    [REQUEST_FIGURE: type="surgical" topic="MCA aneurysm clipping technique"]
    [REQUEST_FIGURE: type="anatomy" topic="middle cerebral artery bifurcation"]
    [REQUEST_FIGURE: type="imaging" topic="preoperative MRI showing lesion"]

Pass 2 Resolution:
    Requests are matched to available figures using semantic similarity,
    then replaced with actual figure IDs for the LLM to cite.
"""

import logging
import re
from dataclasses import dataclass
from typing import Optional

import numpy as np

logger = logging.getLogger("FigureRequestParser")


@dataclass
class FigureRequest:
    """A parsed figure request from Pass 1 output."""

    full_match: str  # Original placeholder text
    position: int  # Character position in text
    requested_type: str | None  # Image type filter (surgical, anatomy, imaging, etc.)
    topic: str  # Description of what figure should show
    paragraph_index: int  # Which paragraph the request appears in


@dataclass
class ResolvedRequest:
    """A resolved figure request with matched figure."""

    request: FigureRequest
    figure_id: str
    figure_caption: str
    similarity_score: float
    image_type: str


class FigureRequestParser:
    """
    Parse and resolve figure requests from Pass 1 synthesis output.

    This enables 2-pass synthesis where:
    - Pass 1: LLM drafts content with [REQUEST_FIGURE: ...] placeholders
    - Resolution: This parser matches requests to actual figures
    - Pass 2: LLM refines content with resolved figure IDs
    """

    # Regex pattern for figure requests
    # Matches: [REQUEST_FIGURE: type="..." topic="..."]
    # or simplified: [REQUEST_FIGURE: topic description here]
    REQUEST_PATTERN = re.compile(
        r"\[REQUEST_FIGURE:\s*"
        r'(?:type\s*=\s*["\']?(\w+)["\']?\s+)?'  # Optional type
        r'(?:topic\s*=\s*["\']?([^"\'\]]+)["\']?|([^"\'\]]+))'  # Topic (quoted or unquoted)
        r"\s*\]",
        re.IGNORECASE,
    )

    # Simpler pattern for informal requests
    SIMPLE_REQUEST_PATTERN = re.compile(
        r"\[REQUEST_FIGURE:\s*([^\]]+)\]", re.IGNORECASE
    )

    def __init__(self, vision_embedder=None):
        """
        Initialize the parser.

        Args:
            vision_embedder: BiomedCLIPSearcher instance for semantic matching
        """
        self._embedder = vision_embedder

    @property
    def embedder(self):
        """Lazy-load embedder if not provided."""
        if self._embedder is None:
            try:
                from neurosynth.ai.biomed_searcher import BiomedCLIPSearcher

                self._embedder = BiomedCLIPSearcher()
            except Exception as e:
                logger.warning(f"Failed to load embedder: {e}")
        return self._embedder

    def parse_requests(self, text: str) -> list[FigureRequest]:
        """
        Parse all figure requests from Pass 1 output.

        Args:
            text: Synthesized text containing [REQUEST_FIGURE: ...] placeholders

        Returns:
            List of FigureRequest objects
        """
        requests = []

        # Try structured pattern first
        for match in self.REQUEST_PATTERN.finditer(text):
            req_type = match.group(1)  # May be None
            topic = match.group(2) or match.group(3)  # Either quoted or unquoted

            if topic:
                requests.append(
                    FigureRequest(
                        full_match=match.group(0),
                        position=match.start(),
                        requested_type=req_type.lower() if req_type else None,
                        topic=topic.strip(),
                        paragraph_index=self._get_paragraph_index(text, match.start()),
                    )
                )

        # If no structured matches, try simple pattern
        if not requests:
            for match in self.SIMPLE_REQUEST_PATTERN.finditer(text):
                content = match.group(1).strip()
                # Parse type from content if present
                req_type = None
                topic = content
                type_match = re.match(r"(\w+)[\s:/-]+(.+)", content)
                if type_match and type_match.group(1).lower() in (
                    "surgical",
                    "anatomy",
                    "imaging",
                    "diagram",
                    "illustration",
                ):
                    req_type = type_match.group(1).lower()
                    topic = type_match.group(2).strip()

                requests.append(
                    FigureRequest(
                        full_match=match.group(0),
                        position=match.start(),
                        requested_type=req_type,
                        topic=topic,
                        paragraph_index=self._get_paragraph_index(text, match.start()),
                    )
                )

        return requests

    def _get_paragraph_index(self, text: str, position: int) -> int:
        """Get paragraph index for a character position."""
        text_before = text[:position]
        return text_before.count("\n\n")

    def resolve_requests(
        self,
        requests: list[FigureRequest],
        available_figures: list[dict],
        max_per_request: int = 1,
    ) -> list[ResolvedRequest]:
        """
        Resolve figure requests to actual figures using semantic similarity.

        Args:
            requests: List of FigureRequest from parse_requests()
            available_figures: List of figure dicts with keys:
                - id: Figure ID
                - caption: Figure caption
                - image_type: Type classification
                - embedding: Optional pre-computed embedding
            max_per_request: Max figures to match per request

        Returns:
            List of ResolvedRequest objects
        """
        resolved = []
        used_ids = set()

        for request in requests:
            matches = self._find_matching_figures(
                request,
                available_figures,
                used_ids,
                max_per_request,
            )

            for match in matches:
                resolved.append(match)
                used_ids.add(match.figure_id)

        return resolved

    def _find_matching_figures(
        self,
        request: FigureRequest,
        figures: list[dict],
        used_ids: set[str],
        max_matches: int,
    ) -> list[ResolvedRequest]:
        """Find figures matching a request using semantic similarity."""
        # Filter by type if specified
        candidates = figures
        if request.requested_type:
            type_map = {
                "surgical": ["surgical_photo", "surgical_step"],
                "anatomy": ["anatomy_diagram", "anatomical"],
                "imaging": ["imaging_mri", "imaging_ct", "imaging_angio", "imaging"],
                "diagram": ["diagram", "illustration"],
                "illustration": ["illustration", "diagram"],
            }
            allowed_types = type_map.get(
                request.requested_type, [request.requested_type]
            )
            candidates = [
                f
                for f in figures
                if f.get("image_type", "").lower() in allowed_types
                or any(t in f.get("image_type", "").lower() for t in allowed_types)
            ]

        # Filter out already used
        candidates = [f for f in candidates if f.get("id") not in used_ids]

        if not candidates:
            return []

        # Score candidates by semantic similarity
        scored = []
        topic_embedding = None

        if self.embedder:
            try:
                emb = self.embedder.embed_text(request.topic)
                if emb.size > 0:
                    topic_embedding = emb[0]
            except Exception:
                pass

        for fig in candidates:
            score = self._score_figure(fig, request.topic, topic_embedding)
            scored.append((fig, score))

        # Sort by score and take top matches
        scored.sort(key=lambda x: x[1], reverse=True)

        results = []
        for fig, score in scored[:max_matches]:
            if score >= 0.15:  # Minimum threshold
                results.append(
                    ResolvedRequest(
                        request=request,
                        figure_id=fig.get("id", ""),
                        figure_caption=fig.get("caption", ""),
                        similarity_score=score,
                        image_type=fig.get("image_type", "unknown"),
                    )
                )

        return results

    def _score_figure(
        self,
        figure: dict,
        topic: str,
        topic_embedding: np.ndarray | None,
    ) -> float:
        """Score a figure against a topic request."""
        score = 0.0

        # Semantic similarity with BiomedCLIP
        if topic_embedding is not None:
            fig_caption = figure.get("caption", "")
            if fig_caption and self.embedder:
                try:
                    cap_emb = self.embedder.embed_text(fig_caption)
                    if cap_emb.size > 0:
                        similarity = float(np.dot(topic_embedding, cap_emb[0]))
                        # CLIP similarities typically 0.15-0.35, normalize
                        score = max(0.0, min(1.0, (similarity - 0.10) / 0.25))
                except Exception:
                    pass

        # Fallback: keyword overlap
        if score == 0.0:
            topic_words = set(topic.lower().split())
            caption_words = set(figure.get("caption", "").lower().split())
            overlap = len(topic_words & caption_words)
            score = min(overlap / 4, 1.0)

        return score

    def replace_requests_with_figures(
        self,
        text: str,
        resolved: list[ResolvedRequest],
    ) -> str:
        """
        Replace [REQUEST_FIGURE: ...] placeholders with resolved [FIGURE: id] tags.

        Args:
            text: Original text with REQUEST_FIGURE placeholders
            resolved: List of resolved requests

        Returns:
            Text with placeholders replaced by figure tags
        """
        result = text

        # Sort by position descending to replace from end first (preserves positions)
        for res in sorted(resolved, key=lambda r: r.request.position, reverse=True):
            # Replace the request placeholder with resolved figure tag
            new_tag = f"[FIGURE: {res.figure_id}]"
            result = (
                result[: res.request.position]
                + new_tag
                + result[res.request.position + len(res.request.full_match) :]
            )

        return result

    def get_request_count(self, text: str) -> int:
        """Count figure requests in text."""
        return len(self.parse_requests(text))
