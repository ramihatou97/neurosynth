"""
Proposition Chunker (Small-to-Big Indexing)
===========================================
Splits documents into atomic "propositions" (sentences) but retains full
parent context retrieval.

Strategy:
1.  Split text into sentences using robust regex.
2.  Group sentences into chunks of 3-5 sentences (approx 500-800 chars).
3.  ENRICH: Add "Title > Section > Evidence" header to the embedding text.
4.  CONTEXT: Store the original full section text in `parent_context`.
"""

import hashlib
import re
from typing import List, Optional

from neurosynth.integration.evidence import detect_evidence_level
from src.models import Chunk, ChunkType, Section


class PropositionChunker:
    """
    Creates "Small-to-Big" chunks.
    Small for embedding (Precision), Big for retrieval (Context).
    """

    def __init__(self, target_chunk_size: int = 800):
        self.target_chunk_size = target_chunk_size

        # Regex for sentence splitting (Negative lookbehind for common abbr)
        # Handles: Dr., Mr., vs., Fig., et al., e.g.
        # Note: Lookbehinds must be fixed width.
        # "Dr." is 3 chars. "Mr." is 3 chars. "Ms." is 3 chars. "vs." is 3 chars.
        # "Fig." is 4 chars. "Mrs." is 4 chars.
        # We can group them or use multiple lookbehinds.

        # Fixed-width lookbehinds:
        self.sentence_split_pattern = re.compile(
            r"(?<!\bMr\.)(?<!\bDr\.)(?<!\bMs\.)(?<!\bvs\.)(?<!\bFig\.)(?<!Mrs\.)(?<!\bet\sal\.)(?<!\be\.g\.)(?<!\bi\.e\.)(?<=[.!?])\s+(?=[A-Z0-9])"
        )

    def chunk_section(
        self, section: Section, source_id: str, source_title: str
    ) -> list[Chunk]:
        """
        Convert a Section into Proposition Chunks.
        """
        content = section.content.strip()
        if not content:
            return []

        # 1. Detect Evidence Level (for Enrichment)
        evidence = detect_evidence_level(content)
        evidence_str = evidence.level.value if evidence else "unknown"

        # 2. Split into sentences
        sentences = self._split_sentences(content)

        # 3. Group sentences into propositions
        propositions = self._group_sentences(sentences)

        # 4. Create Chunks
        chunks = []
        for i, prop_text in enumerate(propositions):
            # Create ID
            chunk_id = self._generate_chunk_id(source_id, section.title, i)

            # Context Enrichment (The "Small" part for Embedding)
            # Format: "Title > Section [Evidence: X] \n Content"
            enriched_content = (
                f"Source: {source_title} | Section: {section.title} "
                f"[Evidence: {evidence_str}]\n{prop_text}"
            )

            chunk = Chunk(
                id=chunk_id,
                source_id=source_id,
                source_title=source_title,
                section_title=section.title,
                content=enriched_content,  # Enriched text for embedding
                chunk_type=ChunkType.NARRATIVE,  # Default to narrative for now
                page_start=section.page_start,
                page_end=section.page_end,
                image_ids=[img.id for img in section.images],
                evidence_level=evidence_str,
                # KEY: Small-to-Big Fields
                parent_context=content,  # <--- The "Big" part (Full Section)
                is_proposition=True,
            )
            chunks.append(chunk)

        # Handle case where section is tiny (shorter than 1 sentence?)
        if not chunks and content:
            # Fallback to single chunk
            chunks.append(
                self._create_fallback_chunk(
                    section, source_id, source_title, content, evidence_str
                )
            )

        return chunks

    def _split_sentences(self, text: str) -> list[str]:
        """Split text into sentences using regex."""
        # Clean specific whitespace issues
        text = re.sub(r"\s+", " ", text).strip()
        sentences = self.sentence_split_pattern.split(text)
        return [s.strip() for s in sentences if s.strip()]

    def _group_sentences(self, sentences: list[str]) -> list[str]:
        """Group sentences into windowed chunks."""
        groups = []
        current_group = []
        current_len = 0

        for sent in sentences:
            sent_len = len(sent)

            # If adding this sentence exceeds target significantly
            # We use target_chunk_size as the soft limit.
            if current_len + sent_len > self.target_chunk_size and current_group:
                groups.append(" ".join(current_group))
                current_group = [sent]
                current_len = sent_len
            else:
                current_group.append(sent)
                current_len += sent_len

        if current_group:
            groups.append(" ".join(current_group))

        return groups

    def _generate_chunk_id(self, source_id: str, section_title: str, index: int) -> str:
        hash_input = f"{source_id}_{section_title}_prop_{index}"
        return hashlib.md5(hash_input.encode()).hexdigest()[:16]

    def _create_fallback_chunk(
        self, section, source_id, source_title, content, evidence_level
    ):
        """Create a standard chunk if splitting fails."""
        chunk_id = self._generate_chunk_id(source_id, section.title, 0)
        return Chunk(
            id=chunk_id,
            source_id=source_id,
            source_title=source_title,
            section_title=section.title,
            content=content,
            chunk_type=ChunkType.NARRATIVE,
            page_start=section.page_start,
            page_end=section.page_end,
            image_ids=[img.id for img in section.images],
            evidence_level=evidence_level,
            parent_context=content,
            is_proposition=True,
        )
