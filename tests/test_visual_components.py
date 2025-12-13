import sys
from unittest.mock import MagicMock, patch

import pytest

# Mock dependencies to avoid import errors in test environment
sys.modules["structlog"] = MagicMock()


# Mock config
mock_config = MagicMock()
sys.modules["src.config"] = mock_config
sys.modules["neurosynth.config"] = mock_config

# IMPORTANT: Do NOT mock "neurosynth" top-level in sys.modules,
# because we need to load real submodules like neurosynth.ai.
# Instead, we import it and inject the config attribute manually.
import neurosynth

neurosynth.config = mock_config

# Mock other external deps
sys.modules["fitz"] = MagicMock()
sys.modules["marker"] = MagicMock()
sys.modules["marker.convert"] = MagicMock()
sys.modules["marker.models"] = MagicMock()
sys.modules["torch"] = MagicMock()

# Mock ingestion siblings to prevent __init__ cascading imports
sys.modules["src.ingest.image_extractor"] = MagicMock()
sys.modules["src.ingest.smart_extractor"] = MagicMock()

# Mock precision_search to avoid Python 3.10 syntax error in py3.9 env
sys.modules["index.precision_search"] = MagicMock()
sys.modules["src.index.precision_search"] = MagicMock()  # Double mock for safety


from index.late_fusion import LateFusionRanker, VisualCandidate

# Import Phase 3 components
# (We need to be careful about imports if they rely on above mocks)
from ingest.extraction_node import ExtractionNode
from neurosynth.ai.visual_verifier import VerificationResult, VisualVerifier

# Restore real modules for later tests
import importlib
import neurosynth as _neurosynth_pkg

try:
    sys.modules["src.config"] = importlib.import_module("src.config")
    sys.modules["neurosynth.config"] = importlib.import_module("neurosynth.config")
    _neurosynth_pkg.config = sys.modules["neurosynth.config"]
except ImportError:
    sys.modules.pop("src.config", None)
    sys.modules.pop("neurosynth.config", None)

try:
    sys.modules["structlog"] = importlib.import_module("structlog")
except ImportError:
    sys.modules.pop("structlog", None)
sys.modules.pop("index.precision_search", None)
sys.modules.pop("src.index.precision_search", None)
sys.modules.pop("src.ingest.image_extractor", None)
sys.modules.pop("src.ingest.smart_extractor", None)

# -----------------------------------------------------------------------------
# 1. ExtractionNode Tests
# -----------------------------------------------------------------------------


def test_extraction_node_fallback():
    """Test that ExtractionNode falls back to PyMuPDF if Marker fails/missing."""
    # Force marker unavailable
    with patch("ingest.extraction_node.MARKER_AVAILABLE", False):
        node = ExtractionNode()
        assert node.use_marker is False

        # Mock _extract_with_pymupdf
        node._extract_with_pymupdf = MagicMock(return_value={1: "PyMuPDF Text"})

        content = node.extract_content("dummy.pdf")
        assert content == {1: "PyMuPDF Text"}
        node._extract_with_pymupdf.assert_called_once()


def test_extraction_node_marker_usage():
    """Test that ExtractionNode tries Marker if available."""
    # Force marker available
    with patch("ingest.extraction_node.MARKER_AVAILABLE", True):
        with patch("ingest.extraction_node.convert_single_pdf") as mock_convert:
            # Mock return of convert: full_text, images, meta
            mock_convert.return_value = ("Marker Full Text", [], {})

            node = ExtractionNode()
            assert node.use_marker is True

            content = node.extract_content("dummy.pdf")
            # Logic implementation: returns {1: full_text}
            assert content[1] == "Marker Full Text"


# -----------------------------------------------------------------------------
# 2. LateFusionRanker Tests
# -----------------------------------------------------------------------------


def test_late_fusion_ranking():
    ranker = LateFusionRanker(alpha=0.5)

    c1 = VisualCandidate(image_id="1", text_score=1.0, visual_score=0.0)  # Avg 0.5
    c2 = VisualCandidate(image_id="2", text_score=0.9, visual_score=0.9)  # Avg 0.9
    c3 = VisualCandidate(image_id="3", text_score=0.0, visual_score=1.0)  # Avg 0.5

    results = ranker.rank([c1, c2, c3])

    assert results[0].image_id == "2"
    assert results[0].combined_score == 0.9
    # c1 and c3 tie at 0.5
    assert results[1].combined_score == 0.5


def test_late_fusion_alpha():
    # Alpha 1.0 = Text Only
    ranker = LateFusionRanker(alpha=1.0)
    c1 = VisualCandidate("1", 1.0, 0.0)
    c2 = VisualCandidate("2", 0.0, 1.0)

    res = ranker.rank([c1, c2])
    assert res[0].image_id == "1"
    assert res[0].combined_score == 1.0


# -----------------------------------------------------------------------------
# 3. VisualVerifier Tests
# -----------------------------------------------------------------------------


def test_visual_verifier_batch():
    verifier = VisualVerifier()
    results = verifier.verify_caption_batch(["img1.jpg"], ["caption1"])

    assert len(results) == 1
    assert isinstance(results[0], VerificationResult)
    assert results[0].is_congruent is True  # Default mock behavior
