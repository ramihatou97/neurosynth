import logging
from typing import List, Optional

from models import Chunk, ChunkType, SearchResult
from qdrant_client import QdrantClient
from qdrant_client.http import models

logger = logging.getLogger(__name__)


class QdrantRetriever:
    """
    Retrieves documents from Qdrant 'deep_dx_collection' (The Showroom).
    Replaces legacy SQLite dense search.
    """

    def __init__(
        self,
        url: str = "http://localhost:6333",
        collection_name: str = "deep_dx_collection",
    ):
        self.url = url
        self.collection_name = collection_name
        self.client = None

        try:
            self.client = QdrantClient(url=self.url)
            # Verify connection
            self.client.get_collections()
            logger.info(f"✓ Connected to Qdrant at {self.url} [{self.collection_name}]")
        except Exception as e:
            logger.warning(f"⚠ Qdrant Connection Failed: {e}")
            self.client = None

    def search(
        self, query_embedding: list[float], top_k: int = 20, min_score: float = 0.5
    ) -> list[SearchResult]:
        """
        Search Qdrant for similar chunks using query embedding.
        """
        if not self.client:
            logger.error("Qdrant client not initialized. Returning empty results.")
            return []

        try:
            # Use query_points (compatible with v1.x)
            results = self.client.query_points(
                collection_name=self.collection_name,
                query=query_embedding,
                limit=top_k,
                with_payload=True,
            ).points

            search_results = []
            for hit in results:
                if hit.score < min_score:
                    continue

                payload = hit.payload

                # Map Payload to Chunk
                chunk = Chunk(
                    id=str(payload.get("original_chunk_id", hit.id)),
                    source_id=str(payload.get("source_doc_id", "unknown")),
                    source_title=payload.get("title", "Unknown Source"),
                    section_title="Imported Section",  # Placeholder as bridge didn't sync section titles
                    content=payload.get("text", ""),
                    chunk_type=ChunkType.NARRATIVE,  # Default
                    page_start=int(payload.get("page", 0)),
                    page_end=int(payload.get("page", 0)),
                    embedding=hit.vector if hit.vector else None,
                )

                search_results.append(SearchResult(chunk=chunk, score=hit.score))

            return search_results

        except Exception as e:
            logger.error(f"Qdrant Search Error: {e}")
            return []
