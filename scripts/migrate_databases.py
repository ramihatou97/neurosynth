#!/usr/bin/env python3
"""
Database Migration Script
=========================
Migrates databases to centralized data/ directory structure.

Before:
- ./neurosynth.db (94MB) - Deep-DX database
- ./reference-library.old/data/library.db (352MB) - Reference Library cache
- ./data/index.db (48K) - Already in target location

After:
- ./data/neurosynth.db
- ./data/library.db
- ./data/index.db (unchanged)

Usage:
    python scripts/migrate_databases.py [--dry-run]
"""

import argparse
import shutil
from pathlib import Path


def main(dry_run: bool = False):
    """Migrate databases to data/ directory."""
    repo_root = Path(__file__).parent.parent
    data_dir = repo_root / "data"

    # Ensure data directory exists
    if not dry_run:
        data_dir.mkdir(parents=True, exist_ok=True)

    migrations = [
        {
            "name": "Deep-DX Database",
            "source": repo_root / "neurosynth.db",
            "target": data_dir / "neurosynth.db",
        },
        {
            "name": "Reference Library Cache",
            "source": repo_root / "reference-library.old" / "data" / "library.db",
            "target": data_dir / "library.db",
        },
    ]

    print("=" * 60)
    print("DATABASE MIGRATION")
    print("=" * 60)

    if dry_run:
        print("\n🔍 DRY RUN MODE - No changes will be made\n")

    for migration in migrations:
        name = migration["name"]
        source = migration["source"]
        target = migration["target"]

        print(f"\n{name}:")
        print(f"  Source: {source.relative_to(repo_root)}")
        print(f"  Target: {target.relative_to(repo_root)}")

        if not source.exists():
            print("  ⚠️  Source not found - skipping")
            continue

        if target.exists():
            print("  ℹ️  Target already exists - skipping")
            continue

        source_size_mb = source.stat().st_size / 1024 / 1024
        print(f"  Size: {source_size_mb:.1f} MB")

        if dry_run:
            print("  ✓ Would move")
        else:
            try:
                shutil.move(str(source), str(target))
                print("  ✅ Moved successfully")
            except Exception as e:
                print(f"  ❌ Error: {e}")

    # Verify final state
    print("\n" + "=" * 60)
    print("VERIFICATION")
    print("=" * 60)

    expected_files = [
        data_dir / "neurosynth.db",
        data_dir / "library.db",
        data_dir / "index.db",
    ]

    all_present = True
    for db_file in expected_files:
        if db_file.exists():
            size_mb = db_file.stat().st_size / 1024 / 1024
            print(f"✓ {db_file.name:<20} ({size_mb:>6.1f} MB)")
        else:
            print(f"✗ {db_file.name:<20} (missing)")
            all_present = False

    print("\n" + "=" * 60)
    if all_present:
        print("✅ Migration complete! All databases in data/ directory")
    else:
        print("⚠️  Migration incomplete - some databases missing")
    print("=" * 60)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Migrate databases to data/ directory")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be done without making changes",
    )
    args = parser.parse_args()

    main(dry_run=args.dry_run)
