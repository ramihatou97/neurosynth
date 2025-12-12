import logging
import sys
from pathlib import Path

# Ensure src is in path
root_dir = Path(__file__).parent.parent
sys.path.append(str(root_dir))

from qdrant_client import QdrantClient

from src.config import settings
from src.index.database import Database
from src.index.unified_search import UnifiedSearchEngine

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(message)s")
logger = logging.getLogger("SystemVerifier")


def verify_system_health():
    logger.info("🏥 Starting Full System Health Check...")
    errors = []

    # 1. Database Check
    try:
        db = Database()
        img_count = db.count_images()
        chunk_count = db.count_chunks()
        logger.info(f"✅ SQLite Database: {img_count} images, {chunk_count} chunks")
    except Exception as e:
        logger.error(f"❌ SQLite Database connection failed: {e}")
        errors.append("SQLite Failure")

    # 2. Qdrant Check
    try:
        qdrant = QdrantClient(url=settings.qdrant_url)
        col_name = "neurosurgical_figures_hybrid"
        if qdrant.collection_exists(col_name):
            count = qdrant.count(col_name).count
            logger.info(f"✅ Qdrant Collection '{col_name}': {count} vectors")
            if count == 0:
                logger.warning("⚠️ Qdrant is empty! (Did repair script run?)")
        else:
            logger.error(f"❌ Qdrant Collection '{col_name}' MISSING")
            errors.append("Qdrant Collection Missing")
    except Exception as e:
        logger.error(f"❌ Qdrant Connection failed: {e}")
        errors.append("Qdrant Connection Failure")

    # 3. Search Engine Check
    try:
        # DB already initialized above
        searcher = UnifiedSearchEngine(db=db)

        # Test Text Search
        res_text = searcher.search("brain tumor", top_k=1)
        if res_text.chunks:
            logger.info("✅ Text Search (BM25+Rerank) functional")
        else:
            logger.warning(
                "⚠️ Text Search returned no results (Index might be building)"
            )

        # Test Visual Search
        # We can use the same result object as it contains both, or run a specific visual query
        res_vis = searcher.search("circle of willis anomaly", top_k=1)
        if res_vis.images:
            logger.info("✅ Visual Search functional")
        else:
            logger.warning("⚠️ Visual Search returned no results")

    except Exception as e:
        logger.error(f"❌ Search Engine critical failure: {e}")
        errors.append(f"Search Engine Crash: {e}")

    logger.info("-" * 30)
    if not errors:
        logger.info("🟢 SYSTEM HEALTHY - All checks passed.")
        sys.exit(0)
    else:
        logger.error(f"🔴 SYSTEM UNHEALTHY - Errors: {errors}")
        sys.exit(1)


if __name__ == "__main__":
    verify_system_health()
