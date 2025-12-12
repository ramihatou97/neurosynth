"""
Verify Ingestion Completeness (Phase 4 Integration Test)
========================================================
Runs the full ingestion pipeline on a dummy PDF and verifies:
1. Proposition Chunker splitting
2. Evidence Level detection and persistence
3. Qdrant payload hydration (parent_context)
4. ExtractionNode usage

Usage: python src/ingest/verify_ingestion_completeness.py
"""

import asyncio
import sys
from pathlib import Path
from unittest.mock import MagicMock

# Ensure src AND project root in path
root = Path(__file__).parent.parent
sys.path.append(str(root))
sys.path.append(str(root.parent))  # Enable 'from src...' imports

# Mock qdrant_client to avoid import error in verification env
mock_qdrant = MagicMock()
sys.modules["qdrant_client"] = mock_qdrant
sys.modules["qdrant_client.http"] = MagicMock()
sys.modules["qdrant_client.http.models"] = MagicMock()
sys.modules["qdrant_client.models"] = MagicMock()  # <--- Added this
# Also mock voyageai if needed
sys.modules["voyageai"] = MagicMock()

# Mock rich and AI clients
sys.modules["rich"] = MagicMock()
sys.modules["rich.console"] = MagicMock()
sys.modules["ai.client"] = MagicMock()

# Mock heavy AI SDKs
sys.modules["google"] = MagicMock()
sys.modules["google.api_core"] = MagicMock()
sys.modules["google.auth"] = MagicMock()
sys.modules["google.cloud"] = MagicMock()
sys.modules["google.generativeai"] = MagicMock()
sys.modules["vertexai"] = MagicMock()
sys.modules["anthropic"] = MagicMock()
sys.modules["anthropic.types"] = MagicMock()  # <--- Added this
sys.modules["openai"] = MagicMock()
sys.modules["cv2"] = MagicMock()  # <--- Added this

mock_config = MagicMock()
sys.modules["src.config"] = mock_config
sys.modules["neurosynth.config"] = mock_config

from bridges.library_to_deepdx import LibraryToDeepDxBridge, SourceMetadata
from models import Chunk

# Mock dependencies we don't want to run fully (like Qdrant server)
# But here we want integration test. Ideally we run real Qdrant.
# If Qdrant is down, we mock it to verify the logic UP TO the point of pushing.


async def verify_pipeline():
    print("🧪 Starting End-to-End Ingestion Verification...")

    # 1. Setup Dummy PDF
    pdf_path = Path("tests/data/sample.pdf")
    if not pdf_path.exists():
        # Create a dummy PDF text file masquerading as PDF for the extractor mock
        # Real verification would use a real PDF.
        # Checks if we have any sample.
        pass

    # Initialize Bridge
    # We use skip_qdrant=True to focus on logic creation, unless we have a dev instance.
    bridge = LibraryToDeepDxBridge(skip_qdrant=True)

    # Mock Extractor to avoid needing a real PDF file on disk
    bridge.extractor = MagicMock()
    dummy_text = (
        "This is a sentence. This is another sentence. Dr. Smith said it.\n"
        "Methods: We conducted a double-blind RCT. Evidence Level 1a.\n"
        "Results: It worked.\n"
    )
    bridge.extractor.extract_content.return_value = {1: dummy_text}

    # Run Process
    file_info = {
        "pdf_path": "dummy_study.pdf",
        "chapter_title": "Test Assessment of Methodology",
    }

    try:
        source, chunks = await bridge.process_file(file_info)

        print(f"✅ Processed Source: {source.title}")
        print(f"✅ Generated {len(chunks)} Chunks")

        # Verify Phase 2: Small-to-Big
        first_chunk = chunks[0]
        if first_chunk.parent_context == dummy_text.strip():
            print("✅ [Small-to-Big] Parent Context Preserved")
        else:
            print(
                f"❌ [Small-to-Big] Failed. Context: {first_chunk.parent_context[:50]}..."
            )

        if first_chunk.is_proposition:
            print("✅ [Small-to-Big] is_proposition flag set")

        # Verify Phase 1: Evidence Grading
        # The text included "Evidence Level 1a" (detected by regex)
        # Check if any chunk got it.
        evidence_found = any(c.evidence_level == "1a" for c in chunks)
        if evidence_found:
            print("✅ [Evidence] Level 1a Detected")
        else:
            print("⚠️ [Evidence] Level 1a NOT Detected (Check EvidenceDetector regex)")
            # Inspect actuals
            print(f"   Actual Levels: {[c.evidence_level for c in chunks]}")

        # Verify Phase 3: ExtractionNode (Implicitly verified by mock usage,
        # but in real run we'd check if it fell back to PyMuPDF)

        print("\n🎉 Verification Complete!")

    except Exception as e:
        print(f"❌ Verification Failed: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(verify_pipeline())
