import sqlite3
import sys
from pathlib import Path

# Ensure src is in path
root_dir = Path(__file__).parent.parent
sys.path.append(str(root_dir))

from src.config import settings


def main():
    db_path = settings.database_path
    if not db_path.exists():
        print(f"❌ Database not found at {db_path}")
        return

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        # Initial Counts
        sources = cursor.execute("SELECT COUNT(*) FROM sources").fetchone()[0]
        chunks = cursor.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]
        images = cursor.execute("SELECT COUNT(*) FROM images").fetchone()[0]

        print("📊 Index Status:")
        print(f"  Sources: {sources}")
        print(f"  Chunks:  {chunks}")
        print(f"  Images:  {images}")

        # Detail
        if sources > 0:
            print("\n📚 Indexed Sources:")
            rows = cursor.execute("SELECT title, id FROM sources LIMIT 5").fetchall()
            for r in rows:
                print(f"  - {r[0]} ({r[1]})")

    except Exception as e:
        print(f"❌ Error querying DB: {e}")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
