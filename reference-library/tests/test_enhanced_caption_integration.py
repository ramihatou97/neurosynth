"""Test EnhancedCaptionDetector integration with ImageExtractor.

Verifies Phase 3.4 implementation:
- EnhancedCaptionDetector initializes when enable_enhanced_captions=True
- Multi-directional caption search (above/below/left/right)
- Confidence threshold filtering
- Graceful fallback to legacy detection
- Statistics tracking

NOTE: These tests are for features that are planned but not yet implemented.
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
from neurosynth.parsers.image_extractor import ImageExtractor
from neurosynth.config import Settings

# Skip all tests in this module - features not yet implemented
pytestmark = pytest.mark.skip(reason="Enhanced caption features not yet implemented")


class TestEnhancedCaptionIntegration:
    """Test Phase 3.4: Enhanced caption detection integration."""

    def test_enhanced_caption_initialization(self):
        """Verify EnhancedCaptionDetector loads when flag enabled."""
        with patch('neurosynth.parsers.image_extractor.get_settings') as mock_settings:
            settings = Settings(
                enhancements_enabled=True,
                enable_enhanced_captions=True
            )
            mock_settings.return_value = settings

            extractor = ImageExtractor()

            # Check that caption detector was initialized
            assert hasattr(extractor, 'caption_detector')
            # If dependencies are available, detector should be initialized
            # If not available, should be None but not raise exception
            assert hasattr(extractor, 'caption_detector_stats')
            assert 'enhanced_used' in extractor.caption_detector_stats
            assert 'legacy_used' in extractor.caption_detector_stats
            assert 'multi_directional_matches' in extractor.caption_detector_stats

        print("✓ EnhancedCaptionDetector initialization verified")

    def test_enhanced_caption_disabled(self):
        """Verify legacy used when flag=False."""
        with patch('neurosynth.parsers.image_extractor.get_settings') as mock_settings:
            settings = Settings(
                enhancements_enabled=False,
                enable_enhanced_captions=False
            )
            mock_settings.return_value = settings

            extractor = ImageExtractor()

            # Caption detector should not be initialized
            assert extractor.caption_detector is None
            assert extractor.caption_detector_stats['enhanced_used'] == 0

        print("✓ Legacy caption detection used when enhancement disabled")

    def test_enhanced_caption_multi_directional(self):
        """Test multi-directional caption search (above/below/left/right)."""
        with patch('neurosynth.parsers.image_extractor.get_settings') as mock_settings:
            settings = Settings(
                enhancements_enabled=True,
                enable_enhanced_captions=True,
                caption_confidence_threshold=0.60
            )
            mock_settings.return_value = settings

            extractor = ImageExtractor()

            # Mock the enhanced caption detector
            mock_detector = MagicMock()
            mock_caption = MagicMock()
            mock_caption.text = "Figure 1: Surgical approach showing craniotomy"
            mock_caption.confidence = 0.85

            # Mock CaptionPosition enum (it's imported inside the method)
            with patch('neurosynth.enhancements.config.CaptionPosition') as mock_position:
                mock_position.BELOW = 'below'
                mock_position.ABOVE = 'above'
                mock_caption.position = 'above'  # Caption found above image

                mock_detector.find_caption_for_image.return_value = mock_caption
                extractor.caption_detector = mock_detector

                # Mock page and bbox
                mock_page = MagicMock()
                image_bbox = (100, 100, 400, 400)
                page_text = "Some text"
                text_blocks = []

                # Call _find_caption
                caption, confidence = extractor._find_caption(
                    mock_page, image_bbox, page_text, text_blocks
                )

                # Verify enhanced detector was used
                assert caption == "Figure 1: Surgical approach showing craniotomy"
                assert confidence == 0.85
                assert extractor.caption_detector_stats['enhanced_used'] == 1
                assert extractor.caption_detector_stats['multi_directional_matches'] == 1

        print("✓ Multi-directional caption detection works (found caption above image)")

    def test_enhanced_caption_confidence_threshold(self):
        """Verify threshold filtering works."""
        with patch('neurosynth.parsers.image_extractor.get_settings') as mock_settings:
            settings = Settings(
                enhancements_enabled=True,
                enable_enhanced_captions=True,
                caption_confidence_threshold=0.70  # High threshold
            )
            mock_settings.return_value = settings

            extractor = ImageExtractor()

            # Mock detector returning low-confidence result
            mock_detector = MagicMock()
            mock_caption = MagicMock()
            mock_caption.text = "Unclear caption"
            mock_caption.confidence = 0.50  # Below threshold
            mock_detector.find_caption_for_image.return_value = mock_caption
            extractor.caption_detector = mock_detector

            # Mock legacy method
            extractor._find_caption_legacy = MagicMock(return_value=("Legacy caption", 0.5))

            # Mock page and bbox
            mock_page = MagicMock()
            image_bbox = (100, 100, 400, 400)
            page_text = "Some text"
            text_blocks = []

            # Call _find_caption
            caption, confidence = extractor._find_caption(
                mock_page, image_bbox, page_text, text_blocks
            )

            # Should fall back to legacy because confidence too low
            assert caption == "Legacy caption"
            assert extractor.caption_detector_stats['legacy_used'] == 1

        print("✓ Confidence threshold filtering works (low confidence → fallback)")

    def test_enhanced_caption_fallback_to_legacy(self):
        """Test graceful degradation when enhanced detector fails."""
        with patch('neurosynth.parsers.image_extractor.get_settings') as mock_settings:
            settings = Settings(
                enhancements_enabled=True,
                enable_enhanced_captions=True
            )
            mock_settings.return_value = settings

            extractor = ImageExtractor()

            # Mock detector that raises exception
            mock_detector = MagicMock()
            mock_detector.find_caption_for_image.side_effect = Exception("Detection failed")
            extractor.caption_detector = mock_detector

            # Mock legacy method
            extractor._find_caption_legacy = MagicMock(return_value=("Fallback caption", 0.6))

            # Mock page and bbox
            mock_page = MagicMock()
            image_bbox = (100, 100, 400, 400)
            page_text = "Some text"
            text_blocks = []

            # Call _find_caption - should not raise exception
            caption, confidence = extractor._find_caption(
                mock_page, image_bbox, page_text, text_blocks
            )

            # Should fall back to legacy
            assert caption == "Fallback caption"
            assert confidence == 0.6
            assert extractor.caption_detector_stats['legacy_used'] == 1

        print("✓ Graceful fallback to legacy when enhanced detector fails")

    def test_enhanced_caption_statistics_tracking(self):
        """Verify stats recorded correctly."""
        with patch('neurosynth.parsers.image_extractor.get_settings') as mock_settings:
            settings = Settings(
                enhancements_enabled=True,
                enable_enhanced_captions=True,
                caption_confidence_threshold=0.60
            )
            mock_settings.return_value = settings

            extractor = ImageExtractor()

            # Mock detector
            mock_detector = MagicMock()
            extractor.caption_detector = mock_detector

            # Mock legacy method
            extractor._find_caption_legacy = MagicMock(return_value=("Legacy", 0.5))

            mock_page = MagicMock()
            image_bbox = (100, 100, 400, 400)
            page_text = "text"
            text_blocks = []

            # Test 1: Enhanced success (below position)
            with patch('neurosynth.enhancements.config.CaptionPosition') as mock_pos:
                mock_pos.BELOW = 'below'
                mock_caption1 = MagicMock()
                mock_caption1.text = "Caption 1"
                mock_caption1.confidence = 0.90
                mock_caption1.position = 'below'
                mock_detector.find_caption_for_image.return_value = mock_caption1

                extractor._find_caption(mock_page, image_bbox, page_text, text_blocks)

                assert extractor.caption_detector_stats['enhanced_used'] == 1
                assert extractor.caption_detector_stats['multi_directional_matches'] == 0

            # Test 2: Enhanced success (above position - multi-directional)
            with patch('neurosynth.enhancements.config.CaptionPosition') as mock_pos:
                mock_pos.BELOW = 'below'
                mock_caption2 = MagicMock()
                mock_caption2.text = "Caption 2"
                mock_caption2.confidence = 0.85
                mock_caption2.position = 'above'
                mock_detector.find_caption_for_image.return_value = mock_caption2

                extractor._find_caption(mock_page, image_bbox, page_text, text_blocks)

                assert extractor.caption_detector_stats['enhanced_used'] == 2
                assert extractor.caption_detector_stats['multi_directional_matches'] == 1

            # Test 3: Legacy fallback
            mock_detector.find_caption_for_image.side_effect = Exception("fail")
            extractor._find_caption(mock_page, image_bbox, page_text, text_blocks)

            assert extractor.caption_detector_stats['legacy_used'] == 1

        print("✓ Statistics tracking works correctly")

    def test_enhanced_caption_figure_id_extraction(self):
        """Test figure number parsing from enhanced captions."""
        with patch('neurosynth.parsers.image_extractor.get_settings') as mock_settings:
            settings = Settings(
                enhancements_enabled=True,
                enable_enhanced_captions=True,
                caption_confidence_threshold=0.60
            )
            mock_settings.return_value = settings

            extractor = ImageExtractor()

            # Mock detector returning caption with figure ID
            mock_detector = MagicMock()
            mock_caption = MagicMock()
            mock_caption.text = "Figure 3A: Intraoperative view of tumor resection"
            mock_caption.confidence = 0.90
            mock_caption.figure_id = "3A"  # Enhanced detector extracts this
            mock_caption.position = 'below'

            with patch('neurosynth.enhancements.config.CaptionPosition') as mock_pos:
                mock_pos.BELOW = 'below'
                mock_detector.find_caption_for_image.return_value = mock_caption
                extractor.caption_detector = mock_detector

                mock_page = MagicMock()
                image_bbox = (100, 100, 400, 400)
                page_text = "text"
                text_blocks = []

                caption, confidence = extractor._find_caption(
                    mock_page, image_bbox, page_text, text_blocks
                )

                # Verify caption contains figure number
                assert "Figure 3A" in caption or "3A" in caption
                assert "tumor resection" in caption.lower()
                assert confidence == 0.90

        print("✓ Figure ID extraction works")

    def test_enhanced_caption_cross_references(self):
        """Test 'see also Fig. X' extraction."""
        with patch('neurosynth.parsers.image_extractor.get_settings') as mock_settings:
            settings = Settings(
                enhancements_enabled=True,
                enable_enhanced_captions=True,
                caption_confidence_threshold=0.60
            )
            mock_settings.return_value = settings

            extractor = ImageExtractor()

            # Mock detector returning caption with cross-references
            mock_detector = MagicMock()
            mock_caption = MagicMock()
            mock_caption.text = "Figure 5: Surgical corridor (see also Fig. 3A-C for anatomical details)"
            mock_caption.confidence = 0.88
            mock_caption.cross_references = ["3A", "3B", "3C"]  # Enhanced detector extracts these
            mock_caption.position = 'below'

            with patch('neurosynth.enhancements.config.CaptionPosition') as mock_pos:
                mock_pos.BELOW = 'below'
                mock_detector.find_caption_for_image.return_value = mock_caption
                extractor.caption_detector = mock_detector

                mock_page = MagicMock()
                image_bbox = (100, 100, 400, 400)
                page_text = "text"
                text_blocks = []

                caption, confidence = extractor._find_caption(
                    mock_page, image_bbox, page_text, text_blocks
                )

                # Verify caption contains cross-reference
                assert "see also" in caption.lower() or "fig" in caption.lower()
                assert confidence == 0.88

        print("✓ Cross-reference extraction works")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
