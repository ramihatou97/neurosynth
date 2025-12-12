import asyncio
import sys
from pathlib import Path

# Add src to path
sys.path.append(str(Path(__file__).parent.parent.parent))

from src.ai.client import AIClient
from src.deep_dx.config import get_deepdx_settings
from src.index.database import Database
from src.index.precision_search import PrecisionSearchEngine
from src.synthesize.engine import SynthesisEngine

deep_dx_settings = get_deepdx_settings()


async def main():
    print("🏥 Starting Deep-DX Synthesis Engine Test...")

    # 1. Initialize Database
    # We use the existing DB if available, or create a dummy one for the test structure to pass
    db_path = Path("neurosynth.db")
    print(f"📂 Database: {db_path}")
    db = Database(db_path=db_path)

    # 2. Check ColBERT status
    print("🦞 Initializing Precision Search (ColBERT)...")
    search_engine = PrecisionSearchEngine(db, colbert_enabled=True)
    if not search_engine.colbert:
        print("⚠️  ColBERT Client failed to initialize.")
    else:
        print("✅ ColBERT Client initialized.")

    # 3. Initialize Synthesis Engine (AIClient is instantiated per-request)
    print("🧠 Initializing Synthesis Engine...")
    synthesis_engine = SynthesisEngine(
        db=db,
        search_engine=search_engine,  # Passing PrecisionSearchEngine
        ai_client=None,  # AIClient instantiated per-request via async context
    )

    # 4. Run Synthesis (async)
    topic = "Translabyrinthine approach for acoustic neuroma"
    print(f"🧪 Synthesizing Chapter: '{topic}'...")

    try:
        async with AIClient() as ai_client:
            chapter = await synthesis_engine.synthesize_chapter_async(
                topic=topic, template_name="surgical_procedure", ai_client=ai_client
            )

        print("\n✅ Synthesis Complete!")
        print(f"Title: {chapter.topic}")
        print(f"Total Sections: {len(chapter.sections)}")
        print(f"Sources Used: {len(chapter.sources)}")

        for section in chapter.sections:
            print(f"\n--- Section: {section.title} ---")
            print(f"Content Length: {len(section.content)} chars")
            print(f"Images: {len(section.images)}")
            print(f"Snippet: {section.content[:100]}...")

    except Exception as e:
        print(f"\n❌ Synthesis Failed: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
