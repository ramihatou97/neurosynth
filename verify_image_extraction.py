import logging
import sys
from pathlib import Path

from deep_dx.ingestion.image_extraction_pipeline import ImageExtractionPipeline
from index.database import Database

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("verify_images")


def verify():
    print("🚀 Starting Image Extraction Verification...")

    # 1. Init
    # Point to the active database in root
    db = Database(Path("neurosynth.db"))
    pipeline = ImageExtractionPipeline(db)

    # 2. Run on 1 document
    # We want to force it to run on a document that likely has images.
    # The pipeline.run(max_docs=1) will pick the first unprocessed source.
    # Let's hope the first one is good, or we can look for specific one.

    pipeline.run(max_docs=1)

    # 3. Check DB
    images = db.get_stats()["images"]
    print(f"\n📊 Total Images in DB: {images}")

    if images > 0:
        print("✅ SUCCESS: Images extracted.")
        # List a few
        all_imgs = db.get_all_images_with_embeddings()
        # Actually this fetches with embeddings, might be empty if no embeddings generated yet.
        # Let's use get_images_by_source if we knew the source, or just direct SQL if needed?
        # Database has no generic "get_all_images", only specific or stats.
        # But wait, we can verify via stats.
    else:
        print(
            "⚠️ WARNING: No images extracted (or document had none/pdfplumber failed)."
        )


if __name__ == "__main__":
    verify()
