"""
Image Extraction Pipeline
=========================
Systematic extraction of visual content from the NeuroLi PDF Library.
Features:
- State persistence (Pause/Resume)
- Smart Filtering (removes icons/artifacts)
- Metadata Enrichment (Captions, Source linkage)
- Direct Database Storage
"""

import hashlib
import json
import logging
import time
import uuid
from pathlib import Path
from typing import Dict, List, Optional

# 3rd party
try:
    import pdfplumber
except ImportError:
    pdfplumber = None

from index.database import Database
from models import ExtractedImage, ImageType, SourceMetadata

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("image_pipeline")

STATE_FILE = Path("extraction_state.json")
ASSETS_DIR = Path("assets/extracted_images")


class ImageExtractionPipeline:
    def __init__(self, db: Database):
        self.db = db
        self.state = self._load_state()
        ASSETS_DIR.mkdir(parents=True, exist_ok=True)

        if not pdfplumber:
            logger.error(
                "❌ pdfplumber not installed. Please install it: pip install pdfplumber"
            )

    def _load_state(self) -> dict:
        if STATE_FILE.exists():
            try:
                with open(STATE_FILE) as f:
                    return json.load(f)
            except Exception as e:
                logger.warning(f"Failed to load state: {e}. Starting fresh.")
        return {"processed_sources": [], "current_source": None, "images_count": 0}

    def _save_state(self):
        with open(STATE_FILE, "w") as f:
            json.dump(self.state, f, indent=2)

    def run(self, max_docs: int = None):
        """Run the extraction pipeline"""
        if not pdfplumber:
            return

        sources = self.db.get_all_sources()
        logger.info(f"📸 Starting Image Extraction on {len(sources)} sources")

        count = 0
        for source in sources:
            if source.id in self.state["processed_sources"]:
                continue

            if max_docs and count >= max_docs:
                logger.info(f"🛑 Reached max_docs limit ({max_docs}). Pausing.")
                break

            # Idle Check
            activity_file = Path(".app_activity")
            if activity_file.exists():
                try:
                    last_active = activity_file.stat().st_mtime
                    if time.time() - last_active < 60:  # 60s cooldown
                        logger.info(
                            "⏳ App is active. Pausing background extraction..."
                        )
                        while time.time() - last_active < 60:
                            time.sleep(5)
                            # Refresh timestamp check
                            if activity_file.exists():
                                last_active = activity_file.stat().st_mtime
                        logger.info("▶️ App idle. Resuming extraction.")
                except Exception:
                    pass

            logger.info(f"Processing: {source.title}...")
            self.state["current_source"] = source.id
            self._save_state()

            try:
                self._process_source(source)
                self.state["processed_sources"].append(source.id)
                self.state["current_source"] = None
                self._save_state()
                count += 1
            except Exception as e:
                logger.error(f"Failed to process {source.title}: {e}")
                # Don't mark as processed, so we retry next time? Or mark as failed?
                # For now, just log and continue to next
                continue

    def _process_source(self, source: SourceMetadata):
        """Extract images from a single PDF"""
        pdf_path = source.file_path

        # Check if file exists (it might be a 'NeuroLi copy' path issue)
        # We need to resolve it effectively.
        # Ideally MetadataManager helper would be used, but let's try direct first.
        if not str(pdf_path).startswith("/"):
            # Relative path?
            pass

        # Simple hack: if file not found, try to find it in common locations?
        # Assuming path in DB is correct absolute path from ingestion
        if not Path(pdf_path).exists():
            logger.warning(f"⚠️ File not found: {pdf_path}")
            return

        images_found = 0
        with pdfplumber.open(pdf_path) as pdf:
            for page_num, page in enumerate(pdf.pages, 1):
                # pdfplumber images
                for img in page.images:
                    # Filter tiny images (icons etc)
                    if img["width"] < 100 or img["height"] < 100:
                        continue

                    # Extract high-res?
                    # pdfplumber extracts as PIL Image
                    try:
                        # bounding box
                        x0, top, x1, bottom = (
                            img["x0"],
                            img["top"],
                            img["x1"],
                            img["bottom"],
                        )

                        # Clamp to page bounds to avoid errors
                        x0 = max(0, x0)
                        top = max(0, top)
                        x1 = min(page.width, x1)
                        bottom = min(page.height, bottom)

                        # Validate dimensions after clamping
                        if (x1 - x0) < 50 or (bottom - top) < 50:
                            continue

                        # crop
                        cropped = page.crop((x0, top, x1, bottom)).to_image(
                            resolution=300
                        )

                        # Generate ID
                        img_id = str(uuid.uuid4())
                        filename = f"{source.id}_{page_num}_{img_id[:8]}.png"
                        save_path = ASSETS_DIR / filename

                        # Save to disk
                        cropped.save(save_path)

                        # Create DB Entry
                        db_image = ExtractedImage(
                            id=img_id,
                            source_id=source.id,
                            page=page_num,
                            file_path=save_path.absolute(),
                            caption=f"Image from p.{page_num}",  # Placeholder for now
                            surrounding_text="",  # Placeholder
                            image_type=ImageType.ILLUSTRATION,
                            width=int(img["width"]),
                            height=int(img["height"]),
                        )

                        self.db.insert_image(db_image)
                        images_found += 1

                    except Exception as e:
                        logger.warning(f"Failed to extract image on p.{page_num}: {e}")

        logger.info(f"   -> Extracted {images_found} images.")
        self.state["images_count"] += images_found


if __name__ == "__main__":
    db = Database()
    pipeline = ImageExtractionPipeline(db)
    pipeline.run()
