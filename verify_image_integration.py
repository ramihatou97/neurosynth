import logging
import sys
from pathlib import Path

# Add src to path to ensure imports work correctly
sys.path.append(str(Path.cwd() / "src"))

# Patch Settings BEFORE other imports to ensure the correct model is used
try:
    from config import settings

    settings.embedding_model = "voyage-large-2-instruct"
    print(f"✅ DEBUG: Force-set embedding model to: {settings.embedding_model}")
except ImportError:
    print("⚠️  Could not import config directly. Trying src.config...")
    from src.config import settings

    settings.embedding_model = "voyage-large-2-instruct"
    print(f"✅ DEBUG: Force-set embedding model to: {settings.embedding_model}")

from ai.client import AIClient
from deep_dx.engine.synthesizer import DeepDxSynthesizer
from index.database import Database
from index.precision_search import PrecisionSearchEngine

# Setup Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("verify_dx")


def verify_sync():
    print("\n🚀 Verifying Sync Synthesis with Images...")

    # Initialize components
    db_path = Path("neurosynth.db")
    if not db_path.exists():
        print(f"❌ Database not found at {db_path}")
        return

    db = Database(db_path)
    engine = PrecisionSearchEngine(db)
    ai = AIClient()

    synthesizer = DeepDxSynthesizer(engine, ai)

    # Query likely to have images (Known source: 248 Pediatric Cerebral Aneurysms)
    query = "Pediatric cerebral aneurysms management and treatment"

    print(f"🔍 Executing Query: '{query}'")
    result = synthesizer.generate_answer(query)

    print(f"\n📝 Answer Snippet:\n{result['answer'][:200]}...\n")

    images = result.get("images", [])
    print(f"📸 Images Returned: {len(images)}")

    if images:
        for i, img in enumerate(images[:5]):
            print(
                f"   {i+1}. [p.{img.page}] {Path(img.file_path).name} (Type: {img.image_type})"
            )

        print("\n✅ SUCCESS: Integrated Extracted Images into Synthesis!")
    else:
        print("⚠️  WARNING: No images returned in sync mode.")
        if result["confidence"] == 0.0:
            print("   (Note: Confidence is 0.0, maybe retrieval failed?)")


if __name__ == "__main__":
    verify_sync()
