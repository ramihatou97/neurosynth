import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, mock_open, patch

# Ensure src is in path
sys.path.append(str(Path(__file__).parent.parent))

# Mock modules that might not be easily importable or need DB
# Mocks MUST be set up BEFORE importing modules that use them
sys.modules["index.database"] = MagicMock()
sys.modules["deep_dx.config"] = MagicMock()
sys.modules["ai.client"] = MagicMock()
sys.modules["rich"] = MagicMock()
sys.modules["rich.console"] = MagicMock()
sys.modules["rich.panel"] = MagicMock()
sys.modules["rich.progress"] = MagicMock()
sys.modules["rich.table"] = MagicMock()
# Also mock typer if needed
sys.modules["typer"] = MagicMock()
sys.modules["pydantic_settings"] = MagicMock()
# Mock neurosynth.config to avoid pydantic dependency issues
sys.modules["neurosynth.config"] = MagicMock()
# Mock Qdrant
sys.modules["qdrant_client"] = MagicMock()
sys.modules["qdrant_client.http"] = MagicMock()
sys.modules["qdrant_client.models"] = MagicMock()
# Mock LLM clients
sys.modules["neurosynth.llm"] = MagicMock()
sys.modules["neurosynth.llm.voyage"] = MagicMock()
sys.modules["neurosynth.llm.gemini"] = MagicMock()
sys.modules["numpy"] = MagicMock()

from bridges.library_to_deepdx import LibraryToDeepDxBridge
from deep_dx.retrieval.ingest_to_db import DeepDxIngestor
from models import Chunk, ChunkType
from neurosynth.integration.evidence import (
    EvidenceDetection,
    EvidenceDetector,
    EvidenceLevel,
)

# Now import the classes to test
# We need to patch the imports INSIDE the modules we are testing if they import at top level
# But specific imports like 'from index.database import Database' happen at import time.
# By mocking sys.modules before import, we control them.


class TestEvidenceIntegration(unittest.TestCase):
    def setUp(self):
        self.mock_detector = MagicMock(spec=EvidenceDetector)
        # Setup mock return value
        self.mock_detector.detect.return_value = EvidenceDetection(
            level=EvidenceLevel.LEVEL_1A, confidence=0.9, indicators=["randomized"]
        )

    @patch("deep_dx.retrieval.ingest_to_db.fitz")
    @patch("deep_dx.retrieval.ingest_to_db.get_deepdx_settings")
    @patch("deep_dx.retrieval.ingest_to_db.Database")
    @patch("deep_dx.retrieval.ingest_to_db.EvidenceDetector")
    def test_deepdx_ingestor_evidence(
        self, MockEvidenceDetector, MockDatabase, MockSettings, MockFitz
    ):
        # Setup
        MockEvidenceDetector.return_value = self.mock_detector
        ingestor = DeepDxIngestor()

        # Mock PDF content
        mock_doc = MagicMock()
        mock_page = MagicMock()
        mock_page.get_text.return_value = (
            "Randomized controlled trial showing significant benefit."
        )
        mock_doc.__len__.return_value = 1
        mock_doc.__iter__.return_value = iter([mock_page])
        MockFitz.open.return_value = mock_doc

        # Mock DB source check
        ingestor.db.source_exists.return_value = False

        # Run
        ingestor.ingest_pdf(Path("test_study.pdf"))

        # Verify
        # Check if insert_chunks was called
        self.assertTrue(ingestor.db.insert_chunks.called)
        chunks = ingestor.db.insert_chunks.call_args[0][0]
        self.assertTrue(len(chunks) > 0)

        chunk = chunks[0]
        # Check evidence level
        self.assertEqual(chunk.evidence_level, "1a")
        # Check detector was called
        self.mock_detector.detect.assert_called()

    @patch("bridges.library_to_deepdx.chunk_text")
    @patch("bridges.library_to_deepdx.Database")
    @patch("bridges.library_to_deepdx.EvidenceDetector")
    @patch("bridges.library_to_deepdx.AIClient")
    def test_bridge_evidence(
        self, MockAIClient, MockEvidenceDetector, MockDatabase, MockChunkText
    ):
        # Setup
        MockEvidenceDetector.return_value = self.mock_detector
        # Mock chunk_text to return valid chunks
        MockChunkText.return_value = [("Clinical trial content.", 0, 20)]

        bridge = LibraryToDeepDxBridge(
            source_db=Path("dummy.db"), target_db=Path("dummy.db"), skip_qdrant=True
        )
        # Mock connections
        bridge._source_conn = MagicMock()

        # Mock process_file input
        file_info = {
            "pdf_path": "study.pdf",
            "chapter_title": "Test Study",
            "cached_pages": 1,
        }

        # Mock get_page_text
        long_text = "Clinical trial content. " * 3  # > 50 chars
        bridge.get_page_text = MagicMock(return_value={1: long_text})

        # Run process_file (it's async but we can just call it if not awaiting async calls inside?)
        # process_file is async def. We need to run it.
        import asyncio

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        source, chunks = loop.run_until_complete(bridge.process_file(file_info))

        # Verify
        self.assertTrue(len(chunks) > 0)
        chunk = chunks[0]
        self.assertEqual(chunk.evidence_level, "1a")
        self.mock_detector.detect.assert_called()

    @patch("neurosynth.chunking.chunker.get_settings")
    @patch("neurosynth.chunking.chunker.EvidenceDetector")
    # Do NOT patch Document, use real class
    def test_semantic_chunker_evidence(self, MockEvidenceDetector, MockGetSettings):
        # Setup
        MockEvidenceDetector.return_value = self.mock_detector
        settings = MagicMock()
        settings.chunk_size = 1000
        settings.chunk_overlap = 100
        MockGetSettings.return_value = settings

        # Import locally to avoid import errors if modules not mocked perfectly globally
        from neurosynth.chunking.chunker import ChunkingStrategy, SemanticChunker
        from neurosynth.models.document import (
            ContentChunk,
            Document,
            DocumentFormat,
            Source,
        )

        chunker = SemanticChunker(strategy=ChunkingStrategy.FIXED)

        # Create a real Document object
        # Since we are using real Document, ensure numpy is mocked if it's used
        # (It's used for embeddings, but we don't use embeddings here)

        source = Source(
            path=Path("test.pdf"), format=DocumentFormat.PDF, title="Test Doc"
        )
        doc = Document(source=source, raw_text="Evidence based medicine trial. " * 50)

        # Run
        import asyncio

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        chunks = loop.run_until_complete(chunker.chunk_document(doc))

        # Verify
        self.assertTrue(len(chunks) > 0, "No chunks were generated")
        for chunk in chunks:
            self.assertEqual(chunk.evidence_level, "1a")
            # Also verify basic chunk properties
            self.assertIsInstance(chunk, ContentChunk)
        self.mock_detector.detect.assert_called()


if __name__ == "__main__":
    unittest.main()
