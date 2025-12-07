import json
import sys
from pathlib import Path

import faiss
import numpy as np
from deep_dx.config import get_deepdx_settings
from sentence_transformers import SentenceTransformer


def main():
    print("🔍 Testing Retrieval Pipeline...")
    settings = get_deepdx_settings()

    index_path = settings.colbert_index_path / settings.colbert_index_name

    # 1. Load Artefacts
    if not index_path.exists():
        print(f"❌ Index not found at {index_path}")
        sys.exit(1)

    print("📂 Loading Index and Metadata...")
    index = faiss.read_index(str(index_path / "index.faiss"))

    with open(index_path / "metadata.json") as f:
        chunks = json.load(f)

    print(f"  ✓ Loaded Index: {index.ntotal} vectors")
    print(f"  ✓ Loaded Metadata: {len(chunks)} chunks")

    # 2. Load Model
    print("🤖 Loading Embedding Model...")
    model = SentenceTransformer("all-MiniLM-L6-v2")

    # 3. Test Queries
    queries = [
        "What are the contraindications for lumbar puncture?",
        "Describe the approach to the pineal region.",
    ]

    for q in queries:
        print(f"\n❓ Query: '{q}'")
        emb = model.encode([q])
        faiss.normalize_L2(emb)

        # Search
        k = 3
        D, I = index.search(emb, k)

        for i in range(k):
            idx = I[0][i]
            score = D[0][i]
            chunk = chunks[idx]
            print(
                f"  [{i+1}] Score: {score:.4f} | Source: {chunk['metadata']['source']}"
            )
            print(f"      Text: {chunk['text'][:100]}...")

    print("\n✅ Smoke Test Passed!")


if __name__ == "__main__":
    main()
