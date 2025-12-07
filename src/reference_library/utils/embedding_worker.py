"""Subprocess-based embedding worker to avoid GIL blocking UI."""
import os
import sys
import json
from pathlib import Path

# Prevent tokenizers deadlock
os.environ["TOKENIZERS_PARALLELISM"] = "false"


def embed_texts(texts: list[str], model_name: str) -> list[list[float]]:
    """Embed texts using SentenceTransformer.

    This runs in a subprocess, so it has its own GIL and won't block the main UI.
    """
    from sentence_transformers import SentenceTransformer

    model = SentenceTransformer(model_name)
    embeddings = model.encode(texts, show_progress_bar=False)
    return embeddings.tolist()


if __name__ == "__main__":
    """Worker process entry point.

    Reads JSON from stdin: {"texts": [...], "model": "..."}
    Writes JSON to stdout: {"embeddings": [[...], ...]}
    """
    # Read input from stdin
    input_data = json.loads(sys.stdin.read())
    texts = input_data["texts"]
    model_name = input_data["model"]

    # Compute embeddings
    embeddings = embed_texts(texts, model_name)

    # Write output to stdout
    print(json.dumps({"embeddings": embeddings}))
