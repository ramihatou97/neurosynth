"""Base parser interface and factory."""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import TYPE_CHECKING

from neurosynth.models.document import Document, DocumentFormat, Source

if TYPE_CHECKING:
    pass


class BaseParser(ABC):
    """Abstract base class for document parsers."""

    supported_formats: list[DocumentFormat] = []

    def __init__(self):
        self.errors: list[str] = []

    @abstractmethod
    async def parse(self, path: Path) -> Document:
        """Parse a document and return structured content.

        Args:
            path: Path to the document file

        Returns:
            Document object with extracted content and metadata
        """
        pass

    @abstractmethod
    async def extract_text(self, path: Path) -> str:
        """Extract raw text from document.

        Args:
            path: Path to the document file

        Returns:
            Raw text content
        """
        pass

    @abstractmethod
    async def extract_metadata(self, path: Path) -> dict:
        """Extract document metadata.

        Args:
            path: Path to the document file

        Returns:
            Dictionary of metadata fields
        """
        pass

    def _create_source(self, path: Path, metadata: dict) -> Source:
        """Create a Source object from path and metadata."""
        return Source(
            path=path,
            format=DocumentFormat.from_path(path),
            title=metadata.get("title", ""),
            authors=metadata.get("authors", []),
            year=metadata.get("year"),
            edition=metadata.get("edition"),
            publisher=metadata.get("publisher"),
        )

    def _log_error(self, message: str) -> None:
        """Log a parsing error."""
        self.errors.append(message)


class ParserFactory:
    """Factory for creating appropriate parser based on file format."""

    _parsers: dict[DocumentFormat, type[BaseParser]] = {}

    @classmethod
    def register(cls, format: DocumentFormat, parser_class: type[BaseParser]) -> None:
        """Register a parser for a format."""
        cls._parsers[format] = parser_class

    @classmethod
    def get_parser(cls, path: Path) -> BaseParser:
        """Get appropriate parser for a file.

        Args:
            path: Path to the document

        Returns:
            Parser instance for the file format

        Raises:
            ValueError: If no parser registered for format
        """
        format = DocumentFormat.from_path(path)

        if format not in cls._parsers:
            # Lazy import to avoid circular imports
            cls._register_defaults()

        if format not in cls._parsers:
            raise ValueError(f"No parser registered for format: {format}")

        return cls._parsers[format]()

    @classmethod
    def _register_defaults(cls) -> None:
        """Register default parsers."""
        from neurosynth.parsers.docx_parser import DOCXParser
        from neurosynth.parsers.epub_parser import EPUBParser
        from neurosynth.parsers.pdf_parser import PDFParser
        from neurosynth.parsers.txt_parser import TXTParser

        cls._parsers[DocumentFormat.PDF] = PDFParser
        cls._parsers[DocumentFormat.EPUB] = EPUBParser
        cls._parsers[DocumentFormat.DOCX] = DOCXParser
        cls._parsers[DocumentFormat.TXT] = TXTParser

    @classmethod
    def parse(cls, path: Path) -> Document:
        """Convenience method to parse a document.

        Args:
            path: Path to the document

        Returns:
            Parsed Document object
        """
        import asyncio

        parser = cls.get_parser(path)
        return asyncio.run(parser.parse(path))
