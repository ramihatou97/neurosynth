#!/usr/bin/env python3
"""
ColBERT Search Script
====================
Runs inside Docker container to search a ColBERT index.

Usage:
    python search.py --input /tmp/search_input.json --output /tmp/search_output.json

Input JSON format:
{
    "query": "What is the position of the facial nerve?",
    "k": 20,
    "index_name": "deep_dx_v1"
}

Output JSON format:
{
    "results": [
        {"id": "chunk_042", "score": 0.91, "text": "..."},
        ...
    ],
    "query": "original query",
    "time_ms": 89.2
}
"""

import json
import argparse
import time
import sys
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description="ColBERT Search")
    parser.add_argument("--input", required=True, help="Input JSON file path")
    parser.add_argument("--output", required=True, help="Output JSON file path")
    parser.add_argument("--index-dir", default="/app/data/colbert_index", help="Index directory")
    args = parser.parse_args()
    
    start_time = time.time()
    
    try:
        # Load input
        with open(args.input, 'r') as f:
            data = json.load(f)
        
        query = data["query"]
        k = data.get("k", 20)
        index_name = data.get("index_name", "deep_dx_v1")
        
        # Find index path
        index_path = Path(args.index_dir) / index_name
        if not index_path.exists():
            raise FileNotFoundError(f"Index not found: {index_path}")
        
        # Load searcher
        from ragatouille import RAGPretrainedModel
        model = RAGPretrainedModel.from_index(str(index_path))
        
        # Search
        search_results = model.search(query=query, k=k)
        
        # Format results
        results = []
        for r in search_results:
            results.append({
                "id": r.get("document_id", r.get("id", "")),
                "score": float(r["score"]),
                "text": r["content"][:500]  # Truncate
            })
        
        elapsed_ms = (time.time() - start_time) * 1000
        
        output = {
            "results": results,
            "query": query,
            "time_ms": elapsed_ms,
            "index_name": index_name
        }
        
        with open(args.output, 'w') as f:
            json.dump(output, f, indent=2)
        
        print(f"✅ Found {len(results)} results in {elapsed_ms:.1f}ms")
        
    except Exception as e:
        error_output = {
            "error": str(e),
            "results": [],
            "query": data.get("query", "") if 'data' in dir() else "",
            "time_ms": (time.time() - start_time) * 1000
        }
        with open(args.output, 'w') as f:
            json.dump(error_output, f)
        print(f"❌ Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
