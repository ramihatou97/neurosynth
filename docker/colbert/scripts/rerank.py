#!/usr/bin/env python3
"""
ColBERT Rerank Script
====================
Runs inside Docker container to rerank documents using ColBERT.

Usage:
    python rerank.py --input /tmp/input.json --output /tmp/output.json

Input JSON format:
{
    "query": "What is anterior to the facial nerve?",
    "documents": ["doc1 text...", "doc2 text...", ...],
    "k": 20
}

Output JSON format:
{
    "results": [
        {"index": 3, "score": 0.89, "text": "doc3 text..."},
        {"index": 1, "score": 0.82, "text": "doc1 text..."},
        ...
    ],
    "query": "original query",
    "time_ms": 145.3
}
"""

import argparse
import json
import sys
import time
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description="ColBERT Reranking")
    parser.add_argument("--input", required=True, help="Input JSON file path")
    parser.add_argument("--output", required=True, help="Output JSON file path")
    parser.add_argument(
        "--model", default="colbert-ir/colbertv2.0", help="ColBERT model"
    )
    args = parser.parse_args()

    start_time = time.time()

    try:
        # Load input
        with open(args.input) as f:
            data = json.load(f)

        query = data["query"]
        documents = data["documents"]
        k = data.get("k", 20)

        if len(documents) == 0:
            # No documents to rerank
            result = {"results": [], "query": query, "time_ms": 0}
            with open(args.output, "w") as f:
                json.dump(result, f)
            return

        # Load ColBERT model
        from ragatouille import RAGPretrainedModel

        model = RAGPretrainedModel.from_pretrained(args.model)

        # Perform reranking
        rerank_results = model.rerank(
            query=query, documents=documents, k=min(k, len(documents))
        )

        # Format results
        results = []
        for r in rerank_results:
            results.append(
                {
                    "index": r["result_index"],
                    "score": float(r["score"]),
                    "text": r["content"][:500],  # Truncate for response
                }
            )

        elapsed_ms = (time.time() - start_time) * 1000

        output = {
            "results": results,
            "query": query,
            "time_ms": elapsed_ms,
            "model": args.model,
        }

        # Write output
        with open(args.output, "w") as f:
            json.dump(output, f, indent=2)

        print(
            f"✅ Reranked {len(documents)} documents to top {len(results)} in {elapsed_ms:.1f}ms"
        )

    except Exception as e:
        error_output = {
            "error": str(e),
            "results": [],
            "query": data.get("query", "") if "data" in dir() else "",
            "time_ms": (time.time() - start_time) * 1000,
        }
        with open(args.output, "w") as f:
            json.dump(error_output, f)
        print(f"❌ Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
