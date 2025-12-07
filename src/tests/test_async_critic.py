"""
Unit tests for DeepDxCritic async methods.

Tests the async critic with mocked HTTP responses.
Following user rules: Mock the LLM Provider.
"""

import asyncio
import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

import httpx


class TestDeepDxCriticAsync:
    """Test suite for DeepDxCritic async methods."""

    @pytest.fixture
    def mock_settings(self, monkeypatch):
        """Mock settings and environment."""
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-anthropic-key")
        
        # Mock the settings modules
        mock_ddx_settings = MagicMock()
        mock_ns_settings = MagicMock()
        mock_ns_settings.anthropic_api_key = "test-anthropic-key"
        
        with patch("deep_dx.config.get_deepdx_settings", return_value=mock_ddx_settings):
            with patch("neurosynth.config.get_settings", return_value=mock_ns_settings):
                yield

    @pytest.fixture
    def mock_httpx_client(self):
        """Create a mock httpx.AsyncClient."""
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        return mock_client

    @pytest.mark.asyncio
    async def test_check_safety_async_safe(self, mock_settings, mock_httpx_client):
        """Test safety check returns safe result."""
        # Arrange
        safety_response = {
            "safe": True,
            "issues": [],
            "risk_level": "low"
        }
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "content": [{"text": json.dumps(safety_response)}]
        }
        mock_response.raise_for_status = MagicMock()
        mock_httpx_client.post = AsyncMock(return_value=mock_response)

        from deep_dx.critic.critic import DeepDxCritic
        
        critic = DeepDxCritic(async_client=mock_httpx_client)

        # Act
        result = await critic.check_safety_async(
            query="What is the approach to VS?",
            answer="The retrosigmoid approach is commonly used."
        )

        # Assert
        assert result["safe"] is True
        assert result["risk_level"] == "low"

    @pytest.mark.asyncio
    async def test_check_safety_async_unsafe(self, mock_settings, mock_httpx_client):
        """Test safety check returns unsafe result with issues."""
        # Arrange
        safety_response = {
            "safe": False,
            "issues": ["Laterality confusion detected"],
            "risk_level": "high"
        }
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "content": [{"text": json.dumps(safety_response)}]
        }
        mock_response.raise_for_status = MagicMock()
        mock_httpx_client.post = AsyncMock(return_value=mock_response)

        from deep_dx.critic.critic import DeepDxCritic
        
        critic = DeepDxCritic(async_client=mock_httpx_client)

        # Act
        result = await critic.check_safety_async(
            query="Left-sided tumor approach",
            answer="Approach from the right side..."  # Wrong laterality
        )

        # Assert
        assert result["safe"] is False
        assert "Laterality confusion detected" in result["issues"]
        assert result["risk_level"] == "high"

    @pytest.mark.asyncio
    async def test_evaluate_relevance_async(self, mock_settings, mock_httpx_client):
        """Test relevance evaluation filters chunks correctly."""
        # Arrange
        relevance_response = [
            {"id": 0, "score": 9, "reason": "Directly relevant"},
            {"id": 1, "score": 5, "reason": "Tangentially related"},
            {"id": 2, "score": 8, "reason": "Good context"},
        ]
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "content": [{"text": json.dumps(relevance_response)}]
        }
        mock_response.raise_for_status = MagicMock()
        mock_httpx_client.post = AsyncMock(return_value=mock_response)

        from deep_dx.critic.critic import DeepDxCritic
        
        critic = DeepDxCritic(async_client=mock_httpx_client)

        chunks = [
            {"text": "Vestibular schwannoma approach..."},
            {"text": "General anesthesia considerations..."},
            {"text": "Facial nerve monitoring during surgery..."},
        ]

        # Act
        result = await critic.evaluate_relevance_async(
            query="VS surgical approach",
            chunks=chunks,
            threshold=7
        )

        # Assert
        assert len(result) == 2  # Only chunks with score >= 7
        assert result[0]["relevance_score"] == 9  # Sorted by score desc


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

