"""
Tests for Deep-DX Synthesizer

Comprehensive test coverage for:
- Answer generation (sync and async)
- API failure handling
- Confidence level calculation
- Query expansion
- Retrieval integration
- Critic integration
- Edge cases
"""

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from deep_dx.engine.synthesizer import DeepDxSynthesizer
from index.precision_search import (
    ConfidenceLevel,
    PrecisionResult,
    PrecisionRetrievalResult,
    QueryType,
)
from models import Chunk, ChunkType, ExtractedImage, ImageType, SearchResult

# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def mock_search_engine():
    """Mock PrecisionSearchEngine"""
    engine = MagicMock()

    # Create sample chunks
    sample_chunk1 = Chunk(
        id="chunk_1",
        source_id="source_1",
        source_title="Test Source 1",
        section_title="Introduction",
        content="The House-Brackmann scale is a grading system for facial nerve function.",
        chunk_type=ChunkType.NARRATIVE,
        page_start=1,
        page_end=1,
        embedding=[0.1] * 384,
        image_ids=[],
        also_in_sources=[],
        metadata={},
    )

    sample_chunk2 = Chunk(
        id="chunk_2",
        source_id="source_1",
        source_title="Test Source 1",
        section_title="Grading",
        content="Grade I indicates normal facial function, while Grade VI indicates complete paralysis.",
        chunk_type=ChunkType.NARRATIVE,
        page_start=2,
        page_end=2,
        embedding=[0.2] * 384,
        image_ids=[],
        also_in_sources=[],
        metadata={},
    )

    # Create PrecisionResult objects
    results = [
        PrecisionResult(
            chunk=sample_chunk1,
            dense_score=0.85,
            colbert_score=0.90,
            final_score=0.875,
            has_safety_content=False,
        ),
        PrecisionResult(
            chunk=sample_chunk2,
            dense_score=0.80,
            colbert_score=0.85,
            final_score=0.825,
            has_safety_content=False,
        ),
    ]

    # Create sample image
    sample_image = ExtractedImage(
        id="img_1",
        source_id="source_1",
        page=1,
        file_path="/tmp/image1.png",
        caption="House-Brackmann Scale Diagram",
        surrounding_text="Figure showing facial nerve grading",
        image_type=ImageType.DIAGRAM,
        width=800,
        height=600,
        embedding=[0.3] * 128,
    )

    # Mock retrieval result
    engine.retrieve_for_topic.return_value = PrecisionRetrievalResult(
        query="House-Brackmann scale",
        query_type=QueryType.FACTUAL,
        results=results,
        images=[sample_image],
        confidence=0.85,
        confidence_level=ConfidenceLevel.HIGH,
        retrieval_time_ms=150.0,
        systems_used=["dense", "colbert"],
        warnings=[],
    )

    return engine


@pytest.fixture
def mock_ai_client():
    """Mock AsyncAIClient"""
    client = AsyncMock()

    # Mock embedding generation
    client.get_embedding.return_value = [0.1] * 384

    # Mock synonym expansion
    client.synthesize.side_effect = [
        "facial nerve paralysis grading",  # Expansion
        "The House-Brackmann scale ranges from Grade I (normal) to Grade VI (complete paralysis). [Test Source 1, p.1]",  # Answer
    ]

    return client


@pytest.fixture
def mock_critic():
    """Mock DeepDxCritic"""
    critic = AsyncMock()

    # Mock safe answer by default
    critic.check_safety_async.return_value = {
        "safe": True,
        "issues": [],
        "risk_level": "low",
    }

    return critic


@pytest.fixture
def synthesizer(mock_search_engine, mock_ai_client, mock_critic):
    """Create DeepDxSynthesizer with mocked dependencies"""
    return DeepDxSynthesizer(
        search_engine=mock_search_engine,
        ai_client=mock_ai_client,
        critic=mock_critic,
    )


# ============================================================================
# Test Cases: Successful Answer Generation
# ============================================================================


@pytest.mark.asyncio
async def test_generate_answer_async_success(
    synthesizer, mock_ai_client, mock_search_engine, mock_critic
):
    """Test successful async answer generation with all components"""
    result = await synthesizer.generate_answer_async(
        "What is the House-Brackmann scale?"
    )

    # Verify answer structure
    assert "answer" in result
    assert "sources" in result
    assert "confidence" in result
    assert "context_used" in result
    assert "images" in result

    # Verify answer content
    assert len(result["answer"]) > 0
    assert "House-Brackmann" in result["answer"]

    # Verify sources
    assert len(result["sources"]) > 0
    assert "Test Source 1" in result["sources"]

    # Verify confidence
    assert result["confidence"] == 1.0  # Safe answer, full confidence

    # Verify context used
    assert len(result["context_used"]) > 0

    # Verify images included
    assert len(result["images"]) > 0

    # Verify AI client was called correctly
    mock_ai_client.get_embedding.assert_called_once()
    assert mock_ai_client.synthesize.call_count == 2  # Expansion + Answer

    # Verify search engine was called
    mock_search_engine.retrieve_for_topic.assert_called_once()

    # Verify critic was called
    mock_critic.check_safety_async.assert_called_once()


@pytest.mark.asyncio
async def test_generate_answer_async_without_critic(mock_search_engine, mock_ai_client):
    """Test answer generation without critic verification"""
    synthesizer = DeepDxSynthesizer(
        search_engine=mock_search_engine,
        ai_client=mock_ai_client,
        critic=None,  # No critic
    )

    result = await synthesizer.generate_answer_async(
        "What is the House-Brackmann scale?"
    )

    # Should still work without critic
    assert "answer" in result
    assert result["confidence"] == 1.0  # Default confidence without critic


# ============================================================================
# Test Cases: Edge Cases and Error Handling
# ============================================================================


@pytest.mark.asyncio
async def test_generate_answer_async_no_results(
    mock_search_engine, mock_ai_client, mock_critic
):
    """Test handling when no search results are found"""
    # Mock empty results
    mock_search_engine.retrieve_for_topic.return_value = PrecisionRetrievalResult(
        query="obscure query",
        query_type=QueryType.FACTUAL,
        results=[],  # No results
        images=[],
        confidence=0.0,
        confidence_level=ConfidenceLevel.INSUFFICIENT,
        retrieval_time_ms=50.0,
        systems_used=["dense"],
        warnings=["No relevant results found"],
    )

    synthesizer = DeepDxSynthesizer(
        search_engine=mock_search_engine,
        ai_client=mock_ai_client,
        critic=mock_critic,
    )

    result = await synthesizer.generate_answer_async(
        "Very obscure neurosurgery question"
    )

    # Should return default "no information" response
    assert (
        result["answer"] == "I do not have enough information to answer this question."
    )
    assert result["sources"] == []
    assert result["confidence"] == 0.0
    assert result["context_used"] == []


@pytest.mark.asyncio
async def test_generate_answer_async_query_expansion_failure(
    mock_search_engine, mock_critic
):
    """Test graceful handling when query expansion fails"""
    # Mock AI client that fails expansion but succeeds on answer
    mock_ai_client = AsyncMock()
    mock_ai_client.get_embedding.return_value = [0.1] * 384
    mock_ai_client.synthesize.side_effect = [
        httpx.TimeoutException("Expansion timeout"),  # Expansion fails
        "The answer to your question. [Test Source 1, p.1]",  # Answer succeeds
    ]

    synthesizer = DeepDxSynthesizer(
        search_engine=mock_search_engine,
        ai_client=mock_ai_client,
        critic=mock_critic,
    )

    result = await synthesizer.generate_answer_async("Test query")

    # Should still generate answer despite expansion failure
    assert "answer" in result
    assert len(result["answer"]) > 0
    # Search should be called with original query (not expanded)
    mock_search_engine.retrieve_for_topic.assert_called_once()


@pytest.mark.asyncio
async def test_generate_answer_async_embedding_failure(mock_search_engine, mock_critic):
    """Test handling of embedding API failure"""
    # Mock AI client with embedding failure
    mock_ai_client = AsyncMock()
    mock_ai_client.get_embedding.side_effect = httpx.ReadTimeout("Embedding timeout")

    synthesizer = DeepDxSynthesizer(
        search_engine=mock_search_engine,
        ai_client=mock_ai_client,
        critic=mock_critic,
    )

    # Should raise the exception (no retry at this level)
    with pytest.raises(httpx.ReadTimeout):
        await synthesizer.generate_answer_async("Test query")


# ============================================================================
# Test Cases: Critic Integration
# ============================================================================


@pytest.mark.asyncio
async def test_generate_answer_async_critic_flags_unsafe(
    mock_search_engine, mock_ai_client
):
    """Test that unsafe answers are flagged with confidence=0 and warning"""
    # Mock critic that flags answer as unsafe
    mock_critic = AsyncMock()
    mock_critic.check_safety_async.return_value = {
        "safe": False,
        "issues": ["Laterality confusion: answer says left but source says right"],
        "risk_level": "high",
    }

    synthesizer = DeepDxSynthesizer(
        search_engine=mock_search_engine,
        ai_client=mock_ai_client,
        critic=mock_critic,
    )

    result = await synthesizer.generate_answer_async("Which side is the tumor?")

    # Answer should contain safety warning
    assert "SAFETY WARNING" in result["answer"]
    assert "laterality confusion" in result["answer"].lower()

    # Confidence should be 0
    assert result["confidence"] == 0.0


@pytest.mark.asyncio
async def test_generate_answer_async_critic_multiple_issues(
    mock_search_engine, mock_ai_client
):
    """Test critic with multiple safety violations"""
    # Mock critic with multiple issues
    mock_critic = AsyncMock()
    mock_critic.check_safety_async.return_value = {
        "safe": False,
        "issues": [
            "Dosage error: recommended dose exceeds safe limits",
            "Contraindication ignored: patient has known allergy",
        ],
        "risk_level": "critical",
    }

    synthesizer = DeepDxSynthesizer(
        search_engine=mock_search_engine,
        ai_client=mock_ai_client,
        critic=mock_critic,
    )

    result = await synthesizer.generate_answer_async("What is the recommended dose?")

    # Answer should contain both issues
    assert "SAFETY WARNING" in result["answer"]
    assert "Dosage error" in result["answer"]
    assert "Contraindication ignored" in result["answer"]


# ============================================================================
# Test Cases: Confidence Levels
# ============================================================================


@pytest.mark.asyncio
async def test_generate_answer_async_low_confidence_results(
    mock_ai_client, mock_critic
):
    """Test handling of low confidence retrieval results"""
    # Mock search engine with low confidence
    mock_search_engine = MagicMock()

    sample_chunk = Chunk(
        id="chunk_1",
        source_id="source_1",
        source_title="Tangentially Related Source",
        section_title="Vague Section",
        content="Some general information about neurosurgery.",
        chunk_type=ChunkType.NARRATIVE,
        page_start=1,
        page_end=1,
        embedding=[0.1] * 384,
    )

    mock_search_engine.retrieve_for_topic.return_value = PrecisionRetrievalResult(
        query="very specific question",
        query_type=QueryType.SPATIAL,
        results=[
            PrecisionResult(
                chunk=sample_chunk,
                dense_score=0.3,  # Low score
                colbert_score=None,
                final_score=0.3,
                has_safety_content=False,
            )
        ],
        images=[],
        confidence=0.3,  # Low confidence
        confidence_level=ConfidenceLevel.LOW,
        retrieval_time_ms=100.0,
        systems_used=["dense"],
        warnings=["Low confidence results"],
    )

    synthesizer = DeepDxSynthesizer(
        search_engine=mock_search_engine,
        ai_client=mock_ai_client,
        critic=mock_critic,
    )

    result = await synthesizer.generate_answer_async(
        "Very specific anatomical question"
    )

    # Should still generate answer but may note limitations
    assert "answer" in result
    assert len(result["sources"]) > 0


# ============================================================================
# Test Cases: Query Types
# ============================================================================


@pytest.mark.asyncio
async def test_generate_answer_async_spatial_query(
    synthesizer, mock_search_engine, mock_ai_client, mock_critic
):
    """Test handling of spatial anatomical queries"""
    # Update mock to return SPATIAL query type
    retrieval_result = mock_search_engine.retrieve_for_topic.return_value
    retrieval_result.query_type = QueryType.SPATIAL

    result = await synthesizer.generate_answer_async(
        "Where is the facial nerve in relation to the vestibular nerve?"
    )

    # Should handle spatial queries correctly
    assert "answer" in result
    mock_search_engine.retrieve_for_topic.assert_called_once()


@pytest.mark.asyncio
async def test_generate_answer_async_procedural_query(
    synthesizer, mock_search_engine, mock_ai_client, mock_critic
):
    """Test handling of procedural step-by-step queries"""
    # Update mock to return PROCEDURAL query type
    retrieval_result = mock_search_engine.retrieve_for_topic.return_value
    retrieval_result.query_type = QueryType.PROCEDURAL

    result = await synthesizer.generate_answer_async(
        "What are the steps for translabyrinthine approach?"
    )

    # Should handle procedural queries correctly
    assert "answer" in result
    mock_search_engine.retrieve_for_topic.assert_called_once()


# ============================================================================
# Test Cases: Synchronous generate_answer() Method
# ============================================================================


def test_generate_answer_sync_success(mock_search_engine, mock_critic):
    """Test synchronous answer generation"""
    # Create synchronous mock AI client
    mock_ai_client = MagicMock()
    mock_ai_client.get_embedding.return_value = [0.1] * 384
    mock_ai_client.synthesize.side_effect = [
        "synonyms here",
        "Synchronous answer. [Test Source 1, p.1]",
    ]

    # Create synchronous mock critic
    mock_critic_sync = MagicMock()
    mock_critic_sync.check_safety.return_value = {
        "safe": True,
        "issues": [],
        "risk_level": "low",
    }

    synthesizer = DeepDxSynthesizer(
        search_engine=mock_search_engine,
        ai_client=mock_ai_client,
        critic=mock_critic_sync,
    )

    result = synthesizer.generate_answer("Synchronous query")

    # Verify answer structure
    assert "answer" in result
    assert "sources" in result
    assert len(result["answer"]) > 0

    # Verify sync methods were called
    mock_ai_client.get_embedding.assert_called_once()
    mock_critic_sync.check_safety.assert_called_once()


# ============================================================================
# Test Cases: Complex Integration Scenarios
# ============================================================================


@pytest.mark.asyncio
async def test_generate_answer_async_with_images(
    synthesizer, mock_search_engine, mock_ai_client, mock_critic
):
    """Test that images from retrieval are included in results"""
    result = await synthesizer.generate_answer_async("Query with images")

    # Verify images are in result
    assert "images" in result
    assert len(result["images"]) > 0
    assert result["images"][0].caption == "House-Brackmann Scale Diagram"


@pytest.mark.asyncio
async def test_generate_answer_async_deduplication(
    synthesizer, mock_search_engine, mock_ai_client, mock_critic
):
    """Test that duplicate sources are deduplicated"""
    # Create multiple chunks from same source
    chunk1 = Chunk(
        id="chunk_1",
        source_id="source_1",
        source_title="Same Source",
        section_title="Section 1",
        content="Content 1",
        chunk_type=ChunkType.NARRATIVE,
        page_start=1,
        page_end=1,
        embedding=[0.1] * 384,
    )

    chunk2 = Chunk(
        id="chunk_2",
        source_id="source_1",  # Same source
        source_title="Same Source",
        section_title="Section 2",
        content="Content 2",
        chunk_type=ChunkType.NARRATIVE,
        page_start=2,
        page_end=2,
        embedding=[0.2] * 384,
    )

    mock_search_engine.retrieve_for_topic.return_value.results = [
        PrecisionResult(chunk=chunk1, dense_score=0.9, final_score=0.9),
        PrecisionResult(chunk=chunk2, dense_score=0.85, final_score=0.85),
    ]

    result = await synthesizer.generate_answer_async("Test query")

    # Should deduplicate sources (only one "Same Source")
    assert len(result["sources"]) == 1
    assert "Same Source" in result["sources"]


# ============================================================================
# Test Cases: Error Resilience
# ============================================================================


@pytest.mark.asyncio
async def test_generate_answer_async_answer_synthesis_failure(
    mock_search_engine, mock_critic
):
    """Test handling when answer synthesis API call fails"""
    # Mock AI client where synthesis fails
    mock_ai_client = AsyncMock()
    mock_ai_client.get_embedding.return_value = [0.1] * 384
    mock_ai_client.synthesize.side_effect = [
        "expansion works",  # Expansion succeeds
        httpx.ConnectError("Cannot connect to API"),  # Answer synthesis fails
    ]

    synthesizer = DeepDxSynthesizer(
        search_engine=mock_search_engine,
        ai_client=mock_ai_client,
        critic=mock_critic,
    )

    # Should raise the exception (let retry logic at AIClient level handle it)
    with pytest.raises(httpx.ConnectError):
        await synthesizer.generate_answer_async("Test query")
