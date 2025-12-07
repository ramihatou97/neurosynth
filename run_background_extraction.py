import logging
import sys
import time
from pathlib import Path

from deep_dx.ingestion.image_extraction_pipeline import ImageExtractionPipeline
from index.database import Database

# Setup basic logging to file
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("background_extraction.log"),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger("background_runner")


def run_forever():
    """Run the pipeline in a loop until done or stopped"""
    logger.info("🚀 Starting Background Image Extraction Service")
    logger.info("ℹ️  Will pause if '.app_activity' is updated within 60s")

    db = Database(Path("neurosynth.db"))
    pipeline = ImageExtractionPipeline(db)

    try:
        # Run without limit (max_docs=None) to process full library
        pipeline.run(max_docs=None)
        logger.info("✅ Full Library Extraction Complete!")
    except KeyboardInterrupt:
        logger.info("🛑 Service stopped by user.")
    except Exception as e:
        logger.error(f"❌ Service crashed: {e}")


if __name__ == "__main__":
    run_forever()
