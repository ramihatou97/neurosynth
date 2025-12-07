import asyncio
import logging
import os
import sys
from unittest.mock import MagicMock

# Add src to path
sys.path.append("src")

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("verify_author")

from config import settings

# FORCE OVERRIDE: Match the model used by bridge_sync.py
settings.embedding_model = "voyage-large-2-instruct"
print(f"🔧 Overriding embedding model to: {settings.embedding_model}")

from ai.client import AIClient
from deep_dx.engine.synthesizer import DeepDxSynthesizer
from index.database import Database
from index.precision_search import PrecisionSearchEngine


class MockDatabase:
    def get_all_chunks(self):
        return []


def verify_author():
    print("🚀 Verifying The Author (Synthesis Pipeline)...")

    # 1. Initialize AI Client
    # Requires Keys in Env. Assuming they exist as bridge_sync.py worked.
    try:
        ai_client = AIClient()
        print("  ✓ AI Client (Voyage/Claude) initialized.")
    except Exception as e:
        print(f"  ❌ AI Client Init Failed: {e}")
        return

    # 2. Initialize Search Engine
    try:
        # DB needed for BM25 init internally, mock it to avoid issues/slowness
        db = MockDatabase()
        search_engine = PrecisionSearchEngine(
            db, colbert_enabled=False
        )  # Disable ColBERT for speed/simplicity
        print("  ✓ Search Engine initialized.")
    except Exception as e:
        print(f"  ❌ Search Engine Init Failed: {e}")
        return

    # 3. Initialize Synthesizer
    synthesizer = DeepDxSynthesizer(
        search_engine=search_engine,
        ai_client=ai_client,
        critic=None,  # Disable critic for this dry run
    )
    print("  ✓ Synthesizer initialized.")

    # 4. Run Test Query
    query = "What are the surgical approaches for Vestibular Schwannoma?"
    print(f"\n❓ Query: {query}")
    print("  ... Synthesizing answer (this calls Qdrant + Voyage + Claude) ...")

    try:
        # Note: generate_answer is synchronous in the class I viewed
        result = synthesizer.generate_answer(query)

        print("\n" + "=" * 60)
        print("📝 GENERATED ANSWER:")
        print("=" * 60)
        print(result["answer"])
        print("=" * 60)

        print(f"\n📚 Sources Used ({len(result['sources'])}):")
        for s in result["sources"]:
            print(f"  - {s}")

        print(f"\n💡 Confidence: {result['confidence']}")

        if result["confidence"] > 0.5:
            print("\n✅ SUCCESS: The Author is speaking!")
        else:
            print("\n⚠️ WARNING: Low confidence (or flagged issues).")

    except Exception as e:
        print(f"\n❌ Synthesis Failed: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    verify_author()
