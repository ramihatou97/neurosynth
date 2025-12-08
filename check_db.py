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
        try:
            count = cursor.execute("SELECT COUNT(*) FROM sources").fetchone()[0]
            print(f"📊 Total Sources in DB: {count}")

            if count > 0:
                print("\nFirst 5 Sources:")
                rows = cursor.execute(
                    "SELECT id, title, file_path FROM sources LIMIT 5"
                ).fetchall()
                for r in rows:
                    print(f"  - [{r[0]}] {r[1]} ({r[2]})")

        except sqlite3.OperationalError as e:
            print(f"❌ Error querying sources table: {e}")
            # List tables
            tables = cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
            print(f"  Tables found: {[t[0] for t in tables]}")

        conn.close()
    except Exception as e:
        print(f"❌ Failed to connect: {e}")
