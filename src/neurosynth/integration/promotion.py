"""Promotion Pipeline for Reference Library → NeuroSynth handoff.

This module enables seamless handoff from the Reference Library GUI to
NeuroSynth CLI, reusing cached data (extracted text, embeddings) to avoid
redundant processing.

Workflow:
1. User selects PDFs in Reference Library and clicks "Promote to NeuroSynth"
2. PromotionPipeline exports selected papers with cached data
3. NeuroSynth imports promoted papers, skipping re-extraction/re-embedding
4. User runs synthesis in NeuroSynth CLI with reduced latency

Data Reuse:
- Extracted text from Reference Library cache (PDFSearcher)
- Embeddings if compatible models used
- Metadata (title, authors, DOI, year)
"""

import json
import sqlite3
import zipfile
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Iterator

from rich.console import Console

from neurosynth import get_logger
from neurosynth.config import get_settings
from neurosynth.shared.database import SharedDatabase

console = Console()
logger = get_logger("integration.promotion")


@dataclass
class PromotedPaper:
    """A paper promoted from Reference Library to NeuroSynth."""

    # Identifiers
    pdf_path: Path
    reference_id: str | None = None  # Reference Library internal ID
    doi: str | None = None

    # Metadata
    title: str | None = None
    authors: list[str] = field(default_factory=list)
    year: int | None = None
    journal: str | None = None

    # Cached content (from Reference Library)
    extracted_text: str | None = None
    page_texts: dict[int, str] = field(default_factory=dict)  # page_num -> text

    # Optional embeddings (if compatible)
    text_embeddings: dict[str, list[float]] | None = None
    embedding_model: str | None = None

    # Processing status
    needs_extraction: bool = True
    needs_embedding: bool = True


@dataclass
class PromotionManifest:
    """Manifest describing a promotion batch."""

    id: str
    created_at: datetime
    source: str = "reference-library"
    papers: list[PromotedPaper] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


class PromotionPipeline:
    """Handle Reference Library to NeuroSynth promotion."""

    # Export format version for compatibility checking
    FORMAT_VERSION = "1.0"

    def __init__(self, reference_library_path: Path | None = None):
        """Initialize the promotion pipeline.

        Args:
            reference_library_path: Path to Reference Library data directory.
                                   Defaults to ~/.reference-library/
        """
        self.rl_path = reference_library_path or Path.home() / ".reference-library"
        self.rl_db = SharedDatabase(self.rl_path / "cache.db")

    def list_available_papers(self) -> list[dict[str, Any]]:
        """List papers available in Reference Library for promotion.

        Returns:
            List of paper info dicts with title, authors, path, etc.
        """
        papers = []

        try:
            with self.rl_db.get_connection() as conn:
                # Query the documents table
                cursor = conn.execute("""
                    SELECT id, file_path, title, authors, year, doi, created_at
                    FROM documents
                    WHERE extracted_text IS NOT NULL
                    ORDER BY created_at DESC
                """)

                for row in cursor:
                    papers.append({
                        "id": row["id"],
                        "path": row["file_path"],
                        "title": row["title"],
                        "authors": json.loads(row["authors"]) if row["authors"] else [],
                        "year": row["year"],
                        "doi": row["doi"],
                        "added_at": row["created_at"],
                    })
        except Exception as e:
            logger.warning(f"Could not list papers from Reference Library: {e}")

        return papers

    def promote_papers(
        self,
        paper_ids: list[str],
        output_path: Path,
        include_embeddings: bool = True,
    ) -> Path:
        """Promote selected papers to a NeuroSynth-compatible bundle.

        Args:
            paper_ids: List of Reference Library paper IDs to promote
            output_path: Directory to write the promotion bundle
            include_embeddings: Include embeddings if available and compatible

        Returns:
            Path to the created promotion bundle (zip file)
        """
        output_path.mkdir(parents=True, exist_ok=True)

        manifest = PromotionManifest(
            id=f"promo_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            created_at=datetime.now(),
            metadata={
                "format_version": self.FORMAT_VERSION,
                "reference_library_path": str(self.rl_path),
            },
        )

        papers_data = []

        for paper_id in paper_ids:
            paper = self._load_paper_from_rl(paper_id, include_embeddings)
            if paper:
                manifest.papers.append(paper)
                papers_data.append(self._paper_to_dict(paper))

        # Write manifest
        manifest_data = {
            "id": manifest.id,
            "created_at": manifest.created_at.isoformat(),
            "source": manifest.source,
            "format_version": self.FORMAT_VERSION,
            "paper_count": len(manifest.papers),
            "papers": papers_data,
        }

        manifest_path = output_path / "manifest.json"
        with open(manifest_path, "w") as f:
            json.dump(manifest_data, f, indent=2)

        # Create zip bundle
        bundle_path = output_path / f"{manifest.id}.nsb"  # NeuroSynth Bundle
        with zipfile.ZipFile(bundle_path, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.write(manifest_path, "manifest.json")

            # Include PDF copies if requested
            for paper in manifest.papers:
                if paper.pdf_path.exists():
                    zf.write(paper.pdf_path, f"pdfs/{paper.pdf_path.name}")

        console.print(f"[green]Created promotion bundle: {bundle_path}[/green]")
        console.print(f"  Papers: {len(manifest.papers)}")

        return bundle_path

    def _load_paper_from_rl(
        self,
        paper_id: str,
        include_embeddings: bool,
    ) -> PromotedPaper | None:
        """Load paper data from Reference Library cache."""
        try:
            with self.rl_db.get_connection() as conn:
                cursor = conn.execute("""
                    SELECT file_path, title, authors, year, doi, extracted_text
                    FROM documents
                    WHERE id = ?
                """, (paper_id,))

                row = cursor.fetchone()
                if not row:
                    return None

                paper = PromotedPaper(
                    pdf_path=Path(row["file_path"]),
                    reference_id=paper_id,
                    title=row["title"],
                    authors=json.loads(row["authors"]) if row["authors"] else [],
                    year=row["year"],
                    doi=row["doi"],
                    extracted_text=row["extracted_text"],
                    needs_extraction=row["extracted_text"] is None,
                )

                # Load page texts if available
                page_cursor = conn.execute("""
                    SELECT page_number, text
                    FROM pages
                    WHERE document_id = ?
                    ORDER BY page_number
                """, (paper_id,))

                for page_row in page_cursor:
                    paper.page_texts[page_row["page_number"]] = page_row["text"]

                return paper

        except Exception as e:
            logger.warning(f"Could not load paper {paper_id}: {e}")
            return None

    def _paper_to_dict(self, paper: PromotedPaper) -> dict[str, Any]:
        """Convert PromotedPaper to serializable dict."""
        return {
            "pdf_path": str(paper.pdf_path),
            "reference_id": paper.reference_id,
            "doi": paper.doi,
            "title": paper.title,
            "authors": paper.authors,
            "year": paper.year,
            "extracted_text": paper.extracted_text,
            "page_texts": {str(k): v for k, v in paper.page_texts.items()},
            "needs_extraction": paper.needs_extraction,
            "needs_embedding": paper.needs_embedding,
        }


class PromotionImporter:
    """Import promoted papers into NeuroSynth project."""

    def __init__(self, project_path: Path):
        """Initialize the importer.

        Args:
            project_path: Path to NeuroSynth project directory
        """
        self.project_path = project_path
        self.sources_dir = project_path / "data" / "sources"
        self.sources_dir.mkdir(parents=True, exist_ok=True)

    def import_bundle(self, bundle_path: Path) -> list[Path]:
        """Import a promotion bundle into the project.

        Args:
            bundle_path: Path to .nsb bundle file

        Returns:
            List of imported PDF paths
        """
        imported = []

        with zipfile.ZipFile(bundle_path, "r") as zf:
            # Read manifest
            manifest_data = json.loads(zf.read("manifest.json"))

            console.print(f"[blue]Importing promotion bundle: {manifest_data['id']}[/blue]")
            console.print(f"  Papers: {manifest_data['paper_count']}")

            for paper_data in manifest_data["papers"]:
                pdf_name = Path(paper_data["pdf_path"]).name
                pdf_in_zip = f"pdfs/{pdf_name}"

                # Extract PDF if included
                if pdf_in_zip in zf.namelist():
                    target_path = self.sources_dir / pdf_name
                    with zf.open(pdf_in_zip) as src, open(target_path, "wb") as dst:
                        dst.write(src.read())
                    imported.append(target_path)
                    console.print(f"  ✓ Imported: {pdf_name}", style="dim")

                # Store cached data for reuse
                self._store_cached_data(paper_data)

        console.print(f"[green]Imported {len(imported)} papers[/green]")
        return imported

    def _store_cached_data(self, paper_data: dict[str, Any]) -> None:
        """Store cached extraction data for reuse during synthesis."""
        # Store in project cache database
        cache_path = self.project_path / "data" / "promotion_cache.json"

        cache = {}
        if cache_path.exists():
            with open(cache_path) as f:
                cache = json.load(f)

        pdf_name = Path(paper_data["pdf_path"]).name
        cache[pdf_name] = {
            "extracted_text": paper_data.get("extracted_text"),
            "page_texts": paper_data.get("page_texts", {}),
            "metadata": {
                "title": paper_data.get("title"),
                "authors": paper_data.get("authors", []),
                "year": paper_data.get("year"),
                "doi": paper_data.get("doi"),
            },
            "needs_extraction": paper_data.get("needs_extraction", True),
        }

        with open(cache_path, "w") as f:
            json.dump(cache, f, indent=2)

    def get_cached_text(self, pdf_name: str) -> str | None:
        """Get cached extracted text for a PDF.

        Args:
            pdf_name: Name of the PDF file

        Returns:
            Cached extracted text or None if not available
        """
        cache_path = self.project_path / "data" / "promotion_cache.json"

        if not cache_path.exists():
            return None

        with open(cache_path) as f:
            cache = json.load(f)

        paper_cache = cache.get(pdf_name, {})
        return paper_cache.get("extracted_text")

    def get_cached_metadata(self, pdf_name: str) -> dict[str, Any] | None:
        """Get cached metadata for a PDF."""
        cache_path = self.project_path / "data" / "promotion_cache.json"

        if not cache_path.exists():
            return None

        with open(cache_path) as f:
            cache = json.load(f)

        paper_cache = cache.get(pdf_name, {})
        return paper_cache.get("metadata")


def promote_from_cli(
    paper_ids: list[str],
    output_dir: Path,
) -> Path:
    """CLI convenience function to promote papers.

    Args:
        paper_ids: Reference Library paper IDs
        output_dir: Output directory

    Returns:
        Path to created bundle
    """
    pipeline = PromotionPipeline()
    return pipeline.promote_papers(paper_ids, output_dir)


def import_from_cli(
    bundle_path: Path,
    project_path: Path,
) -> list[Path]:
    """CLI convenience function to import a bundle.

    Args:
        bundle_path: Path to .nsb bundle
        project_path: NeuroSynth project path

    Returns:
        List of imported PDF paths
    """
    importer = PromotionImporter(project_path)
    return importer.import_bundle(bundle_path)
