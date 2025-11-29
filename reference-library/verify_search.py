
import sys
import os
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from src import config
from src.search.pdf_searcher import PDFSearcher
from src.cache.database import Database

# Mock Database
class MockDatabase(Database):
    def __init__(self):
        pass
    def is_page_indexed_semantically(self, *args):
        return False
    def track_semantic_index(self, *args):
        pass

# Mock Semantic Searcher
class MockSemanticSearcher:
    def __init__(self, database):
        self.enabled = True
    def search(self, query, n_results=30, category_filter=None):
        print(f"Semantic search called with query='{query}', filter='{category_filter}'")
        return []

def test_search_integration():
    print("\nTesting Search Integration...")
    
    db = MockDatabase()
    searcher = PDFSearcher(Path("."), db, enable_query_expansion=True)
    
    # Mock the semantic searcher to verify calls
    searcher.semantic = MockSemanticSearcher(db)
    
    # Test 1: Search with Surgical filter
    print("\nTest 1: Search with Surgical filter")
    list(searcher.search_library("test query", mode="semantic", category_filter="Surgical/Anatomical"))
    
    # Test 2: Search with Theoretical filter
    print("\nTest 2: Search with Theoretical filter")
    list(searcher.search_library("test query", mode="semantic", category_filter="Theoretical"))
    
    # Test 3: Search with No filter
    print("\nTest 3: Search with No filter")
    list(searcher.search_library("test query", mode="semantic", category_filter=None))

    # Test 4: Query Expansion (Keyword Mode)
    print("\nTest 4: Query Expansion (Keyword Mode)")
    # We can't easily mock the internal _find_matches without more complex mocking,
    # but we can verify the method exists and runs without error.
    try:
        # This will likely yield nothing since we have no PDFs, but it shouldn't crash
        list(searcher.search_library("vestibular schwannoma", mode="keyword"))
        print("Keyword search ran successfully")
    except Exception as e:
        print(f"Keyword search failed: {e}")

if __name__ == "__main__":
    test_search_integration()
