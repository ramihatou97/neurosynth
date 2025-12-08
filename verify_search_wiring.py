import logging
import sys
from pathlib import Path

# Add src to path
sys.path.append(str(Path(__file__).parent / "src"))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("IntegrationTest")


def test_wiring():
    print("\n🔌 Testing Search Engine Wiring...\n")

    try:
        from index.database import Database
        from index.precision_search import PrecisionSearchEngine

        # Mock Database
        db = Database()

        # Initialize Engine
        print("Initializing PrecisionSearchEngine...")
        engine = PrecisionSearchEngine(
            db, colbert_enabled=False
        )  # Disable colbert to speed up init

        # Check Vision Embedder
        if engine.vision_embedder:
            print(
                f"✅ Vision Embedder initialized: {type(engine.vision_embedder).__name__}"
            )
        else:
            print("❌ Vision Embedder NOT initialized")

        # Check Qdrant Client
        if engine.qdrant and engine.qdrant.client:
            print(f"✅ Qdrant Client connected: {engine.qdrant.url}")
        else:
            print("⚠️ Qdrant Client not connected (Is Qdrant running?)")

        # Attempt to call the new internal method (Private method access for testing)
        if hasattr(engine, "_search_images_ai"):
            print("✅ _search_images_ai method exists")
        else:
            print("❌ _search_images_ai method missing")

    except Exception as e:
        print(f"❌ Wiring test failed: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    test_wiring()
