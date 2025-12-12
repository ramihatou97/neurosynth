import logging
import sqlite3
import sys
from pathlib import Path

# Setup paths
project_root = Path(__file__).resolve().parent.parent
sys.path.append(str(project_root / "src"))

from config import settings

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("ImageHealth")


def check_sqlite():
    """Check SQLite database status."""
    db_path = settings.database_path
    if not db_path.exists():
        return False, "Database file not found"

    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Check images table
        try:
            cursor.execute("SELECT COUNT(*) FROM images")
            count = cursor.fetchone()[0]

            # Check embeddings
            cursor.execute("SELECT COUNT(*) FROM images WHERE embedding IS NOT NULL")
            embedded_count = cursor.fetchone()[0]

            return True, f"Images: {count}, With Embeddings: {embedded_count}"
        except sqlite3.OperationalError:
            return False, "Table 'images' does not exist"
        finally:
            conn.close()
    except Exception as e:
        return False, f"Connection failed: {e}"


def check_qdrant():
    """Check Qdrant status. Prioritizes Docker server over local path."""
    try:
        from qdrant_client import QdrantClient

        # Try Docker server first (localhost:6333), then fall back to local path
        connection_attempts = [
            (
                "Docker (localhost:6333)",
                lambda: QdrantClient(host="localhost", port=6333),
            ),
        ]

        # Add local path as fallback if configured
        if settings.qdrant_path:
            connection_attempts.append(
                (
                    f"Local ({settings.qdrant_path})",
                    lambda p=settings.qdrant_path: QdrantClient(path=str(p)),
                )
            )

        for loc, connect_fn in connection_attempts:
            try:
                client = connect_fn()
                collections = client.get_collections().collections
                names = [c.name for c in collections]

                if "neurosurgical_figures_hybrid" in names:
                    info = client.get_collection("neurosurgical_figures_hybrid")
                    return (
                        True,
                        f"Connected ({loc}). Collection found. Points: {info.points_count}",
                    )
                else:
                    # Connected but collection missing - continue to try other sources
                    continue
            except Exception:
                # Connection failed, try next
                continue

        # All attempts failed or collection not found anywhere
        return (
            False,
            "Collection 'neurosurgical_figures_hybrid' not found (tried Docker + local)",
        )

    except ImportError:
        return False, "qdrant-client not installed"


def check_integration():
    """Check if integration code exists."""
    import importlib.util

    # Check category_outline.py
    spec = importlib.util.spec_from_file_location(
        "category_outline",
        project_root / "src/neurosynth/synthesis/category_outline.py",
    )
    if spec and spec.loader:
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        if hasattr(module, "assign_images_to_outline"):
            return True, "assign_images_to_outline found"
        else:
            return False, "assign_images_to_outline MISSING in category_outline.py"

    return False, "category_outline.py not found"


def run_health_check():
    print("\n--- NeuroSynth Image Pipeline Health Check ---")

    # 1. SQLite
    ok, msg = check_sqlite()
    status = "✅" if ok else "❌"
    print(f"{status} SQLite: {msg}")
    sqlite_ok = ok

    # 2. Qdrant
    ok, msg = check_qdrant()
    status = "✅" if ok else "❌"
    print(f"{status} Qdrant: {msg}")
    qdrant_ok = ok

    # 3. Integration Code
    ok, msg = check_integration()
    status = "✅" if ok else "❌"
    print(f"{status} Code Integration: {msg}")
    code_ok = ok

    print("-" * 40)
    if sqlite_ok and qdrant_ok and code_ok:
        print("🚀 PIPELINE STATUS: HEALTHY")
    elif code_ok:
        print("⚠️  PIPELINE STATUS: CODE READY, DATA MISSING (Run backfill/extraction)")
    else:
        print("🚨 PIPELINE STATUS: BROKEN")


if __name__ == "__main__":
    run_health_check()
