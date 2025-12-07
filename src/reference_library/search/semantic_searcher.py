"""Semantic search engine using vector embeddings."""
import threading
from pathlib import Path
from typing import List, Dict, Any, Optional, TYPE_CHECKING

# Lazy imports for fast startup - these are heavy modules
chromadb = None
SentenceTransformer = None
SEMANTIC_AVAILABLE = None  # Determined on first use

from reference_library import config
from ..cache.database import Database


def _lazy_load_semantic():
    """Lazy load heavy semantic search dependencies."""
    global chromadb, SentenceTransformer, SEMANTIC_AVAILABLE
    if SEMANTIC_AVAILABLE is not None:
        return SEMANTIC_AVAILABLE
    try:
        import chromadb as _chromadb
        from sentence_transformers import SentenceTransformer as _SentenceTransformer
        chromadb = _chromadb
        SentenceTransformer = _SentenceTransformer
        SEMANTIC_AVAILABLE = True
    except ImportError:
        SEMANTIC_AVAILABLE = False
    return SEMANTIC_AVAILABLE

# ChromaDB batch size limit (well under the 5461 HNSW limit)
CHROMADB_BATCH_SIZE = 1000


# Available embedding models
EMBEDDING_MODELS = {
    "general": "all-MiniLM-L6-v2",  # Fast, general-purpose (default)
    "medical": "pritamdeka/S-PubMedBert-MS-MARCO",  # Medical domain-specific
    "retrieval": "BAAI/bge-small-en-v1.5",  # Optimized for retrieval
    "large": "BAAI/bge-large-en-v1.5",  # Higher quality, slower
}


class SemanticSearcher:
    """Manages vector embeddings and semantic search queries."""

    def __init__(self, database: Database):
        self.database = database
        self._enabled = None  # Lazy - determined on first access
        self.client = None
        self.collection = None
        self.captions_collection = None  # Collection for figure captions
        self.model = None
        self._initialized = False

        # Thread safety locks - SentenceTransformer and ChromaDB are not thread-safe
        self._model_lock = threading.Lock()
        self._collection_lock = threading.Lock()

        # Store collection names for consistent access
        self.collection_name = None
        self.captions_collection_name = None

    @property
    def enabled(self) -> bool:
        """Lazy check if semantic search is available."""
        if self._enabled is None:
            self._enabled = _lazy_load_semantic() and config.SEMANTIC_SEARCH_ENABLED
        return self._enabled

    def _ensure_initialized(self):
        """Lazy initialize resources on first use."""
        if not self._initialized and self.enabled:
            self._init_resources()
            self._initialized = True

    def _init_resources(self):
        """Initialize ChromaDB and Embedding Model."""
        try:
            # Persistent storage for vectors
            config.CHROMA_DB_PATH.mkdir(parents=True, exist_ok=True)
            self.client = chromadb.PersistentClient(path=str(config.CHROMA_DB_PATH))

            # Create or get collection with cosine similarity for pages
            # Collection name includes model type to avoid mixing embeddings
            self.collection_name = f"neurosurgery_pages_{config.EMBEDDING_MODEL_TYPE}"
            self.collection = self.client.get_or_create_collection(
                name=self.collection_name,
                metadata={
                    "hnsw:space": "cosine",
                    "model": config.EMBEDDING_MODEL,
                    "model_type": config.EMBEDDING_MODEL_TYPE
                }
            )

            # Create or get collection for figure captions
            self.captions_collection_name = f"figure_captions_{config.EMBEDDING_MODEL_TYPE}"
            self.captions_collection = self.client.get_or_create_collection(
                name=self.captions_collection_name,
                metadata={
                    "hnsw:space": "cosine",
                    "model": config.EMBEDDING_MODEL,
                    "model_type": config.EMBEDDING_MODEL_TYPE
                }
            )

            # Load model (downloads on first run)
            print(f"Loading embedding model: {config.EMBEDDING_MODEL} ({config.EMBEDDING_MODEL_TYPE})")
            self.model = SentenceTransformer(config.EMBEDDING_MODEL)
            print(f"Semantic search initialized successfully with {config.EMBEDDING_MODEL_TYPE} model")

        except Exception as e:
            print(f"Failed to initialize semantic search: {e}")
            self.enabled = False

    def index_page(self, pdf_path: Path, page_number: int, text: str, checksum: str) -> bool:
        """
        Embed and index a single page.

        Args:
            pdf_path: Path to the PDF file
            page_number: 1-indexed page number
            text: Full text content of the page
            checksum: File checksum for cache invalidation

        Returns:
            True if indexed successfully, False otherwise
        """
        self._ensure_initialized()
        if not self.enabled or not text.strip():
            return False

        # Check if already indexed with current checksum
        if self.database.is_page_indexed_semantically(pdf_path, page_number, checksum):
            return True

        try:
            # Generate embedding (thread-safe)
            with self._model_lock:
                embedding = self.model.encode(text).tolist()

            # Unique ID format: path:page
            doc_id = f"{pdf_path}:{page_number}"

            # Store in ChromaDB (thread-safe)
            # Text is already stored in SQLite pdf_text_cache
            with self._collection_lock:
                self.collection.upsert(
                    ids=[doc_id],
                    embeddings=[embedding],
                    metadatas=[{
                        "pdf_path": str(pdf_path),
                        "page_number": page_number,
                        "checksum": checksum
                    }]
                )

            # Track in SQLite for cache management
            self.database.track_semantic_index(pdf_path, page_number, checksum)
            return True

        except Exception as e:
            print(f"Error indexing page {page_number} of {pdf_path.name}: {e}")
            return False

    def _encode_subprocess(self, texts: list[str]) -> list[list[float]]:
        """Encode texts in a subprocess to avoid blocking UI with GIL.

        This spawns a separate Python process that has its own GIL,
        so the main process UI thread remains responsive.
        """
        import subprocess
        import json
        import sys

        # Path to the worker script
        worker_path = Path(__file__).parent.parent / "utils" / "embedding_worker.py"

        # Prepare input
        input_data = json.dumps({
            "texts": texts,
            "model": config.EMBEDDING_MODEL
        })

        # Run subprocess
        result = subprocess.run(
            [sys.executable, str(worker_path)],
            input=input_data,
            capture_output=True,
            text=True,
            timeout=300  # 5 minute timeout
        )

        if result.returncode != 0:
            raise RuntimeError(f"Embedding worker failed: {result.stderr}")

        # Parse output
        output = json.loads(result.stdout)
        return output["embeddings"]

    def index_pages_batch(
        self,
        pdf_path: Path,
        pages: dict[int, str],
        checksum: str,
        use_subprocess: bool = True
    ) -> int:
        """
        Batch embed and index multiple pages.

        Args:
            pdf_path: Path to the PDF file
            pages: Dict of page_number -> text content
            checksum: File checksum for cache invalidation
            use_subprocess: If True, run embedding in subprocess (no GIL block)

        Returns:
            Number of pages indexed
        """
        if not self.enabled:
            return 0

        # Filter out already indexed pages and empty pages
        to_index = []
        for page_num, text in pages.items():
            if text.strip() and not self.database.is_page_indexed_semantically(
                pdf_path, page_num + 1, checksum
            ):
                to_index.append((page_num, text))

        if not to_index:
            return 0

        try:
            # Get embeddings (subprocess or in-process with lock)
            texts = [t for _, t in to_index]
            if use_subprocess:
                embeddings = self._encode_subprocess(texts)
            else:
                with self._model_lock:
                    embeddings = self.model.encode(texts, show_progress_bar=False).tolist()

            # Prepare batch data for ChromaDB
            ids = []
            metas = []
            for i, (page_num, _) in enumerate(to_index):
                doc_id = f"{pdf_path}:{page_num + 1}"
                ids.append(doc_id)
                metas.append({
                    "pdf_path": str(pdf_path),
                    "page_number": page_num + 1,
                    "checksum": checksum
                })

            # Batch upsert to ChromaDB with chunking to avoid HNSW limits
            with self._collection_lock:
                for i in range(0, len(ids), CHROMADB_BATCH_SIZE):
                    batch_ids = ids[i:i + CHROMADB_BATCH_SIZE]
                    batch_embeddings = embeddings[i:i + CHROMADB_BATCH_SIZE]
                    batch_metas = metas[i:i + CHROMADB_BATCH_SIZE]
                    self.collection.upsert(
                        ids=batch_ids,
                        embeddings=batch_embeddings,
                        metadatas=batch_metas
                    )

            # Track in SQLite
            for page_num, _ in to_index:
                self.database.track_semantic_index(pdf_path, page_num + 1, checksum)

            return len(to_index)

        except Exception as e:
            print(f"Error batch indexing {pdf_path.name}: {e}")
            return 0

    def search(self, query: str, n_results: int = 30,
               category_filter: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Perform semantic search with optional category filtering.

        Args:
            query: Search query (natural language)
            n_results: Maximum number of results to return
            category_filter: Optional filter by category group
                           ("Surgical/Anatomical" or "Theoretical")

        Returns:
            List of dicts with: pdf_path, page_number, score, category_group (if available)
        """
        self._ensure_initialized()
        if not self.enabled:
            return []

        try:
            # Embed the query (thread-safe)
            with self._model_lock:
                query_embedding = self.model.encode(query).tolist()

            # Build metadata filter if specified
            where = None
            if category_filter in ["Surgical/Anatomical", "Theoretical"]:
                where = {"category_group": category_filter}

            # Search ChromaDB with optional filter (thread-safe)
            with self._collection_lock:
                results = self.collection.query(
                    query_embeddings=[query_embedding],
                    n_results=n_results,
                    where=where,  # Apply category filter if specified
                    include=["metadatas", "distances"]
                )

            # Transform to cleaner format
            clean_results = []
            if not results['ids'] or not results['ids'][0]:
                return []

            for i in range(len(results['ids'][0])):
                meta = results['metadatas'][0][i]
                # Convert cosine distance to similarity score
                score = 1.0 - results['distances'][0][i]
                clean_results.append({
                    "pdf_path": Path(meta["pdf_path"]),
                    "page_number": int(meta["page_number"]),
                    "score": score,
                    "category_group": meta.get("category_group")  # Include if available
                })

            return clean_results

        except Exception as e:
            print(f"Semantic search error: {e}")
            return []

    def update_page_category(self, pdf_path: Path, page_number: int,
                            category_group: str, category: str):
        """
        Update category metadata for an already-indexed page.

        This allows us to enrich the semantic index with category information
        after AI categorization has been performed.

        Args:
            pdf_path: Path to the PDF
            page_number: Page number (1-indexed)
            category_group: "Surgical/Anatomical" or "Theoretical"
            category: Specific subcategory
        """
        if not self.enabled:
            return

        try:
            doc_id = f"{pdf_path}:{page_number}"

            # Get existing metadata (thread-safe)
            with self._collection_lock:
                existing = self.collection.get(ids=[doc_id], include=["metadatas"])
                if not existing['ids']:
                    return  # Page not indexed yet

                # Update metadata
                metadata = existing['metadatas'][0]
                metadata["category_group"] = category_group
                metadata["category"] = category

                # Update in ChromaDB (requires re-upserting with same embedding)
                # Note: ChromaDB doesn't have a metadata-only update, so we keep the embedding
                self.collection.update(
                    ids=[doc_id],
                    metadatas=[metadata]
                )

        except Exception as e:
            print(f"Warning: Failed to update category for {pdf_path.name} p{page_number}: {e}")

    def get_indexed_count(self) -> int:
        """Get number of indexed pages in ChromaDB."""
        if not self.enabled or not self.collection:
            return 0
        try:
            return self.collection.count()
        except (RuntimeError, ValueError, AttributeError):
            # RuntimeError: ChromaDB internal errors
            # ValueError: Invalid collection state
            # AttributeError: Collection not properly initialized
            return 0

    def get_model_info(self) -> dict:
        """Get information about the current embedding model."""
        if not self.enabled:
            return {
                "enabled": False,
                "model": None,
                "model_type": None,
                "indexed_count": 0
            }

        return {
            "enabled": True,
            "model": config.EMBEDDING_MODEL,
            "model_type": config.EMBEDDING_MODEL_TYPE,
            "indexed_count": self.get_indexed_count(),
            "collection_name": self.collection.name if self.collection else None
        }

    def clear_index(self):
        """Clear the vector index (for rebuilding)."""
        if not self.enabled:
            return

        try:
            # Delete and recreate collection using stored name (thread-safe)
            with self._collection_lock:
                if self.collection_name:
                    self.client.delete_collection(self.collection_name)
                self.collection = self.client.get_or_create_collection(
                    name=self.collection_name,
                    metadata={
                        "hnsw:space": "cosine",
                        "model": config.EMBEDDING_MODEL,
                        "model_type": config.EMBEDDING_MODEL_TYPE
                    }
                )
            # Also clear SQLite tracking
            self.database.clear_semantic_index()
            print("Semantic index cleared")
        except Exception as e:
            print(f"Error clearing semantic index: {e}")

    # ==================== Caption Search Methods ====================

    def index_figure_caption(
        self,
        figure_id: str,
        caption: str,
        pdf_path: Path,
        page_number: int,
        image_type: str = "unknown"
    ) -> bool:
        """
        Embed and index a figure caption.

        Args:
            figure_id: Unique figure identifier
            caption: Figure caption text
            pdf_path: Path to the PDF containing the figure
            page_number: Page number where figure appears
            image_type: Type of image (surgical_step, anatomical, etc.)

        Returns:
            True if indexed successfully
        """
        if not self.enabled or not caption or not caption.strip():
            return False

        # Check if already indexed
        if self.database.is_figure_embedded(figure_id):
            return True

        try:
            # Generate embedding for caption (thread-safe)
            with self._model_lock:
                embedding = self.model.encode(caption).tolist()

            # Store in ChromaDB captions collection (thread-safe)
            with self._collection_lock:
                self.captions_collection.upsert(
                    ids=[figure_id],
                    embeddings=[embedding],
                    metadatas=[{
                        "pdf_path": str(pdf_path),
                        "page_number": page_number,
                        "image_type": image_type,
                        "caption_preview": caption[:200]  # Store preview for display
                    }]
                )

            # Track in SQLite (figure_id used as both element_id and point_id for ChromaDB)
            self.database.track_visual_embedding(figure_id, figure_id, "caption")
            return True

        except Exception as e:
            print(f"Error indexing caption for {figure_id}: {e}")
            return False

    def index_figures_batch(
        self,
        figures: List[Dict[str, Any]],
        on_progress: Optional[callable] = None
    ) -> int:
        """
        Batch index figure captions.

        Args:
            figures: List of figure dicts with id, caption, pdf_path, page_number
            on_progress: Optional callback(current, total)

        Returns:
            Number of figures indexed
        """
        if not self.enabled:
            return 0

        indexed = 0
        total = len(figures)

        for i, fig in enumerate(figures):
            caption = fig.get("caption")
            if caption and caption.strip():
                success = self.index_figure_caption(
                    figure_id=fig["id"],
                    caption=caption,
                    pdf_path=Path(fig["pdf_path"]),
                    page_number=fig["page_number"],
                    image_type=fig.get("image_type", "unknown")
                )
                if success:
                    indexed += 1

            if on_progress:
                on_progress(i + 1, total)

        return indexed

    def search_captions(
        self,
        query: str,
        n_results: int = 20,
        image_types: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """
        Search figure captions semantically.

        Args:
            query: Search query
            n_results: Maximum results to return
            image_types: Optional filter by image types

        Returns:
            List of dicts with: figure_id, pdf_path, page_number, image_type, score, caption_preview
        """
        if not self.enabled or not self.captions_collection:
            return []

        try:
            # Embed the query (thread-safe)
            with self._model_lock:
                query_embedding = self.model.encode(query).tolist()

            # Build where filter if image_types specified
            where = None
            if image_types:
                where = {"image_type": {"$in": image_types}}

            # Search captions collection (thread-safe)
            with self._collection_lock:
                results = self.captions_collection.query(
                    query_embeddings=[query_embedding],
                    n_results=n_results,
                    where=where,
                    include=["metadatas", "distances"]
                )

            # Transform to cleaner format
            clean_results = []
            if not results['ids'] or not results['ids'][0]:
                return []

            for i in range(len(results['ids'][0])):
                meta = results['metadatas'][0][i]
                score = 1.0 - results['distances'][0][i]
                clean_results.append({
                    "figure_id": results['ids'][0][i],
                    "pdf_path": Path(meta["pdf_path"]),
                    "page_number": int(meta["page_number"]),
                    "image_type": meta.get("image_type", "unknown"),
                    "caption_preview": meta.get("caption_preview", ""),
                    "score": score
                })

            return clean_results

        except Exception as e:
            print(f"Caption search error: {e}")
            return []

    def search_combined(
        self,
        query: str,
        n_text_results: int = 30,
        n_caption_results: int = 15,
        include_captions: bool = True
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        Perform combined search across text and captions.

        Args:
            query: Search query
            n_text_results: Max text results
            n_caption_results: Max caption results
            include_captions: Whether to include caption search

        Returns:
            Dict with 'text_results' and 'caption_results' lists
        """
        results = {
            "text_results": self.search(query, n_text_results),
            "caption_results": []
        }

        if include_captions:
            results["caption_results"] = self.search_captions(query, n_caption_results)

        return results

    def get_caption_index_count(self) -> int:
        """Get number of indexed captions."""
        if not self.enabled or not self.captions_collection:
            return 0
        try:
            return self.captions_collection.count()
        except (RuntimeError, ValueError, AttributeError):
            # RuntimeError: ChromaDB internal errors
            # ValueError: Invalid collection state
            # AttributeError: Collection not properly initialized
            return 0

    def clear_caption_index(self):
        """Clear the caption index."""
        if not self.enabled:
            return

        try:
            # Use stored collection name (thread-safe)
            with self._collection_lock:
                if self.captions_collection_name:
                    self.client.delete_collection(self.captions_collection_name)
                self.captions_collection = self.client.get_or_create_collection(
                    name=self.captions_collection_name,
                    metadata={
                        "hnsw:space": "cosine",
                        "model": config.EMBEDDING_MODEL,
                        "model_type": config.EMBEDDING_MODEL_TYPE
                    }
                )
            print("Caption index cleared")
        except Exception as e:
            print(f"Error clearing caption index: {e}")
