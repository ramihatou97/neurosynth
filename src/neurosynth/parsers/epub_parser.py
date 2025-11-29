"""EPUB document parser using ebooklib."""

import asyncio
from pathlib import Path
from typing import Any

from bs4 import BeautifulSoup
from rich.console import Console

from neurosynth.models.document import Document, DocumentFormat
from neurosynth.parsers.base import BaseParser

console = Console()


class EPUBParser(BaseParser):
    """Parser for EPUB documents using ebooklib."""

    supported_formats = [DocumentFormat.EPUB]

    async def parse(self, path: Path) -> Document:
        """Parse an EPUB document."""
        if not path.exists():
            raise FileNotFoundError(f"EPUB not found: {path}")

        # Extract metadata
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

        # Extract TOC
        doc.toc = await self._extract_toc(path)

        return doc

    async def extract_text(self, path: Path) -> str:
        """Extract text from EPUB."""
        loop = asyncio.get_event_loop()

        def extract():
            import ebooklib
            from ebooklib import epub

            book = epub.read_epub(str(path))
            text_parts = []

            for item in book.get_items():
                if item.get_type() == ebooklib.ITEM_DOCUMENT:
                    # Parse HTML content
                    soup = BeautifulSoup(item.get_content(), "html.parser")

                    # Extract title if present
                    title_elem = soup.find(["h1", "h2", "h3"])
                    if title_elem:
                        text_parts.append(f"\n## {title_elem.get_text().strip()}\n")

                    # Extract body text
                    body = soup.find("body")
                    if body:
                        text = body.get_text(separator="\n", strip=True)
                        if text:
                            text_parts.append(text)

            return "\n\n".join(text_parts)

        return await loop.run_in_executor(None, extract)

    async def extract_metadata(self, path: Path) -> dict[str, Any]:
        """Extract metadata from EPUB."""
        loop = asyncio.get_event_loop()

        def extract():
            from ebooklib import epub

            book = epub.read_epub(str(path))

            # Get title
            title = ""
            title_data = book.get_metadata("DC", "title")
            if title_data:
                title = title_data[0][0] if title_data[0] else ""

            # Get authors
            authors = []
            creator_data = book.get_metadata("DC", "creator")
            for creator in creator_data:
                if creator[0]:
                    authors.append(creator[0])

            # Get publisher
            publisher = ""
            pub_data = book.get_metadata("DC", "publisher")
            if pub_data:
                publisher = pub_data[0][0] if pub_data[0] else ""

            # Get year from date
            year = None
            date_data = book.get_metadata("DC", "date")
            if date_data and date_data[0]:
                import re

                match = re.search(r"(\d{4})", str(date_data[0][0]))
                if match:
                    year = int(match.group(1))

            return {
                "title": title,
                "authors": authors,
                "publisher": publisher,
                "year": year,
            }

        return await loop.run_in_executor(None, extract)

    async def _extract_toc(self, path: Path) -> list[dict[str, Any]]:
        """Extract table of contents from EPUB."""
        loop = asyncio.get_event_loop()

        def extract():
            from ebooklib import epub

            book = epub.read_epub(str(path))
            toc = []

            def process_toc_item(item, level=1):
                if isinstance(item, tuple):
                    # Section with children
                    section, children = item
                    toc.append(
                        {
                            "level": level,
                            "title": section.title,
                            "href": section.href if hasattr(section, "href") else "",
                        }
                    )
                    for child in children:
                        process_toc_item(child, level + 1)
                elif hasattr(item, "title"):
                    # Single link
                    toc.append(
                        {
                            "level": level,
                            "title": item.title,
                            "href": item.href if hasattr(item, "href") else "",
                        }
                    )

            for item in book.toc:
                process_toc_item(item)

            return toc

        return await loop.run_in_executor(None, extract)

    async def extract_chapters(self, path: Path) -> list[dict[str, Any]]:
        """Extract individual chapters from EPUB."""
        loop = asyncio.get_event_loop()

        def extract():
            import ebooklib
            from ebooklib import epub

            book = epub.read_epub(str(path))
            chapters = []

            for item in book.get_items():
                if item.get_type() == ebooklib.ITEM_DOCUMENT:
                    soup = BeautifulSoup(item.get_content(), "html.parser")

                    # Get chapter title
                    title = ""
                    title_elem = soup.find(["h1", "h2"])
                    if title_elem:
                        title = title_elem.get_text().strip()

                    # Get body text
                    body = soup.find("body")
                    if body:
                        text = body.get_text(separator="\n", strip=True)
                        if text and len(text) > 100:  # Skip very short items
                            chapters.append(
                                {
                                    "title": title or item.get_name(),
                                    "content": text,
                                    "item_name": item.get_name(),
                                }
                            )

            return chapters

        return await loop.run_in_executor(None, extract)
