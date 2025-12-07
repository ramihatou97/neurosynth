"""
Synthesis Engine

The core intelligence that synthesizes chapters from retrieved content.
"""

import numpy as np
from typing import List, Optional, Dict, Set
from datetime import datetime
from dataclasses import dataclass

from models import (
    Chunk,
    ExtractedImage,
    SearchResult,
    SynthesizedSection,
    SynthesizedChapter,
    ChapterTemplate,
    SectionTemplate,
    SourceMetadata,
    ChunkType,
    ImageType,
    SURGICAL_PROCEDURE_TEMPLATE,
    ANATOMY_TEMPLATE,
    CLINICAL_TOPIC_TEMPLATE,
    get_template,
)
from config import settings
from index.database import Database
from index.search import SearchEngine, RetrievalResult
from ai.client import AIClient


@dataclass
class DeduplicatedChunk:
    """A chunk with deduplication metadata"""
    chunk: Chunk
    score: float
    also_in_sources: List[str]


class SynthesisEngine:
    """
    Orchestrates the synthesis of comprehensive chapters.
    
    Pipeline:
    1. Retrieve relevant content for topic
    2. Deduplicate similar content
    3. Synthesize each section using AI
    4. Select best images for each section
    5. Compile into complete chapter
    """
    
    def __init__(
        self,
        db: Database,
        search_engine: SearchEngine,
        ai_client: AIClient
    ):
        self.db = db
        self.search = search_engine
        self.ai = ai_client
    
    def synthesize_chapter(
        self,
        topic: str,
        template_name: str = "surgical_procedure"
    ) -> SynthesizedChapter:
        """
        Synthesize a complete chapter on a topic.
        
        Args:
            topic: The topic to synthesize (e.g., "translabyrinthine approach")
            template_name: Template to use (surgical_procedure, anatomy, clinical_topic)
            
        Returns:
            Complete SynthesizedChapter
        """
        template = get_template(template_name)
        
        # Step 1: Get query embedding
        query_embedding = self.ai.get_embedding(topic)
        
        # Step 2: Retrieve all relevant content
        retrieval = self.search.retrieve_for_topic(
            query_embedding=query_embedding,
            topic=topic,
            top_k=settings.retrieval_top_k
        )
        
        # Step 3: Deduplicate chunks
        deduplicated = self._deduplicate_chunks(retrieval.chunks)
        
        # Step 4: Synthesize each section
        sections = []
        for section_template in template.sections:
            section = self._synthesize_section(
                topic=topic,
                section_template=section_template,
                all_chunks=deduplicated,
                all_images=retrieval.images,
                query_embedding=query_embedding
            )
            sections.append(section)
        
        # Step 5: Get source metadata
        sources = self._get_sources_metadata(retrieval.sources_used)
        
        # Count total images
        total_images = sum(len(s.images) for s in sections)
        
        return SynthesizedChapter(
            topic=topic,
            sections=sections,
            sources=sources,
            total_chunks_used=len(deduplicated),
            total_images=total_images,
            generated_at=datetime.now(),
            template_used=template_name
        )
    
    def _deduplicate_chunks(
        self,
        results: List[SearchResult]
    ) -> List[DeduplicatedChunk]:
        """
        Deduplicate chunks that contain similar content.
        
        Groups similar chunks and keeps the best one from each group.
        """
        if not results:
            return []
        
        # Get embeddings for similarity comparison
        chunks_with_emb = []
        for result in results:
            if result.chunk.embedding:
                chunks_with_emb.append((result, result.chunk.embedding))
            else:
                # Generate embedding if missing
                emb = self.ai.get_embedding(result.chunk.content[:2000])
                chunks_with_emb.append((result, emb))
        
        # Find similar groups
        threshold = settings.dedup_threshold
        used = set()
        deduplicated = []
        
        for i, (result_i, emb_i) in enumerate(chunks_with_emb):
            if i in used:
                continue
            
            # Start a new group
            group = [result_i]
            group_sources = [result_i.chunk.source_id]
            used.add(i)
            
            # Find similar chunks
            emb_i_arr = np.array(emb_i)
            for j, (result_j, emb_j) in enumerate(chunks_with_emb[i+1:], start=i+1):
                if j in used:
                    continue
                
                emb_j_arr = np.array(emb_j)
                similarity = self._cosine_similarity(emb_i_arr, emb_j_arr)
                
                if similarity >= threshold:
                    group.append(result_j)
                    group_sources.append(result_j.chunk.source_id)
                    used.add(j)
            
            # Select best from group
            best = self._select_best_chunk(group)
            other_sources = [s for s in group_sources if s != best.chunk.source_id]
            
            deduplicated.append(DeduplicatedChunk(
                chunk=best.chunk,
                score=best.score,
                also_in_sources=other_sources
            ))
        
        return deduplicated
    
    def _select_best_chunk(self, group: List[SearchResult]) -> SearchResult:
        """
        Select the best chunk from a group of similar chunks.
        
        Prefers: longer content, higher relevance score
        """
        if len(group) == 1:
            return group[0]
        
        # Score each chunk
        def score_chunk(result: SearchResult) -> float:
            length_score = min(len(result.chunk.content) / 2000, 1.0)
            relevance_score = result.score
            return (length_score * 0.4) + (relevance_score * 0.6)
        
        return max(group, key=score_chunk)
    
    def _synthesize_section(
        self,
        topic: str,
        section_template: SectionTemplate,
        all_chunks: List[DeduplicatedChunk],
        all_images: List[ExtractedImage],
        query_embedding: List[float]
    ) -> SynthesizedSection:
        """Synthesize a single section of the chapter"""
        
        # Filter chunks relevant to this section
        section_chunks = self._filter_chunks_for_section(
            chunks=all_chunks,
            section_name=section_template.name,
            chunk_types=section_template.chunk_types
        )
        
        # If no chunks found, try broader search
        if not section_chunks:
            section_chunks = all_chunks[:10]  # Use top chunks as fallback
        
        # Prepare source material for AI
        source_material = [
            {
                "content": dc.chunk.content,
                "source_title": dc.chunk.source_title,
                "page": dc.chunk.page_start
            }
            for dc in section_chunks[:15]  # Limit to prevent token overflow
        ]
        
        # Synthesize content
        if source_material:
            content = self.ai.synthesize_section(
                topic=topic,
                section_name=section_template.name,
                subsections=section_template.subsections,
                source_chunks=source_material,
                format_type=section_template.format
            )
        else:
            content = f"[No content found for {section_template.name}]"
        
        # Select images for this section
        max_images = settings.max_images_per_section
        if section_template.image_priority == "high":
            max_images = max_images + 2
        elif section_template.image_priority == "low":
            max_images = max(1, max_images - 2)
        
        images = self._select_images_for_section(
            all_images=all_images,
            section_name=section_template.name,
            section_content=content,
            max_images=max_images,
            query_embedding=query_embedding
        )
        
        # Collect sources used
        sources_used = list(set(dc.chunk.source_id for dc in section_chunks))
        
        return SynthesizedSection(
            title=section_template.name,
            content=content,
            images=images,
            sources_used=sources_used
        )
    
    def _filter_chunks_for_section(
        self,
        chunks: List[DeduplicatedChunk],
        section_name: str,
        chunk_types: List[ChunkType]
    ) -> List[DeduplicatedChunk]:
        """Filter chunks relevant to a specific section"""
        
        # If chunk types specified, filter by type
        if chunk_types:
            type_filtered = [
                dc for dc in chunks
                if dc.chunk.chunk_type in chunk_types
            ]
            if type_filtered:
                return type_filtered
        
        # Fallback: keyword matching on section name
        section_lower = section_name.lower()
        keywords = section_lower.split()
        
        scored = []
        for dc in chunks:
            content_lower = dc.chunk.content.lower()
            section_title_lower = dc.chunk.section_title.lower()
            
            # Score based on keyword matches
            score = 0
            for kw in keywords:
                if kw in content_lower:
                    score += 1
                if kw in section_title_lower:
                    score += 2
            
            if score > 0:
                scored.append((dc, score))
        
        # Sort by score and return
        scored.sort(key=lambda x: x[1], reverse=True)
        return [dc for dc, _ in scored]
    
    def _select_images_for_section(
        self,
        all_images: List[ExtractedImage],
        section_name: str,
        section_content: str,
        max_images: int,
        query_embedding: List[float]
    ) -> List[ExtractedImage]:
        """Select the best images for a section"""
        
        if not all_images:
            return []
        
        # Determine preferred image types based on section
        preferred_types = self._get_preferred_image_types(section_name)
        
        # Score each image
        scored_images = []
        query_vec = np.array(query_embedding)
        
        for img in all_images:
            # Type preference score
            type_score = 1.0 if img.image_type in preferred_types else 0.5
            
            # Caption relevance
            caption_score = 0.0
            if img.caption:
                # Simple keyword overlap
                section_words = set(section_name.lower().split())
                caption_words = set(img.caption.lower().split())
                overlap = len(section_words & caption_words)
                caption_score = min(overlap / 3, 1.0)
            
            # Context embedding similarity (if available)
            context_score = 0.5
            if img.embedding:
                img_vec = np.array(img.embedding)
                context_score = self._cosine_similarity(query_vec, img_vec)
            
            # Combined score
            total_score = (type_score * 0.3) + (caption_score * 0.3) + (context_score * 0.4)
            scored_images.append((img, total_score))
        
        # Sort by score
        scored_images.sort(key=lambda x: x[1], reverse=True)
        
        # Select top images, avoiding duplicates (similar images)
        selected = []
        for img, score in scored_images:
            if len(selected) >= max_images:
                break
            
            # Check if too similar to already selected
            is_duplicate = False
            for sel in selected:
                if self._images_similar(img, sel):
                    is_duplicate = True
                    break
            
            if not is_duplicate:
                selected.append(img)
        
        return selected
    
    def _get_preferred_image_types(self, section_name: str) -> List[ImageType]:
        """Get preferred image types for a section"""
        section_lower = section_name.lower()
        
        if "anatomy" in section_lower:
            return [ImageType.ANATOMY_DIAGRAM, ImageType.ILLUSTRATION]
        elif "technique" in section_lower or "operative" in section_lower:
            return [ImageType.SURGICAL_PHOTO, ImageType.ANATOMY_DIAGRAM]
        elif "imaging" in section_lower or "diagnosis" in section_lower:
            return [ImageType.IMAGING_MRI, ImageType.IMAGING_CT, ImageType.IMAGING_ANGIO]
        elif "complication" in section_lower:
            return [ImageType.SURGICAL_PHOTO, ImageType.IMAGING_CT]
        else:
            return [ImageType.ILLUSTRATION, ImageType.DIAGRAM]
    
    def _images_similar(self, img1: ExtractedImage, img2: ExtractedImage) -> bool:
        """Check if two images are likely duplicates"""
        # Same source and close pages
        if img1.source_id == img2.source_id and abs(img1.page - img2.page) <= 1:
            return True
        
        # Check embedding similarity if available
        if img1.embedding and img2.embedding:
            similarity = self._cosine_similarity(
                np.array(img1.embedding),
                np.array(img2.embedding)
            )
            return similarity > 0.95
        
        return False
    
    def _get_sources_metadata(self, source_ids: Set[str]) -> List[SourceMetadata]:
        """Get metadata for all sources used"""
        sources = []
        for source_id in source_ids:
            metadata = self.db.get_source(source_id)
            if metadata:
                sources.append(metadata)
        return sources
    
    def _cosine_similarity(self, a: np.ndarray, b: np.ndarray) -> float:
        """Calculate cosine similarity"""
        norm_a = np.linalg.norm(a)
        norm_b = np.linalg.norm(b)
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return float(np.dot(a, b) / (norm_a * norm_b))
