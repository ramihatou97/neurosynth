import logging
import sys
from datetime import datetime
from pathlib import Path

# Add src to path
sys.path.append(str(Path(__file__).parent / "src"))

from deep_dx.knowledge.metadata_manager import MetadataManager
from index.database import Database
from models import DocumentType, SourceMetadata, Specialty

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("InitDB")


def initialize_database():
    print("🚀 Initializing Database from NeuroLi Library...")

    # 1. Init Database
    db = Database()

    # 2. Init Metadata Manager (Scans disk)
    manager = MetadataManager()
    if not manager.is_loaded:
        print("❌ Failed to load MetadataManager. Check library path.")
        return

    print(f"   -> Found {len(manager.file_map)} files in library.")

    # 3. Populate Database
    count = 0
    print("   -> Populating 'sources' table...")

    for filename, meta in manager.file_map.items():
        # Reconstruct full path? MetadataManager stores dict, we need to find items.
        # file_map is filename -> metadata.
        # But where is the full path?
        # MetadataManager._scan_library iterates rglob.
        # But file_map doesn't store full path?
        # Wait, let's look at MetadataManager again.
        pass

    # Re-reading MetadataManager code:
    # It stores self.file_map[filename] = meta
    # It doesn't store the full path in file_map! That's a flaw if filenames aren't unique.
    # But for now, let's re-scan in this script or modify MetadataManager?
    # Modifying MetadataManager is better, but this script is a quick fix.
    # I'll just re-scan using the same logic but inserting to DB.

    library_root = Path("/Users/ramihatoum/Desktop/NeuroLi")

    for file_path in library_root.rglob("*.pdf"):
        filename = file_path.name
        meta = manager.resolve_metadata_from_path(str(file_path))

        # Create SourceMetadata
        # We use filename (or hash) as ID?
        # Let's use MD5 of filename for ID to be consistent?
        # Or just filename if unique enough?
        # Existing logic used a hash. Let's use a simple hash of the path.
        import hashlib

        source_id = hashlib.md5(str(file_path).encode()).hexdigest()[:12]

        doc_type = (
            DocumentType.TEXTBOOK
            if meta.get("collection") == "Textbooks"
            else DocumentType.CHAPTER
        )
        specialty = Specialty.GENERAL

        # Try to map specialty string to Enum
        try:
            s_str = meta.get("subspecialty", "General").upper()
            if s_str in Specialty.__members__:
                specialty = Specialty[s_str]
        except:
            pass

        source = SourceMetadata(
            id=source_id,
            title=file_path.stem,
            doc_type=doc_type,
            file_path=file_path,
            authors=None,
            year=None,
            specialty=specialty,
            total_pages=0,  # We don't know yet without opening
            processed_at=datetime.now(),
        )

        db.insert_source(source)
        count += 1
        if count % 100 == 0:
            print(f"      Processed {count}...")

    print(f"✅ Database population complete. Inserted {count} sources.")


if __name__ == "__main__":
    initialize_database()
