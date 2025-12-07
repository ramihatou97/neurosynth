import argparse
import json
import sys

from ragatouille import RAGPretrainedModel


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    # Reranking usually doesn't need an index path, it uses the base model
    args = parser.parse_args()

    # 1. Load Input
    with open(args.input) as f:
        data = json.load(f)

    query = data["query"]
    documents = data["documents"]  # List of strings
    k = data.get("k", 10)

    # 2. Load Model (Not index, just the reranker model)
    # Note: RAGatouille can use the base model for zero-shot reranking if no index exists
    RAG = RAGPretrainedModel.from_pretrained("colbert-ir/colbertv2.0")

    # 3. Rerank
    results = RAG.rerank(query=query, documents=documents, k=k)

    # 4. Output
    with open(args.output, "w") as f:
        json.dump({"results": results}, f)


if __name__ == "__main__":
    main()
