#!/usr/bin/env python3
"""
Backfill script to enrich existing Qdrant image entries with:
1. Anatomical region detection
2. OCR caption extraction
3. Enhanced caption combining all sources

Usage:
    python scripts/backfill_image_enhancements.py --batch-size 100 --limit 1000
    python scripts/backfill_image_enhancements.py --all  # Process all images
"""

import argparse
import json
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from qdrant_client import QdrantClient
from qdrant_client.models import PointStruct

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class ImageEnhancementBackfill:
    """Backfill existing Qdrant images with region detection and OCR."""

    def __init__(self, qdrant_path: Path, images_base_path: Path):
        self.client = QdrantClient(path=str(qdrant_path))
        self.images_base_path = images_base_path
        self.collection_name = "neurosurgical_figures_hybrid"

        # Lazy load enhancement modules
        self._region_detector = None
        self._ocr_extractor = None

        # Stats
        self.stats = {
            "processed": 0,
            "regions_added": 0,
            "ocr_extracted": 0,
            "errors": 0,
        }

    @property
    def region_detector(self):
        if self._region_detector is None:
            from neurosynth.enhancements.region_detector import AnatomicalRegionDetector

            self._region_detector = AnatomicalRegionDetector()
        return self._region_detector

    @property
    def ocr_extractor(self):
        if self._ocr_extractor is None:
            from ingest.ocr_caption_extractor import OCRCaptionExtractor

            self._ocr_extractor = OCRCaptionExtractor()
        return self._ocr_extractor

    def find_image_file(self, payload: dict) -> Path | None:
        """Find the actual image file on disk."""
        filename = payload.get("filename", "")
        path_field = payload.get("path", "")

        # Try multiple locations
        candidates = [
            # Direct path from Qdrant (relative to project root)
            Path.cwd() / path_field,
            # Just the filename in base path
            self.images_base_path / filename,
            # Absolute path
            Path(path_field),
            # ~/.neurosynth location
            Path.home() / ".neurosynth" / "extracted_images" / filename,
        ]

        for candidate in candidates:
            if candidate.exists():
                return candidate
        return None

    def enrich_point(
        self, point_id: str, payload: dict, enable_ocr: bool = True
    ) -> dict:
        """Enrich a single point with region detection and optional OCR."""
        import re

        updates = {}

        caption = payload.get("caption", "")
        context = payload.get("context", "")
        source_pdf = payload.get("source_pdf", "")

        # 1. Upgrade caption from context if current caption is generic
        if caption.startswith("Image from") and context:
            # Try to extract Figure reference from context
            fig_match = re.search(
                r"((?:Fig(?:ure)?\.?\s*\d+[A-Za-z]?)[:\.\s\-]+[^\.]{10,200})",
                context,
                re.IGNORECASE,
            )
            if fig_match:
                updates["caption"] = fig_match.group(1).strip()
                updates["caption_upgraded"] = True
                caption = updates[
                    "caption"
                ]  # Use upgraded caption for region detection

        # 2. Region detection from all available text
        combined_text = " ".join([source_pdf, caption, context])

        regions = self.region_detector.detect_regions(combined_text)
        detailed = self.region_detector.detect_regions_detailed(combined_text)

        updates["detected_regions"] = regions
        updates["region_confidence"] = detailed[0].confidence if detailed else 0.0

        if regions:
            self.stats["regions_added"] += 1

        # 2. OCR extraction (if enabled and image exists)
        if enable_ocr:
            image_path = self.find_image_file(payload)
            if image_path:
                try:
                    ocr_text = self.ocr_extractor.extract_text(image_path)
                    if ocr_text and len(ocr_text.strip()) > 10:
                        updates["ocr_text"] = ocr_text[:500]  # Limit size

                        # Extract structured caption if possible
                        caption_result = self.ocr_extractor.extract_caption(image_path)
                        if caption_result:
                            updates["ocr_caption"] = caption_result.get("caption", "")
                            updates["ocr_figure_id"] = caption_result.get(
                                "figure_id", ""
                            )

                        self.stats["ocr_extracted"] += 1

                        # Re-run region detection with OCR text
                        ocr_regions = self.region_detector.detect_regions(ocr_text)
                        if ocr_regions:
                            updates["detected_regions"] = list(
                                set(regions + ocr_regions)
                            )
                except Exception as e:
                    logger.debug(f"OCR failed for {image_path}: {e}")

        # 3. Determine caption source
        if updates.get("ocr_caption"):
            updates["caption_source"] = "ocr"
        elif payload.get("context"):
            updates["caption_source"] = "proximity"
        else:
            updates["caption_source"] = "filename"

        return updates

    def run(
        self,
        batch_size: int = 100,
        limit: int | None = None,
        enable_ocr: bool = True,
    ):
        """Run the backfill process."""
        logger.info(
            f"Starting backfill: batch_size={batch_size}, limit={limit}, ocr={enable_ocr}"
        )

        offset = None
        total_processed = 0

        while True:
            if limit and total_processed >= limit:
                break

            # Fetch batch
            results = self.client.scroll(
                collection_name=self.collection_name,
                limit=min(
                    batch_size, (limit - total_processed) if limit else batch_size
                ),
                offset=offset,
                with_payload=True,
                with_vectors=False,
            )

            points = results[0]
            if not points:
                break

            # Process batch
            updates = []
            for point in points:
                try:
                    enriched = self.enrich_point(
                        str(point.id), point.payload, enable_ocr
                    )

                    # Merge with existing payload
                    new_payload = {**point.payload, **enriched}
                    updates.append((point.id, new_payload))

                    self.stats["processed"] += 1
                except Exception as e:
                    logger.error(f"Error processing {point.id}: {e}")
                    self.stats["errors"] += 1

            # Batch update payloads
            for point_id, new_payload in updates:
                self.client.set_payload(
                    collection_name=self.collection_name,
                    payload=new_payload,
                    points=[point_id],
                )

            total_processed += len(points)
            offset = results[1]

            logger.info(
                f"Processed {total_processed} images | Regions: {self.stats['regions_added']} | OCR: {self.stats['ocr_extracted']}"
            )

            if offset is None:
                break

        logger.info(f"Backfill complete: {json.dumps(self.stats, indent=2)}")
        return self.stats


def main():
    parser = argparse.ArgumentParser(
        description="Backfill image enhancements to Qdrant"
    )
    parser.add_argument(
        "--batch-size", type=int, default=50, help="Batch size for processing"
    )
    parser.add_argument(
        "--limit", type=int, default=None, help="Max images to process (None=all)"
    )
    parser.add_argument("--all", action="store_true", help="Process all images")
    parser.add_argument("--no-ocr", action="store_true", help="Skip OCR extraction")
    parser.add_argument(
        "--qdrant-path", type=str, default=str(Path.home() / ".neurosynth" / "qdrant")
    )
    parser.add_argument(
        "--images-path",
        type=str,
        default=str(Path.cwd() / "assets" / "extracted_images"),
    )

    args = parser.parse_args()

    limit = None if args.all else (args.limit or 100)

    backfill = ImageEnhancementBackfill(
        qdrant_path=Path(args.qdrant_path),
        images_base_path=Path(args.images_path),
    )

    stats = backfill.run(
        batch_size=args.batch_size,
        limit=limit,
        enable_ocr=not args.no_ocr,
    )

    # Save report
    report_path = Path.home() / ".neurosynth" / "backfill_report.json"
    report_path.write_text(
        json.dumps(
            {
                "completed_at": datetime.now().isoformat(),
                "stats": stats,
            },
            indent=2,
        )
    )
    print(f"\nReport saved to: {report_path}")


if __name__ == "__main__":
    main()
