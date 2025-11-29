"""Tests for document parsers."""

import pytest

from neurosynth.models.document import DocumentFormat, Source
from neurosynth.parsers.base import ParserFactory


class TestDocumentFormat:
    """Tests for DocumentFormat enum."""

    def test_from_path_pdf(self, tmp_path):
        """Test PDF format detection."""
        pdf_path = tmp_path / "test.pdf"
        pdf_path.touch()
        assert DocumentFormat.from_path(pdf_path) == DocumentFormat.PDF

    def test_from_path_epub(self, tmp_path):
        """Test EPUB format detection."""
        epub_path = tmp_path / "test.epub"
        epub_path.touch()
        assert DocumentFormat.from_path(epub_path) == DocumentFormat.EPUB

    def test_from_path_docx(self, tmp_path):
        """Test DOCX format detection."""
        docx_path = tmp_path / "test.docx"
        docx_path.touch()
        assert DocumentFormat.from_path(docx_path) == DocumentFormat.DOCX

    def test_from_path_txt(self, tmp_path):
        """Test TXT format detection."""
        txt_path = tmp_path / "test.txt"
        txt_path.touch()
        assert DocumentFormat.from_path(txt_path) == DocumentFormat.TXT

    def test_from_path_unsupported(self, tmp_path):
        """Test unsupported format raises error."""
        unsupported = tmp_path / "test.xyz"
        unsupported.touch()
        with pytest.raises(ValueError):
            DocumentFormat.from_path(unsupported)


class TestSource:
    """Tests for Source model."""

    def test_source_creation(self, tmp_path):
        """Test basic source creation."""
        path = tmp_path / "test.pdf"
        path.touch()

        source = Source(
            path=path,
            format=DocumentFormat.PDF,
            title="Test Document",
            authors=["Author One", "Author Two"],
            year=2023,
        )

        assert source.title == "Test Document"
        assert len(source.authors) == 2
        assert source.year == 2023

    def test_source_citation_key(self, tmp_path):
        """Test citation key generation."""
        path = tmp_path / "test.pdf"
        path.touch()

        source = Source(
            path=path,
            format=DocumentFormat.PDF,
            authors=["John Smith"],
            year=2023,
        )

        assert source.citation_key == "Smith2023"

    def test_source_title_from_filename(self, tmp_path):
        """Test title derivation from filename."""
        path = tmp_path / "vestibular_schwannoma_chapter.pdf"
        path.touch()

        source = Source(
            path=path,
            format=DocumentFormat.PDF,
        )

        assert "vestibular" in source.title.lower()


class TestParserFactory:
    """Tests for ParserFactory."""

    def test_get_parser_pdf(self, tmp_path):
        """Test getting PDF parser."""
        path = tmp_path / "test.pdf"
        path.touch()

        parser = ParserFactory.get_parser(path)
        assert parser.__class__.__name__ == "PDFParser"

    def test_get_parser_epub(self, tmp_path):
        """Test getting EPUB parser."""
        path = tmp_path / "test.epub"
        path.touch()

        parser = ParserFactory.get_parser(path)
        assert parser.__class__.__name__ == "EPUBParser"


@pytest.fixture
def sample_text():
    """Sample neurosurgical text for testing."""
    return """
# Vestibular Schwannoma

## Introduction

Vestibular schwannomas are benign tumors arising from the Schwann cells
of the vestibular portion of cranial nerve VIII.

## Epidemiology

The incidence is approximately 1 per 100,000 per year. These tumors
account for 6-8% of all intracranial tumors.

## Surgical Technique

Three main approaches are used:
- Retrosigmoid approach
- Middle fossa approach
- Translabyrinthine approach
"""


class TestTXTParser:
    """Tests for TXT parser."""

    @pytest.mark.asyncio
    async def test_parse_txt(self, tmp_path, sample_text):
        """Test parsing a text file."""
        from neurosynth.parsers.txt_parser import TXTParser

        txt_path = tmp_path / "test.txt"
        txt_path.write_text(sample_text)

        parser = TXTParser()
        doc = await parser.parse(txt_path)

        assert doc.is_parsed
        assert "Vestibular Schwannoma" in doc.raw_text
        assert len(doc.toc) > 0  # Should infer structure

    @pytest.mark.asyncio
    async def test_infer_structure(self, tmp_path, sample_text):
        """Test structure inference from text."""
        from neurosynth.parsers.txt_parser import TXTParser

        txt_path = tmp_path / "test.txt"
        txt_path.write_text(sample_text)

        parser = TXTParser()
        doc = await parser.parse(txt_path)

        # Should find markdown headings
        titles = [entry["title"] for entry in doc.toc]
        assert any("Introduction" in t for t in titles)
