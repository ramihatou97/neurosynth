"""
Image Extraction Pipeline
=========================
Systematic extraction of visual content from the NeuroLi PDF Library.
Features:
- AI-Powered Extraction (SmartExtractor)
- Visual Embedding & Search Indexing (BiomedIngestor)
- SQL Persistence for Legacy Compatibility
"""

import json
import logging
import sys
import time
from pathlib import Path

# Add src to path to resolve 'index', 'models', etc.
sys.path.append(str(Path(__file__).resolve().parents[3] / "src"))

from index.database import Database
from models import ExtractedImage, ImageType, SourceMetadata

# AI Components
try:
    from ingest.smart_extractor import ExtractedFigure, SmartImageExtractor
    from neurosynth.ai.ingestor import BiomedIngestor
except ImportError as e:
    logging.warning(f"AI components missing: {e}")
    SmartImageExtractor = None
    BiomedIngestor = None

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("image_pipeline")

STATE_FILE = Path("extraction_state.json")
ASSETS_DIR = Path("assets/extracted_images")


class ImageExtractionPipeline:
    def __init__(self, db: Database):
        self.db = db
        self.state = self._load_state()
        ASSETS_DIR.mkdir(parents=True, exist_ok=True)

        # Initialize AI Components
        if SmartImageExtractor:
            self.extractor = SmartImageExtractor(str(ASSETS_DIR))
            self.ingestor = BiomedIngestor()
        else:
            self.extractor = None
            logger.error("❌ SmartExtractor dependencies missing. Pipeline disabled.")

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
        if not self.extractor:
            logger.error("Pipeline cannot run without SmartExtractor.")
            return

        sources = self.db.get_all_sources()
        logger.info(f"📸 Starting AI Image Extraction on {len(sources)} sources")

        count = 0
        for source in sources:
            if source.id in self.state["processed_sources"]:
                continue

            if max_docs and count >= max_docs:
                logger.info(f"🛑 Reached max_docs limit ({max_docs}). Pausing.")
                break

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
                continue

    def _process_source(self, source: SourceMetadata):
        """Extract images from a single PDF using AI Pipeline"""
        pdf_path = Path(source.file_path)

        if not pdf_path.exists():
            logger.warning(f"⚠️ File not found: {pdf_path}")
            return

        # 1. Extract Figures (Smart Mode)
        figures = self.extractor.process_pdf(str(pdf_path))
        if not figures:
            logger.info("   -> No relevant images found.")
            return

        logger.info(f"   -> Found {len(figures)} relevant images.")

        # 2. Ingest into AI Engine (Vector DB)
        # This creates the embeddings and searchable index
        logger.info("   -> Embedding and indexing...")
        self.ingestor.ingest_figures(figures)

        # 3. Persist to SQL Database (Old formatted records)
        # We need this for the current UI/Synthesis logic that reads from SQL
        saved_count = 0
        for fig in figures:
            try:
                db_image = self._convert_to_db_model(fig, source.id)
                self.db.insert_image(db_image)
                saved_count += 1
            except Exception as e:
                logger.warning(f"SQL insert failed for {fig.image_filename}: {e}")

        self.state["images_count"] += saved_count
        logger.info(f"   -> Saved {saved_count} images to SQL.")

    def _convert_to_db_model(
        self, fig: ExtractedFigure, source_id: str
    ) -> ExtractedImage:
        """Convert ExtractedFigure to ExtractedImage for SQL storage"""
        # Simple heuristic mapping for image type
        caption_lower = fig.caption.lower()
        img_type = ImageType.ILLUSTRATION

        if "mri" in caption_lower or "ct" in caption_lower:
            img_type = ImageType.IMAGING_MRI
        elif "intraoperative" in caption_lower or "view" in caption_lower:
            img_type = ImageType.SURGICAL_PHOTO
        elif "anatomy" in caption_lower:
            img_type = ImageType.ANATOMICAL_DIAGRAM

        return ExtractedImage(
            id=fig.image_filename,  # Using filename as ID for simplicity
            source_id=source_id,
            page=fig.page_num,
            file_path=fig.local_path,
            caption=fig.caption,
            surrounding_text=fig.context,
            image_type=img_type,
            width=0,  # Dimensions not available without re-reading
            height=0,
        )


if __name__ == "__main__":
    db = Database()
    pipeline = ImageExtractionPipeline(db)
    pipeline.run()
