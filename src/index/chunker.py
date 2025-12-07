"""
Semantic Chunker

Splits documents into meaningful chunks for indexing and retrieval.
Respects document structure and content type.
"""

import hashlib
import re
from typing import List, Optional

from config import settings
from models import Chunk, ChunkType, ProcessedDocument, Section


class SemanticChunker:
    """
    Creates semantic chunks from processed documents.

    Features:
    - Respects section boundaries
    - Classifies content type
    - Maintains context overlap
    - Intelligent paragraph grouping
    """

    # Patterns for content type classification
    PROCEDURE_PATTERNS = [
        r"\b(?:step|position|incision|dissect|retract|identify|expose|clip|coagulate)\b",
        r"\b(?:then|next|subsequently|following this|at this point)\b",
        r"\b(?:patient is|patient should be|operating room)\b",
    ]

    ANATOMY_PATTERNS = [
        r"\b(?:artery|vein|nerve|muscle|bone|ligament|tendon|fascia)\b",
        r"\b(?:origin|insertion|course|branches|drains|supplies)\b",
        r"\b(?:lies|courses|travels|passes|emerges|enters)\b",
        r"\b(?:anterior|posterior|medial|lateral|superior|inferior)\b",
    ]

    COMPLICATIONS_PATTERNS = [
        r"\b(?:complication|risk|avoid|prevent|injury|damage|hemorrhage)\b",
        r"\b(?:careful|caution|danger|warning|critical)\b",
    ]

    OUTCOMES_PATTERNS = [
        r"\b(?:outcome|result|success|rate|percentage|survival)\b",
        r"\b(?:study|trial|series|patients|follow-up)\b",
    ]

    def __init__(self, chunk_size: int = None, chunk_overlap: int = None):
        self.chunk_size = chunk_size or settings.chunk_size
        self.chunk_overlap = chunk_overlap or settings.chunk_overlap

    def chunk_document(self, document: ProcessedDocument) -> list[Chunk]:
        """
        Create chunks from a processed document.

        Args:
            document: ProcessedDocument to chunk

        Returns:
            List of Chunk objects
        """
        chunks = []

        for section in document.sections:
            section_chunks = self._chunk_section(
                section=section,
                source_id=document.metadata.id,
                source_title=document.metadata.title,
            )
            chunks.extend(section_chunks)

        return chunks

    def _chunk_section(
        self, section: Section, source_id: str, source_title: str
    ) -> list[Chunk]:
        """Chunk a single section"""
        chunks = []
        content = section.content.strip()

        if not content:
            return chunks

        # For short sections, create single chunk
        if len(content) <= self.chunk_size:
            chunk_id = self._generate_chunk_id(source_id, section.title, 0)
            chunk_type = self._classify_content(content)

            chunks.append(
                Chunk(
                    id=chunk_id,
                    source_id=source_id,
                    source_title=source_title,
                    section_title=section.title,
                    content=content,
                    chunk_type=chunk_type,
                    page_start=section.page_start,
                    page_end=section.page_end,
                    image_ids=[img.id for img in section.images],
                )
            )
            return chunks

        # Split by paragraphs first
        paragraphs = self._split_paragraphs(content)

        # Group paragraphs into chunks
        current_chunk = []
        current_length = 0
        chunk_index = 0

        for para in paragraphs:
            para_length = len(para)

            # If single paragraph exceeds chunk size, split it
            if para_length > self.chunk_size:
                # Save current chunk first
                if current_chunk:
                    chunk_text = "\n\n".join(current_chunk)
                    chunks.append(
                        self._create_chunk(
                            chunk_text, source_id, source_title, section, chunk_index
                        )
                    )
                    chunk_index += 1
                    current_chunk = []
                    current_length = 0

                # Split large paragraph
                sub_chunks = self._split_large_paragraph(para)
                for sub in sub_chunks:
                    chunks.append(
                        self._create_chunk(
                            sub, source_id, source_title, section, chunk_index
                        )
                    )
                    chunk_index += 1
                continue

            # Check if adding this paragraph exceeds chunk size
            if current_length + para_length > self.chunk_size and current_chunk:
                # Save current chunk
                chunk_text = "\n\n".join(current_chunk)
                chunks.append(
                    self._create_chunk(
                        chunk_text, source_id, source_title, section, chunk_index
                    )
                )
                chunk_index += 1

                # Start new chunk with overlap
                if self.chunk_overlap > 0 and len(current_chunk) > 1:
                    # Keep last paragraph for overlap
                    overlap_para = current_chunk[-1]
                    current_chunk = [overlap_para, para]
                    current_length = len(overlap_para) + para_length
                else:
                    current_chunk = [para]
                    current_length = para_length
            else:
                current_chunk.append(para)
                current_length += para_length

        # Save remaining content
        if current_chunk:
            chunk_text = "\n\n".join(current_chunk)
            chunks.append(
                self._create_chunk(
                    chunk_text, source_id, source_title, section, chunk_index
                )
            )

        return chunks

    def _create_chunk(
        self,
        content: str,
        source_id: str,
        source_title: str,
        section: Section,
        chunk_index: int,
    ) -> Chunk:
        """Create a Chunk object"""
        chunk_id = self._generate_chunk_id(source_id, section.title, chunk_index)
        chunk_type = self._classify_content(content)

        # Find relevant images (those on same pages)
        # This is approximate - images are associated by page range
        image_ids = [img.id for img in section.images]

        return Chunk(
            id=chunk_id,
            source_id=source_id,
            source_title=source_title,
            section_title=section.title,
            content=content,
            chunk_type=chunk_type,
            page_start=section.page_start,
            page_end=section.page_end,
            image_ids=image_ids,
        )

    def _split_paragraphs(self, text: str) -> list[str]:
        """Split text into paragraphs"""
        # Split on double newlines or multiple newlines
        paragraphs = re.split(r"\n\s*\n", text)

        # Clean and filter
        cleaned = []
        for para in paragraphs:
            para = para.strip()
            if para and len(para) > 20:  # Skip very short fragments
                cleaned.append(para)

        return cleaned

    def _split_large_paragraph(self, text: str) -> list[str]:
        """Split a large paragraph into smaller chunks"""
        chunks = []
        sentences = re.split(r"(?<=[.!?])\s+", text)

        current = []
        current_length = 0

        for sentence in sentences:
            if current_length + len(sentence) > self.chunk_size and current:
                chunks.append(" ".join(current))
                current = [sentence]
                current_length = len(sentence)
            else:
                current.append(sentence)
                current_length += len(sentence)

        if current:
            chunks.append(" ".join(current))

        return chunks

    def _classify_content(self, text: str) -> ChunkType:
        """Classify the type of content in a chunk"""
        text_lower = text.lower()

        # Count pattern matches for each type
        scores = {
            ChunkType.PROCEDURE_STEP: self._count_pattern_matches(
                text_lower, self.PROCEDURE_PATTERNS
            ),
            ChunkType.ANATOMY: self._count_pattern_matches(
                text_lower, self.ANATOMY_PATTERNS
            ),
            ChunkType.COMPLICATIONS: self._count_pattern_matches(
                text_lower, self.COMPLICATIONS_PATTERNS
            ),
            ChunkType.OUTCOMES: self._count_pattern_matches(
                text_lower, self.OUTCOMES_PATTERNS
            ),
        }

        # Check for positioning specifically
        if "position" in text_lower and (
            "patient" in text_lower or "head" in text_lower
        ):
            if scores[ChunkType.PROCEDURE_STEP] > 0:
                return ChunkType.POSITIONING

        # Find highest scoring type
        max_type = max(scores, key=scores.get)
        if scores[max_type] >= 2:  # Require at least 2 matches
            return max_type

        return ChunkType.NARRATIVE

    def _count_pattern_matches(self, text: str, patterns: list[str]) -> int:
        """Count how many patterns match in text"""
        count = 0
        for pattern in patterns:
            count += len(re.findall(pattern, text, re.IGNORECASE))
        return count

    def _generate_chunk_id(self, source_id: str, section_title: str, index: int) -> str:
        """Generate a unique chunk ID"""
        hash_input = f"{source_id}_{section_title}_{index}"
        return hashlib.md5(hash_input.encode()).hexdigest()[:16]
