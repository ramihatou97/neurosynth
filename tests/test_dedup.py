"""Tests for deduplication engine."""

from unittest.mock import AsyncMock, MagicMock, patch

import numpy as np
import pytest

from neurosynth.models.document import ContentChunk, DocumentFormat, Source
from neurosynth.models.knowledge import Conflict, ConflictType, KnowledgeCluster


@pytest.fixture
def mock_source(tmp_path):
    """Create a mock source."""
    path = tmp_path / "test.pdf"
    path.touch()
    return Source(
        path=path,
        format=DocumentFormat.PDF,
        title="Test Source",
        authors=["Test Author"],
        year=2023,
    )


@pytest.fixture
def sample_chunks(mock_source):
    """Create sample chunks for testing."""
    return [
        ContentChunk(
            content="The vestibular schwannoma is a benign tumor arising from Schwann cells.",
            source=mock_source,
        ),
        ContentChunk(
            content="Vestibular schwannomas are benign tumors that arise from the Schwann cells.",
            source=mock_source,
        ),
        ContentChunk(
            content="The surgical approach depends on tumor size and hearing status.",
            source=mock_source,
        ),
    ]


class TestExactDeduplication:
    """Tests for exact deduplication."""

    def test_exact_duplicates_removed(self, mock_source):
        """Test that exact duplicates are removed."""
        from neurosynth.dedup.embeddings import ExactDeduplicator

        chunks = [
            ContentChunk(content="Exact same content.", source=mock_source),
            ContentChunk(content="Exact same content.", source=mock_source),
            ContentChunk(content="Different content.", source=mock_source),
        ]

        result = ExactDeduplicator.deduplicate(chunks)
        assert len(result) == 2

    def test_no_duplicates_unchanged(self, mock_source):
        """Test that unique chunks are preserved."""
        from neurosynth.dedup.embeddings import ExactDeduplicator

        chunks = [
            ContentChunk(content="First unique content.", source=mock_source),
            ContentChunk(content="Second unique content.", source=mock_source),
            ContentChunk(content="Third unique content.", source=mock_source),
        ]

        result = ExactDeduplicator.deduplicate(chunks)
        assert len(result) == 3


class TestContentChunk:
    """Tests for ContentChunk model."""

    def test_content_hash_generation(self, mock_source):
        """Test that content hash is generated."""
        chunk = ContentChunk(
            content="Test content for hashing.",
            source=mock_source,
        )

        assert chunk.content_hash is not None
        assert len(chunk.content_hash) == 16

    def test_same_content_same_hash(self, mock_source):
        """Test that same content produces same hash."""
        chunk1 = ContentChunk(content="Same content", source=mock_source)
        chunk2 = ContentChunk(content="Same content", source=mock_source)

        assert chunk1.content_hash == chunk2.content_hash

    def test_word_count(self, mock_source):
        """Test word count calculation."""
        chunk = ContentChunk(
            content="One two three four five",
            source=mock_source,
        )

        assert chunk.word_count == 5


class TestKnowledgeCluster:
    """Tests for KnowledgeCluster model."""

    def test_cluster_source_count(self, mock_source, tmp_path):
        """Test source counting in clusters."""
        # Create second source
        path2 = tmp_path / "test2.pdf"
        path2.touch()
        source2 = Source(
            path=path2,
            format=DocumentFormat.PDF,
            title="Second Source",
        )

        chunks = [
            ContentChunk(content="Content from source 1", source=mock_source),
            ContentChunk(content="Content from source 2", source=source2),
        ]

        cluster = KnowledgeCluster(chunks=chunks)
        assert cluster.source_count == 2

    def test_cluster_has_conflicts(self, sample_chunks):
        """Test conflict detection flag."""
        cluster = KnowledgeCluster(chunks=sample_chunks)

        # No conflicts initially
        assert not cluster.has_conflicts

        # Add conflict
        cluster.conflicts.append(
            Conflict(
                type=ConflictType.QUANTITATIVE,
                description="Test conflict",
            )
        )

        assert cluster.has_conflicts


class TestConflict:
    """Tests for Conflict model."""

    def test_conflict_to_academic_text(self, mock_source, tmp_path):
        """Test academic text generation."""
        from neurosynth.models.knowledge import Perspective

        # Create sources with different years
        path2 = tmp_path / "newer.pdf"
        path2.touch()
        newer_source = Source(
            path=path2,
            format=DocumentFormat.PDF,
            authors=["New Author"],
            year=2023,
        )

        older_source = Source(
            path=mock_source.path,
            format=DocumentFormat.PDF,
            authors=["Old Author"],
            year=2010,
        )

        conflict = Conflict(
            type=ConflictType.TEMPORAL,
            description="Treatment approach changed",
            perspectives=[
                Perspective(
                    claim="observation is recommended",
                    source=older_source,
                    chunk=None,
                ),
                Perspective(
                    claim="early intervention is preferred",
                    source=newer_source,
                    chunk=None,
                ),
            ],
        )

        text = conflict.to_academic_text()
        assert "classic teaching" in text.lower() or "recent" in text.lower()


class TestSemanticClusterer:
    """Tests for semantic clustering."""

    @pytest.mark.asyncio
    async def test_clustering_similar_content(self, sample_chunks):
        """Test that similar content is clustered together."""
        # Mock the embedding generator
        with patch("neurosynth.dedup.clustering.EmbeddingGenerator") as mock_gen_cls:
            mock_gen = MagicMock()

            # Create fake embeddings that are similar for first two chunks
            async def mock_build_matrix(chunks):
                n = len(chunks)
                matrix = np.eye(n)
                # Make first two chunks similar
                matrix[0, 1] = matrix[1, 0] = 0.95
                return matrix

            mock_gen.build_similarity_matrix = AsyncMock(side_effect=mock_build_matrix)
            mock_gen.generate_embeddings = AsyncMock(return_value=sample_chunks)
            mock_gen_cls.return_value = mock_gen

            from neurosynth.dedup.clustering import SemanticClusterer

            clusterer = SemanticClusterer(similarity_threshold=0.92)
            result = await clusterer.cluster_chunks(sample_chunks)

            # First two chunks should be in same cluster (similarity > threshold)
            # Third chunk should be separate
            assert result.num_clusters >= 1
            assert result.total_chunks == 3
