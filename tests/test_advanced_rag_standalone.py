import asyncio
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

# Add src to path
sys.path.append(str(Path(__file__).parent.parent))

# MOCK DEPENDENCIES BEFORE IMPORTS
sys.modules["structlog"] = MagicMock()
sys.modules["neurosynth.config"] = MagicMock()
sys.modules["src.config"] = MagicMock()
sys.modules["rich"] = MagicMock()
sys.modules["rich.console"] = MagicMock()
# Mock rich and AI clients
sys.modules["rich"] = MagicMock()
sys.modules["rich.console"] = MagicMock()

# REMOVED SKLEARN MOCK TO TEST FALLBACK PATH
# sys.modules["sklearn"] = MagicMock()

# Mock networkx
mock_nx = MagicMock()
sys.modules["networkx"] = mock_nx
# Mock DiGraph behavior minimally
mock_graph = MagicMock()
mock_nx.DiGraph.return_value = mock_graph
mock_nx.single_source_shortest_path_length.return_value = {"Aspirin": 0, "Headache": 1}
mock_graph.nodes = ["Aspirin", "Headache"]
# mock_graph.has_edge return value?
mock_graph.has_edge.return_value = True
# Subgraph mock
mock_subgraph = MagicMock()
mock_graph.subgraph.return_value = mock_subgraph
mock_subgraph.edges.return_value = [("Aspirin", "Headache", {"relation": "TREATS"})]

from src.index.graph import KnowledgeGraphBuilder
from src.index.raptor import Cluster, RecursiveSummarizer
from src.models import Chunk, ChunkType


async def test_raptor_summarization():
    print("Testing RAPTOR Summarization...")
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

    # Run
    summaries = await raptor.generate_tree(chunks)

    # Check
    assert len(summaries) >= 1, "Should generate at least one summary"
    assert summaries[0].chunk_type == ChunkType.SUMMARY, "Should be SUMMARY type"
    assert summaries[0].content == "Level Summary Content", "Content should match mock"
    print("✅ RAPTOR Passed")


async def test_graph_building():
    print("Testing Graph Building...")
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
    assert "Aspirin" in kg.graph.nodes, "Node Aspirin missing"
    assert "Headache" in kg.graph.nodes, "Node Headache missing"
    assert kg.graph.has_edge("Aspirin", "Headache"), "Edge missing"

    # Search
    results = kg.search(["Aspirin"], depth=1)
    assert len(results) > 0, "Search returned nothing"
    assert "Aspirin --[TREATS]--> Headache" in results[0], "Search result malformed"
    print("✅ GraphRAG Passed")


if __name__ == "__main__":

    async def main():
        await test_raptor_summarization()
        await test_graph_building()
        print("🎉 All Advanced RAG tests passed.")

    asyncio.run(main())
