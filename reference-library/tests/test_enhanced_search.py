"""Unit tests for Enhanced Search modules (Phase 0).

Tests:
- MasterIndex: COMPREHENSIVE.ini parsing and authority lookup
- IntentDetector: Query intent classification
- SectionDetector: Section header detection and window calculation
"""
import sys
import pytest
from pathlib import Path

# Add reference-library to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.search.master_index import get_master_index, MasterIndex, TEXT_AUTHORITY
from src.search.query_intent_lean import get_intent_detector, IntentDetector, QueryIntent, IntentResult
from src.search.section_detector import get_section_detector, SectionDetector, MatchConfidence, DetectedSection


# ============================================================================
# MasterIndex Tests
# ============================================================================

class TestMasterIndex:
    """Tests for MasterIndex parser."""
    
    @pytest.fixture
    def index(self):
        """Get singleton MasterIndex."""
        return get_master_index()
    
    def test_singleton(self):
        """Test that get_master_index returns a singleton."""
        idx1 = get_master_index()
        idx2 = get_master_index()
        assert idx1 is idx2
    
    def test_find_term_exact(self, index):
        """Test exact term lookup."""
        # Assuming COMPREHENSIVE.ini has "aneurysm" entries
        matches = index.find_term("aneurysm")
        assert len(matches) > 0
        assert any("aneurysm" in m.term.lower() for m in matches)
    
    def test_find_term_case_insensitive(self, index):
        """Test case-insensitive matching."""
        lower = index.find_term("aneurysm")
        upper = index.find_term("ANEURYSM")
        mixed = index.find_term("Aneurysm")
        
        # All should return results
        assert len(lower) > 0
        assert len(upper) > 0
        assert len(mixed) > 0
    
    def test_authority_boost_lawton(self, index):
        """Test authority boost for Lawton Seven Aneurysms."""
        path = Path("/library/Lawton_Seven_Aneurysms_Ch1.pdf")
        boost = index.get_authority_boost(path)
        assert boost == TEXT_AUTHORITY["L7"]  # Should be 100
    
    def test_authority_boost_greenberg(self, index):
        """Test authority boost for Greenberg Handbook."""
        path = Path("/library/Greenberg_Handbook_9th.pdf")
        boost = index.get_authority_boost(path)
        assert boost == TEXT_AUTHORITY["GH"]  # Should be 80
    
    def test_authority_boost_default(self, index):
        """Test default authority boost for unknown text."""
        path = Path("/library/Unknown_Textbook.pdf")
        boost = index.get_authority_boost(path)
        assert boost == TEXT_AUTHORITY["DEFAULT"]  # Should be 70


# ============================================================================
# IntentDetector Tests
# ============================================================================

class TestIntentDetector:
    """Tests for IntentDetector."""
    
    @pytest.fixture
    def detector(self):
        """Get singleton IntentDetector."""
        return get_intent_detector()
    
    def test_singleton(self):
        """Test that get_intent_detector returns a singleton."""
        d1 = get_intent_detector()
        d2 = get_intent_detector()
        assert d1 is d2
    
    def test_technique_intent(self, detector):
        """Test TECHNIQUE intent detection."""
        result = detector.detect("basilar aneurysm technique")
        assert result.intent == QueryIntent.TECHNIQUE
        assert result.cleaned_query == "basilar aneurysm"
    
    def test_complication_intent(self, detector):
        """Test COMPLICATION intent detection."""
        result = detector.detect("lumbar discectomy complications")
        assert result.intent == QueryIntent.COMPLICATION
        assert result.cleaned_query == "lumbar discectomy"
    
    def test_anatomy_intent(self, detector):
        """Test ANATOMY intent detection."""
        result = detector.detect("middle cerebral artery anatomy")
        assert result.intent == QueryIntent.ANATOMY
    
    def test_protected_phrase_approach(self, detector):
        """Test that 'approach' is preserved in query."""
        result = detector.detect("pterional approach")
        assert result.intent == QueryIntent.TECHNIQUE
        assert result.cleaned_query == "pterional approach"  # NOT stripped
    
    def test_general_intent(self, detector):
        """Test GENERAL intent for non-specific queries."""
        result = detector.detect("history of neurosurgery")
        assert result.intent == QueryIntent.GENERAL
        assert result.cleaned_query == "history of neurosurgery"
    
    def test_suggested_sections_technique(self, detector):
        """Test that TECHNIQUE returns relevant section suggestions."""
        result = detector.detect("aneurysm technique")
        assert len(result.suggested_sections) > 0
        assert any("technique" in s.lower() for s in result.suggested_sections)


# ============================================================================
# SectionDetector Tests
# ============================================================================

class TestSectionDetector:
    """Tests for SectionDetector."""
    
    @pytest.fixture
    def detector(self):
        """Get singleton SectionDetector."""
        return get_section_detector()
    
    def test_singleton(self):
        """Test that get_section_detector returns a singleton."""
        d1 = get_section_detector()
        d2 = get_section_detector()
        assert d1 is d2

    def test_detect_numbered_header(self, detector):
        """Test detection of numbered section headers."""
        text = "1. Surgical Technique"
        sections = detector.detect_section_headers(text, page_num=5)
        assert len(sections) > 0
        assert sections[0].confidence == MatchConfidence.HIGH

    def test_detect_uppercase_header(self, detector):
        """Test detection of uppercase section headers."""
        text = "SURGICAL ANATOMY"
        sections = detector.detect_section_headers(text, page_num=10)
        assert len(sections) > 0

    def test_detect_complications_header(self, detector):
        """Test detection of complications section."""
        text = "COMPLICATIONS"  # Must match pattern exactly
        sections = detector.detect_section_headers(text, page_num=15)
        assert len(sections) > 0
        assert any(s.section_type == "Complication" for s in sections)

    def test_no_match_random_text(self, detector):
        """Test that random text doesn't match."""
        text = "Just some random text about nothing"
        sections = detector.detect_section_headers(text, page_num=25)
        assert len(sections) == 0

    def test_safe_extraction_window_with_next_section(self, detector):
        """Test window calculation when next section exists."""
        sections = [
            DetectedSection(title="Technique", section_type="Technique",
                          page_num=5, confidence=MatchConfidence.HIGH, start_offset=0),
            DetectedSection(title="Anatomy", section_type="Anatomy",
                          page_num=10, confidence=MatchConfidence.HIGH, start_offset=0),
        ]
        start, end = detector.get_safe_extraction_window(sections[0], sections, total_pages=100)
        assert start == 5
        assert end == 10  # Stops at next section

    def test_safe_extraction_window_last_section(self, detector):
        """Test window calculation for last section."""
        sections = [
            DetectedSection(title="Technique", section_type="Technique",
                          page_num=20, confidence=MatchConfidence.HIGH, start_offset=0),
        ]
        start, end = detector.get_safe_extraction_window(sections[0], sections, total_pages=100)
        assert start == 20
        assert end == 24  # Minimum 4 pages

    def test_fallback_section_window(self, detector):
        """Test fallback window creation."""
        start, end = detector.create_fallback_section(keyword_page=50, total_pages=100)
        assert start == 49  # -1 page
        assert end == 53    # +3 pages


# ============================================================================
# Integration Tests
# ============================================================================

class TestEnhancedSearchIntegration:
    """Integration tests for the enhanced search pipeline."""

    def test_intent_to_section_mapping(self):
        """Test that intent detection maps to appropriate sections."""
        intent_detector = get_intent_detector()

        # Detect intent
        result = intent_detector.detect("aneurysm technique")
        assert result.intent == QueryIntent.TECHNIQUE

        # Verify suggested sections are returned
        assert len(result.suggested_sections) > 0

        # Verify at least one section contains technique-related keywords
        technique_keywords = ["technique", "surgical", "operative", "steps", "procedure"]
        has_technique_section = any(
            any(kw in section.lower() for kw in technique_keywords)
            for section in result.suggested_sections
        )
        assert has_technique_section

    def test_authority_affects_ranking(self):
        """Test that authority scores affect result ranking."""
        index = get_master_index()

        # High authority source
        lawton_boost = index.get_authority_boost(Path("Lawton_Seven_Aneurysms.pdf"))

        # Lower authority source
        generic_boost = index.get_authority_boost(Path("Generic_Textbook.pdf"))

        assert lawton_boost > generic_boost

