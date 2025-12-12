import asyncio
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

# Adjust path
sys.path.append(str(Path.cwd()))

# --- MOCKS ---
sys.modules["rich"] = MagicMock()
sys.modules["rich.console"] = MagicMock()
sys.modules["structlog"] = MagicMock()
sys.modules["qdrant_client"] = MagicMock()
sys.modules["voyageai"] = MagicMock()
sys.modules["anthropic"] = MagicMock()
sys.modules["cv2"] = MagicMock()
sys.modules["PIL"] = MagicMock()
# We need real networkx for reasoning verification if possible, or mock it carefully
try:
    import networkx as nx
except ImportError:
    # If missing, we mock it, but then reasoning logic test will be artificial
    mock_nx = MagicMock()
    sys.modules["networkx"] = mock_nx
    sys.modules["networkx.readwrite"] = MagicMock()

# Mock Config & Pydantic
sys.modules["pydantic_settings"] = MagicMock()
sys.modules["pydantic"] = MagicMock()

# Pre-mock src.config to avoid import errors
mock_config = MagicMock()
mock_config.settings = MagicMock()
mock_config.settings.enable_raptor = True
mock_config.settings.enable_graph = True
mock_config.settings.enable_graph = True
sys.modules["src.config"] = mock_config
sys.modules["neurosynth.config"] = mock_config

# Mock src.models to avoid Pydantic issues
mock_models = MagicMock()


class MockChunk:
    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)


mock_models.Chunk = MockChunk
mock_models.Section = MagicMock()
sys.modules["src.models"] = mock_models

import logging

# Setup Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("Phase6Verifier")


async def test_async_manager():
    logger.info("--- Testing AsyncIngestionManager ---")

    # 1. Setup Mock Bridge
    mock_bridge = MagicMock()
    mock_bridge.raptor = MagicMock()
    mock_bridge.raptor.generate_tree = AsyncMock(return_value=["SummaryChunk"])
    mock_bridge.embed_chunks = AsyncMock()
    mock_bridge.push_to_qdrant = AsyncMock()
    mock_bridge._target_db = MagicMock()

    # 2. Init Manager
    from src.index.async_manager import AsyncIngestionManager

    manager = AsyncIngestionManager(mock_bridge)

    # 3. Start Worker (Background)
    worker = asyncio.create_task(manager.start_worker())

    # 4. Submit Job
    mock_source = MagicMock()
    mock_source.id = "test_source"
    mock_source.title = "Test Source"

    await manager.submit_job("RAPTOR", mock_source, ["Chunk1", "Chunk2"])

    # 5. Wait for processing (allow loop to run)
    await asyncio.sleep(0.1)

    # 6. Verify processing happened
    mock_bridge.raptor.generate_tree.assert_called_once()
    mock_bridge.embed_chunks.assert_called_once()

    logger.info("✅ Async RAPTOR Job processed successfully")

    # cleanup
    manager._running = False
    worker.cancel()
    try:
        await worker
    except:
        pass


async def test_reasoning_mode():
    logger.info("\n--- Testing SearchMode.REASONING ---")

    # 1. Setup Mock DB & Graph
    mock_db = MagicMock()

    # Create a real small graph for testing if NX available
    import networkx as nx

    if isinstance(nx, MagicMock):
        # Configure Mock Graph
        graph = MagicMock()
        graph.nodes.return_value = ["Tumor", "Brain", "cortex"]

        # Determine neighbors logic
        def get_neighbors(n):
            if n == "Tumor":
                return ["Brain"]
            if n == "Brain":
                return ["cortex"]
            return []

        graph.neighbors.side_effect = get_neighbors

        # Edges and attributes
        # graph.edges[u, v] access via __getitem__
        graph.edges = MagicMock()

        def get_edge_data(pair):
            u, v = pair
            if u == "Tumor" and v == "Brain":
                return {"relation": "located_in"}
            if u == "Brain" and v == "cortex":
                return {"relation": "part_of"}
            return {}

        graph.edges.__getitem__.side_effect = get_edge_data

    else:
        graph = nx.DiGraph()
        graph.add_edge("Brain", "cortex", relation="part_of")
        graph.add_edge("Tumor", "Brain", relation="located_in")

    # Verify Graph Mock Locally
    logger.info(f"Verified Graph Mock nodes(): {graph.nodes()}")
    if not list(graph.nodes()):
        logger.error("Graph mock returns empty nodes!")

    # 2. Init Search Engine
    # We need to bypass the __init__ logic that tries to load from file
    # so we'll patch checking dependencies

    from src.index.unified_search import SearchMode, UnifiedSearchEngine

    engine = UnifiedSearchEngine(mock_db)
    logger.info(f"DEBUG Script: Engine ID={id(engine)}")
    logger.info(f"DEBUG Script: Engine Graph (Init)={engine.graph}")

    engine.graph = graph  # Inject graph manually
    logger.info(f"DEBUG Script: Engine Graph (After Set)={engine.graph}")
    logger.info(f"DEBUG Script: Mock Graph ID={id(graph)}")

    # 3. Execute Search
    # We mock qdrant search results
    mock_res = MagicMock()
    mock_res.chunk.id = "c1"
    mock_res.score = 0.9
    engine.qdrant = MagicMock()
    engine.qdrant.search.return_value = [mock_res]

    result = engine.search("tumor in brain", mode=SearchMode.REASONING)

    # 4. Verify Context
    logger.info(f"Graph Context found: {result.graph_context}")

    expected_snippets = ["Brain --[part_of]--> cortex", "Tumor --[located_in]--> Brain"]
    # Logic in engine is simple lookup. "tumor" and "brain" are in query.
    # So it should find nodes "Tumor" and "Brain".
    # And their neighbors.
    # Tumor -> Brain (relation: located_in)
    # Brain -> cortex (relation: part_of)

    if len(result.graph_context) > 0:
        logger.info("✅ Reasoning Mode extracted graph context")
    else:
        logger.error("❌ Reasoning Mode failed to extract context")


async def run_verification():
    print("🧪 Verifying Phase 6: Deep Integration")
    await test_async_manager()
    await test_reasoning_mode()


if __name__ == "__main__":
    asyncio.run(run_verification())
