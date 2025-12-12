import asyncio
import sys

# Add src to path
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

sys.path.append(str(Path(__file__).parent.parent))

from src.index.graph import KnowledgeGraphBuilder
from src.index.raptor import Cluster, RecursiveSummarizer
from src.models import Chunk, ChunkType


@pytest.mark.asyncio
async def test_raptor_summarization():
    # Setup
    mock_ai = MagicMock()
    # Mock generate to return a summary string
    mock_ai.generate = AsyncMock(return_value="Level Summary Content")

    chunks = [
        Chunk(
            id="1",
            content="Text A",
            chunk_type=ChunkType.NARRATIVE,
            source_id="s1",
            source_title="T1",
            section_title="S1",
            page_start=1,
            page_end=1,
            embedding=[0.1, 0.2],
        ),
        Chunk(
            id="2",
            content="Text B",
            chunk_type=ChunkType.NARRATIVE,
            source_id="s1",
            source_title="T1",
            section_title="S1",
            page_start=1,
            page_end=1,
            embedding=[0.1, 0.3],
        ),
    ]

    raptor = RecursiveSummarizer(ai_client=mock_ai, database=MagicMock())
    # Force single cluster for test simple case
    raptor.target_levels = 1

    # Mock clustering to return one cluster
    # We can patch _cluster_chunks but here let's trust the naive logic if sklearn missing

    # Run
    summaries = await raptor.generate_tree(chunks)

    # Check
    assert len(summaries) >= 1
    assert summaries[0].chunk_type == ChunkType.SUMMARY
    assert summaries[0].content == "Level Summary Content"
    assert "Level 1" in summaries[0].section_title


@pytest.mark.asyncio
async def test_graph_building():
    # Setup
    mock_ai = MagicMock()
    mock_ai.generate = AsyncMock(
        return_value='{"triples": [{"head": "Aspirin", "relation": "TREATS", "tail": "Headache", "head_type": "Drug", "tail_type": "Symptom"}]}'
    )

    kg = KnowledgeGraphBuilder(ai_client=mock_ai)
    chunk = Chunk(
        id="1",
        content="Aspirin treats headache.",
        chunk_type=ChunkType.NARRATIVE,
        source_id="s1",
        source_title="T1",
        section_title="S1",
        page_start=1,
        page_end=1,
    )

    # Run
    await kg.process_chunks([chunk])

    # Check
    assert "Aspirin" in kg.graph.nodes
    assert "Headache" in kg.graph.nodes
    assert kg.graph.has_edge("Aspirin", "Headache")

    # Search
    results = kg.search(["Aspirin"], depth=1)
    assert len(results) > 0
    assert "Aspirin --[TREATS]--> Headache" in results[0]
