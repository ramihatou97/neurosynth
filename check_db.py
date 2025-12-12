import sqlite3
from pathlib import Path

# Config says default is "data/index.db"
# But we are running from root, so it should be relative to root?
# Or maybe the app was run from somewhere else before?

db_path = Path("data/index.db")

if not db_path.exists():
    print(f"❌ Database not found at: {db_path.absolute()}")
    # Try looking for other .db files
    print("Searching for other .db files...")
    for p in Path(".").rglob("*.db"):
        print(f"  Found: {p}")
else:
    print(f"✅ Found database at: {db_path}")
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Count Sources
        source_count = 0
        try:
            source_count = cursor.execute("SELECT COUNT(*) FROM sources").fetchone()[0]
            print(f"📊 Total Sources in DB: {source_count}")
        except sqlite3.OperationalError:
            print("❌ 'sources' table not found.")

        # Count Chunks
        try:
            chunk_count = cursor.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]
            print(f"📊 Total Chunks in DB: {chunk_count}")

            embedded_chunk_count = cursor.execute(
                "SELECT COUNT(*) FROM chunks WHERE embedding IS NOT NULL"
            ).fetchone()[0]
            print(f"📊 Embedded Chunks: {embedded_chunk_count}")
        except sqlite3.OperationalError:
            print("❌ 'chunks' table not found.")

        # Count Images
        try:
            image_count = cursor.execute("SELECT COUNT(*) FROM images").fetchone()[0]
            print(f"📊 Total Images in DB: {image_count}")
        except sqlite3.OperationalError:
            print("❌ 'images' table not found.")

        conn.close()
    except Exception as e:
        print(f"❌ Failed to connect: {e}")
