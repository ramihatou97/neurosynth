import asyncio
import logging
from pathlib import Path

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

from index.database import Database
from index.precision_search import PrecisionSearchEngine


def verify_integration():
    print("🚀 Verifying NeuroLi Metadata Integration...")

    # 1. Setup Engine & AI
    from ai.client import AIClient
    from config import settings

    settings.embedding_model = "voyage-large-2-instruct"  # Safety

    ai = AIClient()
    db_path = Path("/Users/ramihatoum/neurosynth/neurosynth.db")
    db = Database(db_path=db_path)
    engine = PrecisionSearchEngine(db, colbert_enabled=False)

    # 2. Check Manager (Same)
    if not engine.metadata_manager:
        print("❌ Metadata Manager NOT initialized.")
        return

    if not engine.metadata_manager.is_loaded:
        print("❌ Metadata Manager NOT loaded (Scan failed?).")
        return

    print("✅ Metadata Manager Loaded.")

    # 3. Check Stats
    subs = engine.metadata_manager.get_all_subspecialties()
    print(f"📋 Found Subspecialties: {subs}")

    if not subs:
        print("⚠️ No subspecialties found in scan. Check library path.")

    # 4. Search with Filter
    query = "MCA Aneurysm clipping"
    target_sub = "Vascular"

    print(f"\nExample Search: '{query}' [Filter: {target_sub}]")

    # Generate Embedding
    print("  Generating embedding...")
    emb = ai.get_embedding(query)

    # Call search (Note: PrecisionSearchEngine.search returns PrecisionRetrievalResult NOT list)
    # Wait, looking at code in 732, it returns PrecisionRetrievalResult? No, existing search returns list[SearchResult].
    # But my replace_file_content in 727 tried to change signature.
    # The view in 732 showed: -> PrecisionRetrievalResult (line 277).
    # But currently `search` implementation returns `final_results` which is a list.
    # It seems the type hint says PrecisionRetrievalResult but implementation returns list?
    # Let's inspect the return.

    results = engine.search(
        query, query_embedding=emb, top_k=5, filter_subspecialty=target_sub
    )

    # Handle return type
    if hasattr(results, "results"):
        res_list = results.results
    else:
        res_list = results

    print(f"Found {len(res_list)} results.")

    for r in res_list:
        # r is SearchResult or PrecisionResult
        chunk = r.chunk if hasattr(r, "chunk") else r
        meta = chunk.metadata
        print(
            f"   - {chunk.source_title} | Sub: {meta.get('subspecialty')} | Auth: {meta.get('authority_score')}"
        )

        if meta.get("subspecialty") != target_sub:
            print(f"     ❌ FILTER FAIL: Got {meta.get('subspecialty')}")
        else:
            print("     ✅ Match")

    # 5. Search without Filter
    print(f"\nControl Search: '{query}' [No Filter]")
    results_control = engine.search(query, query_embedding=emb, top_k=5)

    if hasattr(results_control, "results"):
        ctrl_list = results_control.results
    else:
        ctrl_list = results_control

    # ...
    # 5. Search without Filter
    print(f"\nControl Search: '{query}' [No Filter]")
    results_control = engine.search(query, query_embedding=emb, top_k=5)

    if hasattr(results_control, "results"):
        ctrl_list = results_control.results
    else:
        ctrl_list = results_control

    print("Top result metadata debugging:")
    if ctrl_list:
        chunk = ctrl_list[0].chunk if hasattr(ctrl_list[0], "chunk") else ctrl_list[0]
        print(f"   - Source ID: '{chunk.source_id}'")
        print(f"   - Source Title: '{chunk.source_title}'")
        print(f"   - Metadata: {chunk.metadata}")

        # Check Manager Keys
        print(f"   - Manager has {len(engine.metadata_manager.file_map)} keys.")

        # Try finding by title
        if chunk.source_title in engine.metadata_manager.file_map:
            print("   - MATCH FOUND via Title!")
        else:
            print("   - NO MATCH via Title.")

        if chunk.source_id in engine.metadata_manager.file_map:
            print("   - MATCH FOUND via ID!")
        else:
            print("   - NO MATCH via ID.")

        # Check source map resolution
        resolved_filename = engine.source_map.get(chunk.source_id)
        print(f"   - Resolved Filename from Source Map: '{resolved_filename}'")

        if resolved_filename in engine.metadata_manager.file_map:
            print(
                f"   - MATCH FOUND via Resolved Filename! Meta: {engine.metadata_manager.file_map[resolved_filename]}"
            )
        else:
            print("   - NO MATCH via Resolved Filename.")

        # Check Full Path in Source Map
        # Note: source_map currently stores only filename.
        # But we need full path to verify folder structure.

        src_meta = engine.db.get_source(chunk.source_id)
        if src_meta:
            print(f"   - DB Full Path: {src_meta.file_path}")

    print("\n✅ Verification Complete.")


if __name__ == "__main__":
    verify_integration()
