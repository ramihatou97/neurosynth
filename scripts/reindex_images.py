import logging
import sys
from pathlib import Path
from uuid import uuid4

from tqdm import tqdm

# Setup paths
project_root = Path(__file__).resolve().parent.parent
sys.path.append(str(project_root))  # Add root for 'src' imports
sys.path.append(str(project_root / "src"))  # Add src for direct imports if needed

from src.config import settings
from src.index.database import Database
from src.neurosynth.ai.biomed_searcher import BiomedCLIPSearcher

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("ImageReindexer")


def reindex_images(dry_run: bool = False, force_all: bool = False):
    """
    Re-index images: generate embeddings and upsert to Qdrant.

    Args:
        dry_run: If True, only simulate actions.
        force_all: If True, process ALL images, not just those without embeddings.
    """
    # 1. Initialize Components
    logger.info("Initializing Database...")
    db = Database()

    logger.info("Initializing BiomedCLIP Searcher...")
    try:
        embedder = BiomedCLIPSearcher()
    except Exception as e:
        logger.error(f"Failed to load BiomedCLIP: {e}")
        return

    # Check Qdrant
    try:
        from qdrant_client import QdrantClient
        from qdrant_client.models import Distance, PointStruct, VectorParams

        if settings.qdrant_path:
            q_client = QdrantClient(path=str(settings.qdrant_path))
        else:
            q_client = QdrantClient(host="localhost", port=6333)

        collection_name = "neurosurgical_figures_hybrid"

        # Ensure collection exists
        if not dry_run:
            collections = q_client.get_collections().collections
            exists = any(c.name == collection_name for c in collections)
            if not exists:
                logger.info(f"Creating Qdrant collection: {collection_name}")
                q_client.create_collection(
                    collection_name=collection_name,
                    vectors_config={
                        "biomed": VectorParams(size=512, distance=Distance.COSINE)
                    },
                )
    except ImportError:
        logger.error("qdrant-client not installed.")
        return
    except Exception as e:
        logger.error(f"Qdrant connection failed: {e}")
        return

    # 2. Fetch Images
    if force_all:
        logger.info("Fetching ALL images from database...")
        images = db.get_all_images()
    else:
        logger.info("Fetching images without embeddings...")
        images = db.get_images_without_embeddings()

    if not images:
        logger.info("No images found to process.")
        return

    logger.info(f"Found {len(images)} images to process.")

    # 3. Process Images
    success_count = 0
    fail_count = 0

    batch_size = 8

    for i in tqdm(range(0, len(images), batch_size)):
        batch = images[i : i + batch_size]

        # Prepare valid paths
        valid_batch = []
        valid_paths = []

        for img in batch:
            if img.file_path.exists():
                valid_batch.append(img)
                valid_paths.append(str(img.file_path))
            else:
                logger.warning(f"File not found: {img.file_path}")
                fail_count += 1

        if not valid_batch:
            continue

        if dry_run:
            logger.info(f"[DRY RUN] Would process batch of {len(valid_batch)} images")
            continue

        try:
            # Embed
            embeddings = embedder.embed_image(valid_paths)

            points = []

            for img, emb in zip(valid_batch, embeddings):
                # Update SQLite
                db.update_image_embedding(img.id, emb.tolist())

                # Prepare Qdrant point
                payload = {
                    "filename": img.id,
                    "source_pdf": img.source_id,
                    "page_num": img.page,
                    "path": str(img.file_path),
                    "caption": img.caption,
                    "context": img.surrounding_text,
                    "modality": img.modality,
                    "image_type": (
                        img.image_type.value
                        if hasattr(img.image_type, "value")
                        else str(img.image_type)
                    ),
                    "detected_regions": img.detected_regions,
                }

                points.append(
                    PointStruct(
                        id=str(uuid4()),
                        vector={"biomed": emb.tolist()},
                        payload=payload,
                    )
                )

                success_count += 1

            # Upsert to Qdrant
            if points:
                q_client.upsert(collection_name=collection_name, points=points)

        except Exception as e:
            logger.error(f"Batch failed: {e}")
            fail_count += len(valid_batch)

    logger.info(f"Processing complete. Success: {success_count}, Failed: {fail_count}")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Re-index images into Qdrant")
    parser.add_argument(
        "--dry-run", action="store_true", help="Simulate without changes"
    )
    parser.add_argument(
        "--force", action="store_true", help="Process all images, even if valid"
    )
    args = parser.parse_args()

    reindex_images(dry_run=args.dry_run, force_all=args.force)
