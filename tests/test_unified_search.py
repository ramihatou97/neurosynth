import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# START MOCKING
# 0. Dependencies
mock_structlog = MagicMock()
sys.modules["structlog"] = mock_structlog

# 1. Config (Both neurosynth and src.config paths)
mock_config_module = MagicMock()
mock_config_module.settings.search_mode = "fast"  # default
sys.modules["neurosynth.config"] = mock_config_module

mock_src = MagicMock()
mock_src.config = mock_config_module
sys.modules["src"] = mock_src
sys.modules["src.config"] = mock_config_module

# BLOCKAGE: Mock sibling modules in index package to prevent __init__ from crashing on imports
mock_precision = MagicMock()
sys.modules["index.precision_search"] = mock_precision
mock_search = MagicMock()
sys.modules["index.search"] = mock_search
mock_chunker = MagicMock()
sys.modules["index.chunker"] = mock_chunker

# 2. Database
mock_db_module = MagicMock()
mock_db_class = MagicMock()
mock_db_module.Database = mock_db_class
sys.modules["neurosynth.index.database"] = mock_db_module
sys.modules["src.index.database"] = mock_db_module  # Safety net

# 3. Models
mock_models_module = MagicMock()


# Create mock classes that act like data classes
class MockSearchResult:
    def __init__(self, chunk, score):
        self.chunk = chunk
        self.score = score


mock_models_module.SearchResult = MockSearchResult


class MockChunk:
    def __init__(self, id, content):
        self.id = id
        self.content = content
        self.parent_context = None  # <--- Added for Phase 2 hydration tests


mock_models_module.Chunk = MockChunk
mock_models_module.ChunkType = MagicMock()
mock_models_module.ExtractedImage = MagicMock()
sys.modules["neurosynth.models"] = mock_models_module
sys.modules["src.models"] = mock_models_module  # Safety net

# 4. Optional Deps
mock_biomed = MagicMock()
sys.modules["neurosynth.ai.biomed_searcher"] = mock_biomed
mock_colbert = MagicMock()
sys.modules["deep_dx.retrieval.colbert_client"] = mock_colbert
mock_qdrant = MagicMock()
sys.modules["deep_dx.retrieval.qdrant_retriever"] = mock_qdrant
mock_bm25 = MagicMock()
sys.modules["deep_dx.retrieval.bm25"] = mock_bm25

# 5. Connect Config
import neurosynth

neurosynth.config = mock_config_module
# Also bypass index/__init__ if possible? No, we need it.
# If we mock src.config, chunker.py should survive.

# END MOCKING - Import SUT
from index.unified_search import SearchMode, UnifiedSearchEngine

# Restore real modules so later tests aren't affected
import importlib

try:
    sys.modules["structlog"] = importlib.import_module("structlog")
except ImportError:
    sys.modules.pop("structlog", None)

sys.modules.pop("index.precision_search", None)
sys.modules.pop("index.search", None)
sys.modules.pop("index.chunker", None)
sys.modules.pop("neurosynth.index.database", None)
sys.modules.pop("src.index.database", None)
sys.modules.pop("neurosynth.ai.biomed_searcher", None)
sys.modules.pop("deep_dx.retrieval.colbert_client", None)
sys.modules.pop("deep_dx.retrieval.qdrant_retriever", None)
sys.modules.pop("deep_dx.retrieval.bm25", None)
try:
    import neurosynth as _neurosynth_pkg

    sys.modules["src"] = importlib.import_module("src")
    sys.modules["src.config"] = importlib.import_module("src.config")
    sys.modules["neurosynth.config"] = importlib.import_module("neurosynth.config")
    sys.modules["neurosynth.models"] = importlib.import_module("neurosynth.models")
    _neurosynth_pkg.config = sys.modules["neurosynth.config"]
except ImportError:
    sys.modules.pop("src", None)
    sys.modules.pop("src.config", None)
    sys.modules.pop("neurosynth.config", None)
    sys.modules.pop("neurosynth.models", None)


@pytest.fixture
def mock_db():
    return mock_db_class()


def test_init_fast_mode(mock_db):
    """Test initialization defaults."""
    engine = UnifiedSearchEngine(mock_db)
    assert engine.mode == SearchMode.FAST


def test_search_fast_only_qdrant(mock_db):
    """Test FAST mode only uses Qdrant."""
    engine = UnifiedSearchEngine(mock_db)
    # Mock Qdrant presence
    engine.qdrant = MagicMock()
    engine.qdrant.search.return_value = [MockSearchResult(MockChunk("1", "A"), 0.9)]

    result = engine.search("query", [0.1], mode=SearchMode.FAST)

    engine.qdrant.search.assert_called_once()
    assert len(result.chunks) == 1
    assert result.mode == SearchMode.FAST


def test_search_deep_fallback(mock_db):
    """Test falling back to BALANCED if ColBERT is missing."""
    engine = UnifiedSearchEngine(mock_db)
    engine.colbert = None  # force missing
    engine.bm25 = MagicMock()  # has bm25
    engine.qdrant = MagicMock()

    # Run with DEEP
    result = engine.search("query", [0.1], mode=SearchMode.DEEP)

    # Should downgrade
    assert result.mode == SearchMode.BALANCED
    assert "ColBERT unavailable" in result.warnings[0]


def test_search_balanced_mix(mock_db):
    """Test BALANCED mixes Qdrant and BM25."""
    engine = UnifiedSearchEngine(mock_db)
    engine.qdrant = MagicMock()
    engine.bm25 = MagicMock()

    # Qdrant returns ID 1
    engine.qdrant.search.return_value = [
        MockSearchResult(MockChunk("1", "VectorContent"), 0.9)
    ]
    # BM25 returns ID 2
    # Mock BM25 hit structure: tuple(dict, score) or similar depending on implementation
    # Implementation: self.bm25.search returns list of hits. hit[0] is doc dict.
    engine.bm25.search.return_value = [
        ({"chunk_obj": MockChunk("2", "KeywordContent")}, 10.0)
    ]

    result = engine.search("query", [0.1], mode=SearchMode.BALANCED)

    assert len(result.chunks) == 2
    ids = {c.chunk.id for c in result.chunks}
    assert "1" in ids
    assert "2" in ids


def test_search_hydration(mock_db):
    """Test that parent_context is swapped into content."""
    engine = UnifiedSearchEngine(mock_db)
    engine.qdrant = MagicMock()

    # Mock chunk with parent_context
    chunk = MockChunk("1", "Proposition Text")
    chunk.parent_context = "Full Section Context"

    engine.qdrant.search.return_value = [MockSearchResult(chunk, 0.9)]

    result = engine.search("query", [0.1], mode=SearchMode.FAST)

    assert len(result.chunks) == 1
    # Check that content was swapped
    assert result.chunks[0].chunk.content == "Full Section Context"
