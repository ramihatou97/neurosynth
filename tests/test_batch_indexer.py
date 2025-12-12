"""
Tests for BatchIndexer with Advanced RAG features.

Tests:
- Config-driven chunker selection (SemanticChunker vs PropositionChunker)
- RAPTOR integration
- GraphRAG integration
- Batch progress tracking
"""

from dataclasses import dataclass, field
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.models import Chunk, ChunkType, ExtractedImage, Section
from src.services.batch_indexer import (
    BatchIndexer,
    BatchProgress,
    FileProgress,
    IndexingStage,
)


@pytest.fixture
def mock_db():
    """Mock database with basic CRUD operations."""
    db = MagicMock()
    db.insert_source = MagicMock()
    db.insert_chunks = MagicMock()
    db.insert_image = MagicMock()
    return db


@pytest.fixture
def mock_processed_result():
    """Mock result from DocumentProcessor.process()"""
    result = MagicMock()
    result.metadata = {
        "source_id": "test-source-001",
        "title": "Test Neurosurgery Chapter",
        "authors": ["Smith J"],
        "year": 2023,
    }
    result.sections = [
        Section(
            title="Surgical Anatomy",
            level=1,
            page_start=1,
            page_end=5,
            content="The middle cerebral artery bifurcates at the limen insulae. "
            "The superior trunk supplies the motor cortex.",
            images=[],
        ),
        Section(
            title="Technique",
            level=1,
            page_start=6,
            page_end=10,
            content="A pterional craniotomy is performed with the patient supine. "
            "The head is rotated 30 degrees to the contralateral side.",
            images=[],
        ),
    ]
    result.images = []
    result.path = Path("/tmp/test.pdf")
    return result


@pytest.fixture
def mock_chunks():
    """Sample chunks returned by chunker."""
    return [
        Chunk(
            id="chunk-001",
            source_id="test-source-001",
            source_title="Test Chapter",
            section_title="Anatomy",
            content="The MCA bifurcates...",
            chunk_type=ChunkType.ANATOMY,
            page_start=1,
            page_end=2,
            embedding=[0.1] * 1024,
        ),
        Chunk(
            id="chunk-002",
            source_id="test-source-001",
            source_title="Test Chapter",
            section_title="Technique",
            content="Pterional craniotomy...",
            chunk_type=ChunkType.PROCEDURE_STEP,
            page_start=6,
            page_end=7,
            embedding=[0.2] * 1024,
        ),
    ]


class TestBatchIndexerConfig:
    """Test config-driven chunker selection."""

    @patch("src.index.chunker.SemanticChunker")
    @patch("src.services.batch_indexer.settings")
    def test_uses_semantic_chunker_when_proposition_disabled(
        self, mock_settings, MockSemanticChunker, mock_db
    ):
        """When enable_proposition_chunker=False, use SemanticChunker."""
        mock_settings.enable_proposition_chunker = False
        mock_settings.enable_raptor = False
        mock_settings.enable_graph_rag = False
        mock_settings.chunk_size = 1500
        mock_settings.chunk_overlap = 200

        MockSemanticChunker.return_value = MagicMock()
        indexer = BatchIndexer(mock_db)
        _ = indexer.chunker
        MockSemanticChunker.assert_called_once_with(chunk_size=1500, chunk_overlap=200)

    @patch("src.index.proposition_chunker.PropositionChunker")
    @patch("src.services.batch_indexer.settings")
    def test_uses_proposition_chunker_when_enabled(
        self, mock_settings, MockPropositionChunker, mock_db
    ):
        """When enable_proposition_chunker=True, use PropositionChunker."""
        mock_settings.enable_proposition_chunker = True
        mock_settings.enable_raptor = False
        mock_settings.enable_graph_rag = False
        mock_settings.chunk_size = 1500
        mock_settings.chunk_overlap = 200

        MockPropositionChunker.return_value = MagicMock()
        indexer = BatchIndexer(mock_db)
        _ = indexer.chunker
        MockPropositionChunker.assert_called_once_with(target_chunk_size=800)


class TestBatchIndexerPipeline:
    """Test the full indexing pipeline."""

    @patch("src.services.batch_indexer.settings")
    def test_index_batch_yields_progress(
        self, mock_settings, mock_db, mock_processed_result, mock_chunks
    ):
        """Verify batch indexing yields progress updates."""
        mock_settings.enable_proposition_chunker = False
        mock_settings.enable_raptor = False
        mock_settings.enable_graph_rag = False
        mock_settings.chunk_size = 1500
        mock_settings.chunk_overlap = 200

    @patch("src.services.batch_indexer.settings")
    def test_raptor_stage_runs_when_enabled(
        self, mock_settings, mock_db, mock_processed_result, mock_chunks
    ):
        """Verify RAPTOR stage runs when enabled."""
        mock_settings.enable_proposition_chunker = False
        mock_settings.enable_raptor = True
        mock_settings.enable_graph_rag = False
        mock_settings.chunk_size = 1500
        mock_settings.chunk_overlap = 200

        # Mock processor
        mock_processor = MagicMock()
        mock_processor.process.return_value = mock_processed_result

        # Mock chunker
        mock_chunker = MagicMock()
        mock_chunker.chunk_document.return_value = mock_chunks

        # Mock RAPTOR
        mock_raptor = MagicMock()
        mock_raptor.generate_tree = AsyncMock(
            return_value=[
                Chunk(
                    id="raptor-001",
                    source_id="test-source-001",
                    source_title="Test Chapter",
                    section_title="Summary",
                    content="Summary of surgical anatomy...",
                    chunk_type=ChunkType.NARRATIVE,
                    page_start=1,
                    page_end=10,
                )
            ]
        )

        indexer = BatchIndexer(mock_db, processor=mock_processor, chunker=mock_chunker)
        indexer._raptor = mock_raptor

        pdf_files = [Path("/tmp/test.pdf")]
        progress_updates = list(indexer.index_batch(pdf_files))

        # RAPTOR was called
        mock_raptor.generate_tree.assert_called_once()
        # Both regular chunks and RAPTOR chunks were inserted
        assert mock_db.insert_chunks.call_count == 2


class TestIndexingStages:
    """Test stage progression tracking."""

    def test_all_stages_exist(self):
        """Verify all expected stages are defined."""
        expected_stages = [
            "pending",
            "text_extraction",
            "chunking",
            "text_embedding",
            "image_extraction",
            "image_embedding",
            "raptor",
            "graph_rag",
            "storage",
            "complete",
            "failed",
        ]
        actual_stages = [s.value for s in IndexingStage]
        for stage in expected_stages:
            assert stage in actual_stages, f"Missing stage: {stage}"

    def test_file_progress_tracking(self):
        """Test FileProgress properties."""
        fp = FileProgress(
            file_path=Path("/tmp/test.pdf"),
            file_name="test.pdf",
            stage=IndexingStage.COMPLETE,
            chunks_created=50,
            images_extracted=10,
        )
        assert fp.is_complete is True
        assert fp.is_success is True

        fp.stage = IndexingStage.FAILED
        assert fp.is_complete is True
        assert fp.is_success is False

    def test_batch_progress_stats(self):
        """Test BatchProgress computed properties."""
        bp = BatchProgress(total_files=10, completed_files=5, failed_files=1)
        assert bp.percent_complete == 50.0

        # Zero files case
        bp_empty = BatchProgress(total_files=0)
        assert bp_empty.percent_complete == 100.0


class TestTextEmbedding:
    """Test text embedding integration."""

    @pytest.mark.asyncio
    async def test_async_embedder_embeds_chunks(self):
        """AsyncEmbedder should populate chunk embeddings."""
        from src.services.embedder import AsyncEmbedder

        chunks = [
            Chunk(
                id="embed-test-1",
                source_id="source-1",
                source_title="Test",
                section_title="Section 1",
                content="This is test content for embedding.",
                chunk_type=ChunkType.NARRATIVE,
                page_start=1,
                page_end=2,
            ),
            Chunk(
                id="embed-test-2",
                source_id="source-1",
                source_title="Test",
                section_title="Section 2",
                content="Another chunk to embed.",
                chunk_type=ChunkType.NARRATIVE,
                page_start=3,
                page_end=4,
            ),
        ]

        # Verify chunks start without embeddings
        assert chunks[0].embedding is None
        assert chunks[1].embedding is None

        with patch("src.ai.client.AsyncAIClient") as MockClient:
            mock_instance = MagicMock()
            mock_instance.get_embeddings = AsyncMock(
                return_value=[[0.1] * 1024, [0.2] * 1024]
            )
            MockClient.return_value = mock_instance

            embedder = AsyncEmbedder()
            result = await embedder.embed_chunks(chunks)

            # Verify embeddings were set
            assert result[0].embedding is not None
            assert result[1].embedding is not None
            assert len(result[0].embedding) == 1024
            assert len(result[1].embedding) == 1024

            # Verify API was called with correct texts
            mock_instance.get_embeddings.assert_called_once()
            call_args = mock_instance.get_embeddings.call_args[0][0]
            assert "This is test content" in call_args[0]
            assert "Another chunk" in call_args[1]

    @pytest.mark.asyncio
    async def test_async_embedder_handles_empty_list(self):
        """AsyncEmbedder should handle empty chunk list gracefully."""
        from src.services.embedder import AsyncEmbedder

        embedder = AsyncEmbedder()
        result = await embedder.embed_chunks([])

        assert result == []

    @patch("src.services.batch_indexer.settings")
    def test_batch_indexer_embeds_chunks(
        self, mock_settings, mock_db, mock_processed_result, mock_chunks
    ):
        """BatchIndexer should call embedder during TEXT_EMBEDDING stage."""
        mock_settings.enable_proposition_chunker = False
        mock_settings.enable_raptor = False
        mock_settings.enable_graph_rag = False
        mock_settings.chunk_size = 1500
        mock_settings.chunk_overlap = 200

        # Mock processor
        mock_processor = MagicMock()
        mock_processor.process.return_value = mock_processed_result

        # Mock chunker - return chunks WITHOUT embeddings initially
        chunks_without_embeddings = [
            Chunk(
                id="chunk-001",
                source_id="test-source-001",
                source_title="Test",
                section_title="Test Section",
                content="Test content",
                chunk_type=ChunkType.NARRATIVE,
                page_start=1,
                page_end=2,
                embedding=None,  # No embedding yet
            )
        ]
        mock_chunker = MagicMock()
        mock_chunker.chunk_document.return_value = chunks_without_embeddings

        indexer = BatchIndexer(mock_db, processor=mock_processor, chunker=mock_chunker)

        # Mock the embedder
        with patch.object(indexer, "_embed_chunks") as mock_embed:
            # Make embedder add embeddings
            def add_embeddings(chunks):
                for c in chunks:
                    c.embedding = [0.1] * 1024
                return chunks

            mock_embed.side_effect = add_embeddings

            pdf_files = [Path("/tmp/test.pdf")]
            list(indexer.index_batch(pdf_files))

            # Verify embedder was called
            mock_embed.assert_called_once()

            # Verify chunks passed to insert_chunks have embeddings
            insert_call = mock_db.insert_chunks.call_args
            inserted_chunks = insert_call[0][0]
            assert inserted_chunks[0].embedding is not None

    @patch("src.services.batch_indexer.settings")
    def test_batch_indexer_continues_on_embedding_failure(
        self, mock_settings, mock_db, mock_processed_result
    ):
        """BatchIndexer should continue even if embedding fails."""
        mock_settings.enable_proposition_chunker = False
        mock_settings.enable_raptor = False
        mock_settings.enable_graph_rag = False
        mock_settings.chunk_size = 1500
        mock_settings.chunk_overlap = 200

        # Mock processor
        mock_processor = MagicMock()
        mock_processor.process.return_value = mock_processed_result

        # Mock chunker
        mock_chunker = MagicMock()
        mock_chunker.chunk_document.return_value = [
            Chunk(
                id="chunk-001",
                source_id="test-source-001",
                source_title="Test",
                section_title="Test Section",
                content="Test content",
                chunk_type=ChunkType.NARRATIVE,
                page_start=1,
                page_end=2,
            )
        ]

        indexer = BatchIndexer(mock_db, processor=mock_processor, chunker=mock_chunker)

        # Make embedder raise an exception
        with patch.object(indexer, "_embed_chunks") as mock_embed:
            mock_embed.side_effect = Exception("API Error")

            pdf_files = [Path("/tmp/test.pdf")]
            progress_list = list(indexer.index_batch(pdf_files))

            # Indexing should complete despite embedding failure
            final_progress = progress_list[-1]
            assert final_progress.completed_files == 1

            # Chunks should still be inserted (without embeddings)
            mock_db.insert_chunks.assert_called_once()


class TestQdrantPush:
    """Tests for Qdrant vector store push functionality."""

    @pytest.fixture
    def mock_chunks_with_embeddings(self):
        """Create chunks with embeddings for Qdrant tests."""
        return [
            Chunk(
                id="chunk-001",
                source_id="test-source-001",
                source_title="Test Chapter",
                section_title="Anatomy",
                content="The brain is complex.",
                chunk_type=ChunkType.NARRATIVE,
                page_start=1,
                page_end=2,
                embedding=[0.1] * 1024,
            ),
            Chunk(
                id="chunk-002",
                source_id="test-source-001",
                source_title="Test Chapter",
                section_title="Procedure",
                content="Surgical technique details.",
                chunk_type=ChunkType.PROCEDURE_STEP,
                page_start=3,
                page_end=4,
                embedding=[0.2] * 1024,
            ),
        ]

    @pytest.fixture
    def mock_source_metadata(self):
        """Create source metadata for Qdrant tests."""
        from src.models import DocumentType, SourceMetadata, Specialty

        return SourceMetadata(
            id="test-source-001",
            title="Test Chapter",
            doc_type=DocumentType.TEXTBOOK,
            file_path=Path("/tmp/test.pdf"),
            specialty=Specialty.GENERAL,
        )

    def test_qdrant_service_push_chunks(
        self, mock_chunks_with_embeddings, mock_source_metadata
    ):
        """QdrantService should push embedded chunks."""
        from src.services.qdrant_service import QdrantService

        with patch("src.services.qdrant_service.QdrantClient") as MockClient:
            mock_client = MagicMock()
            mock_client.get_collection.return_value = MagicMock()
            MockClient.return_value = mock_client

            service = QdrantService()
            pushed = service.push_chunks(
                mock_chunks_with_embeddings, mock_source_metadata
            )

            assert pushed == 2
            mock_client.upsert.assert_called_once()
            call_args = mock_client.upsert.call_args
            assert call_args.kwargs["collection_name"] == "neurosynth_chunks"
            assert len(call_args.kwargs["points"]) == 2

    def test_qdrant_service_skips_chunks_without_embeddings(self, mock_source_metadata):
        """QdrantService should skip chunks without embeddings."""
        from src.services.qdrant_service import QdrantService

        chunks_no_embedding = [
            Chunk(
                id="chunk-no-embed",
                source_id="test-source-001",
                source_title="Test",
                section_title="Section",
                content="No embedding here.",
                chunk_type=ChunkType.NARRATIVE,
                page_start=1,
                page_end=1,
                embedding=None,
            )
        ]

        with patch("src.services.qdrant_service.QdrantClient") as MockClient:
            mock_client = MagicMock()
            mock_client.get_collection.return_value = MagicMock()
            MockClient.return_value = mock_client

            service = QdrantService()
            pushed = service.push_chunks(chunks_no_embedding, mock_source_metadata)

            assert pushed == 0
            mock_client.upsert.assert_not_called()

    @patch("src.services.batch_indexer.settings")
    def test_batch_indexer_pushes_to_qdrant(
        self,
        mock_settings,
        mock_db,
        mock_processed_result,
        mock_chunks_with_embeddings,
        mock_source_metadata,
    ):
        """BatchIndexer should push to Qdrant during STORAGE stage."""
        mock_settings.enable_proposition_chunker = False
        mock_settings.enable_raptor = False
        mock_settings.enable_graph_rag = False
        mock_settings.enable_qdrant_push = True
        mock_settings.chunk_size = 1500
        mock_settings.chunk_overlap = 200

        mock_processor = MagicMock()
        mock_processor.process.return_value = mock_processed_result

        mock_chunker = MagicMock()
        mock_chunker.chunk_document.return_value = mock_chunks_with_embeddings

        indexer = BatchIndexer(mock_db, processor=mock_processor, chunker=mock_chunker)

        # Mock the qdrant service
        mock_qdrant = MagicMock()
        mock_qdrant.push_chunks.return_value = 2
        indexer._qdrant = mock_qdrant

        # Mock embedder to return chunks as-is (already have embeddings)
        with patch.object(
            indexer, "_embed_chunks", return_value=mock_chunks_with_embeddings
        ):
            pdf_files = [Path("/tmp/test.pdf")]
            progress_list = list(indexer.index_batch(pdf_files))

            # Verify Qdrant push was called
            mock_qdrant.push_chunks.assert_called()
            assert mock_qdrant.push_chunks.call_count >= 1

    @patch("src.services.batch_indexer.settings")
    def test_batch_indexer_continues_on_qdrant_failure(
        self, mock_settings, mock_db, mock_processed_result, mock_chunks_with_embeddings
    ):
        """BatchIndexer should continue if Qdrant push fails."""
        mock_settings.enable_proposition_chunker = False
        mock_settings.enable_raptor = False
        mock_settings.enable_graph_rag = False
        mock_settings.enable_qdrant_push = True
        mock_settings.chunk_size = 1500
        mock_settings.chunk_overlap = 200

        mock_processor = MagicMock()
        mock_processor.process.return_value = mock_processed_result

        mock_chunker = MagicMock()
        mock_chunker.chunk_document.return_value = mock_chunks_with_embeddings

        indexer = BatchIndexer(mock_db, processor=mock_processor, chunker=mock_chunker)

        # Mock qdrant to raise exception
        mock_qdrant = MagicMock()
        mock_qdrant.push_chunks.side_effect = Exception("Qdrant connection failed")
        indexer._qdrant = mock_qdrant

        with patch.object(
            indexer, "_embed_chunks", return_value=mock_chunks_with_embeddings
        ):
            pdf_files = [Path("/tmp/test.pdf")]
            progress_list = list(indexer.index_batch(pdf_files))

            # Indexing should complete despite Qdrant failure
            final_progress = progress_list[-1]
            assert final_progress.completed_files == 1

            # SQLite insert should still happen
            mock_db.insert_chunks.assert_called_once()


class TestRaptorEmbedding:
    """Tests for RAPTOR embedding integration."""

    @pytest.fixture
    def mock_chunks_with_embeddings(self):
        """Create chunks with embeddings for RAPTOR tests."""
        return [
            Chunk(
                id="chunk-001",
                source_id="test-source-001",
                source_title="Test Chapter",
                section_title="Anatomy",
                content="The brain is complex.",
                chunk_type=ChunkType.NARRATIVE,
                page_start=1,
                page_end=2,
                embedding=[0.1] * 1024,
            ),
            Chunk(
                id="chunk-002",
                source_id="test-source-001",
                source_title="Test Chapter",
                section_title="Procedure",
                content="Surgical technique details.",
                chunk_type=ChunkType.PROCEDURE_STEP,
                page_start=3,
                page_end=4,
                embedding=[0.2] * 1024,
            ),
        ]

    @pytest.mark.asyncio
    async def test_raptor_embeds_summary_chunks(self, mock_chunks_with_embeddings):
        """RAPTOR should embed summary chunks when embedder is provided."""
        from src.index.raptor import RecursiveSummarizer

        mock_ai = MagicMock()
        mock_ai.generate = AsyncMock(return_value="This is a summary of the content.")
        mock_db = MagicMock()

        mock_embedder = MagicMock()
        mock_embedder.embed_chunks = AsyncMock(
            side_effect=lambda chunks: [
                Chunk(
                    id=c.id,
                    source_id=c.source_id,
                    source_title=c.source_title,
                    section_title=c.section_title,
                    content=c.content,
                    chunk_type=c.chunk_type,
                    page_start=c.page_start,
                    page_end=c.page_end,
                    embedding=[0.5] * 1024,  # Embedded!
                )
                for c in chunks
            ]
        )

        raptor = RecursiveSummarizer(mock_ai, mock_db, embedder=mock_embedder)
        raptor.target_levels = 1  # Just one level for test

        summary_chunks = await raptor.generate_tree(mock_chunks_with_embeddings)

        # Verify embedder was called
        mock_embedder.embed_chunks.assert_called()

        # Verify summary chunks have embeddings
        for chunk in summary_chunks:
            assert chunk.embedding is not None
            assert len(chunk.embedding) == 1024

    @pytest.mark.asyncio
    async def test_raptor_works_without_embedder(self, mock_chunks_with_embeddings):
        """RAPTOR should work without embedder (backward compatible)."""
        from src.index.raptor import RecursiveSummarizer

        mock_ai = MagicMock()
        mock_ai.generate = AsyncMock(return_value="This is a summary.")
        mock_db = MagicMock()

        # No embedder provided
        raptor = RecursiveSummarizer(mock_ai, mock_db, embedder=None)
        raptor.target_levels = 1

        summary_chunks = await raptor.generate_tree(mock_chunks_with_embeddings)

        # Should still produce summaries (without embeddings)
        assert len(summary_chunks) >= 1
        # Embeddings will be None since no embedder
        for chunk in summary_chunks:
            assert chunk.embedding is None

    @patch("src.services.batch_indexer.settings")
    def test_batch_indexer_passes_embedder_to_raptor(self, mock_settings, mock_db):
        """BatchIndexer should pass embedder to RAPTOR."""
        mock_settings.enable_proposition_chunker = False
        mock_settings.enable_raptor = True
        mock_settings.enable_graph_rag = False
        mock_settings.enable_qdrant_push = False
        mock_settings.chunk_size = 1500
        mock_settings.chunk_overlap = 200

        indexer = BatchIndexer(mock_db)

        # Access raptor property to trigger lazy loading
        with patch("src.index.raptor.RecursiveSummarizer") as MockRaptor:
            # Force raptor creation
            indexer._raptor = None
            _ = indexer.raptor

            # Verify embedder was passed
            MockRaptor.assert_called_once()
            call_kwargs = MockRaptor.call_args.kwargs
            assert "embedder" in call_kwargs
            assert call_kwargs["embedder"] is not None


class TestAsyncBatchIndexer:
    """Tests for async batch indexing functionality."""

    @pytest.fixture
    def mock_processed_result_async(self, tmp_path):
        """Create a mock ProcessedDocument for async tests."""
        from src.models import DocumentType, ProcessedDocument, Section, SourceMetadata

        return ProcessedDocument(
            metadata=SourceMetadata(
                id="test-async-001",
                title="Async Test Chapter",
                doc_type=DocumentType.TEXTBOOK,
                file_path=tmp_path / "test.pdf",
            ),
            sections=[
                Section(
                    title="Test Section",
                    level=1,
                    page_start=1,
                    page_end=2,
                    content="Test content for async processing.",
                )
            ],
            images=[],
            raw_text="Test content for async processing.",
        )

    @pytest.mark.asyncio
    @patch("src.services.batch_indexer.settings")
    async def test_index_batch_async_processes_files(
        self, mock_settings, mock_db, mock_processed_result_async, tmp_path
    ):
        """Test that async indexer processes files correctly."""
        mock_settings.enable_proposition_chunker = False
        mock_settings.enable_raptor = False
        mock_settings.enable_graph_rag = False
        mock_settings.enable_qdrant_push = False
        mock_settings.max_concurrent_pdfs = 2
        mock_settings.chunk_size = 1500
        mock_settings.chunk_overlap = 200

        pdf1 = tmp_path / "test1.pdf"
        pdf2 = tmp_path / "test2.pdf"
        pdf1.touch()
        pdf2.touch()

        indexer = BatchIndexer(mock_db)

        # Mock processor and embedder
        mock_processor = MagicMock()
        mock_processor.process = MagicMock(return_value=mock_processed_result_async)
        indexer._processor = mock_processor

        mock_embedder = MagicMock()
        mock_embedder.embed_chunks = AsyncMock(
            side_effect=lambda chunks: [
                Chunk(
                    id=c.id,
                    source_id=c.source_id,
                    source_title=c.source_title,
                    section_title=c.section_title,
                    content=c.content,
                    chunk_type=c.chunk_type,
                    page_start=c.page_start,
                    page_end=c.page_end,
                    embedding=[0.1] * 1024,
                )
                for c in chunks
            ]
        )
        indexer._embedder = mock_embedder

        results = []
        async for progress in indexer.index_batch_async([pdf1, pdf2]):
            results.append(progress)

        # Should have received 2 progress updates (one per file)
        assert len(results) == 2

        # Final progress should show 2 completed files
        final_progress = results[-1]
        assert final_progress.completed_files == 2
        assert final_progress.failed_files == 0
        assert final_progress.concurrent_mode is True

    @pytest.mark.asyncio
    @patch("src.services.batch_indexer.settings")
    async def test_index_batch_async_respects_concurrency_limit(
        self, mock_settings, mock_db, mock_processed_result_async, tmp_path
    ):
        """Test that async indexer respects max_concurrent_pdfs setting."""
        mock_settings.enable_proposition_chunker = False
        mock_settings.enable_raptor = False
        mock_settings.enable_graph_rag = False
        mock_settings.enable_qdrant_push = False
        mock_settings.max_concurrent_pdfs = 1  # Sequential
        mock_settings.chunk_size = 1500
        mock_settings.chunk_overlap = 200

        pdfs = [tmp_path / f"test{i}.pdf" for i in range(3)]
        for pdf in pdfs:
            pdf.touch()

        indexer = BatchIndexer(mock_db)

        mock_processor = MagicMock()
        mock_processor.process = MagicMock(return_value=mock_processed_result_async)
        indexer._processor = mock_processor

        mock_embedder = MagicMock()
        mock_embedder.embed_chunks = AsyncMock(side_effect=lambda chunks: chunks)
        indexer._embedder = mock_embedder

        results = []
        async for progress in indexer.index_batch_async(pdfs, max_concurrent=1):
            results.append(progress)

        assert len(results) == 3
        assert results[-1].completed_files == 3

    @patch("src.services.batch_indexer.settings")
    def test_batch_progress_has_concurrent_fields(self, mock_settings):
        """Test that BatchProgress has concurrent processing fields."""
        from pathlib import Path

        from src.services.batch_indexer import BatchProgress, FileProgress

        progress = BatchProgress(total_files=5, concurrent_mode=True)

        # Should have active_files list and active_count property
        assert hasattr(progress, "active_files")
        assert hasattr(progress, "active_count")
        assert progress.active_count == 0

        # Add an active file
        fp = FileProgress(file_path=Path("/test.pdf"), file_name="test.pdf")
        progress.active_files.append(fp)
        assert progress.active_count == 1


class TestImageEmbedding:
    """Test image embedding pipeline."""

    @pytest.fixture
    def mock_extracted_images(self):
        """Sample extracted images for testing."""
        from src.models import ImageType

        return [
            ExtractedImage(
                id="img-001",
                source_id="test-source-001",
                page=1,
                file_path=Path("/tmp/test_img1.png"),
                caption="MCA bifurcation",
                surrounding_text="Figure showing the middle cerebral artery",
                image_type=ImageType.ANATOMY_DIAGRAM,
            ),
            ExtractedImage(
                id="img-002",
                source_id="test-source-001",
                page=2,
                file_path=Path("/tmp/test_img2.png"),
                caption="Surgical approach",
                surrounding_text="Pterional craniotomy exposure",
                image_type=ImageType.SURGICAL_PHOTO,
            ),
        ]

    @patch("src.services.batch_indexer.settings")
    def test_async_image_embedder_embeds_images(
        self, mock_settings, mock_extracted_images
    ):
        """Test that AsyncImageEmbedder generates embeddings for images."""
        import asyncio

        from src.services.image_embedder import AsyncImageEmbedder

        mock_settings.image_embedding_batch_size = 32

        # Mock BiomedCLIPSearcher at the import location
        with patch.dict("sys.modules", {"neurosynth.ai.biomed_searcher": MagicMock()}):
            with patch(
                "neurosynth.ai.biomed_searcher.BiomedCLIPSearcher"
            ) as MockBiomedCLIP:
                mock_searcher = MagicMock()
                # Return 512-dim embeddings (BiomedCLIP)
                mock_searcher.embed_image.return_value = [[0.1] * 512, [0.2] * 512]
                mock_searcher.device = "cpu"
                MockBiomedCLIP.return_value = mock_searcher

                embedder = AsyncImageEmbedder(model="biomedclip")
                embedder._embedder = mock_searcher  # Inject mock directly
                embedder._load_attempted = True

                # Mock file existence
                with patch("pathlib.Path.exists", return_value=True):
                    result = asyncio.run(embedder.embed_images(mock_extracted_images))

                assert len(result) == 2
                assert result[0].embedding is not None
                assert len(result[0].embedding) == 512
                assert result[1].embedding is not None

    @patch("src.services.batch_indexer.settings")
    def test_async_image_embedder_handles_empty_list(self, mock_settings):
        """Test that AsyncImageEmbedder handles empty image list."""
        import asyncio

        from src.services.image_embedder import AsyncImageEmbedder

        mock_settings.image_embedding_batch_size = 32

        embedder = AsyncImageEmbedder(model="biomedclip")
        result = asyncio.run(embedder.embed_images([]))

        assert result == []

    @patch("src.services.batch_indexer.settings")
    def test_async_image_embedder_disabled_mode(self, mock_settings):
        """Test that AsyncImageEmbedder skips embedding when model=none."""
        import asyncio

        from src.services.image_embedder import AsyncImageEmbedder

        mock_settings.image_embedding_batch_size = 32

        embedder = AsyncImageEmbedder(model="none")
        assert embedder.is_available is False

        # Should return images unchanged
        images = [MagicMock(embedding=None)]
        result = asyncio.run(embedder.embed_images(images))
        assert result[0].embedding is None


class TestImageQdrantPush:
    """Test image Qdrant push functionality."""

    @pytest.fixture
    def mock_embedded_images(self):
        """Sample images with embeddings."""
        from src.models import ImageType

        return [
            ExtractedImage(
                id="img-001",
                source_id="test-source-001",
                page=1,
                file_path=Path("/tmp/test_img1.png"),
                caption="MCA bifurcation",
                surrounding_text="Figure showing MCA",
                image_type=ImageType.ANATOMY_DIAGRAM,
                embedding=[0.1] * 512,
            ),
            ExtractedImage(
                id="img-002",
                source_id="test-source-001",
                page=2,
                file_path=Path("/tmp/test_img2.png"),
                caption="Surgical approach",
                surrounding_text="Pterional exposure",
                image_type=ImageType.SURGICAL_PHOTO,
                embedding=[0.2] * 512,
            ),
        ]

    @patch("src.services.qdrant_service.settings")
    def test_qdrant_service_push_images(self, mock_settings, mock_embedded_images):
        """Test that QdrantService.push_images pushes to correct collection."""
        from src.models import DocumentType, SourceMetadata, Specialty
        from src.services.qdrant_service import QdrantService

        mock_settings.qdrant_url = "http://localhost:6333"
        mock_settings.qdrant_collection_name = "neurosynth_chunks"
        mock_settings.qdrant_vector_dim = 1024
        mock_settings.image_qdrant_collection = "neurosurgical_figures_hybrid"
        mock_settings.image_qdrant_vector_dim = 512

        source = SourceMetadata(
            id="source-001",
            title="Test Chapter",
            doc_type=DocumentType.CHAPTER,
            file_path=Path("/tmp/test.pdf"),
            specialty=Specialty.VASCULAR,
        )

        with patch("src.services.qdrant_service.QdrantClient") as MockClient:
            mock_client = MagicMock()
            MockClient.return_value = mock_client

            service = QdrantService()
            pushed = service.push_images(mock_embedded_images, source)

            assert pushed == 2
            mock_client.upsert.assert_called_once()

            # Verify collection name
            call_args = mock_client.upsert.call_args
            assert call_args.kwargs["collection_name"] == "neurosurgical_figures_hybrid"

    @patch("src.services.qdrant_service.settings")
    def test_qdrant_service_skips_images_without_embeddings(self, mock_settings):
        """Test that push_images skips images without embeddings."""
        from src.models import DocumentType, ImageType, SourceMetadata, Specialty
        from src.services.qdrant_service import QdrantService

        mock_settings.qdrant_url = "http://localhost:6333"
        mock_settings.qdrant_collection_name = "neurosynth_chunks"
        mock_settings.qdrant_vector_dim = 1024
        mock_settings.image_qdrant_collection = "neurosurgical_figures_hybrid"
        mock_settings.image_qdrant_vector_dim = 512

        # Images without embeddings
        images = [
            ExtractedImage(
                id="img-001",
                source_id="test-source-001",
                page=1,
                file_path=Path("/tmp/test.png"),
                caption="Test",
                surrounding_text="Test",
                image_type=ImageType.ANATOMY_DIAGRAM,
                embedding=None,  # No embedding
            ),
        ]

        source = SourceMetadata(
            id="source-001",
            title="Test Chapter",
            doc_type=DocumentType.CHAPTER,
            file_path=Path("/tmp/test.pdf"),
            specialty=Specialty.VASCULAR,
        )

        with patch("src.services.qdrant_service.QdrantClient") as MockClient:
            mock_client = MagicMock()
            MockClient.return_value = mock_client

            service = QdrantService()
            pushed = service.push_images(images, source)

            assert pushed == 0
            mock_client.upsert.assert_not_called()
