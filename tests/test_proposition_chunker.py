import sys
from unittest.mock import MagicMock

# START MOCKING
# 0. System Dependencies
mock_structlog = MagicMock()
sys.modules["structlog"] = mock_structlog

# 1. Config
mock_config_module = MagicMock()
mock_config_module.settings.chunk_size = 1500
mock_config_module.settings.chunk_overlap = 200
sys.modules["neurosynth.config"] = mock_config_module

mock_src = MagicMock()
mock_src.config = mock_config_module
sys.modules["src"] = mock_src
sys.modules["src.config"] = mock_config_module

# 1.5 Index Siblings (Prevent __init__ crash)
mock_chunker = MagicMock()
sys.modules["index.chunker"] = mock_chunker
mock_precision = MagicMock()
sys.modules["index.precision_search"] = mock_precision

# 2. Models
mock_models = MagicMock()


class MockSection:
    def __init__(self, title, level, page_start, page_end, content, images):
        self.title = title
        self.level = level
        self.page_start = page_start
        self.page_end = page_end
        self.content = content
        self.images = images


class MockChunk:
    def __init__(
        self,
        id,
        source_id,
        source_title,
        section_title,
        content,
        chunk_type,
        page_start,
        page_end,
        image_ids,
        evidence_level,
        parent_context,
        is_proposition,
    ):
        self.id = id
        self.source_id = source_id
        self.source_title = source_title
        self.section_title = section_title
        self.content = content
        self.chunk_type = chunk_type
        self.page_start = page_start
        self.page_end = page_end
        self.image_ids = image_ids
        self.evidence_level = evidence_level
        self.parent_context = parent_context
        self.is_proposition = is_proposition


mock_models.Section = MockSection
mock_models.Chunk = MockChunk
mock_models.ChunkType = MagicMock()
sys.modules["neurosynth.models"] = mock_models
sys.modules["src.models"] = mock_models

# 1.5 Index Siblings (Prevent __init__ crash - needs models)
mock_database = MagicMock()
sys.modules["index.database"] = mock_database  # Now safe

mock_chunker = MagicMock()
sys.modules["index.chunker"] = mock_chunker
mock_precision = MagicMock()
sys.modules["index.precision_search"] = mock_precision
mock_search = MagicMock()
sys.modules["index.search"] = mock_search

# 3. Evidence
mock_evidence = MagicMock()
mock_detection = MagicMock()
mock_detection.level.value = "unknown"
mock_evidence.detect_evidence_level.return_value = mock_detection
sys.modules["neurosynth.integration.evidence"] = mock_evidence

import pytest

# END MOCKING
from index.proposition_chunker import PropositionChunker

# Restore real modules so other tests are unaffected
import importlib

try:
    sys.modules["src"] = importlib.import_module("src")
    sys.modules["src.config"] = importlib.import_module("src.config")
    sys.modules["neurosynth.config"] = importlib.import_module("neurosynth.config")
    sys.modules["neurosynth.models"] = importlib.import_module("neurosynth.models")
    sys.modules["structlog"] = importlib.import_module("structlog")
except ImportError:
    sys.modules.pop("src", None)
    sys.modules.pop("src.config", None)
    sys.modules.pop("neurosynth.config", None)
    sys.modules.pop("neurosynth.models", None)
    sys.modules.pop("structlog", None)

sys.modules.pop("index.chunker", None)
sys.modules.pop("index.precision_search", None)
sys.modules.pop("index.search", None)
sys.modules.pop("index.database", None)
sys.modules.pop("neurosynth.integration.evidence", None)

@pytest.fixture
def chunker():
    return PropositionChunker(target_chunk_size=50)  # Small size for testing


def test_split_sentences(chunker):
    text = "Dr. Smith oper. on the patient. The result was good! Was it? Yes."
    sentences = chunker._split_sentences(text)

    assert "Dr. Smith oper. on the patient." in sentences
    assert "The result was good!" in sentences
    assert "Was it?" in sentences
    assert "Yes." in sentences
    assert len(sentences) == 4


def test_group_sentences(chunker):
    # sents of len ~10
    sentences = ["Sent 1.", "Sent 2.", "Sent 3.", "Sent 4 is longer."]

    groups = chunker._group_sentences(sentences)
    assert len(groups) == 1
    assert groups[0] == "Sent 1. Sent 2. Sent 3. Sent 4 is longer."


def test_group_sentences_overflow(chunker):
    # Force split
    sentences = ["A" * 40, "B" * 40]

    groups = chunker._group_sentences(sentences)
    assert len(groups) == 2
    assert groups[0] == "A" * 40
    assert groups[1] == "B" * 40


def test_enrichment():
    chunker = PropositionChunker()
    # Ensure chunker uses our mock Section
    section = MockSection(
        title="My Section",
        level=1,
        page_start=1,
        page_end=1,
        content="This is a test sentence.",
        images=[],
    )
    chunks = chunker.chunk_section(section, "source_1", "My Chapter")

    assert len(chunks) == 1
    c = chunks[0]

    # Check Enrichment Header
    assert "Source: My Chapter" in c.content
    assert "Section: My Section" in c.content
    assert "Evidence: unknown" in c.content

    # Check Metadata
    assert c.parent_context == "This is a test sentence."
    assert c.is_proposition is True
