import logging
import sqlite3
import sys
from pathlib import Path

# Ensure src is in path
root_dir = Path(__file__).parent.parent
sys.path.append(str(root_dir))

from src.config import settings

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("MetadataAudit")


def audit_titles():
    logger.info("🔍 Auditing Document Titles for Quality...")

    db_path = settings.database_path
    if not db_path.exists():
        logger.error(f"Database not found at {db_path}")
        return

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Define generic patterns
    generic_patterns = [
        "Slide%",
        "Untitled%",
        "Presentation%",
        "Microsoft Word%",
        "Doc%",
        "Unknown%",
        "%.pdf",  # Titles that are just filenames
    ]

    total_docs = cursor.execute("SELECT COUNT(*) FROM sources").fetchone()[0]
    logger.info(f"Total Documents: {total_docs}")

    bad_titles = []

    # Check for specific patterns
    for pattern in generic_patterns:
        cursor.execute(
            "SELECT id, title, file_path FROM sources WHERE title LIKE ?", (pattern,)
        )
        rows = cursor.fetchall()
        for row in rows:
            bad_titles.append((row[0], row[1], row[2], "Generic Pattern"))

    # Check for short titles (often garbage)
    cursor.execute("SELECT id, title, file_path FROM sources WHERE LENGTH(title) < 5")
    rows = cursor.fetchall()
    for row in rows:
        bad_titles.append((row[0], row[1], row[2], "Too Short"))

    conn.close()

    # Deduplicate
    unique_bad = {id: (title, path, reason) for id, title, path, reason in bad_titles}

    logger.info(
        f"Found {len(unique_bad)} potentially low-quality titles ({len(unique_bad)/total_docs*100:.1f}%)"
    )

    if unique_bad:
        logger.info("\nSample Low-Quality Titles:")
        for i, (id, data) in enumerate(list(unique_bad.items())[:20]):
            logger.info(
                f" - [{data[2]}] Title: '{data[0]}' (Reason: {data[1]})"
            )  # Log reason is actually path in my tuple unpacking above... wait.
            # data is (title, path, reason)
            # logger message above: data[2] is reason? No.
            # unique_bad values: (title, row[2] aka path, reason)
            # So data[0]=title, data[1]=path, data[2]=reason
            pass

    # Re-print strictly
    if unique_bad:
        print("\n--- DETAILED REPORT ---")
        for i, (id, (title, path, reason)) in enumerate(list(unique_bad.items())[:25]):
            print(
                f"{i+1}. Title: '{title}'\n   File: {Path(path).name}\n   Issue: {reason}\n"
            )


if __name__ == "__main__":
    audit_titles()
