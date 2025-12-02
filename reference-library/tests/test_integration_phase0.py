"""Integration Test for Phase 0 Pipeline.

Verifies the entire flow:
Search -> Intent/Authority -> Result Model -> Extraction -> Manifest
"""
import sys
import unittest
import json
from unittest.mock import MagicMock, patch, mock_open
from pathlib import Path

# Add reference-library to path
sys.path.append(str(Path(__file__).parent.parent))

from src.search.pdf_searcher import PDFSearcher
from src.search.result_model import MatchType, MatchLocation
from src.export.page_extractor import extract_relevant_pages, generate_manifest

class TestPhase0Integration(unittest.TestCase):
    def setUp(self):
        self.mock_db = MagicMock()
        self.mock_scanner = MagicMock()
        
        # Patch LibraryScanner
        with patch('src.search.pdf_searcher.LibraryScanner', return_value=self.mock_scanner):
            # Patch ProcessPoolExecutor to use ThreadPoolExecutor (mocks can't be pickled)
            with patch('concurrent.futures.ProcessPoolExecutor', side_effect=lambda **kwargs: __import__('concurrent.futures').futures.ThreadPoolExecutor(**kwargs)):
                self.searcher = PDFSearcher(Path("."), self.mock_db, enable_query_expansion=False)
            
        # Create dummy PDF file
        self.pdf_path = Path("Lawton_Seven_Aneurysms.pdf")
        self.pdf_path.touch()

    def tearDown(self):
        if self.pdf_path.exists():
            self.pdf_path.unlink()

    def test_full_pipeline(self):
        print("\nTesting Full Phase 0 Pipeline...")
        
        # --- Step 1: Search ---
        print("1. Executing Search...")
        
        # Mock PDF Metadata
        pdf_path = Path("Lawton_Seven_Aneurysms.pdf")
        self.mock_scanner.get_all_pdfs.return_value = [pdf_path]
        mock_metadata = MagicMock()
        mock_metadata.chapter_title = "Vascular Neurosurgery" # Generic title
        mock_metadata.book_series = "Lawton"
        self.mock_scanner.get_pdf_metadata.return_value = mock_metadata
        
        # Mock Page Count
        self.searcher._get_pdf_page_count = MagicMock(return_value=100)
        
        # Mock Cached Text (for section detection)
        self.mock_db.get_all_cached_pages.return_value = {
            4: "Page 5 text... \n1. Surgical Technique\n ... basilar aneurysm ...",
            5: "Page 6 text... step 1...",
            6: "Page 7 text... step 2...",
            7: "Page 8 text... \n2. Complications\n ... bleeding ..."
        }
        
        # Mock Search Matches
        self.searcher.search_pdf_aggregated = MagicMock(return_value={
            5: {
                'locations': [MatchLocation.BODY_TEXT],
                'best_context': "context",
                'best_match_text': "match",
                'match_count': 1,
                'is_title_match': False
            }
        })
        
        # Execute Search
        results = list(self.searcher.search_library_chapters("basilar aneurysm technique"))
        self.assertEqual(len(results), 1)
        result = results[0]
        
        # Verify Search Result Metadata
        print(f"   Result: {result.chapter_title}")
        print(f"   Authority: {result.authority_score}")
        print(f"   Sections: {[s.title for s in result.matched_sections]}")
        
        self.assertEqual(result.authority_score, 100)
        self.assertEqual(result.match_type, MatchType.RELATED_SECTION)
        self.assertEqual(len(result.matched_sections), 1)
        self.assertEqual(result.matched_sections[0].title, "1. Surgical Technique")
        
        # --- Step 2: Extraction ---
        print("2. Executing Extraction...")
        
        # Mock fitz.open for extraction
        mock_doc = MagicMock()
        mock_doc.__len__.return_value = 100
        mock_page = MagicMock()
        mock_page.get_text.return_value = "Extracted Text"
        mock_doc.load_page.return_value = mock_page
        
        # Mock new_doc (output PDF)
        mock_new_doc = MagicMock()
        
        with patch('fitz.open', side_effect=[mock_doc, mock_new_doc]):
            # Mock output dir
            output_dir = MagicMock()
            mock_path = MagicMock()
            mock_path.exists.return_value = False
            output_dir.__truediv__.return_value = mock_path
            
            extracted = extract_relevant_pages([result], output_dir)
            
        self.assertEqual(len(extracted), 1)
        source = extracted[0]
        
        # Verify Extracted Source Metadata
        print(f"   Extracted Authority: {source.authority_score}")
        print(f"   Extracted Intent: {source.intent}")
        print(f"   Extracted Sections: {source.matched_sections}")
        
        self.assertEqual(source.authority_score, 100)
        self.assertEqual(source.intent, "RELATED_SECTION") # Enum name
        self.assertEqual(source.matched_sections, ["1. Surgical Technique"])
        self.assertEqual(source.pages, [5, 6, 7, 8, 9]) # Zero Data Loss Window
        
        # --- Step 3: Manifest Generation ---
        print("3. Generating Manifest...")
        
        # Mock json.dump
        mock_file = mock_open()
        with patch('builtins.open', mock_file):
            generate_manifest(
                topic="Test Topic",
                sources=extracted,
                output_path=Path("manifest.json"),
                search_query="basilar aneurysm technique"
            )
            
        # Verify JSON content
        # Get the arguments passed to json.dump
        # We need to find the call to json.dump
        # Since we patched open, json.dump writes to the file handle
        
        # Alternatively, patch json.dump
        with patch('json.dump') as mock_json_dump:
            with patch('builtins.open', mock_open()):
                 generate_manifest(
                    topic="Test Topic",
                    sources=extracted,
                    output_path=Path("manifest.json"),
                    search_query="basilar aneurysm technique"
                )
            
            args, _ = mock_json_dump.call_args
            manifest_data = args[0]
            
            print("   Manifest Data Verified")
            source_data = manifest_data['sources'][0]
            self.assertEqual(source_data['authority_score'], 100)
            self.assertEqual(source_data['matched_sections'], ["1. Surgical Technique"])
            self.assertEqual(source_data['intent'], "RELATED_SECTION")

if __name__ == "__main__":
    unittest.main()
