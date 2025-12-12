import os
import sys

sys.path.append(os.getcwd())

import asyncio
from unittest.mock import AsyncMock, MagicMock

from src.index.search import RetrievalResult, SearchEngine, SearchResult

from src.index.database import Database
from src.models import Chunk, ExtractedImage, ImageType, SourceMetadata
from src.synthesize.engine import SynthesisEngine


async def test_engine_respects_source_filters():
    # 1. Setup Mocks
    mock_db = MagicMock(spec=Database)
    mock_search = MagicMock(spec=SearchEngine)
    mock_ai = AsyncMock()

    # Mock retrieval result
    mock_chunk = MagicMock(spec=Chunk)
    mock_chunk.source_id = "target_source_123"
    mock_chunk.source_title = "Target Source"
    mock_chunk.content = "Relevant content"
    mock_chunk.page_start = 1

    # Create the search result object
    search_result = SearchResult(chunk=mock_chunk, score=0.9)

    mock_retrieval = RetrievalResult(
        chunks=[search_result],
        images=[],
        sources_used={"target_source_123"},
        total_chunks=1,
        total_images=0,
    )

    # Configure mock search to return our result
    mock_search.retrieve_for_topic.return_value = mock_retrieval

    # Mock prompts rendering
    mock_ai.get_embedding.return_value = [0.1, 0.2, 0.3]
    mock_ai.synthesize.return_value = "Generated section content."

    # Initialize Engine
    engine = SynthesisEngine(mock_db, mock_search, mock_ai)

    # 2. Execute
    target_source_ids = ["target_source_123"]
    result = await engine.synthesize_section_async(
        topic="Test Topic",
        section_title="Test Section",
        ai_client=mock_ai,
        source_ids=target_source_ids,
    )

    # 3. Verify
    # Check that retrieve_for_topic was called with source_ids
    mock_search.retrieve_for_topic.assert_called_once()
    call_args = mock_search.retrieve_for_topic.call_args

    print("Call kwargs:", call_args.kwargs)

    assert call_args.kwargs["source_ids"] == target_source_ids, "source_ids mismatch"
    assert call_args.kwargs["topic"] == "Test Topic", "topic mismatch"

    print("Verification Successful: source_ids were passed correctly.")


if __name__ == "__main__":
    asyncio.run(test_engine_respects_source_filters())
