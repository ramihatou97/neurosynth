
import sys
import json
import argparse
import os
from ragatouille import RAGPretrainedModel

def main():
    print("🦞 Docker-Side Indexing Started...", file=sys.stderr)
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--index_name", required=True)
    parser.add_argument("--index_root", default="/app/data/colbert_index/.ragatouille/") 
    args = parser.parse_args()

    # 1. Load Documents
    with open(args.input, 'r') as f:
        data = json.load(f)
    
    documents = data["documents"] # List of strings or dicts
    # If dicts with 'content' key, extract content
    if documents and isinstance(documents[0], dict):
        documents = [d.get("content", "") for d in documents]

    print(f"📥 Loaded {len(documents)} documents.", file=sys.stderr)

    # 2. Initialize Model
    RAG = RAGPretrainedModel.from_pretrained("colbert-ir/colbertv2.0")

    # 3. Create Index
    # .ragatouille path handling is tricky. We'll set the ROOT.
    # index_path = RAG.index(index_name=args.index_name, collection=documents, split_documents=False)
    # To control path better:
    print(f"⚙️  Indexing to {args.index_root}...", file=sys.stderr)
    
    # Run Indexing
    path = RAG.index(
        index_name=args.index_name,
        collection=documents,
        split_documents=False, # Assume pre-chunked for now or let it chunk? Let's say pre-chunked if possible, but boolean is ignored if not raw text
    )
    
    print(f"✅ Index created at {path}", file=sys.stderr)

if __name__ == "__main__":
    main()
