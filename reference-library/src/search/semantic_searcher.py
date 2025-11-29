"""Semantic search engine using vector embeddings."""
from pathlib import Path
from typing import List, Dict, Any, Optional

try:
    import chromadb
    from sentence_transformers import SentenceTransformer
    SEMANTIC_AVAILABLE = True
except ImportError:
    SEMANTIC_AVAILABLE = False

import config
from ..cache.database import Database


class SemanticSearcher:
    """Manages vector embeddings and semantic search queries."""

    def __init__(self, database: Database):
        self.database = database
        self.enabled = SEMANTIC_AVAILABLE and config.SEMANTIC_SEARCH_ENABLED
        self.client = None
        self.collection = None
        self.captions_collection = None  # Collection for figure captions
        self.model = None

        if self.enabled:
            self._init_resources()

    def _init_resources(self):
        """Initialize ChromaDB and Embedding Model."""
        try:
            # Persistent storage for vectors
            config.CHROMA_DB_PATH.mkdir(parents=True, exist_ok=True)
            self.client = chromadb.PersistentClient(path=str(config.CHROMA_DB_PATH))

            # Create or get collection with cosine similarity for pages
            self.collection = self.client.get_or_create_collection(
                name="neurosurgery_pages",
                metadata={"hnsw:space": "cosine"}
            )

            # Create or get collection for figure captions
            self.captions_collection = self.client.get_or_create_collection(
                name="figure_captions",
                metadata={"hnsw:space": "cosine"}
            )

            # Load model (downloads on first run, ~80MB)
            print(f"Loading embedding model: {config.EMBEDDING_MODEL}")
            self.model = SentenceTransformer(config.EMBEDDING_MODEL)
            print("Semantic search initialized successfully")

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
        if not self.enabled or not text.strip():
            return False

        # Check if already indexed with current checksum
        if self.database.is_page_indexed_semantically(pdf_path, page_number, checksum):
            return True

        try:
            # Generate embedding
            embedding = self.model.encode(text).tolist()

            # Unique ID format: path:page
            doc_id = f"{pdf_path}:{page_number}"

            # Store in ChromaDB (embeddings + metadata only, no documents)
            # Text is already stored in SQLite pdf_text_cache
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
            # Get embeddings (subprocess or in-process)
            texts = [t for _, t in to_index]
            if use_subprocess:
                embeddings = self._encode_subprocess(texts)
            else:
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

            # Batch upsert to ChromaDB
            self.collection.upsert(
                ids=ids,
                embeddings=embeddings,
                metadatas=metas
            )

            # Track in SQLite
            for page_num, _ in to_index:
                self.database.track_semantic_index(pdf_path, page_num + 1, checksum)

            return len(to_index)

        except Exception as e:
            print(f"Error batch indexing {pdf_path.name}: {e}")
            return 0

    def search(self, query: str, n_results: int = 30) -> List[Dict[str, Any]]:
        """
        Perform semantic search.

        Args:
            query: Search query (natural language)
            n_results: Maximum number of results to return

        Returns:
            List of dicts with: pdf_path, page_number, score
        """
        if not self.enabled:
            return []

        try:
            # Embed the query
            query_embedding = self.model.encode(query).tolist()

            # Search ChromaDB
            results = self.collection.query(
                query_embeddings=[query_embedding],
                n_results=n_results,
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
                    "score": score
                })

            return clean_results

        except Exception as e:
            print(f"Semantic search error: {e}")
            return []

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

    def clear_index(self):
        """Clear the vector index (for rebuilding)."""
        if not self.enabled:
            return

        try:
            # Delete and recreate collection
            self.client.delete_collection("neurosurgery_pages")
            self.collection = self.client.get_or_create_collection(
                name="neurosurgery_pages",
                metadata={"hnsw:space": "cosine"}
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
            # Generate embedding for caption
            embedding = self.model.encode(caption).tolist()

            # Store in ChromaDB captions collection
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
            # Embed the query
            query_embedding = self.model.encode(query).tolist()

            # Build where filter if image_types specified
            where = None
            if image_types:
                where = {"image_type": {"$in": image_types}}

            # Search captions collection
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
            self.client.delete_collection("figure_captions")
            self.captions_collection = self.client.get_or_create_collection(
                name="figure_captions",
                metadata={"hnsw:space": "cosine"}
            )
            print("Caption index cleared")
        except Exception as e:
            print(f"Error clearing caption index: {e}")
