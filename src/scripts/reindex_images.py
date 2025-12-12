#!/usr/bin/env python3
"""
Image Embedding Backfill with Checkpoint Resumption
Features: 4-tier path resolution, atomic checkpoints, tqdm progress, error categorization
"""
import argparse
import json
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

import numpy as np
from tqdm import tqdm

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.config import settings
from src.index.database import Database
from src.neurosynth.ai.biomed_searcher import BiomedCLIPSearcher
from src.neurosynth.ai.ingestor import BiomedIngestor

# Configuration
DB_PATH = settings.database_path
ASSETS_DIR = Path("assets/extracted_images")
if not ASSETS_DIR.exists():
    ASSETS_DIR = Path("/app/assets/extracted_images")
CHECKPOINT_FILE = Path("data/reindex_checkpoint.json")
BATCH_SIZE = 4
BASE_PATHS = [
    ASSETS_DIR,
    Path("/Users/ramihatoum/neurosynth/reference-library/data/images"),
]

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.FileHandler("logs/reindex_images.log"), logging.StreamHandler()],
)
logger = logging.getLogger(__name__)


class CheckpointManager:
    """Atomic checkpoint management for resumable processing."""

    def __init__(self, filepath: Path):
        self.filepath = filepath
        self.state = self._load()
        self.dirty = False

    def _load(self) -> dict:
        if self.filepath.exists():
            with open(self.filepath) as f:
                state = json.load(f)
                logger.info(f"📂 Resuming: {len(state['processed_ids'])} already done")
                return state
        return {
            "processed_ids": [],
            "failed": {"path": [], "embed": [], "db": []},
            "stats": {"success": 0, "fail_path": 0, "fail_embed": 0, "fail_db": 0},
            "started_at": datetime.now().isoformat(),
        }

    def save(self):
        if not self.dirty:
            return
        self.state["last_updated"] = datetime.now().isoformat()
        temp = self.filepath.with_suffix(".tmp")
        with open(temp, "w") as f:
            json.dump(self.state, f, indent=2)
        temp.replace(self.filepath)
        self.dirty = False

    def mark_success(self, img_id: str):
        self.state["processed_ids"].append(img_id)
        self.state["stats"]["success"] += 1
        self.dirty = True

    def mark_failed(self, img_id: str, category: str):
        self.state["processed_ids"].append(img_id)
        self.state["failed"][category].append(img_id)
        self.state["stats"][f"fail_{category}"] += 1
        self.dirty = True

    def is_processed(self, img_id: str) -> bool:
        return img_id in self.state["processed_ids"]


def resolve_path(stored_path: Path) -> Path | None:
    """4-tier path resolution strategy."""
    # Tier 1: Direct
    if stored_path.exists():
        return stored_path

    filename = stored_path.name

    # Tier 2: Base paths
    for base in BASE_PATHS:
        candidate = base / filename
        if candidate.exists():
            return candidate

    # Tier 3: Recursive glob
    for base in BASE_PATHS:
        if base.exists():
            matches = list(base.rglob(filename))
            if matches:
                return matches[0]

    # Tier 4: Extension variants
    stem = stored_path.stem
    for base in BASE_PATHS:
        for ext in [".png", ".jpg", ".jpeg"]:
            candidate = base / f"{stem}{ext}"
            if candidate.exists():
                return candidate

    return None


class ImageAdapter:
    """Duck-type adapter for BiomedIngestor compatibility."""

    def __init__(self, img, resolved_path: Path):
        self.local_path = resolved_path
        self.image_filename = img.id
        self.source_pdf = img.source_id
        self.caption = img.caption or ""
        self.context = img.surrounding_text or ""
        self.page_num = img.page or 1
        # Add attributes expected by Ingestor's _process_batch
        self.detected_regions = []
        self.region_confidence = 0.0
        self.ocr_caption = ""
        self.caption_source = "db_backfill"
        self.figure_number = ""
        self.parsed_caption = ""


def main():
    parser = argparse.ArgumentParser(description="Reindex images with BiomedCLIP")
    parser.add_argument("--dry-run", action="store_true", help="Process first 32 only")
    parser.add_argument("--fresh", action="store_true", help="Ignore checkpoint")
    parser.add_argument("--limit", type=int, help="Limit total images")
    args = parser.parse_args()

    # Ensure logs dir
    Path("logs").mkdir(exist_ok=True)

    # Fresh start
    if args.fresh and CHECKPOINT_FILE.exists():
        CHECKPOINT_FILE.unlink()
        logger.info("🗑️ Checkpoint cleared")

    # Initialize
    # Adjust DB_PATH if needed to be absolute or relative correctly
    # Use settings from config if available or default
    db = Database(DB_PATH)

    ingestor = BiomedIngestor()
    # Note: BiomedIngestor creates embedder internally, but we need one for manual embedding too
    # or expose it. Ingestor has self.embedder.
    embedder = ingestor.embedder

    ckpt = CheckpointManager(CHECKPOINT_FILE)

    # Get images
    images = db.get_images_without_embeddings()
    total = len(images)
    logger.info(f"Found {total:,} images without embeddings")

    if total == 0:
        logger.info("✅ All images already have embeddings!")
        return

    if args.dry_run:
        images = images[:BATCH_SIZE]
        logger.info(f"🧪 Dry run: {len(images)} images")
    elif args.limit:
        images = images[: args.limit]

    # Process
    with tqdm(total=len(images), desc="Reindexing") as pbar:
        batch_imgs, batch_paths = [], []

        for img in images:
            if ckpt.is_processed(img.id):
                pbar.update(1)
                continue

            resolved = resolve_path(img.file_path)
            if not resolved:
                ckpt.mark_failed(img.id, "path")
                pbar.update(1)
                continue

            batch_imgs.append(img)
            batch_paths.append(resolved)

            if len(batch_imgs) >= BATCH_SIZE:
                _process_batch(batch_imgs, batch_paths, db, embedder, ingestor, ckpt)
                pbar.update(len(batch_imgs))
                batch_imgs, batch_paths = [], []
                ckpt.save()

        # Final batch
        if batch_imgs:
            _process_batch(batch_imgs, batch_paths, db, embedder, ingestor, ckpt)
            pbar.update(len(batch_imgs))
            ckpt.save()

    # Report
    stats = ckpt.state["stats"]
    logger.info("=" * 50)
    logger.info("📊 COMPLETE")
    logger.info(f"   Success:     {stats['success']:,}")
    logger.info(f"   Failed path: {stats['fail_path']:,}")
    logger.info(f"   Failed embed:{stats['fail_embed']:,}")
    logger.info(f"   Failed DB:   {stats['fail_db']:,}")


def _process_batch(imgs, paths, db, embedder, ingestor, ckpt):
    """Process a batch of images."""
    try:
        vectors = embedder.embed_image([str(p) for p in paths])

        if len(vectors) != len(imgs):
            logger.warning(f"Vector count mismatch: {len(vectors)} vs {len(imgs)}")
            # This can happen if some images fail to load inside embedder
            # But embedder usually returns empty array on failure or raises error
            # Assuming 1-to-1 for now or handled by embedder

        for img, vec in zip(imgs, vectors):
            try:
                db.update_image_embedding(img.id, vec.tolist())
                ckpt.mark_success(img.id)
            except Exception as e:
                logger.error(f"DB error {img.id}: {e}")
                ckpt.mark_failed(img.id, "db")

        # Qdrant upsert
        adapted = [ImageAdapter(img, path) for img, path in zip(imgs, paths)]
        ingestor.ingest_figures(adapted)

    except Exception as e:
        logger.error(f"Batch embedding failed: {e}")
        for img in imgs:
            ckpt.mark_failed(img.id, "embed")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logger.warning("\n⚠️ Interrupted - progress saved to checkpoint")
        sys.exit(130)
