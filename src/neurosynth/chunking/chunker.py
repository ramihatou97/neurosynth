"""Semantic chunking for document content."""

import re
from dataclasses import dataclass
from enum import Enum
from typing import Any

from rich.console import Console

from neurosynth.config import get_settings
from neurosynth.models.document import ContentChunk, Document

console = Console()


class ChunkingStrategy(str, Enum):
    """Available chunking strategies."""

    STRUCTURAL = "structural"  # Use document structure (TOC, headings)
    SEMANTIC = "semantic"  # Use AI to find natural boundaries
    FIXED = "fixed"  # Fixed word count chunks
    HYBRID = "hybrid"  # Combine structural + semantic


@dataclass
class ChunkBoundary:
    """Represents a boundary between chunks."""

    position: int
    confidence: float
    reason: str


class SemanticChunker:
    """Chunk documents into meaningful semantic units."""

    def __init__(
        self,
        target_size: int | None = None,
        overlap: int | None = None,
        strategy: ChunkingStrategy = ChunkingStrategy.HYBRID,
    ):
        settings = get_settings()
        self.target_size = target_size or settings.chunk_size
        self.overlap = overlap or settings.chunk_overlap
        self.strategy = strategy

        # Patterns for detecting natural boundaries
        self._heading_pattern = re.compile(
            r"^(#{1,4}|\d+\.[\d.]*)\s+[A-Z]",
            re.MULTILINE,
        )
        self._section_markers = [
            r"^Introduction\s*$",
            r"^Background\s*$",
            r"^Methods?\s*$",
            r"^Results?\s*$",
            r"^Discussion\s*$",
            r"^Conclusion\s*$",
            r"^References?\s*$",
            r"^Surgical Technique\s*$",
            r"^Complications?\s*$",
            r"^Anatomy\s*$",
            r"^Pathophysiology\s*$",
        ]

    async def chunk_document(self, doc: Document) -> list[ContentChunk]:
        """Chunk a document using the configured strategy."""
        if self.strategy == ChunkingStrategy.STRUCTURAL:
            return await self._chunk_structural(doc)
        elif self.strategy == ChunkingStrategy.FIXED:
            return self._chunk_fixed(doc)
        elif self.strategy == ChunkingStrategy.HYBRID:
            return await self._chunk_hybrid(doc)
        else:
            return await self._chunk_semantic(doc)

    async def _chunk_structural(self, doc: Document) -> list[ContentChunk]:
        """Chunk based on document structure (TOC, headings)."""
        chunks = []

        if doc.toc:
            # Use TOC to guide chunking
            text = doc.raw_text
            toc_positions = self._find_toc_positions(text, doc.toc)

            for i, (start, entry) in enumerate(toc_positions):
                end = (
                    toc_positions[i + 1][0] if i + 1 < len(toc_positions) else len(text)
                )
                content = text[start:end].strip()

                if content:
                    chunk = doc.add_chunk(
                        content=content,
                        section_title=entry.get("title", ""),
                        chapter_title=doc.source.title,
                    )
                    chunks.append(chunk)

        else:
            # Fallback to heading-based chunking
            chunks = self._chunk_by_headings(doc)

        return chunks

    def _chunk_fixed(self, doc: Document) -> list[ContentChunk]:
        """Chunk into fixed-size segments with overlap."""
        chunks = []
        words = doc.raw_text.split()
        total_words = len(words)

        i = 0
        chunk_num = 0
        while i < total_words:
            # Get chunk words
            end = min(i + self.target_size, total_words)
            chunk_words = words[i:end]
            content = " ".join(chunk_words)

            chunk = doc.add_chunk(
                content=content,
                section_title=f"Segment {chunk_num + 1}",
            )
            chunks.append(chunk)

            # Move forward with overlap
            i += self.target_size - self.overlap
            chunk_num += 1

        return chunks

    async def _chunk_hybrid(self, doc: Document) -> list[ContentChunk]:
        """Combine structural and semantic chunking."""
        chunks = []

        # First pass: structural chunking
        structural_chunks = await self._chunk_structural(doc)

        # Second pass: split large chunks, merge small ones
        for chunk in structural_chunks:
            if chunk.word_count > self.target_size * 1.5:
                # Split large chunks
                sub_chunks = self._split_large_chunk(chunk, doc)
                chunks.extend(sub_chunks)
            elif chunk.word_count < self.target_size * 0.3:
                # Mark for potential merging (handled later)
                chunk.cluster_id = "small"
                chunks.append(chunk)
            else:
                chunks.append(chunk)

        # Merge small adjacent chunks
        chunks = self._merge_small_chunks(chunks, doc)

        return chunks

    async def _chunk_semantic(self, doc: Document) -> list[ContentChunk]:
        """Use AI to find semantic boundaries."""
        from neurosynth.llm.gemini import GeminiClient

        gemini = GeminiClient()
        segments = await gemini.segment_into_chunks(
            doc.raw_text,
            target_size=self.target_size,
        )

        chunks = []
        for seg in segments:
            chunk = doc.add_chunk(
                content=seg["content"],
                section_title=seg.get("suggested_title", ""),
            )
            chunks.append(chunk)

        return chunks

    def _chunk_by_headings(self, doc: Document) -> list[ContentChunk]:
        """Chunk based on heading patterns in text."""
        chunks = []
        text = doc.raw_text

        # Find all headings
        heading_positions = []
        for match in self._heading_pattern.finditer(text):
            heading_positions.append(match.start())

        # Also check for section markers
        for pattern in self._section_markers:
            for match in re.finditer(pattern, text, re.MULTILINE | re.IGNORECASE):
                heading_positions.append(match.start())

        heading_positions = sorted(set(heading_positions))

        if not heading_positions:
            # No headings found, use fixed chunking
            return self._chunk_fixed(doc)

        # Create chunks between headings
        for i, start in enumerate(heading_positions):
            end = (
                heading_positions[i + 1]
                if i + 1 < len(heading_positions)
                else len(text)
            )
            content = text[start:end].strip()

            if content:
                # Extract heading from content
                first_line = content.split("\n")[0].strip()
                section_title = re.sub(r"^[#\d.]+\s*", "", first_line)

                chunk = doc.add_chunk(
                    content=content,
                    section_title=section_title,
                )
                chunks.append(chunk)

        return chunks

    def _find_toc_positions(
        self,
        text: str,
        toc: list[dict[str, Any]],
    ) -> list[tuple[int, dict]]:
        """Find positions of TOC entries in text."""
        positions = []

        for entry in toc:
            title = entry.get("title", "")
            if not title:
                continue

            # Search for title in text
            pattern = re.escape(title)
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                positions.append((match.start(), entry))

        return sorted(positions, key=lambda x: x[0])

    def _split_large_chunk(
        self,
        chunk: ContentChunk,
        doc: Document,
    ) -> list[ContentChunk]:
        """Split a large chunk into smaller pieces."""
        chunks = []
        text = chunk.content
        text = chunk.content
        # words = text.split()

        # Find natural split points (paragraphs, sentences)
        paragraphs = text.split("\n\n")

        current_content = []
        current_words = 0

        for para in paragraphs:
            para_words = len(para.split())

            if current_words + para_words > self.target_size and current_content:
                # Create chunk from current content
                content = "\n\n".join(current_content)
                new_chunk = doc.add_chunk(
                    content=content,
                    section_title=chunk.section_title,
                    chapter_title=chunk.chapter_title,
                )
                chunks.append(new_chunk)

                current_content = [para]
                current_words = para_words
            else:
                current_content.append(para)
                current_words += para_words

        # Add remaining content
        if current_content:
            content = "\n\n".join(current_content)
            new_chunk = doc.add_chunk(
                content=content,
                section_title=chunk.section_title,
                chapter_title=chunk.chapter_title,
            )
            chunks.append(new_chunk)

        return chunks

    def _merge_small_chunks(
        self,
        chunks: list[ContentChunk],
        doc: Document,
    ) -> list[ContentChunk]:
        """Merge small adjacent chunks."""
        if len(chunks) <= 1:
            return chunks

        merged = []
        i = 0

        while i < len(chunks):
            current = chunks[i]

            # Check if current and next are both small
            if (
                current.cluster_id == "small"
                and i + 1 < len(chunks)
                and chunks[i + 1].cluster_id == "small"
            ):
                # Merge chunks
                combined_content = current.content + "\n\n" + chunks[i + 1].content
                merged_chunk = doc.add_chunk(
                    content=combined_content,
                    section_title=current.section_title or chunks[i + 1].section_title,
                    chapter_title=current.chapter_title,
                )
                merged.append(merged_chunk)
                i += 2
            else:
                current.cluster_id = None  # Clear temporary marker
                merged.append(current)
                i += 1

        return merged
