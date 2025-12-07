"""
Unit tests for AsyncAIClient.

Tests the async AI client with mocked HTTP responses.
Following user rules: Mock the LLM Provider and Vector DB.
"""

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

import httpx


class TestAsyncAIClient:
    """Test suite for AsyncAIClient."""

    @pytest.fixture
    def mock_env(self, monkeypatch):
        """Mock environment variables."""
        monkeypatch.setenv("VOYAGE_API_KEY", "test-voyage-key")
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-anthropic-key")

    @pytest.fixture
    def mock_httpx_client(self):
        """Create a mock httpx.AsyncClient."""
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        return mock_client

    @pytest.mark.asyncio
    async def test_get_embedding_success(self, mock_env, mock_httpx_client):
        """Test successful embedding retrieval."""
        # Arrange - include 'index' field as Voyage API returns
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": [{"index": 0, "embedding": [0.1, 0.2, 0.3] * 341}]  # 1023 dims
        }
        mock_response.raise_for_status = MagicMock()
        mock_httpx_client.post = AsyncMock(return_value=mock_response)

        from ai.async_client import AsyncAIClient

        client = AsyncAIClient()
        client._client = mock_httpx_client

        # Act
        embedding = await client.get_embedding("test query")

        # Assert
        assert len(embedding) == 1023
        assert embedding[0] == 0.1
        mock_httpx_client.post.assert_called_once()

    @pytest.mark.asyncio
    async def test_synthesize_success(self, mock_env, mock_httpx_client):
        """Test successful synthesis call."""
        # Arrange
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "content": [{"type": "text", "text": "This is a test answer."}]
        }
        mock_response.raise_for_status = MagicMock()
        mock_httpx_client.post = AsyncMock(return_value=mock_response)

        from ai.async_client import AsyncAIClient
        
        client = AsyncAIClient()
        client._client = mock_httpx_client

        # Act
        result = await client.synthesize(
            prompt="What is the approach to vestibular schwannoma?",
            system_prompt="You are a neurosurgical assistant."
        )

        # Assert
        assert result == "This is a test answer."
        mock_httpx_client.post.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_embeddings_batch(self, mock_env, mock_httpx_client):
        """Test batch embedding retrieval."""
        # Arrange - include 'index' field as Voyage API returns
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": [
                {"index": 0, "embedding": [0.1] * 1024},
                {"index": 1, "embedding": [0.2] * 1024},
            ]
        }
        mock_response.raise_for_status = MagicMock()
        mock_httpx_client.post = AsyncMock(return_value=mock_response)

        from ai.async_client import AsyncAIClient

        client = AsyncAIClient()
        client._client = mock_httpx_client

        # Act
        embeddings = await client.get_embeddings(["query1", "query2"])

        # Assert
        assert len(embeddings) == 2
        assert len(embeddings[0]) == 1024

    @pytest.mark.asyncio
    async def test_client_close(self, mock_env, mock_httpx_client):
        """Test client cleanup."""
        from ai.async_client import AsyncAIClient
        
        client = AsyncAIClient()
        client._client = mock_httpx_client
        mock_httpx_client.aclose = AsyncMock()

        # Act
        await client.close()

        # Assert
        mock_httpx_client.aclose.assert_called_once()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

