import json
import logging
import math
import re
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List

logger = logging.getLogger(__name__)

# Default persistence path
DEFAULT_BM25_INDEX_PATH = Path.home() / ".neurosynth" / "bm25_index" / "index.json"


class BM25Retriever:
    """
    Lightweight in-memory BM25 implementation for Hybrid Search.
    Ideal for < 100,000 chunks.
    """

    def __init__(self, chunks: list[dict[str, Any]]):
        """
        Initialize with a list of chunks/docs.
        chunks: List of dicts, must have 'content' and 'id' fields.
        """
        self.chunks = chunks
        self.corpus_size = len(chunks)
        self.avgdl = 0
        self.doc_freqs = []
        self.idf = {}
        self.doc_len = []
        self.tokenized_corpus = []

        # Hyperparameters
        self.k1 = 1.5
        self.b = 0.75

        self._index_corpus()

    def _tokenize(self, text: str) -> list[str]:
        """Simple regex analyzer."""
        return [w.lower() for w in re.findall(r"\b\w\w+\b", text)]

    def _index_corpus(self):
        """Builds stats for BM25."""
        if not self.chunks:
            return

        print(f"Index: Building BM25 for {self.corpus_size} chunks...")
        total_len = 0

        for chunk in self.chunks:
            tokens = self._tokenize(chunk.get("content", ""))
            self.tokenized_corpus.append(tokens)
            self.doc_len.append(len(tokens))
            total_len += len(tokens)

            # Count frequencies
            freqs = Counter(tokens)
            self.doc_freqs.append(freqs)

            for token in freqs.keys():
                self.idf[token] = self.idf.get(token, 0) + 1

        self.avgdl = total_len / self.corpus_size

        # Calculate IDF
        for token, freq in self.idf.items():
            self.idf[token] = math.log(
                1 + (self.corpus_size - freq + 0.5) / (freq + 0.5)
            )

    def _get_score(self, query_tokens: list[str], index: int) -> float:
        score = 0.0
        doc_tokens = self.doc_freqs[index]
        doc_len = self.doc_len[index]

        for token in query_tokens:
            if token not in doc_tokens:
                continue

            freq = doc_tokens[token]
            numerator = self.idf.get(token, 0) * freq * (self.k1 + 1)
            denominator = freq + self.k1 * (1 - self.b + self.b * doc_len / self.avgdl)
            score += numerator / denominator

        return score

    def search(self, query: str, top_k: int = 20) -> list[dict[str, Any]]:
        """
        Search the corpus.
        Returns list of (chunk, score).
        """
        if not self.chunks:
            return []

        query_tokens = self._tokenize(query)
        scores = []

        for i in range(self.corpus_size):
            score = self._get_score(query_tokens, i)
            if score > 0:
                scores.append((self.chunks[i], score))

        # Sort desc
        scores.sort(key=lambda x: x[1], reverse=True)
        return scores[:top_k]

    def add_documents(self, new_chunks: list[dict[str, Any]]) -> int:
        """
        Incrementally add new documents to the index.

        Args:
            new_chunks: List of dicts with 'content' and 'id' fields

        Returns:
            Number of documents added
        """
        if not new_chunks:
            return 0

        added = 0
        for chunk in new_chunks:
            content = chunk.get("content", "")
            if not content:
                continue

            tokens = self._tokenize(content)
            self.tokenized_corpus.append(tokens)
            self.doc_len.append(len(tokens))
            self.chunks.append(chunk)

            # Update frequencies
            freqs = Counter(tokens)
            self.doc_freqs.append(freqs)

            for token in freqs.keys():
                self.idf[token] = self.idf.get(token, 0) + 1

            added += 1

        # Recalculate corpus stats
        self.corpus_size = len(self.chunks)

        if self.corpus_size > 0:
            total_len = sum(self.doc_len)
            self.avgdl = total_len / self.corpus_size

            # Recalculate IDF for all terms
            for token, freq in self.idf.items():
                self.idf[token] = math.log(
                    1 + (self.corpus_size - freq + 0.5) / (freq + 0.5)
                )

        return added

    def get_document_count(self) -> int:
        """Return the number of indexed documents."""
        return self.corpus_size

    def save(self, path: Path | str | None = None) -> bool:
        """
        Save the BM25 index to disk for persistence.

        Args:
            path: Path to save the index. Defaults to ~/.neurosynth/bm25_index/index.json

        Returns:
            True if saved successfully, False otherwise
        """
        import dataclasses

        save_path = Path(path) if path else DEFAULT_BM25_INDEX_PATH
        save_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            # Prepare chunks for serialization (handle dataclasses)
            serializable_chunks = []
            for c in self.chunks:
                c_copy = c.copy()
                if "chunk_obj" in c_copy and dataclasses.is_dataclass(
                    c_copy["chunk_obj"]
                ):
                    c_copy["chunk_obj"] = dataclasses.asdict(c_copy["chunk_obj"])
                serializable_chunks.append(c_copy)

            # Serialize state - convert Counter objects to dicts for JSON
            state = {
                "chunks": serializable_chunks,
                "corpus_size": self.corpus_size,
                "avgdl": self.avgdl,
                "doc_freqs": [dict(freq) for freq in self.doc_freqs],
                "idf": self.idf,
                "doc_len": self.doc_len,
                "tokenized_corpus": self.tokenized_corpus,
                "k1": self.k1,
                "b": self.b,
            }

            with open(save_path, "w") as f:
                json.dump(state, f)

            logger.info(
                f"BM25 index saved: {self.corpus_size} documents -> {save_path}"
            )
            return True

        except Exception as e:
            logger.error(f"Failed to save BM25 index: {e}")
            return False

    @classmethod
    def load(cls, path: Path | str | None = None) -> "BM25Retriever | None":
        """
        Load a BM25 index from disk.

        Args:
            path: Path to load the index from. Defaults to ~/.neurosynth/bm25_index/index.json

        Returns:
            BM25Retriever instance if loaded successfully, None otherwise
        """
        from src.models import Chunk  # Lazy import to avoid circular dependencies

        load_path = Path(path) if path else DEFAULT_BM25_INDEX_PATH

        if not load_path.exists():
            logger.info(f"No BM25 index found at {load_path}")
            return None

        try:
            with open(load_path) as f:
                state = json.load(f)

            # Create empty instance and restore state
            instance = cls.__new__(cls)

            # Restore chunks and convert dicts back to Chunk objects
            restored_chunks = []
            for c in state["chunks"]:
                if "chunk_obj" in c and isinstance(c["chunk_obj"], dict):
                    # We assume it matches Chunk schema.
                    # If schema changed, this might fail, necessitating versioning.
                    try:
                        c["chunk_obj"] = Chunk(**c["chunk_obj"])
                    except Exception as e:
                        logger.warning(f"Failed to reconstruct Chunk object: {e}")
                        # Fallback: keep as dict or remove? defaulting to dict might break unified_search
                restored_chunks.append(c)

            instance.chunks = restored_chunks
            instance.corpus_size = state["corpus_size"]
            instance.avgdl = state["avgdl"]
            instance.doc_freqs = [Counter(freq) for freq in state["doc_freqs"]]
            instance.idf = state["idf"]
            instance.doc_len = state["doc_len"]
            instance.tokenized_corpus = state["tokenized_corpus"]
            instance.k1 = state.get("k1", 1.5)
            instance.b = state.get("b", 0.75)

            logger.info(
                f"BM25 index loaded: {instance.corpus_size} documents <- {load_path}"
            )
            return instance

        except Exception as e:
            logger.error(f"Failed to load BM25 index: {e}")
            return None

    @classmethod
    def load_or_create(
        cls, chunks: list[dict[str, Any]] | None = None, path: Path | str | None = None
    ) -> "BM25Retriever":
        """
        Load existing index from disk, or create new one from chunks.

        Args:
            chunks: Chunks to index if no saved index exists
            path: Path to the index file

        Returns:
            BM25Retriever instance (loaded or newly created)
        """
        # Try to load existing index
        instance = cls.load(path)
        if instance is not None:
            return instance

        # Create new index from chunks
        logger.info("Creating new BM25 index...")
        return cls(chunks or [])
