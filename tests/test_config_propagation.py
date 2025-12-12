"""
Tests for configuration parameter propagation.

Validates that UI configuration selections (chunk size, overlap, embedding models)
flow correctly from UI → DocumentProcessor → backend components.
"""

from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pytest

from src.ingest.processor import DocumentProcessor


class TestChunkConfiguration:
    """Test chunk size and overlap parameter propagation."""

    def test_chunk_size_propagation(self):
        """Test chunk_size flows from UI → DocumentProcessor."""
        processor = DocumentProcessor(
            chunk_size=2000, chunk_overlap=300, entropy_threshold=5.0
        )

        assert processor.chunk_size == 2000
        assert processor.chunk_overlap == 300
        assert processor.entropy_threshold == 5.0

    def test_chunk_defaults(self):
        """Test default values when not specified."""
        processor = DocumentProcessor()

        # Should use settings defaults
        assert processor.chunk_size is not None
        assert processor.chunk_overlap is not None
        assert processor.entropy_threshold == 4.5

    def test_chunk_size_none_uses_settings(self):
        """Test that None values fall back to settings."""
        processor = DocumentProcessor(chunk_size=None, chunk_overlap=None)

        # Should fall back to settings
        assert processor.chunk_size is not None
        assert processor.chunk_overlap is not None


class TestTextEmbeddingModel:
    """Test text embedding model parameter propagation."""

    def test_text_embedding_model_propagation(self):
        """Test text embedding model parameter is stored."""
        processor = DocumentProcessor(text_embedding_model="voyage-3")

        assert processor.text_embedding_model == "voyage-3"

    def test_text_embedding_model_default(self):
        """Test text embedding model defaults to settings."""
        processor = DocumentProcessor()

        # Should use settings.embedding_model (voyage-3-lite by default)
        assert processor.text_embedding_model is not None
        assert isinstance(processor.text_embedding_model, str)

    def test_text_embedding_model_none_uses_settings(self):
        """Test that None falls back to settings."""
        processor = DocumentProcessor(text_embedding_model=None)

        # Should fall back to settings
        assert processor.text_embedding_model is not None


class TestImageEmbeddingModel:
    """Test image embedding model parameter propagation."""

    def test_image_embedding_model_propagation(self):
        """Test image embedding model parameter is stored."""
        processor = DocumentProcessor(image_embedding_model="clip-vit-large-patch14")

        assert processor.image_embedding_model == "clip-vit-large-patch14"

    def test_image_embedding_model_none(self):
        """Test image embedding can be disabled with 'none'."""
        processor = DocumentProcessor(image_embedding_model="none")

        assert processor.image_embedding_model == "none"

    def test_image_embedding_model_default(self):
        """Test image embedding model defaults to settings."""
        processor = DocumentProcessor()

        # Should use settings.colpali_model
        assert processor.image_embedding_model is not None
        assert isinstance(processor.image_embedding_model, str)


class TestImageEmbeddingConditionalLogic:
    """Test image embedding conditional logic based on model selection."""

    def test_image_embedding_none_selected(self):
        """Test no embeddings when 'none' selected."""
        processor = DocumentProcessor(image_embedding_model="none")

        # Create mock images without embedding attribute
        mock_images = [
            Mock(spec=["file_path"], file_path=Path("test1.png")),
            Mock(spec=["file_path"], file_path=Path("test2.png")),
        ]

        result = processor._embed_images(mock_images)

        # Should return images unchanged without embedding
        assert result == mock_images
        # Verify no embedding attribute was added
        for img in result:
            assert not hasattr(img, "embedding")

    @patch("neurosynth.llm.colpali.get_colpali_client")
    def test_image_embedding_colpali_selected(self, mock_get_colpali):
        """Test ColPali is used when selected."""
        # Setup mock ColPali client
        mock_client = MagicMock()
        mock_embeddings = [
            [0.1, 0.2, 0.3],  # Mock embedding 1
            [0.4, 0.5, 0.6],  # Mock embedding 2
        ]
        mock_client._embed_images_sync.return_value = [
            MagicMock(tolist=lambda e=e: e) for e in mock_embeddings
        ]
        mock_get_colpali.return_value = mock_client

        processor = DocumentProcessor(image_embedding_model="colpali-v1.2")

        # Create mock images
        mock_images = [
            Mock(file_path=Path("test1.png"), embedding=None),
            Mock(file_path=Path("test2.png"), embedding=None),
        ]

        result = processor._embed_images_colpali(mock_images)

        # Should call ColPali client
        mock_get_colpali.assert_called_once()
        mock_client._embed_images_sync.assert_called_once()

        # Images should have embeddings attached
        assert len(result) == 2
        for img in result:
            assert hasattr(img, "embedding")
            assert img.embedding is not None

    def test_image_embedding_clip_not_implemented(self):
        """Test CLIP returns warning when not implemented."""
        processor = DocumentProcessor(image_embedding_model="clip-vit-large-patch14")

        # Create mock images
        mock_images = [Mock(file_path=Path("test.png"), embedding=None)]

        # Should return images unchanged with warning
        result = processor._embed_images_clip(mock_images)

        assert result == mock_images

    def test_image_embedding_unknown_model(self):
        """Test unknown model returns images unchanged."""
        processor = DocumentProcessor(image_embedding_model="unknown-model")

        # Create mock images
        mock_images = [Mock(file_path=Path("test.png"), embedding=None)]

        result = processor._embed_images(mock_images)

        # Should return images unchanged
        assert result == mock_images


class TestEndToEndParameterFlow:
    """Test complete parameter flow from constructor to methods."""

    def test_all_parameters_together(self):
        """Test all parameters can be set together."""
        processor = DocumentProcessor(
            chunk_size=2000,
            chunk_overlap=300,
            entropy_threshold=5.0,
            text_embedding_model="voyage-3",
            image_embedding_model="colpali-v1.2",
        )

        # All parameters should be stored correctly
        assert processor.chunk_size == 2000
        assert processor.chunk_overlap == 300
        assert processor.entropy_threshold == 5.0
        assert processor.text_embedding_model == "voyage-3"
        assert processor.image_embedding_model == "colpali-v1.2"

    def test_optional_parameters_use_defaults(self):
        """Test that optional parameters default correctly when not provided."""
        processor = DocumentProcessor()

        # All parameters should have reasonable defaults
        assert processor.chunk_size > 0
        assert processor.chunk_overlap >= 0
        assert processor.entropy_threshold > 0
        assert len(processor.text_embedding_model) > 0
        assert len(processor.image_embedding_model) > 0
