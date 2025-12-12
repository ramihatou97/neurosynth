import logging
import sys
import uuid
from pathlib import Path

# Ensure src is in path
root_dir = Path(__file__).parent.parent
sys.path.append(str(root_dir))

from qdrant_client import QdrantClient
from qdrant_client.models import Distance, PointStruct, VectorParams

from src.config import settings
from src.index.database import Database

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("QdrantRepair")

NAMESPACE_NEUROSYNTH = uuid.uuid5(uuid.NAMESPACE_DNS, "neurosynth.org")


def get_uuid(text_id: str) -> str:
    """Hash string ID to a valid UUID string for Qdrant validation."""
    return str(uuid.uuid5(NAMESPACE_NEUROSYNTH, str(text_id)))


def repair_qdrant_images():
    logger.info("🔧 Starting Qdrant Image Sync Repair...")

    # Initialize Database
    db = Database()

    # Initialize Qdrant
    try:
        qdrant = QdrantClient(url=settings.qdrant_url)
        collection_name = (
            settings.image_qdrant_collection
        )  # "neurosurgical_figures_hybrid"

        # Ensure collection exists
        if not qdrant.collection_exists(collection_name):
            logger.info(f"Creating Qdrant collection: {collection_name}")
            qdrant.create_collection(
                collection_name=collection_name,
                vectors_config=VectorParams(size=512, distance=Distance.COSINE),
            )
        else:
            logger.info(f"Collection {collection_name} exists.")

    except Exception as e:
        logger.error(f"❌ Failed to connect to Qdrant: {e}")
        return

    # Fetch all images with embeddings from SQLite
    logger.info("Fetching images from SQLite...")
    images_with_embeds = db.get_all_images_with_embeddings()
    logger.info(f"Found {len(images_with_embeds)} images with embeddings in SQLite.")

    if not images_with_embeds:
        logger.warning("No images found to sync!")
        return

    # Batch Upsert
    batch_size = 100
    points = []
    synced_count = 0

    for img, embedding in images_with_embeds:
        try:
            # Construct Point
            # We must match the payload logic from run_ingestion.py
            point = PointStruct(
                id=get_uuid(img.id),
                vector=embedding,
                payload={
                    "source_pdf": img.source_id,
                    "page_num": img.page,
                    "path": str(img.file_path),
                    "caption": img.caption,
                    "context": (
                        img.surrounding_text[:1000] if img.surrounding_text else ""
                    ),
                    "modality": "unknown",
                    "image_type": img.image_type.value,
                    # "detected_regions": [] # Not stored in SQLite explicitly in get_all_images default
                },
            )
            points.append(point)

            if len(points) >= batch_size:
                qdrant.upsert(collection_name=collection_name, points=points)
                synced_count += len(points)
                logger.info(f"Synced {synced_count} records...")
                points = []

        except Exception as e:
            logger.error(f"Error preparing point for {img.id}: {e}")

    # Final batch
    if points:
        try:
            qdrant.upsert(collection_name=collection_name, points=points)
            synced_count += len(points)
            logger.info(f"Synced {synced_count} records...")
        except Exception as e:
            logger.error(f"Error upserting final batch: {e}")

    logger.info(
        f"✅ Repair Complete! Total synced: {synced_count}/{len(images_with_embeds)}"
    )


if __name__ == "__main__":
    repair_qdrant_images()
