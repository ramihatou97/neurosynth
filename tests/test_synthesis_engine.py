"""Tests for SynthesisEngine async methods.

Tests the Phase 3 fix (async pattern standardization).
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.models import (
    ChapterTemplate,
    Chunk,
    ChunkType,
    DocumentType,
    ExtractedImage,
    ImageType,
    SectionTemplate,
    SourceMetadata,
)


@pytest.fixture
def mock_database():
    """Create mock database."""
    from pathlib import Path

    db = MagicMock()
    db.get_source_metadata.return_value = SourceMetadata(
        id="test-source",
        title="Test Source",
        doc_type=DocumentType.TEXTBOOK,
        file_path=Path("/test/test.pdf"),
        total_pages=50,
    )
    return db


@pytest.fixture
def mock_search_engine():
    """Create mock search engine."""
    from src.index.search import RetrievalResult, SearchResult

    mock_chunk = Chunk(
        id="chunk-1",
        content="Test content about vestibular schwannoma surgical approach.",
        source_id="test-source",
        source_title="Test Source",
        section_title="Introduction",
        page_start=1,
        page_end=2,
        chunk_type=ChunkType.NARRATIVE,
        # Pre-populate embedding to skip deduplication embedding generation
        embedding=[0.1] * 1024,
    )

    search = MagicMock()
    search.retrieve_for_topic.return_value = RetrievalResult(
        chunks=[SearchResult(chunk=mock_chunk, score=0.95)],
        images=[],
        sources_used={"test-source"},
        total_chunks=1,
        total_images=0,
    )
    return search


@pytest.fixture
def mock_ai_client():
    """Create mock async AI client."""
    ai = AsyncMock()
    ai.get_embedding.return_value = [0.1] * 1024
    ai.synthesize.return_value = "Synthesized section content about the topic."
    return ai


@pytest.fixture
def mock_template_manager():
    """Create mock template manager."""
    tm = MagicMock()
    tm.render_prompt.return_value = ("System prompt", "User prompt")
    return tm


class TestSynthesisEngineInit:
    """Tests for SynthesisEngine initialization."""

    def test_init_with_ai_client(
        self, mock_database, mock_search_engine, mock_ai_client
    ):
        """Test initialization with AIClient."""
        from src.synthesize.engine import SynthesisEngine

        engine = SynthesisEngine(
            db=mock_database, search_engine=mock_search_engine, ai_client=mock_ai_client
        )

        assert engine.db == mock_database
        assert engine.search == mock_search_engine
        assert engine.ai == mock_ai_client

    def test_init_without_ai_client(self, mock_database, mock_search_engine):
        """Test initialization without AIClient (per-request mode)."""
        from src.synthesize.engine import SynthesisEngine

        engine = SynthesisEngine(
            db=mock_database, search_engine=mock_search_engine, ai_client=None
        )

        assert engine.ai is None


class TestSynthesizeChapterAsync:
    """Tests for synthesize_chapter_async method."""

    @pytest.mark.asyncio
    async def test_synthesize_chapter_async_with_client_param(
        self, mock_database, mock_search_engine, mock_ai_client, mock_template_manager
    ):
        """Test async synthesis with AIClient passed as parameter."""
        from src.synthesize.engine import SynthesisEngine

        with patch(
            "src.synthesize.engine.TemplateManager", return_value=mock_template_manager
        ):
            engine = SynthesisEngine(
                db=mock_database,
                search_engine=mock_search_engine,
                ai_client=None,  # No client at init
            )

        chapter = await engine.synthesize_chapter_async(
            topic="Vestibular Schwannoma",
            template_name="surgical_procedure",
            ai_client=mock_ai_client,
        )

        assert chapter is not None
        assert chapter.topic == "Vestibular Schwannoma"
        assert len(chapter.sections) > 0

        # Verify AI client was called
        mock_ai_client.get_embedding.assert_called_once_with("Vestibular Schwannoma")
        mock_ai_client.synthesize.assert_called()

    @pytest.mark.asyncio
    async def test_synthesize_chapter_async_raises_without_client(
        self, mock_database, mock_search_engine
    ):
        """Test that synthesis raises error when no AIClient is available."""
        from src.synthesize.engine import SynthesisEngine

        engine = SynthesisEngine(
            db=mock_database, search_engine=mock_search_engine, ai_client=None
        )

        with pytest.raises(ValueError, match="AIClient must be provided"):
            await engine.synthesize_chapter_async(
                topic="Test Topic",
                template_name="surgical_procedure",
                ai_client=None,  # No client provided
            )

    @pytest.mark.asyncio
    async def test_synthesize_chapter_async_uses_instance_client(
        self, mock_database, mock_search_engine, mock_ai_client, mock_template_manager
    ):
        """Test that instance AIClient is used when no per-request client provided."""
        from src.synthesize.engine import SynthesisEngine

        with patch(
            "src.synthesize.engine.TemplateManager", return_value=mock_template_manager
        ):
            engine = SynthesisEngine(
                db=mock_database,
                search_engine=mock_search_engine,
                ai_client=mock_ai_client,  # Client at init
            )

        chapter = await engine.synthesize_chapter_async(
            topic="Test Topic",
            template_name="surgical_procedure",
            # No ai_client param - should use instance client
        )

        assert chapter is not None
        mock_ai_client.get_embedding.assert_called()


class TestSynthesizeSectionAsync:
    """Tests for _synthesize_section_async method."""

    @pytest.mark.asyncio
    async def test_section_synthesis_calls_ai(
        self, mock_database, mock_search_engine, mock_ai_client, mock_template_manager
    ):
        """Test that section synthesis calls AI correctly."""
        from src.synthesize.engine import SynthesisEngine

        with patch(
            "src.synthesize.engine.TemplateManager", return_value=mock_template_manager
        ):
            engine = SynthesisEngine(
                db=mock_database, search_engine=mock_search_engine, ai_client=None
            )

        mock_chunk = MagicMock()
        mock_chunk.chunk = MagicMock()
        mock_chunk.chunk.source_id = "test-source"
        mock_chunk.chunk.source_title = "Test Source"
        mock_chunk.chunk.content = "Test content"
        mock_chunk.chunk.page_start = 1
        mock_chunk.chunk.chunk_type = ChunkType.NARRATIVE
        mock_chunk.score = 0.9
        mock_chunk.also_in_sources = []

        section_template = SectionTemplate(
            name="Introduction",
            format="narrative",
            chunk_types=[ChunkType.NARRATIVE],
        )

        # Mock _filter_chunks_for_section to return our test chunks
        with patch.object(
            engine, "_filter_chunks_for_section", return_value=[mock_chunk]
        ):
            with patch.object(engine, "_select_images_for_section", return_value=[]):
                section = await engine._synthesize_section_async(
                    topic="Test Topic",
                    section_template=section_template,
                    all_chunks=[mock_chunk],
                    all_images=[],
                    query_embedding=[0.1] * 1024,
                    ai_client=mock_ai_client,
                )

        assert section is not None
        assert section.title == "Introduction"
        mock_ai_client.synthesize.assert_called_once()

    @pytest.mark.asyncio
    async def test_section_synthesis_no_content_fallback(
        self, mock_database, mock_search_engine, mock_ai_client, mock_template_manager
    ):
        """Test section synthesis handles no content gracefully."""
        from src.synthesize.engine import SynthesisEngine

        with patch(
            "src.synthesize.engine.TemplateManager", return_value=mock_template_manager
        ):
            engine = SynthesisEngine(
                db=mock_database, search_engine=mock_search_engine, ai_client=None
            )

        section_template = SectionTemplate(
            name="Empty Section",
            format="narrative",
            chunk_types=[ChunkType.NARRATIVE],
        )

        # Mock to return empty chunks
        with patch.object(engine, "_filter_chunks_for_section", return_value=[]):
            section = await engine._synthesize_section_async(
                topic="Test Topic",
                section_template=section_template,
                all_chunks=[],  # No chunks
                all_images=[],
                query_embedding=[0.1] * 1024,
                ai_client=mock_ai_client,
            )

        # Should return fallback content
        assert "[No content found" in section.content
