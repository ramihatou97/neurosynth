"""Plain text document parser with structure inference."""

import asyncio
import re
from pathlib import Path
from typing import Any

from rich.console import Console

from neurosynth.models.document import Document, DocumentFormat
from neurosynth.parsers.base import BaseParser

console = Console()


class TXTParser(BaseParser):
    """Parser for plain text documents with structure inference."""

    supported_formats = [DocumentFormat.TXT]

    async def parse(self, path: Path) -> Document:
        """Parse a plain text document."""
        if not path.exists():
            raise FileNotFoundError(f"Text file not found: {path}")

        # Extract metadata (limited for plain text)
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

        # Infer structure
        doc.toc = await self._infer_structure(raw_text)

        return doc

    async def extract_text(self, path: Path) -> str:
        """Extract text from file."""
        loop = asyncio.get_event_loop()

        def extract():
            # Try different encodings
            encodings = ["utf-8", "latin-1", "cp1252"]

            for encoding in encodings:
                try:
                    with open(path, "r", encoding=encoding) as f:
                        return f.read()
                except UnicodeDecodeError:
                    continue

            # Last resort: read with errors ignored
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                return f.read()

        return await loop.run_in_executor(None, extract)

    async def extract_metadata(self, path: Path) -> dict[str, Any]:
        """Extract metadata from text file (limited)."""
        # Read first few lines for potential metadata
        loop = asyncio.get_event_loop()

        def extract():
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                first_lines = [f.readline() for _ in range(10)]

            title = ""
            authors = []
            year = None

            # Look for title in first non-empty line
            for line in first_lines:
                line = line.strip()
                if line and not line.startswith("#"):
                    # Likely title
                    title = line
                    break
                elif line.startswith("# "):
                    title = line[2:].strip()
                    break

            # Look for year pattern
            text = "".join(first_lines)
            year_match = re.search(r"\b(19|20)\d{2}\b", text)
            if year_match:
                year = int(year_match.group())

            # Look for author patterns
            author_match = re.search(
                r"(?:Author|By|Written by)[:\s]+([^\n]+)",
                text,
                re.IGNORECASE,
            )
            if author_match:
                authors = [a.strip() for a in author_match.group(1).split(",")]

            return {
                "title": title,
                "authors": authors,
                "year": year,
            }

        return await loop.run_in_executor(None, extract)

    async def _infer_structure(self, text: str) -> list[dict[str, Any]]:
        """Infer document structure from text patterns."""
        toc = []

        # Pattern 1: Markdown-style headings
        md_headings = re.finditer(r"^(#{1,4})\s+(.+)$", text, re.MULTILINE)
        for match in md_headings:
            level = len(match.group(1))
            title = match.group(2).strip()
            toc.append({"level": level, "title": title})

        if toc:
            return toc

        # Pattern 2: Numbered sections
        numbered = re.finditer(
            r"^(\d+(?:\.\d+)*)[.\s]+([A-Z][^\n]+)$",
            text,
            re.MULTILINE,
        )
        for match in numbered:
            number = match.group(1)
            title = match.group(2).strip()
            level = number.count(".") + 1
            toc.append({"level": level, "title": f"{number} {title}"})

        if toc:
            return toc

        # Pattern 3: ALL CAPS headings
        caps_headings = re.finditer(r"^([A-Z][A-Z\s]{5,})$", text, re.MULTILINE)
        for match in caps_headings:
            title = match.group(1).strip()
            # Skip if it's just a few words
            if len(title) > 10:
                toc.append({"level": 1, "title": title.title()})

        return toc

    async def extract_sections(self, path: Path) -> list[dict[str, Any]]:
        """Extract sections based on inferred structure."""
        text = await self.extract_text(path)
        toc = await self._infer_structure(text)

        if not toc:
            # No structure found, return whole document
            return [{"title": "Content", "content": text}]

        sections = []

        # Find section boundaries
        for i, entry in enumerate(toc):
            title = entry["title"]

            # Find start of section
            start_match = re.search(
                re.escape(title),
                text,
                re.IGNORECASE,
            )
            if not start_match:
                continue

            start = start_match.end()

            # Find end (start of next section or end of document)
            if i + 1 < len(toc):
                next_title = toc[i + 1]["title"]
                end_match = re.search(
                    re.escape(next_title),
                    text[start:],
                    re.IGNORECASE,
                )
                if end_match:
                    end = start + end_match.start()
                else:
                    end = len(text)
            else:
                end = len(text)

            content = text[start:end].strip()
            if content:
                sections.append(
                    {
                        "title": title,
                        "content": content,
                        "level": entry["level"],
                    }
                )

        return sections
