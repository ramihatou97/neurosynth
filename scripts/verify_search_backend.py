import logging
import sys
from pathlib import Path

# Add src to path
root_dir = Path(__file__).parent.parent
sys.path.append(str(root_dir))

from src.index.database import Database
from src.index.unified_search import SearchMode, UnifiedSearchEngine

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("SearchVerifier")


def verify_search():
    logger.info("🧪 Verifying Search Backend...")

    try:
        # Initialize Engine with Database
        db = Database()
        engine = UnifiedSearchEngine(db=db)

        # Test Query
        query = "brain tumor"
        logger.info(f"🔎 Curernt Query: '{query}'")

        # Search in DEEP mode (uses Qdrant + ColBERT/BiomedCLIP)
        results = engine.search(query=query, mode=SearchMode.DEEP, top_k=5)

        # Access results object
        logger.info(
            f"✅ Found {results.total_chunks} text chunks and {results.total_images} images"
        )

        if results.warnings:
            logger.warning(f"⚠️ Search Warnings: {results.warnings}")

        if results.total_chunks == 0 and results.total_images == 0:
            logger.error("❌ No results found! Index might be empty.")
            sys.exit(1)

        logger.info("--- Text Results ---")
        for i, res in enumerate(results.chunks[:3]):
            logger.info(
                f"  {i+1}. [{res.score:.2f}] {res.chunk.source_title} - {res.chunk.section_title}"
            )

        logger.info("--- Image Results ---")
        for i, img in enumerate(results.images[:3]):
            logger.info(f"  {i+1}. {img.caption[:50]}... ({img.source_id})")

        logger.info("✨ Search Verification Passed!")

    except Exception as e:
        logger.error(f"❌ Search Verification Failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    verify_search()
