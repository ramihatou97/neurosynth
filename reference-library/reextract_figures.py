#!/usr/bin/env python3
"""
Re-extract figures with relaxed thresholds.

This script re-runs the image extraction pipeline with the new relaxed
thresholds to capture previously filtered anatomical diagrams and line art.

Usage:
    python reextract_figures.py [--force] [--limit N]
"""

import argparse
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

# Import order matters due to circular import in codebase
# Must import config first, then database, then scanner via lazy import
from src import config
from src.cache.database import Database


# Lazy import to avoid circular import
def get_library_scanner():
    from src.utils.library_scanner import LibraryScanner

    return LibraryScanner


def main():
    parser = argparse.ArgumentParser(
        description="Re-extract figures with relaxed thresholds"
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force re-extraction even if already cached",
    )
    parser.add_argument(
        "--limit", type=int, default=0, help="Limit number of PDFs to process (0=all)"
    )
    parser.add_argument(
        "--sample", action="store_true", help="Process only 5 PDFs as a test"
    )
    args = parser.parse_args()

    # Connect to database
    db_path = Path("data/library.db")
    if not db_path.exists():
        print(f"❌ Database not found: {db_path}")
        return 1

    db = Database(db_path)

    # Get current stats
    print("=" * 60)
    print("📊 BEFORE: Current Visual Elements Stats")
    print("=" * 60)
    with db._get_connection() as conn:
        cursor = conn.execute("SELECT COUNT(*) FROM visual_elements")
        before_count = cursor.fetchone()[0]
        print(f"   Visual elements: {before_count}")

        cursor = conn.execute(
            "SELECT image_type, COUNT(*) FROM visual_elements GROUP BY image_type"
        )
        print("   By type:")
        for row in cursor:
            print(f"     - {row[0]}: {row[1]}")

    # Find library path
    library_path = config.LIBRARY_PATH
    if not library_path.exists():
        # Try alternate paths
        alternates = [
            Path("/Users/ramihatoum/Desktop/reference library "),
            Path("/Users/ramihatoum/Desktop/NeuroLi copy"),
        ]
        for alt in alternates:
            if alt.exists():
                library_path = alt
                break

    print(f"\n📁 Library path: {library_path}")
    if not library_path.exists():
        print("❌ Library path not found!")
        return 1

    # Create scanner (lazy import to avoid circular import)
    LibraryScanner = get_library_scanner()
    scanner = LibraryScanner(library_path, db)
    all_pdfs = scanner.get_all_pdfs()
    print(f"📚 Total PDFs in library: {len(all_pdfs)}")

    # Limit if requested
    if args.sample:
        pdfs_to_process = all_pdfs[:5]
        print("🧪 Sample mode: processing only 5 PDFs")
    elif args.limit > 0:
        pdfs_to_process = all_pdfs[: args.limit]
        print(f"⚡ Limited mode: processing {args.limit} PDFs")
    else:
        pdfs_to_process = all_pdfs
        print(f"🔄 Full mode: processing all {len(all_pdfs)} PDFs")

    if args.force:
        print("⚠️  Force mode: re-extracting all figures (ignoring cache)")

    # Progress callback
    def on_progress(pdf_name: str, figures_extracted: int, total_processed: int):
        if figures_extracted >= 0:
            print(
                f"  [{total_processed}/{len(pdfs_to_process)}] {pdf_name}: {figures_extracted} figures"
            )
        else:
            print(f"  [{total_processed}/{len(pdfs_to_process)}] {pdf_name}: ERROR")

    # Run extraction
    print("\n" + "=" * 60)
    print("🚀 Starting Figure Extraction with Relaxed Thresholds")
    print("=" * 60)
    print("   New thresholds:")
    print("   - min_dimension: 70px (was 150px)")
    print("   - min_area: 5,000px² (was 30,000px²)")
    print("   - max_aspect_ratio: 8:1 (was 6:1)")
    print("   - min_bytes: 500 (was 5,000)")
    print()

    stats = scanner.extract_figures_batch(
        pdf_paths=pdfs_to_process, on_progress=on_progress, force=args.force
    )

    # Print results
    print("\n" + "=" * 60)
    print("📊 AFTER: Extraction Results")
    print("=" * 60)
    print(f"   PDFs processed: {stats.get('pdfs_processed', 0)}")
    print(f"   PDFs skipped (cached): {stats.get('pdfs_skipped', 0)}")
    print(f"   Total figures extracted: {stats.get('total_figures', 0)}")
    print("   By type:")
    for fig_type, count in stats.get("figures_by_type", {}).items():
        print(f"     - {fig_type}: {count}")

    # Get final count
    with db._get_connection() as conn:
        cursor = conn.execute("SELECT COUNT(*) FROM visual_elements")
        after_count = cursor.fetchone()[0]

    print("\n" + "=" * 60)
    print("📈 SUMMARY")
    print("=" * 60)
    print(f"   Before: {before_count} visual elements")
    print(f"   After:  {after_count} visual elements")
    print(
        f"   Change: +{after_count - before_count} ({'+' if after_count > before_count else ''}{((after_count - before_count) / max(before_count, 1)) * 100:.1f}%)"
    )

    return 0


if __name__ == "__main__":
    sys.exit(main())
