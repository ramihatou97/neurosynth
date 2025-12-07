#!/usr/bin/env python3
"""
ColBERT Index Script
===================
Runs inside Docker container to build a ColBERT index.

Usage:
    python index.py --input /tmp/index_input.json --output-dir /app/data/colbert_index

Input JSON format:
{
    "chunks": [
        {"id": "chunk_001", "text": "chunk text..."},
        {"id": "chunk_002", "text": "chunk text..."},
        ...
    ],
    "index_name": "deep_dx_v1"
}

Output:
    Creates index at /app/data/colbert_index/{index_name}/
"""

import json
import argparse
import time
import sys
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description="ColBERT Indexing")
    parser.add_argument("--input", required=True, help="Input JSON file path")
    parser.add_argument("--output-dir", default="/app/data/colbert_index", help="Output directory")
    parser.add_argument("--model", default="colbert-ir/colbertv2.0", help="ColBERT model")
    parser.add_argument("--nbits", type=int, default=2, help="Quantization bits (2 = 16x compression)")
    args = parser.parse_args()
    
    start_time = time.time()
    
    try:
        # Load input
        with open(args.input, 'r') as f:
            data = json.load(f)
        
        chunks = data["chunks"]
        index_name = data.get("index_name", "deep_dx_v1")
        
        print(f"📚 Indexing {len(chunks)} chunks...")
        
        # Extract texts and IDs
        texts = [c["text"] for c in chunks]
        doc_ids = [c.get("id", f"doc_{i}") for i, c in enumerate(chunks)]
        
        # Load ColBERT model
        from ragatouille import RAGPretrainedModel
        model = RAGPretrainedModel.from_pretrained(args.model)
        
        # Create index
        index_path = model.index(
            collection=texts,
            document_ids=doc_ids,
            index_name=index_name,
            max_document_length=512,
            split_documents=False  # Already chunked
        )
        
        elapsed_s = time.time() - start_time
        
        # Write metadata
        metadata = {
            "index_name": index_name,
            "index_path": str(index_path),
            "num_chunks": len(chunks),
            "model": args.model,
            "nbits": args.nbits,
            "indexing_time_s": elapsed_s
        }
        
        meta_path = Path(args.output_dir) / index_name / "metadata.json"
        meta_path.parent.mkdir(parents=True, exist_ok=True)
        with open(meta_path, 'w') as f:
            json.dump(metadata, f, indent=2)
        
        print(f"✅ Index created at {index_path} in {elapsed_s:.1f}s")
        print(f"   Chunks: {len(chunks)}, Model: {args.model}")
        
    except Exception as e:
        print(f"❌ Indexing failed: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
