"""Voyage AI client for semantic embeddings."""

import asyncio
import hashlib
import pickle
import sqlite3
import time
from pathlib import Path
from typing import Optional

import httpx
import numpy as np
import voyageai
from rich.console import Console
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from neurosynth import get_logger
from neurosynth.config import get_settings

console = Console()
logger = get_logger("llm.voyage")

# Rate limit handling: Voyage API RateLimitError
try:
    from voyageai.error import RateLimitError as VoyageRateLimitError
except ImportError:
    # Fallback if error module structure differs
    VoyageRateLimitError = Exception

# Additional retryable exceptions
RETRYABLE_EXCEPTIONS = (
    VoyageRateLimitError,
    httpx.TimeoutException,
    httpx.ConnectError,
    httpx.ReadTimeout,
    ConnectionError,
    TimeoutError,
)


class VoyageClient:
    """Client for Voyage AI embeddings - optimized for semantic similarity."""

    def __init__(self, api_key: str | None = None, model: str | None = None):
        settings = get_settings()
        self.api_key = api_key or settings.voyage_api_key
        self.model_name = model or settings.voyage_model
        self.timeout = settings.llm_timeout
        self.max_retries = settings.llm_max_retries

        self.client = voyageai.Client(api_key=self.api_key, timeout=self.timeout)
        logger.info(f"Initialized VoyageClient with model: {self.model_name}")

    async def embed_text(self, text: str) -> np.ndarray:
        """Generate embedding for a single text."""
        embeddings = await self.embed_texts([text])
        return embeddings[0]

    async def embed_texts(
        self,
        texts: list[str],
        batch_size: int | None = None,
        use_cache: bool = True,
    ) -> list[np.ndarray]:
        """Generate embeddings for multiple texts with robust retry handling.

        Args:
            texts: List of texts to embed
            batch_size: Batch size for API calls (default from settings)
            use_cache: Whether to use persistent cache (default True)

        Returns:
            List of embedding vectors as numpy arrays
        """
        settings = get_settings()
        if batch_size is None:
            batch_size = settings.voyage_batch_size

        all_embeddings: list[np.ndarray | None] = [None] * len(texts)
        texts_to_embed: list[tuple[int, str]] = []  # (original_index, text)

        # Check persistent cache first if enabled
        if use_cache and settings.embedding_cache_enabled:
            cache = get_persistent_cache()

            # Compute hashes and check cache
            text_hashes = [PersistentEmbeddingCache.compute_content_hash(t) for t in texts]
            cached = cache.get_batch(text_hashes)

            cache_hits = 0
            for i, (text, text_hash) in enumerate(zip(texts, text_hashes)):
                if text_hash in cached:
                    all_embeddings[i] = cached[text_hash]
                    cache_hits += 1
                else:
                    texts_to_embed.append((i, text))

            if cache_hits > 0:
                logger.info(f"Cache hits: {cache_hits}/{len(texts)} ({100*cache_hits/len(texts):.1f}%)")
                console.print(
                    f"  [green]Embedding cache: {cache_hits}/{len(texts)} hits[/green]",
                    style="dim",
                )
        else:
            texts_to_embed = [(i, t) for i, t in enumerate(texts)]

        if not texts_to_embed:
            # All from cache
            return [e for e in all_embeddings if e is not None]

        logger.debug(f"Embedding {len(texts_to_embed)} texts in batches of {batch_size}")

        # Get cache reference for storing new embeddings
        cache = get_persistent_cache() if (use_cache and settings.embedding_cache_enabled) else None

        # Process texts_to_embed in batches (preserving original indices)
        for batch_start in range(0, len(texts_to_embed), batch_size):
            batch_items = texts_to_embed[batch_start : batch_start + batch_size]
            batch_indices = [idx for idx, _ in batch_items]
            batch_texts = [t[:8000] if len(t) > 8000 else t for _, t in batch_items]

            # Retry logic for rate limits and transient errors
            max_retries = self.max_retries
            retry_delay = 4  # Base delay

            for attempt in range(max_retries):
                try:
                    # Run in executor since voyageai is sync
                    loop = asyncio.get_event_loop()
                    result = await loop.run_in_executor(
                        None,
                        lambda b=batch_texts: self.client.embed(
                            b,
                            model=self.model_name,
                            input_type="document",
                        ),
                    )

                    # Validate API response before processing
                    if len(result.embeddings) != len(batch_items):
                        raise ValueError(
                            f"Voyage API returned {len(result.embeddings)} embeddings "
                            f"for {len(batch_items)} texts - possible API error"
                        )

                    # Store embeddings at correct indices and cache them
                    for j, (orig_idx, (_, text)) in enumerate(zip(batch_indices, batch_items)):
                        embedding = np.array(result.embeddings[j])
                        all_embeddings[orig_idx] = embedding

                        # Cache the new embedding
                        if cache is not None:
                            content_hash = PersistentEmbeddingCache.compute_content_hash(text)
                            cache.set(content_hash, embedding)

                    # Progress indicator for large batches
                    if len(texts_to_embed) > batch_size:
                        embedded_so_far = min(batch_start + batch_size, len(texts_to_embed))
                        console.print(
                            f"  Embedded {embedded_so_far}/{len(texts_to_embed)} texts (+ {len(texts) - len(texts_to_embed)} cached)",
                            style="dim",
                        )

                    # Small delay between batches to avoid rate limits
                    if batch_start + batch_size < len(texts_to_embed):
                        await asyncio.sleep(0.5)

                    break  # Success, exit retry loop

                except RETRYABLE_EXCEPTIONS as e:
                    if attempt < max_retries - 1:
                        # Exponential backoff with jitter
                        wait_time = min(retry_delay * (2 ** attempt), 180)  # Max 3 minutes
                        logger.warning(
                            f"Voyage API {type(e).__name__}, waiting {wait_time}s "
                            f"before retry {attempt + 2}/{max_retries}..."
                        )
                        console.print(
                            f"  [yellow]Voyage API retry {attempt + 2}/{max_retries}: "
                            f"{type(e).__name__}. Waiting {wait_time}s...[/yellow]"
                        )
                        await asyncio.sleep(wait_time)
                    else:
                        logger.error(
                            f"Voyage API failed after {max_retries} retries: "
                            f"{type(e).__name__}: {e}"
                        )
                        raise RuntimeError(
                            f"Voyage embedding failed after {max_retries} retries: {e}"
                        ) from e

                except Exception as e:
                    # Non-retryable error
                    logger.error(
                        f"Voyage API error (non-retryable) during batch "
                        f"{batch_start // batch_size + 1}: {type(e).__name__}: {e}"
                    )
                    raise

        # Return embeddings in original order (filter out any None values shouldn't happen but safety)
        final_embeddings = [e for e in all_embeddings if e is not None]
        logger.debug(f"Successfully embedded {len(final_embeddings)} texts")
        return final_embeddings

    async def compute_similarity(
        self,
        text1: str,
        text2: str,
    ) -> float:
        """Compute cosine similarity between two texts."""
        embeddings = await self.embed_texts([text1, text2])
        return float(
            np.dot(embeddings[0], embeddings[1])
            / (np.linalg.norm(embeddings[0]) * np.linalg.norm(embeddings[1]))
        )

    async def build_similarity_matrix(
        self,
        embeddings: list[np.ndarray],
    ) -> np.ndarray:
        """Build a pairwise cosine similarity matrix."""
        n = len(embeddings)
        matrix = np.zeros((n, n))

        # Stack embeddings for efficient computation
        emb_matrix = np.vstack(embeddings)

        # Normalize
        norms = np.linalg.norm(emb_matrix, axis=1, keepdims=True)
        normalized = emb_matrix / norms

        # Compute similarity matrix
        matrix = np.dot(normalized, normalized.T)

        return matrix

    async def find_similar(
        self,
        query_embedding: np.ndarray,
        corpus_embeddings: list[np.ndarray],
        top_k: int = 10,
        threshold: float = 0.0,
    ) -> list[tuple[int, float]]:
        """Find most similar items in corpus."""
        corpus_matrix = np.vstack(corpus_embeddings)

        # Normalize
        query_norm = query_embedding / np.linalg.norm(query_embedding)
        corpus_norms = np.linalg.norm(corpus_matrix, axis=1, keepdims=True)
        corpus_normalized = corpus_matrix / corpus_norms

        # Compute similarities
        similarities = np.dot(corpus_normalized, query_norm)

        # Get top-k indices above threshold
        indices = np.argsort(similarities)[::-1]
        results = []
        for idx in indices[:top_k]:
            sim = float(similarities[idx])
            if sim >= threshold:
                results.append((int(idx), sim))

        return results


class PersistentEmbeddingCache:
    """SQLite-backed embedding cache with model version invalidation.

    This cache persists embeddings to disk using SQLite with WAL mode,
    allowing for concurrent access and avoiding re-embedding on repeat runs.

    The cache key is a composite of:
    - content_hash: MD5 of the text content
    - model_name: The Voyage model used (e.g., "voyage-large-2-instruct")
    - chunk_config_hash: Hash of chunking parameters for invalidation

    Attributes:
        db_path: Path to the SQLite database file
        model_name: Name of the embedding model
        chunk_config_hash: Hash of chunking configuration
    """

    def __init__(
        self,
        cache_path: Path,
        model_name: str,
        chunk_size: int = 1000,
        chunk_overlap: int = 100,
    ):
        """
        Initialize the persistent embedding cache.

        Args:
            cache_path: Directory for the cache database
            model_name: Name of the embedding model (for invalidation)
            chunk_size: Chunk size setting (for invalidation)
            chunk_overlap: Chunk overlap setting (for invalidation)
        """
        self.db_path = cache_path / "embeddings.db"
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.model_name = model_name

        # Create config hash for invalidation when chunking params change
        config_str = f"{chunk_size}_{chunk_overlap}"
        self.chunk_config_hash = hashlib.md5(config_str.encode()).hexdigest()[:8]

        self._memory_cache: dict[tuple[str, str, str], np.ndarray] = {}
        self._init_db()

        logger.info(
            f"Initialized PersistentEmbeddingCache at {self.db_path} "
            f"(model={model_name}, config={self.chunk_config_hash})"
        )

    def _init_db(self) -> None:
        """Initialize the database schema."""
        with sqlite3.connect(self.db_path, isolation_level=None) as conn:
            # Enable WAL mode for concurrent access
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA busy_timeout=5000")
            conn.execute("PRAGMA synchronous=NORMAL")

            conn.execute("""
                CREATE TABLE IF NOT EXISTS embeddings (
                    content_hash TEXT NOT NULL,
                    model_name TEXT NOT NULL,
                    chunk_config TEXT NOT NULL,
                    embedding BLOB NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (content_hash, model_name, chunk_config)
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_model_config
                ON embeddings(model_name, chunk_config)
            """)

    def _cache_key(self, content_hash: str) -> tuple[str, str, str]:
        """Generate the cache key tuple."""
        return (content_hash, self.model_name, self.chunk_config_hash)

    @staticmethod
    def compute_content_hash(text: str) -> str:
        """Compute MD5 hash of text content."""
        return hashlib.md5(text.encode()).hexdigest()

    def get(self, content_hash: str) -> Optional[np.ndarray]:
        """
        Get cached embedding by content hash.

        Args:
            content_hash: MD5 hash of the text content

        Returns:
            Cached embedding as numpy array, or None if not found
        """
        key = self._cache_key(content_hash)

        # Check memory cache first (hot path)
        if key in self._memory_cache:
            return self._memory_cache[key]

        # Check disk cache
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute(
                    """SELECT embedding FROM embeddings
                       WHERE content_hash = ? AND model_name = ? AND chunk_config = ?""",
                    key,
                )
                row = cursor.fetchone()
                if row:
                    embedding = pickle.loads(row[0])
                    # Populate memory cache for future lookups
                    self._memory_cache[key] = embedding
                    return embedding
        except Exception as e:
            logger.warning(f"Cache lookup failed: {e}")

        return None

    def set(self, content_hash: str, embedding: np.ndarray) -> None:
        """
        Store embedding in cache.

        Args:
            content_hash: MD5 hash of the text content
            embedding: Embedding vector as numpy array
        """
        key = self._cache_key(content_hash)

        # Always update memory cache
        self._memory_cache[key] = embedding

        # Persist to disk
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute(
                    """INSERT OR REPLACE INTO embeddings
                       (content_hash, model_name, chunk_config, embedding)
                       VALUES (?, ?, ?, ?)""",
                    (*key, pickle.dumps(embedding)),
                )
        except Exception as e:
            logger.warning(f"Cache write failed: {e}")

    def get_batch(self, content_hashes: list[str]) -> dict[str, np.ndarray]:
        """
        Get multiple cached embeddings efficiently.

        Args:
            content_hashes: List of content hashes to look up

        Returns:
            Dict mapping found content_hash -> embedding
        """
        found = {}

        # Check memory cache first
        for h in content_hashes:
            key = self._cache_key(h)
            if key in self._memory_cache:
                found[h] = self._memory_cache[key]

        # Check disk for remaining
        missing = [h for h in content_hashes if h not in found]
        if not missing:
            return found

        try:
            with sqlite3.connect(self.db_path) as conn:
                placeholders = ",".join("?" * len(missing))
                cursor = conn.execute(
                    f"""SELECT content_hash, embedding FROM embeddings
                        WHERE model_name = ? AND chunk_config = ?
                        AND content_hash IN ({placeholders})""",
                    (self.model_name, self.chunk_config_hash, *missing),
                )
                for row in cursor:
                    embedding = pickle.loads(row[1])
                    found[row[0]] = embedding
                    self._memory_cache[self._cache_key(row[0])] = embedding
        except Exception as e:
            logger.warning(f"Batch cache lookup failed: {e}")

        return found

    def invalidate_model(self, model_name: str) -> int:
        """
        Invalidate all embeddings for a specific model.

        Args:
            model_name: Model name to invalidate

        Returns:
            Number of entries deleted
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute(
                    "DELETE FROM embeddings WHERE model_name = ?",
                    (model_name,),
                )
                deleted = cursor.rowcount

            # Clear memory cache entries for this model
            self._memory_cache = {
                k: v for k, v in self._memory_cache.items() if k[1] != model_name
            }

            logger.info(f"Invalidated {deleted} embeddings for model {model_name}")
            return deleted
        except Exception as e:
            logger.error(f"Cache invalidation failed: {e}")
            return 0

    def clear(self) -> None:
        """Clear all cached embeddings."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("DELETE FROM embeddings")
            self._memory_cache.clear()
            logger.info("Cleared all cached embeddings")
        except Exception as e:
            logger.error(f"Cache clear failed: {e}")

    @property
    def size(self) -> int:
        """Number of cached embeddings in memory."""
        return len(self._memory_cache)

    def get_stats(self) -> dict:
        """Get cache statistics."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute("SELECT COUNT(*) FROM embeddings")
                total = cursor.fetchone()[0]

                cursor = conn.execute(
                    "SELECT COUNT(*) FROM embeddings WHERE model_name = ? AND chunk_config = ?",
                    (self.model_name, self.chunk_config_hash),
                )
                current_model = cursor.fetchone()[0]

                return {
                    "total_entries": total,
                    "current_model_entries": current_model,
                    "memory_cache_size": len(self._memory_cache),
                    "model_name": self.model_name,
                    "chunk_config": self.chunk_config_hash,
                }
        except Exception as e:
            logger.warning(f"Failed to get cache stats: {e}")
            return {"error": str(e)}


class EmbeddingCache:
    """Simple in-memory cache for embeddings (legacy compatibility)."""

    def __init__(self):
        self._cache: dict[str, np.ndarray] = {}

    def get(self, text_hash: str) -> np.ndarray | None:
        """Get cached embedding."""
        return self._cache.get(text_hash)

    def set(self, text_hash: str, embedding: np.ndarray) -> None:
        """Cache an embedding."""
        self._cache[text_hash] = embedding

    def clear(self) -> None:
        """Clear the cache."""
        self._cache.clear()

    @property
    def size(self) -> int:
        """Number of cached embeddings."""
        return len(self._cache)


# Global cache instances
embedding_cache = EmbeddingCache()  # Legacy in-memory cache
_persistent_cache: Optional[PersistentEmbeddingCache] = None


def get_persistent_cache() -> PersistentEmbeddingCache:
    """Get the global persistent embedding cache instance."""
    global _persistent_cache
    if _persistent_cache is None:
        settings = get_settings()
        _persistent_cache = PersistentEmbeddingCache(
            cache_path=settings.embedding_cache_path,
            model_name=settings.voyage_model,
            chunk_size=settings.chunk_size,
            chunk_overlap=settings.chunk_overlap,
        )
    return _persistent_cache
