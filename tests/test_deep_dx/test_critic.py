"""
Tests for Deep-DX Critic

Comprehensive test coverage for:
- Safety checking (laterality, dosage, anatomy)
- Relevance evaluation
- Risk level assignment
- JSON parsing edge cases
- API failure handling
- Async and sync methods
"""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from deep_dx.critic.critic import DeepDxCritic

# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def mock_anthropic_sync():
    """Mock synchronous Anthropic client"""
    with patch("deep_dx.critic.critic.Anthropic") as mock_class:
        mock_client = MagicMock()
        mock_class.return_value = mock_client

        # Default safe response
        mock_response = MagicMock()
        mock_response.content = [
            MagicMock(
                text=json.dumps({"safe": True, "issues": [], "risk_level": "low"})
            )
        ]
        mock_client.messages.create.return_value = mock_response

        yield mock_client


@pytest.fixture
def critic(mock_anthropic_sync):
    """Create DeepDxCritic instance with mocked Anthropic client"""
    return DeepDxCritic()


# ============================================================================
# Test Cases: Safety Checking - Success Scenarios
# ============================================================================


def test_check_safety_safe_answer(critic, mock_anthropic_sync):
    """Test safety check with a safe answer"""
    # Mock safe response
    mock_anthropic_sync.messages.create.return_value.content[0].text = json.dumps(
        {
            "safe": True,
            "issues": [],
            "risk_level": "low",
        }
    )

    result = critic.check_safety(
        query="What is the House-Brackmann scale?",
        answer="The House-Brackmann scale is a grading system for facial nerve function, ranging from Grade I (normal) to Grade VI (complete paralysis).",
    )

    assert result["safe"] is True
    assert result["issues"] == []
    assert result["risk_level"] == "low"


@pytest.mark.asyncio
async def test_check_safety_async_safe_answer():
    """Test async safety check with a safe answer"""
    # Mock async HTTP client
    mock_async_client = AsyncMock()

    # Mock safe response
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "content": [
            {
                "text": json.dumps(
                    {
                        "safe": True,
                        "issues": [],
                        "risk_level": "low",
                    }
                )
            }
        ]
    }
    mock_async_client.post.return_value = mock_response

    critic = DeepDxCritic(async_client=mock_async_client)

    result = await critic.check_safety_async(
        query="What is the House-Brackmann scale?",
        answer="The House-Brackmann scale ranges from Grade I to Grade VI.",
    )

    assert result["safe"] is True
    assert result["issues"] == []
    assert result["risk_level"] == "low"


# ============================================================================
# Test Cases: Safety Checking - Laterality Detection
# ============================================================================


def test_check_safety_detects_laterality_confusion(critic, mock_anthropic_sync):
    """Test that critic detects left/right confusion"""
    # Mock unsafe response with laterality issue
    mock_anthropic_sync.messages.create.return_value.content[0].text = json.dumps(
        {
            "safe": False,
            "issues": [
                "Laterality confusion: Answer states tumor is on left side, but source clearly indicates right side"
            ],
            "risk_level": "high",
        }
    )

    result = critic.check_safety(
        query="Which side is the tumor?",
        answer="The tumor is on the left petrous ridge. [Source says: right petrous ridge]",
    )

    assert result["safe"] is False
    assert len(result["issues"]) == 1
    assert "laterality" in result["issues"][0].lower()
    assert result["risk_level"] == "high"


@pytest.mark.asyncio
async def test_check_safety_async_laterality_detection():
    """Test async laterality detection"""
    mock_async_client = AsyncMock()

    mock_response = MagicMock()
    mock_response.json.return_value = {
        "content": [
            {
                "text": json.dumps(
                    {
                        "safe": False,
                        "issues": ["Left/right confusion detected"],
                        "risk_level": "high",
                    }
                )
            }
        ]
    }
    mock_async_client.post.return_value = mock_response

    critic = DeepDxCritic(async_client=mock_async_client)

    result = await critic.check_safety_async(
        query="Tumor location?",
        answer="Tumor on left (source says right)",
    )

    assert result["safe"] is False
    assert "left/right" in result["issues"][0].lower()


# ============================================================================
# Test Cases: Safety Checking - Dosage Errors
# ============================================================================


def test_check_safety_detects_dosage_errors(critic, mock_anthropic_sync):
    """Test detection of fatal dosage errors"""
    mock_anthropic_sync.messages.create.return_value.content[0].text = json.dumps(
        {
            "safe": False,
            "issues": ["Fatal dosage error: Recommended 10x the safe maximum dose"],
            "risk_level": "critical",
        }
    )

    result = critic.check_safety(
        query="What is the recommended dose of dexamethasone?",
        answer="The recommended dose is 1000mg every 6 hours.",
    )

    assert result["safe"] is False
    assert "dosage" in result["issues"][0].lower()
    assert result["risk_level"] == "critical"


# ============================================================================
# Test Cases: Safety Checking - Contraindication Violations
# ============================================================================


def test_check_safety_detects_contraindications(critic, mock_anthropic_sync):
    """Test detection of contraindicated procedures"""
    mock_anthropic_sync.messages.create.return_value.content[0].text = json.dumps(
        {
            "safe": False,
            "issues": [
                "Contraindication violation: Procedure recommended despite patient having known allergy to anesthesia"
            ],
            "risk_level": "high",
        }
    )

    result = critic.check_safety(
        query="Can this patient undergo surgery?",
        answer="Yes, proceed with surgery (despite known allergy).",
    )

    assert result["safe"] is False
    assert "contraindication" in result["issues"][0].lower()


# ============================================================================
# Test Cases: Safety Checking - Anatomical Hallucinations
# ============================================================================


def test_check_safety_detects_hallucinated_anatomy(critic, mock_anthropic_sync):
    """Test detection of non-existent anatomical structures"""
    mock_anthropic_sync.messages.create.return_value.content[0].text = json.dumps(
        {
            "safe": False,
            "issues": [
                "Hallucinated anatomy: 'Medial facial artery' does not exist in standard anatomy"
            ],
            "risk_level": "medium",
        }
    )

    result = critic.check_safety(
        query="What vessels are involved?",
        answer="The medial facial artery should be avoided.",
    )

    assert result["safe"] is False
    assert "hallucinated anatomy" in result["issues"][0].lower()


# ============================================================================
# Test Cases: Safety Checking - Multiple Issues
# ============================================================================


def test_check_safety_multiple_issues(critic, mock_anthropic_sync):
    """Test handling of multiple simultaneous safety violations"""
    mock_anthropic_sync.messages.create.return_value.content[0].text = json.dumps(
        {
            "safe": False,
            "issues": [
                "Laterality confusion: left vs right",
                "Dosage error: exceeds safe limits",
                "Contraindication ignored",
            ],
            "risk_level": "critical",
        }
    )

    result = critic.check_safety(
        query="Treatment protocol?",
        answer="Bad answer with multiple errors",
    )

    assert result["safe"] is False
    assert len(result["issues"]) == 3
    assert result["risk_level"] == "critical"


# ============================================================================
# Test Cases: JSON Parsing Edge Cases
# ============================================================================


def test_check_safety_handles_json_with_code_block(critic, mock_anthropic_sync):
    """Test parsing JSON wrapped in markdown code blocks"""
    mock_anthropic_sync.messages.create.return_value.content[
        0
    ].text = """```json
{
    "safe": true,
    "issues": [],
    "risk_level": "low"
}
```"""

    result = critic.check_safety("query", "answer")

    assert result["safe"] is True
    assert result["issues"] == []


def test_check_safety_handles_json_with_generic_code_block(critic, mock_anthropic_sync):
    """Test parsing JSON in generic code block (not marked as json)"""
    mock_anthropic_sync.messages.create.return_value.content[
        0
    ].text = """```
{
    "safe": false,
    "issues": ["Problem detected"],
    "risk_level": "medium"
}
```"""

    result = critic.check_safety("query", "answer")

    assert result["safe"] is False
    assert len(result["issues"]) == 1


def test_check_safety_handles_json_with_extra_text(critic, mock_anthropic_sync):
    """Test parsing JSON when embedded in explanatory text"""
    mock_anthropic_sync.messages.create.return_value.content[
        0
    ].text = """
After careful analysis, here is my assessment:

{
    "safe": true,
    "issues": [],
    "risk_level": "low"
}

This answer appears safe based on the criteria.
"""

    result = critic.check_safety("query", "answer")

    assert result["safe"] is True


def test_check_safety_handles_malformed_json(critic, mock_anthropic_sync):
    """Test graceful handling of unparseable JSON"""
    mock_anthropic_sync.messages.create.return_value.content[0].text = (
        "Not valid JSON at all"
    )

    result = critic.check_safety("query", "answer")

    # Should fail closed (assume unsafe if can't parse)
    assert result["safe"] is False
    assert "failed to validate" in result["issues"][0].lower()


# ============================================================================
# Test Cases: Relevance Evaluation
# ============================================================================


def test_evaluate_relevance_success(critic, mock_anthropic_sync):
    """Test relevance scoring of chunks"""
    # Mock relevance response
    mock_anthropic_sync.messages.create.return_value.content[0].text = json.dumps(
        [
            {"id": 0, "score": 9, "reason": "Directly answers the question"},
            {"id": 1, "score": 7, "reason": "Related but tangential"},
            {"id": 2, "score": 3, "reason": "Barely relevant"},
        ]
    )

    chunks = [
        {"text": "Highly relevant chunk about facial nerve"},
        {"text": "Somewhat related chunk about nerves in general"},
        {"text": "Barely relevant chunk about general anatomy"},
    ]

    result = critic.evaluate_relevance(
        query="What is the facial nerve course?",
        chunks=chunks,
        threshold=7,
    )

    # Should return only chunks with score >= 7
    assert len(result) == 2
    assert result[0]["relevance_score"] == 9
    assert result[1]["relevance_score"] == 7


@pytest.mark.asyncio
async def test_evaluate_relevance_async_filters_by_threshold():
    """Test async relevance evaluation with threshold filtering"""
    mock_async_client = AsyncMock()

    mock_response = MagicMock()
    mock_response.json.return_value = {
        "content": [
            {
                "text": json.dumps(
                    [
                        {"id": 0, "score": 9, "reason": "Perfect match"},
                        {"id": 1, "score": 5, "reason": "Low relevance"},
                    ]
                )
            }
        ]
    }
    mock_async_client.post.return_value = mock_response

    critic = DeepDxCritic(async_client=mock_async_client)

    chunks = [
        {"text": "Highly relevant"},
        {"text": "Not very relevant"},
    ]

    result = await critic.evaluate_relevance_async(
        query="test query",
        chunks=chunks,
        threshold=8,  # High threshold
    )

    # Should only return chunk with score >= 8
    assert len(result) == 1
    assert result[0]["relevance_score"] == 9


def test_evaluate_relevance_empty_chunks(critic):
    """Test handling of empty chunk list"""
    result = critic.evaluate_relevance(query="test", chunks=[])

    assert result == []


def test_evaluate_relevance_sorts_by_score(critic, mock_anthropic_sync):
    """Test that results are sorted by score descending"""
    mock_anthropic_sync.messages.create.return_value.content[0].text = json.dumps(
        [
            {"id": 0, "score": 5, "reason": "Low"},
            {"id": 1, "score": 10, "reason": "High"},
            {"id": 2, "score": 7, "reason": "Medium"},
        ]
    )

    chunks = [
        {"text": "Chunk 1"},
        {"text": "Chunk 2"},
        {"text": "Chunk 3"},
    ]

    result = critic.evaluate_relevance(query="test", chunks=chunks, threshold=5)

    # Should be sorted by score descending
    assert result[0]["relevance_score"] == 10
    assert result[1]["relevance_score"] == 7
    assert result[2]["relevance_score"] == 5


# ============================================================================
# Test Cases: API Failure Handling
# ============================================================================


def test_check_safety_api_failure(critic, mock_anthropic_sync):
    """Test graceful handling of API failures"""
    # Mock API exception
    mock_anthropic_sync.messages.create.side_effect = Exception("API connection failed")

    result = critic.check_safety("query", "answer")

    # Should fail closed
    assert result["safe"] is False
    assert "failed to validate" in result["issues"][0].lower()
    assert result["risk_level"] == "unknown"


@pytest.mark.asyncio
async def test_check_safety_async_api_timeout():
    """Test async handling of API timeout"""
    mock_async_client = AsyncMock()
    mock_async_client.post.side_effect = httpx.ReadTimeout("Request timed out")

    critic = DeepDxCritic(async_client=mock_async_client)

    result = await critic.check_safety_async("query", "answer")

    # Should fail closed
    assert result["safe"] is False
    assert "failed to validate" in result["issues"][0].lower()


@pytest.mark.asyncio
async def test_check_safety_async_http_error():
    """Test async handling of HTTP error status"""
    mock_async_client = AsyncMock()

    mock_response = MagicMock()
    mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
        "500 Internal Server Error", request=MagicMock(), response=MagicMock()
    )
    mock_async_client.post.return_value = mock_response

    critic = DeepDxCritic(async_client=mock_async_client)

    result = await critic.check_safety_async("query", "answer")

    # Should fail closed
    assert result["safe"] is False


def test_evaluate_relevance_api_failure_fallback(critic, mock_anthropic_sync):
    """Test that relevance evaluation falls back on API failure"""
    mock_anthropic_sync.messages.create.side_effect = Exception("API failed")

    chunks = [
        {"text": "Chunk 1"},
        {"text": "Chunk 2"},
        {"text": "Chunk 3"},
        {"text": "Chunk 4"},
    ]

    result = critic.evaluate_relevance(query="test", chunks=chunks)

    # Should return top 3 chunks as fallback
    assert len(result) == 3


# ============================================================================
# Test Cases: Risk Level Assignment
# ============================================================================


def test_check_safety_low_risk(critic, mock_anthropic_sync):
    """Test low risk level assignment"""
    mock_anthropic_sync.messages.create.return_value.content[0].text = json.dumps(
        {
            "safe": True,
            "issues": [],
            "risk_level": "low",
        }
    )

    result = critic.check_safety("query", "safe answer")

    assert result["risk_level"] == "low"


def test_check_safety_medium_risk(critic, mock_anthropic_sync):
    """Test medium risk level assignment"""
    mock_anthropic_sync.messages.create.return_value.content[0].text = json.dumps(
        {
            "safe": False,
            "issues": ["Minor inaccuracy in terminology"],
            "risk_level": "medium",
        }
    )

    result = critic.check_safety("query", "slightly inaccurate answer")

    assert result["risk_level"] == "medium"


def test_check_safety_high_risk(critic, mock_anthropic_sync):
    """Test high risk level assignment"""
    mock_anthropic_sync.messages.create.return_value.content[0].text = json.dumps(
        {
            "safe": False,
            "issues": ["Laterality confusion"],
            "risk_level": "high",
        }
    )

    result = critic.check_safety("query", "dangerous answer")

    assert result["risk_level"] == "high"


def test_check_safety_critical_risk(critic, mock_anthropic_sync):
    """Test critical risk level assignment"""
    mock_anthropic_sync.messages.create.return_value.content[0].text = json.dumps(
        {
            "safe": False,
            "issues": ["Fatal dosage error"],
            "risk_level": "critical",
        }
    )

    result = critic.check_safety("query", "critically unsafe answer")

    assert result["risk_level"] == "critical"


# ============================================================================
# Test Cases: Client Lifecycle Management
# ============================================================================


@pytest.mark.asyncio
async def test_critic_closes_owned_async_client():
    """Test that critic closes async client it created"""
    critic = DeepDxCritic()  # No client provided, will create one

    # Trigger async client creation
    await critic._get_async_client()

    assert critic._async_client is not None
    assert critic._owns_client is True

    # Close should clean up
    await critic.close()

    # Client should be None after close
    assert critic._async_client is None


@pytest.mark.asyncio
async def test_critic_does_not_close_provided_client():
    """Test that critic doesn't close client provided by caller"""
    external_client = AsyncMock()

    critic = DeepDxCritic(async_client=external_client)

    assert critic._async_client is external_client
    assert critic._owns_client is False

    # Close should not affect external client
    await critic.close()

    # External client should still be set
    assert critic._async_client is external_client
