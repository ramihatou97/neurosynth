"""End-to-end integration tests with real documents.

These tests use real PDF documents from tests/fixtures/ and exercise
the full pipeline (parse -> chunk -> embed -> cluster -> synthesize).

LLM API calls (Claude, Gemini, Voyage) are mocked to avoid costs and
ensure reproducibility.

To run these tests:
    pytest tests/test_integration_e2e.py -v -m integration

Note: You must provide real PDF files in tests/fixtures/:
    - sample_chapter.pdf: 1-2 page neurosurgical content
    - sample_images.pdf: PDF with figures/images (optional)
"""

import asyncio
import shutil
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import numpy as np
import pytest


@pytest.fixture
def integration_project(tmp_path, sample_pdf_path):
    """Create a project directory with real PDF for integration testing."""
    project = tmp_path / "integration_project"
    project.mkdir()

    # Create directory structure
    sources_dir = project / "sources"
    processed_dir = project / "processed"
    output_dir = project / "output"

    sources_dir.mkdir()
    processed_dir.mkdir()
    output_dir.mkdir()

    # Copy real PDF to sources
    shutil.copy(sample_pdf_path, sources_dir / "test_chapter.pdf")

    # Create config
    config = 'topic: "Integration Test Chapter"\n'
    (project / "neurosynth.yaml").write_text(config)

    return project


def create_mock_embedding(dim: int = 1024) -> np.ndarray:
    """Create a reproducible mock embedding."""
    return np.random.RandomState(42).rand(dim).astype(np.float32)


@pytest.fixture
def mock_llm_apis():
    """Mock all LLM API calls to avoid costs."""
    with patch("neurosynth.llm.voyage.voyageai") as mock_voyage, \
         patch("neurosynth.llm.claude.anthropic") as mock_claude, \
         patch("neurosynth.llm.gemini.genai") as mock_gemini:

        # Mock Voyage embeddings - return consistent embeddings
        mock_voyage_client = MagicMock()

        def mock_embed(texts, model, input_type):
            # Return embeddings based on text hash for consistency
            embeddings = []
            for i, text in enumerate(texts):
                # Use text hash as seed for reproducibility
                seed = hash(text) % (2**32)
                embeddings.append(np.random.RandomState(seed).rand(1024).tolist())
            mock_response = MagicMock()
            mock_response.embeddings = embeddings
            return mock_response

        mock_voyage_client.embed = mock_embed
        mock_voyage.Client.return_value = mock_voyage_client

        # Mock Claude synthesis responses
        mock_claude_client = MagicMock()

        def mock_claude_create(**kwargs):
            # Return synthesis-like response
            mock_response = MagicMock()
            mock_response.content = [MagicMock(text="""
# Test Section

This is synthesized content from the integration test.

The vestibular schwannoma is a benign tumor arising from Schwann cells
of the vestibular portion of cranial nerve VIII.

## Epidemiology

These tumors account for approximately 8% of intracranial tumors.

## Surgical Approach

Multiple surgical approaches exist including retrosigmoid, middle fossa,
and translabyrinthine approaches.
""")]
            return mock_response

        mock_claude_client.messages.create = mock_claude_create
        mock_claude.Anthropic.return_value = mock_claude_client

        # Mock Gemini responses
        mock_gemini_model = MagicMock()

        def mock_gemini_generate(prompt):
            mock_response = MagicMock()
            mock_response.text = "Verified synthesis content."
            return mock_response

        mock_gemini_model.generate_content = mock_gemini_generate
        mock_gemini.GenerativeModel.return_value = mock_gemini_model

        yield {
            "voyage": mock_voyage,
            "claude": mock_claude,
            "gemini": mock_gemini,
        }


@pytest.mark.integration
@pytest.mark.slow
class TestFullPipelineIntegration:
    """End-to-end pipeline tests with real documents."""

    @pytest.mark.asyncio
    async def test_parse_real_pdf(self, sample_pdf_path):
        """Test parsing a real PDF document."""
        from neurosynth.parsers import ParserFactory
        from neurosynth.models.document import DocumentFormat, Source

        source = Source(
            path=sample_pdf_path,
            format=DocumentFormat.PDF,
            title="Test Chapter",
        )

        parser = ParserFactory.get_parser(source)
        document = await parser.parse()

        assert document is not None
        assert document.is_parsed
        assert len(document.raw_text) > 0
        assert document.total_pages > 0

    @pytest.mark.asyncio
    async def test_parse_and_chunk_real_pdf(self, sample_pdf_path):
        """Test parsing and chunking a real PDF."""
        from neurosynth.parsers import ParserFactory
        from neurosynth.chunking import Chunker
        from neurosynth.models.document import DocumentFormat, Source

        source = Source(
            path=sample_pdf_path,
            format=DocumentFormat.PDF,
            title="Test Chapter",
        )

        # Parse
        parser = ParserFactory.get_parser(source)
        document = await parser.parse()

        # Chunk
        chunker = Chunker(chunk_size=500, chunk_overlap=50)
        chunks = chunker.chunk_document(document)

        assert len(chunks) > 0
        for chunk in chunks:
            assert chunk.content
            assert chunk.source == source
            assert chunk.word_count > 0

    @pytest.mark.asyncio
    async def test_full_pipeline_with_mocked_llm(
        self, integration_project, mock_llm_apis
    ):
        """Test full pipeline: parse -> chunk -> embed -> cluster -> synthesize."""
        from neurosynth.parsers import ParserFactory
        from neurosynth.chunking import Chunker
        from neurosynth.dedup import SemanticClusterer, ClusterMerger
        from neurosynth.models.document import DocumentFormat, Source

        # Parse
        pdf_path = integration_project / "sources" / "test_chapter.pdf"
        source = Source(
            path=pdf_path,
            format=DocumentFormat.PDF,
            title="Integration Test",
        )

        parser = ParserFactory.get_parser(source)
        document = await parser.parse()
        assert document.is_parsed

        # Chunk
        chunker = Chunker(chunk_size=300, chunk_overlap=30)
        chunks = chunker.chunk_document(document)
        assert len(chunks) > 0

        # Skip embedding and clustering if too few chunks
        if len(chunks) < 3:
            pytest.skip("Sample PDF too small for clustering test")

        # Embed (mocked)
        from neurosynth.llm.voyage import VoyageClient

        voyage = VoyageClient()
        embeddings = await voyage.embed_texts([c.content for c in chunks])
        assert len(embeddings) == len(chunks)

        # Assign embeddings to chunks
        for chunk, emb in zip(chunks, embeddings):
            chunk.embedding = emb

        # Cluster
        clusterer = SemanticClusterer(similarity_threshold=0.85)
        result = await clusterer.cluster_chunks(chunks)
        assert result.num_clusters > 0

        # Merge clusters
        merger = ClusterMerger()
        await merger.merge_all_clusters(result.clusters)

        # Verify cluster structure
        for cluster in result.clusters:
            assert len(cluster.chunks) > 0
            assert cluster.merged_content or len(cluster.chunks) == 1


@pytest.mark.integration
@pytest.mark.slow
class TestPipelineOutputs:
    """Test pipeline output generation."""

    @pytest.mark.asyncio
    async def test_json_cluster_serialization(self, integration_project, mock_llm_apis):
        """Test that clusters can be serialized to JSON."""
        import json
        from neurosynth.parsers import ParserFactory
        from neurosynth.chunking import Chunker
        from neurosynth.dedup import SemanticClusterer
        from neurosynth.models.document import DocumentFormat, Source
        from neurosynth.utils.serialization import NumpyEncoder

        # Parse and chunk
        pdf_path = integration_project / "sources" / "test_chapter.pdf"
        source = Source(path=pdf_path, format=DocumentFormat.PDF, title="Test")

        parser = ParserFactory.get_parser(source)
        document = await parser.parse()

        chunker = Chunker(chunk_size=300, chunk_overlap=30)
        chunks = chunker.chunk_document(document)

        if len(chunks) < 2:
            pytest.skip("Sample PDF too small")

        # Embed and cluster
        from neurosynth.llm.voyage import VoyageClient

        voyage = VoyageClient()
        embeddings = await voyage.embed_texts([c.content for c in chunks])
        for chunk, emb in zip(chunks, embeddings):
            chunk.embedding = emb

        clusterer = SemanticClusterer(similarity_threshold=0.85)
        result = await clusterer.cluster_chunks(chunks)

        # Serialize to JSON
        clusters_data = [c.to_dict() for c in result.clusters]
        json_output = json.dumps(clusters_data, cls=NumpyEncoder, indent=2)

        # Verify JSON is valid
        assert json_output
        parsed = json.loads(json_output)
        assert len(parsed) == len(result.clusters)

        # Save to processed directory
        output_path = integration_project / "processed" / "clusters.json"
        output_path.write_text(json_output)
        assert output_path.exists()


@pytest.mark.integration
class TestParserIntegration:
    """Integration tests for document parsers."""

    @pytest.mark.asyncio
    async def test_pdf_metadata_extraction(self, sample_pdf_path):
        """Test that PDF metadata is properly extracted."""
        from neurosynth.parsers import ParserFactory
        from neurosynth.models.document import DocumentFormat, Source

        source = Source(
            path=sample_pdf_path,
            format=DocumentFormat.PDF,
            title="Metadata Test",
        )

        parser = ParserFactory.get_parser(source)
        document = await parser.parse()

        # Verify basic document properties
        assert document.source == source
        assert document.total_pages >= 1
        assert len(document.raw_text) > 100  # Should have meaningful content

    @pytest.mark.asyncio
    async def test_pdf_toc_extraction(self, sample_pdf_path):
        """Test table of contents extraction if available."""
        from neurosynth.parsers import ParserFactory
        from neurosynth.models.document import DocumentFormat, Source

        source = Source(
            path=sample_pdf_path,
            format=DocumentFormat.PDF,
            title="TOC Test",
        )

        parser = ParserFactory.get_parser(source)
        document = await parser.parse()

        # TOC may or may not be present depending on PDF
        # Just verify it doesn't crash
        assert isinstance(document.toc, list)
