#!/usr/bin/env python3
"""
Batch PDF Embedding with Comprehensive Logging
Processes PDFs in batches of 10 with detailed issue tracking
"""
import json
import logging
import sys
import time
import traceback
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config import settings
from src.index.database import Database

# Import extraction and embedding components
from src.ingest.smart_extractor import SmartImageExtractor
from src.neurosynth.ai.ingestor import BiomedIngestor

# Configure logging
log_dir = Path("logs")
log_dir.mkdir(exist_ok=True)

timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
log_file = log_dir / f"batch_embedding_{timestamp}.log"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.FileHandler(log_file), logging.StreamHandler()],
)
logger = logging.getLogger(__name__)


class IssueLogger:
    """Tracks all issues during processing for post-analysis."""

    def __init__(self, log_path: Path):
        self.log_path = log_path
        self.issues = {
            "critical": [],  # Processing stopped
            "error": [],  # Processing failed but continued
            "warning": [],  # Potential issue
            "info": [],  # Notable event
        }
        self.metrics = {
            "pdfs_attempted": 0,
            "pdfs_succeeded": 0,
            "pdfs_failed": 0,
            "images_extracted": 0,
            "images_embedded": 0,
            "total_time_seconds": 0,
        }

    def log_issue(
        self,
        severity: str,
        category: str,
        pdf_name: str,
        description: str,
        details: dict[str, Any] = None,
    ):
        """Log an issue with full context."""
        issue = {
            "timestamp": datetime.now().isoformat(),
            "severity": severity,
            "category": category,
            "pdf": pdf_name,
            "description": description,
            "details": details or {},
        }
        self.issues[severity].append(issue)
        logger.log(
            (
                logging.CRITICAL
                if severity == "critical"
                else (
                    logging.ERROR
                    if severity == "error"
                    else logging.WARNING if severity == "warning" else logging.INFO
                )
            ),
            f"[{category}] {pdf_name}: {description}",
        )

    def update_metrics(self, **kwargs):
        """Update processing metrics."""
        self.metrics.update(kwargs)

    def save(self):
        """Save comprehensive report."""
        report = {
            "generated_at": datetime.now().isoformat(),
            "metrics": self.metrics,
            "issues_summary": {
                "critical": len(self.issues["critical"]),
                "error": len(self.issues["error"]),
                "warning": len(self.issues["warning"]),
                "info": len(self.issues["info"]),
            },
            "issues_detailed": self.issues,
        }

        # Save JSON report
        json_path = self.log_path.with_suffix(".json")
        with open(json_path, "w") as f:
            json.dump(report, f, indent=2)

        # Update markdown log
        self._update_markdown_log(report)

        logger.info(f"Issue report saved: {json_path}")

    def _update_markdown_log(self, report: dict):
        """Append to markdown log."""
        md_log = Path("logs/embedding_issues_log.md")

        with open(md_log, "a") as f:
            f.write(
                f"\n\n---\n\n## Batch Processing Run - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
            )
            f.write("### Metrics\n")
            f.write(f"- PDFs attempted: {report['metrics']['pdfs_attempted']}\n")
            f.write(f"- PDFs succeeded: {report['metrics']['pdfs_succeeded']}\n")
            f.write(f"- PDFs failed: {report['metrics']['pdfs_failed']}\n")
            f.write(f"- Images extracted: {report['metrics']['images_extracted']}\n")
            f.write(f"- Images embedded: {report['metrics']['images_embedded']}\n")
            f.write(f"- Total time: {report['metrics']['total_time_seconds']:.1f}s\n\n")

            f.write("### Issues Summary\n")
            for severity, count in report["issues_summary"].items():
                if count > 0:
                    f.write(f"- {severity.upper()}: {count}\n")
            f.write("\n")

            # Top issues by category
            if (
                report["issues_detailed"]["error"]
                or report["issues_detailed"]["critical"]
            ):
                f.write("### Critical/Error Issues\n")
                for issue in (
                    report["issues_detailed"]["critical"]
                    + report["issues_detailed"]["error"]
                ):
                    f.write(f"- **{issue['pdf']}**: {issue['description']}\n")
                    if issue["details"]:
                        f.write(
                            f"  - Details: {json.dumps(issue['details'], indent=2)}\n"
                        )


def process_pdf_batch(batch_info: dict, issue_logger: IssueLogger) -> dict:
    """Process a batch of PDFs with full logging."""
    batch_num = batch_info["batch_number"]
    pdfs = batch_info["pdfs"]

    logger.info("=" * 80)
    logger.info(f"Starting Batch {batch_num}: {len(pdfs)} PDFs")
    logger.info("=" * 80)

    # Initialize extraction and embedding components
    try:
        output_dir = Path("data/processed/images")
        output_dir.mkdir(parents=True, exist_ok=True)

        extractor = SmartImageExtractor(
            output_dir=str(output_dir),
            min_entropy=4.5,  # Good balance for medical figures
        )
        ingestor = BiomedIngestor()
        db = Database(settings.database_path)

        logger.info("✓ Initialized: SmartImageExtractor, BiomedIngestor, Database")
    except Exception as e:
        issue_logger.log_issue(
            "critical",
            "initialization_failure",
            "batch",
            f"Failed to initialize processing components: {e}",
            {"exception_type": type(e).__name__, "traceback": traceback.format_exc()},
        )
        logger.error(f"CRITICAL: Cannot initialize components: {e}")
        return {
            "batch_number": batch_num,
            "pdfs_processed": [],
            "pdfs_failed": [p["filename"] for p in pdfs],
            "total_images_extracted": 0,
            "total_images_embedded": 0,
        }

    batch_start = time.time()
    results = {
        "batch_number": batch_num,
        "pdfs_processed": [],
        "pdfs_failed": [],
        "total_images_extracted": 0,
        "total_images_embedded": 0,
    }

    for i, pdf_info in enumerate(pdfs, 1):
        pdf_path = Path(pdf_info["path"])
        pdf_name = pdf_info["filename"]

        logger.info(f"\n[{i}/{len(pdfs)}] Processing: {pdf_name}")
        logger.info(f"  Path: {pdf_path}")
        logger.info(f"  Size: {pdf_info['size'] / (1024*1024):.2f} MB")

        pdf_start = time.time()
        images_extracted_count = 0
        images_embedded_count = 0

        try:
            # Check if file exists
            if not pdf_path.exists():
                issue_logger.log_issue(
                    "error",
                    "file_not_found",
                    pdf_name,
                    "PDF file does not exist",
                    {"expected_path": str(pdf_path)},
                )
                results["pdfs_failed"].append(pdf_name)
                continue

            # Check file size
            if pdf_info["size"] == 0:
                issue_logger.log_issue(
                    "warning",
                    "empty_file",
                    pdf_name,
                    "PDF file is empty (0 bytes)",
                    {"path": str(pdf_path)},
                )
                results["pdfs_failed"].append(pdf_name)
                continue

            # STEP 1: Extract images from PDF
            logger.info("  → Extracting images...")
            try:
                figures = extractor.process_pdf(
                    pdf_path=str(pdf_path),
                    enable_caption_parsing=True,
                    enable_deduplication=True,
                    enable_region_detection=True,
                    enable_ocr=False,  # Disable OCR for speed
                )

                images_extracted_count = len(figures)
                results["total_images_extracted"] += images_extracted_count

                if images_extracted_count == 0:
                    issue_logger.log_issue(
                        "warning",
                        "no_images_extracted",
                        pdf_name,
                        "No images extracted from PDF (may be text-only or failed quality filters)",
                        {"pdf_size_bytes": pdf_info["size"]},
                    )
                    logger.info("  ⚠ No images extracted")
                else:
                    logger.info(f"  ✓ Extracted {images_extracted_count} images")

                    # Log extraction details
                    duplicates = sum(1 for f in figures if f.is_duplicate)
                    if duplicates > 0:
                        issue_logger.log_issue(
                            "info",
                            "duplicates_filtered",
                            pdf_name,
                            f"{duplicates} duplicate images filtered out",
                            {
                                "total_extracted": images_extracted_count,
                                "duplicates": duplicates,
                            },
                        )
                        logger.info(f"    ({duplicates} duplicates filtered)")

            except Exception as e:
                issue_logger.log_issue(
                    "error",
                    "extraction_failed",
                    pdf_name,
                    f"Image extraction failed: {str(e)}",
                    {
                        "exception_type": type(e).__name__,
                        "traceback": traceback.format_exc(),
                    },
                )
                logger.error(f"  ✗ Extraction failed: {e}")
                results["pdfs_failed"].append(pdf_name)
                continue

            # STEP 2: Embed images with BiomedCLIP and upload to Qdrant
            if figures:
                logger.info("  → Embedding with BiomedCLIP...")
                try:
                    # Filter out duplicates and header/footer images for embedding
                    valid_figures = [
                        f
                        for f in figures
                        if not f.is_duplicate and f.image_type != "header_footer"
                    ]

                    if len(valid_figures) < len(figures):
                        filtered_count = len(figures) - len(valid_figures)
                        issue_logger.log_issue(
                            "info",
                            "figures_filtered_pre_embedding",
                            pdf_name,
                            f"{filtered_count} figures filtered before embedding (duplicates/headers)",
                            {
                                "total_figures": len(figures),
                                "valid_figures": len(valid_figures),
                                "filtered": filtered_count,
                            },
                        )
                        logger.info(f"    ({filtered_count} figures filtered)")

                    if valid_figures:
                        ingestor.ingest_figures(valid_figures, batch_size=32)
                        images_embedded_count = len(valid_figures)
                        results["total_images_embedded"] += images_embedded_count
                        logger.info(f"  ✓ Embedded {images_embedded_count} images")

                        issue_logger.log_issue(
                            "info",
                            "embedding_success",
                            pdf_name,
                            f"Successfully embedded {images_embedded_count} images",
                            {
                                "extracted": images_extracted_count,
                                "embedded": images_embedded_count,
                                "has_captions": sum(
                                    1 for f in valid_figures if f.caption
                                ),
                                "has_regions": sum(
                                    1 for f in valid_figures if f.detected_regions
                                ),
                            },
                        )
                    else:
                        issue_logger.log_issue(
                            "warning",
                            "no_valid_figures",
                            pdf_name,
                            "No valid figures to embed after filtering",
                            {"extracted": images_extracted_count},
                        )
                        logger.info("  ⚠ No valid figures to embed")

                except Exception as e:
                    issue_logger.log_issue(
                        "error",
                        "embedding_failed",
                        pdf_name,
                        f"Image embedding failed: {str(e)}",
                        {
                            "exception_type": type(e).__name__,
                            "traceback": traceback.format_exc(),
                            "images_extracted": images_extracted_count,
                        },
                    )
                    logger.error(f"  ✗ Embedding failed: {e}")
                    results["pdfs_failed"].append(pdf_name)
                    continue

            pdf_duration = time.time() - pdf_start
            logger.info(
                f"  ✓ Completed in {pdf_duration:.1f}s ({images_extracted_count} extracted, {images_embedded_count} embedded)"
            )
            results["pdfs_processed"].append(pdf_name)

        except Exception as e:
            error_msg = str(e)
            stack_trace = traceback.format_exc()

            issue_logger.log_issue(
                "error",
                "processing_exception",
                pdf_name,
                f"Unhandled exception: {error_msg}",
                {"exception_type": type(e).__name__, "stack_trace": stack_trace},
            )
            results["pdfs_failed"].append(pdf_name)
            logger.error(f"  ✗ Failed: {error_msg}")

    batch_duration = time.time() - batch_start
    logger.info(f"\n{'=' * 80}")
    logger.info(f"Batch {batch_num} Complete:")
    logger.info(f"  Processed: {len(results['pdfs_processed'])}/{len(pdfs)}")
    logger.info(f"  Failed: {len(results['pdfs_failed'])}")
    logger.info(f"  Images extracted: {results['total_images_extracted']}")
    logger.info(f"  Images embedded: {results['total_images_embedded']}")
    logger.info(f"  Duration: {batch_duration:.1f}s")
    logger.info(f"{'=' * 80}\n")

    # Update metrics
    issue_logger.update_metrics(
        pdfs_attempted=issue_logger.metrics["pdfs_attempted"] + len(pdfs),
        pdfs_succeeded=issue_logger.metrics["pdfs_succeeded"]
        + len(results["pdfs_processed"]),
        pdfs_failed=issue_logger.metrics["pdfs_failed"] + len(results["pdfs_failed"]),
        images_extracted=issue_logger.metrics["images_extracted"]
        + results["total_images_extracted"],
        images_embedded=issue_logger.metrics["images_embedded"]
        + results["total_images_embedded"],
        total_time_seconds=issue_logger.metrics["total_time_seconds"] + batch_duration,
    )

    return results


def main():
    """Main batch processing entry point."""
    logger.info("Starting Batch PDF Embedding Process")
    logger.info(f"Log file: {log_file}")

    # Load batch plan
    plan_path = Path("logs/batch_processing_plan.json")
    if not plan_path.exists():
        logger.error("Batch plan not found. Run analysis first.")
        return

    with open(plan_path) as f:
        plan = json.load(f)

    logger.info(
        f"Loaded plan: {plan['planned_batches']} batches, "
        f"{plan['total_unprocessed']} total PDFs"
    )

    # Initialize issue logger
    issue_log_path = log_dir / f"issues_{timestamp}.json"
    issue_logger = IssueLogger(issue_log_path)

    # Process first batch only (for testing)
    if plan["batches"]:
        batch = plan["batches"][0]
        results = process_pdf_batch(batch, issue_logger)

        # Save logs
        issue_logger.save()

        logger.info("\n" + "=" * 80)
        logger.info("BATCH PROCESSING COMPLETE")
        logger.info("=" * 80)
        logger.info("Check logs:")
        logger.info(f"  - Main log: {log_file}")
        logger.info(f"  - Issues: {issue_log_path}")
        logger.info("  - Markdown: logs/embedding_issues_log.md")
    else:
        logger.warning("No batches to process")


if __name__ == "__main__":
    main()
