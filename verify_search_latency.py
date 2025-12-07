import logging
import time

from ai.client import AIClient
from index.database import Database
from index.precision_search import PrecisionSearchEngine

# Setup Logging
logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("latency_test")


def benchmark():
    print("🚀 Starting Latency Benchmark...")

    # Init
    db = Database()
    engine = PrecisionSearchEngine(db)
    ai = AIClient()

    queries = [
        "MCA Aneurysm clipping",
        "Retrosigmoid approach for acoustic neuroma",
        "Anterior cervical discectomy complications",
    ]

    total_time = 0

    for i, q in enumerate(queries):
        print(f"\n[Run {i+1}] Query: '{q}'")

        # 1. Embed
        t0 = time.time()
        # Use explicit model to match Qdrant index (1024d)
        emb = ai.get_embeddings([q], model="voyage-large-2-instruct")[0]
        t_embed = time.time() - t0
        print(f"  - Embedding: {t_embed:.2f}s")

        # 2. Search
        t1 = time.time()
        results = engine.search(q, query_embedding=emb, top_k=5)
        t_search = time.time() - t1

        print(f"  - Search:    {t_search:.2f}s")
        print(f"  - Results:   {len(results.results)}")

        total_time += t_search

    avg_time = total_time / len(queries)
    print("\n✅ Benchmark Complete.")
    print(f"📊 Average Search Latency: {avg_time:.2f}s")


if __name__ == "__main__":
    benchmark()
