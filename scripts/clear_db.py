import sys
from pathlib import Path

# Add src to path
sys.path.append(str(Path.cwd()))

from src.index.database import Database


def main():
    print("Initializing database connection...")
    try:
        db = Database()
        print(f"Targeting database at: {db.db_path}")

        print("Clearing all data...")
        stats = db.reset_all_data()

        print("\nDeletion Complete:")
        print(f"- Sources deleted: {stats['sources_deleted']}")
        print(f"- Chunks deleted: {stats['chunks_deleted']}")
        print(f"- Images deleted: {stats['images_deleted']}")

    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
