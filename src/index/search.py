"""
Search Engine

Vector similarity search for finding relevant content.
"""

import numpy as np
from typing import List, Optional, Tuple, Set
from dataclasses import dataclass

from models import (
    Chunk,
    ExtractedImage,
    SearchResult,
    ChunkType,
    ImageType,
)
from config import settings
from .database import Database


@dataclass
class RetrievalResult:
    """Complete retrieval result with chunks and images"""
    chunks: List[SearchResult]
    images: List[ExtractedImage]
    sources_used: Set[str]
    total_chunks: int
    total_images: int


class SearchEngine:
    """
    Vector similarity search engine.
    
    Features:
    - Semantic search using embeddings
    - Type-filtered search
    - Image search by context
    - Source diversity
    """
    
    def __init__(self, db: Database):
        self.db = db
        self._chunk_cache: Optional[List[Tuple[Chunk, List[float]]]] = None
        self._image_cache: Optional[List[Tuple[ExtractedImage, List[float]]]] = None
    
    def search_chunks(
        self,
        query_embedding: List[float],
        top_k: int = None,
        min_score: float = None,
        chunk_types: Optional[List[ChunkType]] = None,
        source_ids: Optional[List[str]] = None
    ) -> List[SearchResult]:
        """
        Search for relevant chunks.
        
        Args:
            query_embedding: Query vector
            top_k: Number of results to return
            min_score: Minimum similarity score
            chunk_types: Filter by chunk types
            source_ids: Filter by source IDs
            
        Returns:
            List of SearchResult ordered by relevance
        """
        top_k = top_k or settings.retrieval_top_k
        min_score = min_score or settings.similarity_threshold
        
        # Load chunks with embeddings
        if self._chunk_cache is None:
            self._chunk_cache = self.db.get_all_chunks_with_embeddings()
        
        # Calculate similarities
        results = []
        query_vec = np.array(query_embedding)
        
        for chunk, embedding in self._chunk_cache:
            # Apply filters
            if chunk_types and chunk.chunk_type not in chunk_types:
                continue
            if source_ids and chunk.source_id not in source_ids:
                continue
            
            # Calculate cosine similarity
            chunk_vec = np.array(embedding)
            score = self._cosine_similarity(query_vec, chunk_vec)
            
            if score >= min_score:
                results.append(SearchResult(
                    chunk=chunk,
                    score=score
                ))
        
        # Sort by score and return top_k
        results.sort(key=lambda x: x.score, reverse=True)
        return results[:top_k]
    
    def search_images(
        self,
        query_embedding: List[float],
        top_k: int = 20,
        min_score: float = 0.5,
        image_types: Optional[List[ImageType]] = None,
        source_ids: Optional[List[str]] = None
    ) -> List[Tuple[ExtractedImage, float]]:
        """
        Search for relevant images by their context.
        
        Args:
            query_embedding: Query vector
            top_k: Number of results
            min_score: Minimum similarity
            image_types: Filter by image types
            source_ids: Filter by source IDs
            
        Returns:
            List of (image, score) tuples
        """
        # Load images with embeddings
        if self._image_cache is None:
            self._image_cache = self.db.get_all_images_with_embeddings()
        
        results = []
        query_vec = np.array(query_embedding)
        
        for image, embedding in self._image_cache:
            # Apply filters
            if image_types and image.image_type not in image_types:
                continue
            if source_ids and image.source_id not in source_ids:
                continue
            
            # Calculate similarity
            img_vec = np.array(embedding)
            score = self._cosine_similarity(query_vec, img_vec)
            
            if score >= min_score:
                results.append((image, score))
        
        results.sort(key=lambda x: x[1], reverse=True)
        return results[:top_k]
    
    def retrieve_for_topic(
        self,
        query_embedding: List[float],
        topic: str,
        chunk_types: Optional[List[ChunkType]] = None,
        top_k: int = None,
        include_images: bool = True
    ) -> RetrievalResult:
        """
        Comprehensive retrieval for a topic.
        
        Returns chunks and related images, with source diversity.
        """
        top_k = top_k or settings.retrieval_top_k
        
        # Search chunks
        chunk_results = self.search_chunks(
            query_embedding=query_embedding,
            top_k=top_k * 2,  # Get more, then diversify
            chunk_types=chunk_types
        )
        
        # Ensure source diversity (don't let one source dominate)
        diversified = self._diversify_sources(chunk_results, top_k)
        
        # Collect source IDs
        sources_used = set(r.chunk.source_id for r in diversified)
        
        # Get related images
        images = []
        if include_images:
            # Get images from the retrieved chunks' sources
            image_results = self.search_images(
                query_embedding=query_embedding,
                top_k=50,
                source_ids=list(sources_used)
            )
            images = [img for img, score in image_results]
        
        return RetrievalResult(
            chunks=diversified,
            images=images,
            sources_used=sources_used,
            total_chunks=len(diversified),
            total_images=len(images)
        )
    
    def _diversify_sources(
        self,
        results: List[SearchResult],
        target_count: int,
        max_per_source: int = 10
    ) -> List[SearchResult]:
        """
        Ensure diverse source representation in results.
        
        Prevents any single source from dominating the results.
        """
        source_counts = {}
        diversified = []
        
        for result in results:
            source = result.chunk.source_id
            count = source_counts.get(source, 0)
            
            if count < max_per_source:
                diversified.append(result)
                source_counts[source] = count + 1
                
                if len(diversified) >= target_count:
                    break
        
        return diversified
    
    def _cosine_similarity(self, a: np.ndarray, b: np.ndarray) -> float:
        """Calculate cosine similarity between two vectors"""
        norm_a = np.linalg.norm(a)
        norm_b = np.linalg.norm(b)
        
        if norm_a == 0 or norm_b == 0:
            return 0.0
        
        return float(np.dot(a, b) / (norm_a * norm_b))
    
    def clear_cache(self):
        """Clear the embedding cache (call after adding new data)"""
        self._chunk_cache = None
        self._image_cache = None
    
    def get_chunks_by_type(self, chunk_type: ChunkType, limit: int = 100) -> List[Chunk]:
        """Get chunks of a specific type (no embedding required)"""
        all_chunks = self.db.get_all_chunks_with_embeddings()
        matching = [chunk for chunk, _ in all_chunks if chunk.chunk_type == chunk_type]
        return matching[:limit]
