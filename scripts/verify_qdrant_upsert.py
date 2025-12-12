import logging
import sys
import uuid
from pathlib import Path

from qdrant_client import QdrantClient
from qdrant_client.models import Distance, PointStruct, VectorParams

# Ensure src is in path
root_dir = Path(__file__).parent.parent
sys.path.append(str(root_dir))

from src.config import settings

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("QdrantVerifier")

NAMESPACE_NEUROSYNTH = uuid.uuid5(uuid.NAMESPACE_DNS, "neurosynth.org")


def get_uuid(text_id: str) -> str:
    return str(uuid.uuid5(NAMESPACE_NEUROSYNTH, str(text_id)))


def verify_upsert():
    logger.info("🧪 Verifying Qdrant Upsert with UUIDs...")

    collection_name = "test_uuid_support"

    try:
        # Connect
        client = QdrantClient(url=settings.qdrant_url)
        logger.info(f"Connected to {settings.qdrant_url}")

        # Recreate collection
        client.recreate_collection(
            collection_name=collection_name,
            vectors_config=VectorParams(size=4, distance=Distance.COSINE),
        )

        # Create Test Point
        original_id = "super_complex_filename_with_special_chars-1.png"
        hashed_id = get_uuid(original_id)
        logger.info(f"Original ID: {original_id}")
        logger.info(f"Hashed UUID: {hashed_id}")

        point = PointStruct(
            id=hashed_id,
            vector=[0.1, 0.2, 0.3, 0.4],
            payload={"original_id": original_id},
        )

        # Upsert
        client.upsert(collection_name=collection_name, points=[point])

        logger.info("✅ Upsert successful!")

        # Retrieve
        retrieved = client.retrieve(collection_name=collection_name, ids=[hashed_id])

        if retrieved and retrieved[0].payload["original_id"] == original_id:
            logger.info("✅ Retrieval successful and payload matches!")
        else:
            logger.error("❌ Retrieval failed or payload mismatch")
            sys.exit(1)

        # Cleanup
        client.delete_collection(collection_name)

    except Exception as e:
        logger.error(f"❌ Verification Failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    verify_upsert()
