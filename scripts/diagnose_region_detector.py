import logging
import sys
from pathlib import Path

import numpy as np

# Ensure src is in path
root_dir = Path(__file__).parent.parent
sys.path.append(str(root_dir))

from src.config import settings
from src.index.database import Database
from src.neurosynth.enhancements.visual_region_detector import VisualRegionDetector

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("RegionDiagnose")


def diagnose():
    logger.info("🔬 Diagnosing Visual Region Detector...")

    # 1. Initialize Detector
    detector = VisualRegionDetector(
        similarity_threshold=0.0
    )  # Set to 0 to see ALL scores
    success = detector.initialize()
    if not success:
        logger.error("Failed to init detector")
        return

    # 2. Get a sample image from DB
    db = Database()
    images = db.get_all_images()
    if not images:
        logger.error("No images in DB to test with")
        return

    # Pick a few diverse images
    test_images = images[:5]

    for img in test_images:
        if not img.file_path.exists():
            continue

        logger.info(f"\n📸 Testing Image: {img.file_path.name}")
        logger.info(f"   Caption: {img.caption[:50]}...")

        # Detect
        # We can pass the pre-computed embedding from DB if available, else re-embed
        embedding = None
        if img.embedding:
            embedding = np.array(img.embedding)

        results = detector.detect_regions(
            image_path=img.file_path, image_embedding=embedding
        )

        # Print top 5 matches with scores
        for i, match in enumerate(results[:5]):
            logger.info(
                f"   {i+1}. {match.region_name}: {match.similarity:.4f} ({match.source})"
            )


if __name__ == "__main__":
    diagnose()
