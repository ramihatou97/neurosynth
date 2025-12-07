
import sys
import json
import argparse
from ragatouille import RAGPretrainedModel

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--index_path", default="/app/data/colbert_index/.ragatouille/colbert/indexes/neurosynth_v1")
    args = parser.parse_args()

    # 1. Load Input
    with open(args.input, 'r') as f:
        data = json.load(f)
    
    query = data["query"]
    k = data.get("k", 10)

    # 2. Load Index (This is the slow part)
    # We allow the path to be overridden if needed, or fail if missing
    try:
        RAG = RAGPretrainedModel.from_index(args.index_path)
    except Exception as e:
        print(f"Index load error: {e}", file=sys.stderr)
        sys.exit(1)

    # 3. Search
    results = RAG.search(query, k=k)

    # 4. Output
    with open(args.output, 'w') as f:
        json.dump({"results": results}, f)

if __name__ == "__main__":
    main()
