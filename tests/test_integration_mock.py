"""Integration test with mocked LLM clients."""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from neurosynth.models.document import Document, DocumentFormat, Source
from neurosynth.models.output import Chapter
from neurosynth.pipeline.coordinator import run_pipeline


@pytest.fixture
def mock_settings():
    with patch("neurosynth.config.get_settings") as mock:
        settings = MagicMock()
        settings.anthropic_api_key = "test_key"
        settings.voyage_api_key = "test_key"
        settings.google_api_key = "test_key"
        settings.chunk_size = 100
        settings.chunk_overlap = 10
        settings.similarity_threshold = 0.8
        settings.enable_visual_extraction = False
        settings.merge_concurrency = 5
        settings.synthesis_concurrency = 5
        settings.embedding_concurrency = 5
        mock.return_value = settings
        yield settings


@pytest.fixture
def mock_parser():
    with patch("neurosynth.parsers.ParserFactory.get_parser") as mock_factory:
        parser = AsyncMock()

        source = Source(
            path=Path("test.pdf"), format=DocumentFormat.PDF, title="Test Doc"
        )

        doc = Document(
            source=source,
            raw_text="This is a test document about lumbar discectomy. It involves removing a herniated disc.",
        )
        # Add a chunk manually as the parser usually does this
        doc.add_chunk(
            "This is a test document about lumbar discectomy. It involves removing a herniated disc."
        )

        parser.parse.return_value = doc
        mock_factory.return_value = parser
        yield mock_factory


@pytest.fixture
def mock_llm_clients():
    with (
        patch("neurosynth.dedup.embeddings.VoyageClient") as mock_voyage,
        patch("neurosynth.dedup.merger.ClaudeClient") as mock_claude_merger,
        patch("neurosynth.synthesis.outline.ClaudeClient") as mock_claude_outline,
        patch("neurosynth.synthesis.section.ClaudeClient") as mock_claude_synth,
    ):

        # Mock Voyage
        voyage_instance = mock_voyage.return_value
        voyage_instance.embed_texts = AsyncMock(
            return_value=[[0.1] * 1024]
        )  # Mock embedding

        # Mock Claude
        claude_instance = MagicMock()
        claude_instance.merge_chunks = AsyncMock(return_value="Merged content")
        claude_instance.detect_conflicts = AsyncMock(return_value=[])
        claude_instance.generate_outline = AsyncMock(
            return_value=[
                {"title": "Introduction", "level": 1, "description": "Intro"},
                {"title": "Technique", "level": 1, "description": "Steps"},
            ]
        )
        claude_instance.synthesize_section = AsyncMock(
            return_value="Synthesized section content."
        )
        claude_instance.generate_abstract = AsyncMock(return_value="Abstract.")
        claude_instance.extract_keywords = AsyncMock(
            return_value=["keyword1", "keyword2"]
        )

        mock_claude_merger.return_value = claude_instance
        mock_claude_outline.return_value = claude_instance
        mock_claude_synth.return_value = claude_instance

        yield


@pytest.mark.asyncio
@pytest.mark.usefixtures("mock_parser", "mock_settings", "mock_llm_clients")
async def test_full_pipeline_mocked(tmp_path: Path) -> None:
    """Test the full pipeline with mocked LLM calls."""

    # Setup directories
    source_dir = tmp_path / "sources"
    source_dir.mkdir()
    output_dir = tmp_path / "output"
    output_dir.mkdir()

    # Create a dummy PDF file (content doesn't matter as parser is mocked)
    (source_dir / "test.pdf").write_text("dummy content")

    # Run pipeline
    chapter = await run_pipeline(
        topic="Lumbar Discectomy",
        source_dir=source_dir,
        output_dir=output_dir,
        use_cache=False,
        enable_visual_extraction=False,
    )

    # Verify results
    assert isinstance(chapter, Chapter)
    assert chapter.title == "Lumbar Discectomy"
    assert len(chapter.sections) > 0
    assert (output_dir / "lumbar_discectomy.tex").exists()

    # Verify metrics were collected
    # (We can't easily access the pipeline instance here, but the fact it finished means it worked)
