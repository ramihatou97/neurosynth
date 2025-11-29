"""Tests for LLM client implementations."""

from unittest.mock import AsyncMock, MagicMock, patch

import numpy as np
import pytest


class TestClaudeClient:
    """Tests for ClaudeClient."""

    @pytest.mark.asyncio
    async def test_generate_basic(self, mock_claude_response):
        """Test basic generation with Claude."""
        with patch("neurosynth.llm.claude.anthropic") as mock_anthropic:
            mock_client = AsyncMock()
            mock_client.messages.create = AsyncMock(return_value=mock_claude_response)
            mock_anthropic.AsyncAnthropic.return_value = mock_client

            from neurosynth.llm.claude import ClaudeClient

            client = ClaudeClient()
            result = await client.generate("Test prompt")

            assert result == "Test response from Claude"
            mock_client.messages.create.assert_called_once()

    @pytest.mark.asyncio
    async def test_generate_with_system_prompt(self, mock_claude_response):
        """Test generation with custom system prompt."""
        with patch("neurosynth.llm.claude.anthropic") as mock_anthropic:
            mock_client = AsyncMock()
            mock_client.messages.create = AsyncMock(return_value=mock_claude_response)
            mock_anthropic.AsyncAnthropic.return_value = mock_client

            from neurosynth.llm.claude import ClaudeClient

            client = ClaudeClient()
            await client.generate("Test prompt", system="Custom system")

            call_kwargs = mock_client.messages.create.call_args.kwargs
            assert call_kwargs["system"] == "Custom system"

    @pytest.mark.asyncio
    async def test_merge_chunks(self, mock_claude_response):
        """Test chunk merging."""
        with patch("neurosynth.llm.claude.anthropic") as mock_anthropic:
            mock_client = AsyncMock()
            mock_client.messages.create = AsyncMock(return_value=mock_claude_response)
            mock_anthropic.AsyncAnthropic.return_value = mock_client

            from neurosynth.llm.claude import ClaudeClient

            client = ClaudeClient()
            chunks = [
                {"content": "First chunk", "source": "Source1"},
                {"content": "Second chunk", "source": "Source2"},
            ]
            result = await client.merge_chunks(chunks)

            assert isinstance(result, str)
            mock_client.messages.create.assert_called_once()

    @pytest.mark.asyncio
    async def test_detect_conflicts_returns_list(self, mock_claude_response):
        """Test conflict detection returns a list."""
        mock_claude_response.content[0].text = "[]"

        with patch("neurosynth.llm.claude.anthropic") as mock_anthropic:
            mock_client = AsyncMock()
            mock_client.messages.create = AsyncMock(return_value=mock_claude_response)
            mock_anthropic.AsyncAnthropic.return_value = mock_client

            from neurosynth.llm.claude import ClaudeClient

            client = ClaudeClient()
            chunks = [{"content": "Chunk 1"}, {"content": "Chunk 2"}]
            result = await client.detect_conflicts(chunks)

            assert isinstance(result, list)


class TestGeminiClient:
    """Tests for GeminiClient."""

    @pytest.mark.asyncio
    async def test_generate_basic(self, mock_gemini_response):
        """Test basic generation with Gemini."""
        with patch("neurosynth.llm.gemini.genai") as mock_genai:
            mock_model = MagicMock()
            mock_model.generate_content.return_value = mock_gemini_response
            mock_genai.GenerativeModel.return_value = mock_model

            from neurosynth.llm.gemini import GeminiClient

            client = GeminiClient()
            result = await client.generate("Test prompt")

            assert result == "Test response from Gemini"

    @pytest.mark.asyncio
    async def test_extract_structure_returns_dict(self, mock_gemini_response):
        """Test structure extraction returns a dict."""
        mock_gemini_response.text = '{"sections": [], "key_topics": []}'

        with patch("neurosynth.llm.gemini.genai") as mock_genai:
            mock_model = MagicMock()
            mock_model.generate_content.return_value = mock_gemini_response
            mock_genai.GenerativeModel.return_value = mock_model

            from neurosynth.llm.gemini import GeminiClient

            client = GeminiClient()
            result = await client.extract_structure("Sample text")

            assert isinstance(result, dict)
            assert "sections" in result

    @pytest.mark.asyncio
    async def test_extract_metadata(self, mock_gemini_response):
        """Test metadata extraction."""
        mock_gemini_response.text = '{"title": "Test", "authors": ["Smith"], "year": 2023}'

        with patch("neurosynth.llm.gemini.genai") as mock_genai:
            mock_model = MagicMock()
            mock_model.generate_content.return_value = mock_gemini_response
            mock_genai.GenerativeModel.return_value = mock_model

            from neurosynth.llm.gemini import GeminiClient

            client = GeminiClient()
            result = await client.extract_metadata("First pages content")

            assert result["title"] == "Test"
            assert "Smith" in result["authors"]


class TestVoyageClient:
    """Tests for VoyageClient."""

    @pytest.mark.asyncio
    async def test_embed_text(self):
        """Test single text embedding."""
        # Create mock response with exactly 1 embedding for 1 input text
        mock_response = MagicMock()
        mock_response.embeddings = [np.random.rand(1024).tolist()]

        with patch("neurosynth.llm.voyage.voyageai") as mock_voyageai:
            mock_client = MagicMock()
            mock_client.embed.return_value = mock_response
            mock_voyageai.Client.return_value = mock_client

            from neurosynth.llm.voyage import VoyageClient

            client = VoyageClient()
            result = await client.embed_text("Sample text")

            assert isinstance(result, np.ndarray)
            assert len(result) == 1024

    @pytest.mark.asyncio
    async def test_embed_texts_batch(self, mock_voyage_response):
        """Test batch text embedding."""
        with patch("neurosynth.llm.voyage.voyageai") as mock_voyageai:
            mock_client = MagicMock()
            mock_client.embed.return_value = mock_voyage_response
            mock_voyageai.Client.return_value = mock_client

            from neurosynth.llm.voyage import VoyageClient

            client = VoyageClient()
            texts = ["Text 1", "Text 2", "Text 3"]
            result = await client.embed_texts(texts)

            assert len(result) == 3
            assert all(isinstance(e, np.ndarray) for e in result)

    @pytest.mark.asyncio
    async def test_compute_similarity(self):
        """Test similarity computation."""
        # Create mock response with exactly 2 identical embeddings for 2 inputs
        mock_response = MagicMock()
        mock_response.embeddings = [
            np.ones(1024).tolist(),
            np.ones(1024).tolist(),
        ]

        with patch("neurosynth.llm.voyage.voyageai") as mock_voyageai:
            mock_client = MagicMock()
            mock_client.embed.return_value = mock_response
            mock_voyageai.Client.return_value = mock_client

            from neurosynth.llm.voyage import VoyageClient

            # Use unique text to avoid cache hits from other tests
            client = VoyageClient()
            similarity = await client.compute_similarity(
                "Unique text for similarity test A",
                "Unique text for similarity test B"
            )

            # Identical vectors should have similarity of 1.0
            assert 0.99 <= similarity <= 1.01

    @pytest.mark.asyncio
    async def test_build_similarity_matrix(self):
        """Test similarity matrix building."""
        from neurosynth.llm.voyage import VoyageClient

        with patch("neurosynth.llm.voyage.voyageai"):
            client = VoyageClient()

            # Create 3 random embeddings
            embeddings = [np.random.rand(1024) for _ in range(3)]
            matrix = await client.build_similarity_matrix(embeddings)

            assert matrix.shape == (3, 3)
            # Diagonal should be 1.0 (self-similarity)
            np.testing.assert_array_almost_equal(np.diag(matrix), np.ones(3), decimal=5)


class TestEmbeddingCache:
    """Tests for EmbeddingCache."""

    def test_cache_set_and_get(self):
        """Test basic cache operations."""
        from neurosynth.llm.voyage import EmbeddingCache

        cache = EmbeddingCache()
        embedding = np.random.rand(1024)

        cache.set("test_hash", embedding)
        result = cache.get("test_hash")

        np.testing.assert_array_equal(result, embedding)

    def test_cache_miss_returns_none(self):
        """Test cache miss behavior."""
        from neurosynth.llm.voyage import EmbeddingCache

        cache = EmbeddingCache()
        result = cache.get("nonexistent_hash")

        assert result is None

    def test_cache_clear(self):
        """Test cache clearing."""
        from neurosynth.llm.voyage import EmbeddingCache

        cache = EmbeddingCache()
        cache.set("hash1", np.random.rand(1024))
        cache.set("hash2", np.random.rand(1024))

        assert cache.size == 2
        cache.clear()
        assert cache.size == 0
