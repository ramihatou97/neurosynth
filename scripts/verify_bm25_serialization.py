import json
import logging
import sys
from dataclasses import dataclass
from pathlib import Path

# Ensure src is in path
root_dir = Path(__file__).parent.parent
sys.path.append(str(root_dir))

from src.deep_dx.retrieval.bm25 import BM25Retriever

# Import actual Chunk from models
from src.models import Chunk, ChunkType

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("BM25Verifier")


def verify_bm25_serialization():
    logger.info("🧪 Verifying BM25 Serialization...")

    # Create Dummy Data
    chunk = Chunk(
        id="chunk_1",
        source_id="doc_1",
        source_title="Test Doc",
        section_title="Intro",
        content="This is a test document.",
        chunk_type=ChunkType.NARRATIVE,
        page_start=1,
        page_end=1,
        embedding=[0.1, 0.2],
    )

    # BM25 expects dicts with 'content' and 'id' and optionally 'chunk_obj'
    doc = {"content": chunk.content, "id": chunk.id, "chunk_obj": chunk}

    try:
        # Build Index
        retriever = BM25Retriever(chunks=[doc])
        logger.info(f"Built index with {retriever.get_document_count()} docs")

        # Save
        temp_path = Path("/tmp/bm25_test_index.json")
        success = retriever.save(temp_path)

        if success:
            logger.info(f"✅ Saved index to {temp_path}")
        else:
            logger.error("❌ Failed to save index")
            sys.exit(1)

        # Verify JSON content manually (check for dataclass dict conversion)
        with open(temp_path) as f:
            data = json.load(f)
            first_chunk = data["chunks"][0]
            if "chunk_obj" in first_chunk and isinstance(
                first_chunk["chunk_obj"], dict
            ):
                logger.info("✅ Chunk successfully serialized to dict in JSON")
                if first_chunk["chunk_obj"]["id"] == "chunk_1":
                    logger.info("✅ content match")
            else:
                logger.error("❌ Chunk serialization format incorrect")
                sys.exit(1)

        # Load
        loaded_retriever = BM25Retriever.load(temp_path)
        if loaded_retriever:
            logger.info("✅ Loaded index successfully")

            # Verify Object Reconstruction
            loaded_chunk_obj = loaded_retriever.chunks[0].get("chunk_obj")
            if isinstance(loaded_chunk_obj, Chunk):
                logger.info("✅ Chunk object successfully reconstructed to dataclass")
                logger.info(f"   Chunk ID: {loaded_chunk_obj.id}")
            else:
                logger.error(
                    f"❌ Chunk object failed to reconstruct (Type: {type(loaded_chunk_obj)})"
                )
                sys.exit(1)

        else:
            logger.error("❌ Failed to load index")
            sys.exit(1)

        # Cleanup
        if temp_path.exists():
            temp_path.unlink()

    except Exception as e:
        logger.error(f"❌ Verification Failed: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    verify_bm25_serialization()
