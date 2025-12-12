#!/usr/bin/env python3
"""Process remaining batches 5-9"""
import json
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.batch_embed_pdfs import IssueLogger, process_pdf_batch

plan = json.load(open("logs/batch_processing_plan.json"))

total_pdfs = 0
total_images_extracted = 0
total_images_embedded = 0

for batch_num in range(5, 10):  # Batches 5-9
    batch = plan["batches"][batch_num - 1]

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    issue_logger = IssueLogger(
        Path("logs") / f"issues_batch{batch_num}_{timestamp}.json"
    )

    print(f"\n🔄 Processing Batch {batch_num}...")
    results = process_pdf_batch(batch, issue_logger)
    issue_logger.save()

    total_pdfs += len(results["pdfs_processed"])
    total_images_extracted += results["total_images_extracted"]
    total_images_embedded += results["total_images_embedded"]

    print(f"✅ Batch {batch_num} Complete:")
    print(f'  PDFs: {len(results["pdfs_processed"])}/10')
    print(
        f'  Images: {results["total_images_extracted"]} extracted, {results["total_images_embedded"]} embedded'
    )
    print("---")

print("\n\n📊 Batches 5-9 Summary:")
print(f"  Total PDFs processed: {total_pdfs}")
print(f"  Total images extracted: {total_images_extracted}")
print(f"  Total images embedded: {total_images_embedded}")
