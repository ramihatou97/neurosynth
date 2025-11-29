"""PDF document parser using PyMuPDF."""

import asyncio
from pathlib import Path
from typing import Any

import fitz  # PyMuPDF
from rich.console import Console

from neurosynth.models.document import Document, DocumentFormat
from neurosynth.parsers.base import BaseParser

console = Console()


class PDFParser(BaseParser):
    """Parser for PDF documents using PyMuPDF."""

    supported_formats = [DocumentFormat.PDF]

    def __init__(self):
        super().__init__()
        self._use_pymupdf4llm = True

    async def parse(self, path: Path) -> Document:
        """Parse a PDF document with optional image extraction."""
        if not path.exists():
            raise FileNotFoundError(f"PDF not found: {path}")

        # Extract metadata first
        metadata = await self.extract_metadata(path)
        source = self._create_source(path, metadata)

        # Extract text
        raw_text = await self.extract_text(path)

        # Create document
        doc = Document(
            source=source,
            raw_text=raw_text,
            is_parsed=True,
        )

        # Get page count
        doc.total_pages = await self._get_page_count(path)

        # Extract table of contents if available
        doc.toc = await self._extract_toc(path)

        # Extract images if enabled
        from neurosynth.config import get_settings

        settings = get_settings()
        if settings.enable_visual_extraction:
            try:
                from neurosynth.parsers.image_extractor import ImageExtractor

                extractor = ImageExtractor()
                output_dir = settings.processed_dir / "images" / path.stem
                doc.visual_elements = await extractor.extract_images(path, output_dir)
            except Exception as e:
                console.print(f"[yellow]Warning: Image extraction failed: {e}[/yellow]")
                doc.parse_errors.append(f"Image extraction failed: {e}")

        return doc

    async def extract_text(self, path: Path) -> str:
        """Extract text from PDF."""
        loop = asyncio.get_event_loop()

        # Try pymupdf4llm first for better layout preservation
        if self._use_pymupdf4llm:
            try:
                import pymupdf4llm

                text = await loop.run_in_executor(
                    None,
                    lambda: pymupdf4llm.to_markdown(str(path)),
                )
                return text
            except Exception as e:
                self._log_error(f"pymupdf4llm failed, falling back: {e}")

        # Fallback to basic PyMuPDF extraction
        def extract():
            text_parts = []
            with fitz.open(path) as pdf:
                for page_num, page in enumerate(pdf):
                    text = page.get_text("text")
                    if text.strip():
                        text_parts.append(f"[Page {page_num + 1}]\n{text}")
            return "\n\n".join(text_parts)

        return await loop.run_in_executor(None, extract)

    async def extract_metadata(self, path: Path) -> dict[str, Any]:
        """Extract metadata from PDF."""
        loop = asyncio.get_event_loop()

        def extract():
            with fitz.open(path) as pdf:
                meta = pdf.metadata or {}
                return {
                    "title": meta.get("title", ""),
                    "authors": self._parse_authors(meta.get("author", "")),
                    "year": self._extract_year(meta.get("creationDate", "")),
                    "publisher": meta.get("producer", ""),
                    "page_count": pdf.page_count,
                }

        return await loop.run_in_executor(None, extract)

    async def _get_page_count(self, path: Path) -> int:
        """Get total page count."""
        loop = asyncio.get_event_loop()

        def count():
            with fitz.open(path) as pdf:
                return pdf.page_count

        return await loop.run_in_executor(None, count)

    async def _extract_toc(self, path: Path) -> list[dict[str, Any]]:
        """Extract table of contents."""
        loop = asyncio.get_event_loop()

        def extract():
            with fitz.open(path) as pdf:
                toc = pdf.get_toc()
                return [
                    {
                        "level": item[0],
                        "title": item[1],
                        "page": item[2],
                    }
                    for item in toc
                ]

        return await loop.run_in_executor(None, extract)

    async def extract_page_text(self, path: Path, page_num: int) -> str:
        """Extract text from a specific page."""
        loop = asyncio.get_event_loop()

        def extract():
            with fitz.open(path) as pdf:
                if 0 <= page_num < pdf.page_count:
                    return pdf[page_num].get_text("text")
                return ""

        return await loop.run_in_executor(None, extract)

    async def extract_page_range(
        self,
        path: Path,
        start: int,
        end: int,
    ) -> str:
        """Extract text from a range of pages."""
        loop = asyncio.get_event_loop()

        def extract():
            texts = []
            with fitz.open(path) as pdf:
                for page_num in range(start, min(end, pdf.page_count)):
                    text = pdf[page_num].get_text("text")
                    if text.strip():
                        texts.append(f"[Page {page_num + 1}]\n{text}")
            return "\n\n".join(texts)

        return await loop.run_in_executor(None, extract)

    def _parse_authors(self, author_str: str) -> list[str]:
        """Parse author string into list of names."""
        if not author_str:
            return []

        # Common separators
        for sep in [";", " and ", "&", ","]:
            if sep in author_str:
                return [a.strip() for a in author_str.split(sep) if a.strip()]

        return [author_str.strip()] if author_str.strip() else []

    def _extract_year(self, date_str: str) -> int | None:
        """Extract year from PDF date string."""
        if not date_str:
            return None

        # PDF date format: D:YYYYMMDDHHmmSS
        import re

        match = re.search(r"(?:D:)?(\d{4})", date_str)
        if match:
            year = int(match.group(1))
            if 1900 <= year <= 2100:
                return year

        return None


class PDFChunkExtractor:
    """Extract meaningful chunks from PDF based on structure."""

    def __init__(self, parser: PDFParser):
        self.parser = parser

    async def extract_by_toc(
        self,
        path: Path,
        doc: Document,
    ) -> list[dict[str, Any]]:
        """Extract chunks based on table of contents."""
        if not doc.toc:
            return []

        chunks = []
        for i, entry in enumerate(doc.toc):
            start_page = entry["page"] - 1  # 0-indexed

            # Find end page (next entry's page or end of document)
            if i + 1 < len(doc.toc):
                end_page = doc.toc[i + 1]["page"] - 1
            else:
                end_page = doc.total_pages

            # Extract text for this section
            text = await self.parser.extract_page_range(path, start_page, end_page)

            if text.strip():
                chunks.append(
                    {
                        "content": text,
                        "section_title": entry["title"],
                        "level": entry["level"],
                        "start_page": start_page + 1,
                        "end_page": end_page,
                    }
                )

        return chunks

    async def extract_by_pages(
        self,
        path: Path,
        pages_per_chunk: int = 5,
    ) -> list[dict[str, Any]]:
        """Extract chunks by page groups (fallback when no TOC)."""
        page_count = await self.parser._get_page_count(path)
        chunks = []

        for start in range(0, page_count, pages_per_chunk):
            end = min(start + pages_per_chunk, page_count)
            text = await self.parser.extract_page_range(path, start, end)

            if text.strip():
                chunks.append(
                    {
                        "content": text,
                        "start_page": start + 1,
                        "end_page": end,
                    }
                )

        return chunks
