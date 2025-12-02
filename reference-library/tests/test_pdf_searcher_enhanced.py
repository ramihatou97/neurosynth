"""Test script for Enhanced PDF Searcher."""
import sys
import unittest
from unittest.mock import MagicMock, patch
from pathlib import Path

# Add reference-library to path
sys.path.append(str(Path(__file__).parent.parent))

from src.search.pdf_searcher import PDFSearcher
from src.search.result_model import MatchType, MatchLocation
from src.search.query_intent_lean import QueryIntent
from src.search.section_detector import DetectedSection, MatchConfidence

class TestEnhancedSearcher(unittest.TestCase):
    def setUp(self):
        self.mock_db = MagicMock()
        self.mock_scanner = MagicMock()
        
        # Patch LibraryScanner to return our mock
        with patch('src.search.pdf_searcher.LibraryScanner', return_value=self.mock_scanner):
            self.searcher = PDFSearcher(Path("."), self.mock_db, enable_query_expansion=False)

    def test_search_flow(self):
        print("\nTesting Enhanced Search Flow...")
        
        # Setup Mocks
        pdf_path = Path("Lawton_Seven_Aneurysms.pdf")
        self.mock_scanner.get_all_pdfs.return_value = [pdf_path]
        
        mock_metadata = MagicMock()
        mock_metadata.chapter_title = "Vascular Neurosurgery"
        mock_metadata.book_series = "Lawton"
        mock_metadata.book_title = "Seven Aneurysms"
        mock_metadata.chapter_number = 5
        self.mock_scanner.get_pdf_metadata.return_value = mock_metadata
        
        self.mock_db.get_file_checksum.return_value = "checksum"
        self.mock_db.get_all_cached_pages.return_value = {
            4: "Page 5 text... \n1. Surgical Technique\n ... basilar aneurysm ...", # Page 5 (0-indexed 4)
            5: "Page 6 text... step 1...",
            6: "Page 7 text... step 2...",
            7: "Page 8 text... \n2. Complications\n ... bleeding ..."
        }
        
        # Mock page count
        self.searcher._get_pdf_page_count = MagicMock(return_value=100)
        
        # Mock search_pdf_aggregated to return matches
        # We simulate finding "basilar aneurysm" on page 5
        self.searcher.search_pdf_aggregated = MagicMock(return_value={
            5: { # Page 5
                'locations': [MatchLocation.BODY_TEXT],
                'best_context': "context",
                'best_match_text': "match",
                'match_count': 1,
                'is_title_match': False
            }
        })
        
        # Mock Section Detector to find "Surgical Technique" on page 5
        # We need to patch the real one or just let it run if the text supports it.
        # Since I used real text above, let's see if the real detector finds it.
        # But I need to make sure the searcher uses the text I provided.
        # The searcher calls database.get_all_cached_pages, which I mocked.
        
        # Execute Search
        # Query: "basilar aneurysm technique" -> Intent: TECHNIQUE
        results = list(self.searcher.search_library_chapters("basilar aneurysm technique"))
        
        # Verification
        self.assertEqual(len(results), 1)
        res = results[0]
        
        print(f"Result: {res.chapter_title}")
        print(f"Match Type: {res.match_type}")
        print(f"Authority Score: {res.authority_score}")
        print(f"Matched Sections: {[s.title for s in res.matched_sections]}")
        print(f"Matched Pages: {res.matched_pages}")
        
        # Assertions
        self.assertEqual(res.authority_score, 100) # Lawton = 100
        self.assertEqual(res.match_type, MatchType.RELATED_SECTION) # Found section
        self.assertTrue(any(s.section_type == "Technique" for s in res.matched_sections))
        # Zero Data Loss: Should include pages 5, 6, 7 (until Complications at page 8)
        # Page 5 is start. Next section is at Page 8. Window should be 5-8.
        # Wait, my mock text has "2. Complications" on page 8 (index 7).
        # So window should be 5, 6, 7, 8.
        self.assertIn(5, res.matched_pages)
        self.assertIn(6, res.matched_pages)

if __name__ == "__main__":
    unittest.main()
