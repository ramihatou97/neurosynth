
import sys
import os
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

try:
    from src import config
    print("Successfully imported src.config")
    print(f"Categories count: {len(config.CATEGORIES)}")
    print(f"Category Groups: {list(config.CATEGORY_GROUPS.keys())}")
except ImportError as e:
    print(f"Failed to import src.config: {e}")
    sys.exit(1)

from src.ai.categorizer import ContentCategorizer
from src.search.result_model import SearchResult
from src.cache.database import Database

# Mock Database
class MockDatabase(Database):
    def __init__(self):
        pass
    def compute_context_hash(self, term, context):
        return "hash"
    def get_cached_categorization(self, hash):
        return None
    def cache_categorization(self, *args):
        print("Caching result...")

def test_categorization():
    print("\nTesting ContentCategorizer...")
    
    # Check API Key
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("WARNING: ANTHROPIC_API_KEY not set. Categorization will fail/mock.")
    
    db = MockDatabase()
    categorizer = ContentCategorizer(api_key, db)
    
    # Mock Result
    result = SearchResult(
        pdf_path=Path("test.pdf"),
        book_series="Test Series",
        book_title="Test Book",
        chapter_number="1",
        chapter_title="Test Chapter",
        page_number=1,
        context="The surgical approach to vestibular schwannoma involves a retrosigmoid craniotomy. The patient is positioned supine with head turned.",
        match_text="vestibular schwannoma"
    )
    
    print(f"Categorizing result for query: 'vestibular schwannoma'")
    cat_result = categorizer.categorize_result(result, "vestibular schwannoma")
    
    print("\nCategorization Result:")
    print(f"Group: {cat_result.group}")
    print(f"Category: {cat_result.category}")
    print(f"Confidence: {cat_result.confidence}")
    print(f"Reasoning: {cat_result.reasoning}")

if __name__ == "__main__":
    test_categorization()
