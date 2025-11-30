"""
Unit tests for VectorGraphicsExtractor.

Tests Phase 4.1 Module 1:
- Initialization with configuration
- Drawing command extraction and filtering
- Spatial clustering algorithm
- Graphic type classification
- PNG rendering
- Arrow detection
"""

import pytest
from unittest.mock import Mock, MagicMock, patch
from pathlib import Path
import sys

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from neurosynth.enhancements.vector_extractor import (
    VectorGraphicsExtractor,
    VectorGraphic,
)
from neurosynth.enhancements.config import NeuroSynthEnhancedConfig


class TestVectorGraphicsExtractor:
    """Test suite for VectorGraphicsExtractor."""

    @pytest.fixture
    def config(self):
        """Create test configuration."""
        return NeuroSynthEnhancedConfig()

    @pytest.fixture
    def extractor(self, config):
        """Create VectorGraphicsExtractor instance."""
        return VectorGraphicsExtractor(config)

    def test_initialization(self, config):
        """Test extractor initializes with configuration."""
        extractor = VectorGraphicsExtractor(config)

        assert extractor.config == config
        assert extractor.vg_config == config.vector_graphics
        assert extractor.min_paths == config.vector_graphics.min_vector_paths
        assert extractor.min_complexity == config.vector_graphics.min_path_complexity
        assert extractor.grid_size == config.vector_graphics.grid_size
        assert extractor.render_dpi == config.vector_graphics.render_dpi

        print("✓ VectorGraphicsExtractor initialization verified")

    def test_extract_from_page_no_drawings(self, extractor):
        """Test extraction returns empty list when no drawings."""
        mock_page = Mock()
        mock_page.get_drawings.return_value = []

        result = extractor.extract_from_page(mock_page, page_num=0, context_text="")

        assert result == []
        print("✓ Empty page returns empty list")

    def test_filter_complex_paths(self, extractor):
        """Test complexity filtering keeps only complex paths."""
        # Create mock drawings with varying complexity
        simple_drawing = {'items': ['op'] * 10}  # 10 operations (below threshold)
        complex_drawing = {'items': ['op'] * 100}  # 100 operations (above threshold)

        drawings = [simple_drawing, complex_drawing]

        filtered = extractor._filter_complex_paths(drawings)

        # Only complex drawing should remain
        assert len(filtered) == 1
        assert filtered[0] == complex_drawing

        print("✓ Complexity filtering works correctly")

    def test_compute_cluster_bbox(self, extractor):
        """Test bounding box computation for cluster."""
        # Create mock paths with rectangles
        import fitz

        rect1 = fitz.Rect(10, 20, 100, 200)
        rect2 = fitz.Rect(50, 60, 150, 250)
        rect3 = fitz.Rect(30, 40, 120, 220)

        cluster = [
            {'rect': rect1},
            {'rect': rect2},
            {'rect': rect3},
        ]

        bbox = extractor._compute_cluster_bbox(cluster)

        # Should be min/max of all rects
        assert bbox == (10, 20, 150, 250)

        print("✓ Cluster bounding box computed correctly")

    def test_compute_cluster_bbox_empty(self, extractor):
        """Test bounding box for empty cluster."""
        bbox = extractor._compute_cluster_bbox([])

        assert bbox == (0, 0, 0, 0)

        print("✓ Empty cluster returns zero bbox")

    def test_detect_arrows_with_filled_paths(self, extractor):
        """Test arrow detection identifies filled shapes."""
        # Create cluster with filled path (arrow head)
        cluster_with_arrows = [
            {'items': [('f', {}), ('l', {})]},  # 'f' = fill operation
        ]

        assert extractor._detect_arrows(cluster_with_arrows) is True

        print("✓ Arrow detection identifies filled paths")

    def test_detect_arrows_no_filled_paths(self, extractor):
        """Test arrow detection returns False for no fills."""
        # Create cluster with only lines (no fills)
        cluster_without_arrows = [
            {'items': [('l', {}), ('c', {})]},  # 'l' = line, 'c' = curve
        ]

        assert extractor._detect_arrows(cluster_without_arrows) is False

        print("✓ Arrow detection returns False for non-arrow paths")

    def test_classify_flowchart_with_arrows_and_keywords(self, extractor):
        """Test classification as flowchart with arrows + keywords."""
        context = "This algorithm shows the decision pathway for treatment"

        graphic_type, confidence, keywords = extractor._classify_graphic_type(
            context, contains_arrows=True
        )

        assert graphic_type == "flowchart"
        assert confidence >= 0.80  # High confidence
        assert len(keywords) > 0
        assert 'algorithm' in keywords or 'decision' in keywords or 'pathway' in keywords

        print("✓ Flowchart classification with arrows + keywords")

    def test_classify_flowchart_keywords_only(self, extractor):
        """Test classification as flowchart with keywords but no arrows."""
        context = "The workflow protocol is shown in this figure"

        graphic_type, confidence, keywords = extractor._classify_graphic_type(
            context, contains_arrows=False
        )

        assert graphic_type == "flowchart"
        assert confidence >= 0.60  # Medium confidence
        assert 'workflow' in keywords or 'protocol' in keywords

        print("✓ Flowchart classification with keywords only")

    def test_classify_diagram(self, extractor):
        """Test classification as diagram."""
        context = "Anatomical schematic showing cross-section of the brain"

        graphic_type, confidence, keywords = extractor._classify_graphic_type(
            context, contains_arrows=False
        )

        assert graphic_type == "diagram"
        assert confidence >= 0.60
        assert 'anatomy' in keywords or 'schematic' in keywords or 'cross-section' in keywords

        print("✓ Diagram classification works")

    def test_classify_schematic_fallback(self, extractor):
        """Test fallback to schematic for unknown types without arrows."""
        # Use text that won't match any keywords (avoid words like "if", "no", "yes")
        context = "Some generic example text"

        graphic_type, confidence, keywords = extractor._classify_graphic_type(
            context, contains_arrows=False
        )

        assert graphic_type == "schematic"
        assert confidence <= 0.50  # Low confidence
        assert len(keywords) == 0

        print("✓ Schematic fallback for unknown types")

    def test_classify_flowchart_arrows_only(self, extractor):
        """Test classification as flowchart with arrows but no keywords."""
        # Avoid any word that contains flowchart keywords as substring
        context = "Generic example text"

        graphic_type, confidence, keywords = extractor._classify_graphic_type(
            context, contains_arrows=True
        )

        assert graphic_type == "flowchart"
        assert confidence == 0.50  # Medium-low confidence (arrows suggest flowchart)
        assert len(keywords) == 0

        print("✓ Flowchart classification with arrows only")

    def test_render_cluster_to_image(self, extractor):
        """Test PNG rendering of cluster region."""
        mock_page = Mock()
        mock_page.rect = Mock(width=595, height=842)  # A4 dimensions

        # Mock pixmap
        mock_pixmap = Mock()
        mock_pixmap.width = 400
        mock_pixmap.height = 300
        mock_pixmap.tobytes.return_value = b'PNG_DATA_HERE'

        mock_page.get_pixmap.return_value = mock_pixmap

        bbox = (100, 100, 500, 400)
        cluster = [{'rect': Mock(x0=100, y0=100, x1=500, y1=400)}]

        rendered = extractor._render_cluster_to_image(mock_page, cluster, bbox)

        assert rendered == b'PNG_DATA_HERE'
        assert mock_page.get_pixmap.called

        print("✓ Cluster rendering to PNG works")

    def test_render_invalid_bbox(self, extractor):
        """Test rendering with invalid bbox returns None."""
        mock_page = Mock()

        # Invalid bbox (x1 <= x0)
        invalid_bbox = (100, 100, 50, 200)
        cluster = []

        rendered = extractor._render_cluster_to_image(mock_page, cluster, invalid_bbox)

        assert rendered is None

        print("✓ Invalid bbox returns None")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
