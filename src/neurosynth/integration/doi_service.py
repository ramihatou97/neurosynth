"""DOI Resolution Service using CrossRef API.

Resolves DOIs to authoritative bibliographic metadata for proper citation
generation. Uses CrossRef as the primary source for academic paper metadata.

Features:
- DOI extraction from PDFs and text
- CrossRef API integration
- BibTeX generation
- Caching to reduce API calls
"""

import asyncio
import hashlib
import json
import re
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import httpx
from rich.console import Console

from neurosynth import get_logger
from neurosynth.config import get_settings

console = Console()
logger = get_logger("integration.doi_service")


@dataclass
class BibliographicRecord:
    """Bibliographic information resolved from DOI."""

    doi: str
    title: str | None = None
    authors: list[str] = field(default_factory=list)
    year: int | None = None
    journal: str | None = None
    volume: str | None = None
    issue: str | None = None
    pages: str | None = None
    publisher: str | None = None
    abstract: str | None = None
    keywords: list[str] = field(default_factory=list)
    citation_count: int | None = None

    # Raw response for additional fields
    raw_data: dict[str, Any] = field(default_factory=dict)

    @property
    def bibkey(self) -> str:
        """Generate a BibTeX key from the record."""
        first_author = self.authors[0].split()[-1] if self.authors else "Unknown"
        year_str = str(self.year) if self.year else "nd"
        # Sanitize for BibTeX
        bibkey = re.sub(r"[^a-zA-Z0-9]", "", f"{first_author}{year_str}")
        return bibkey

    def to_bibtex(self) -> str:
        """Generate BibTeX entry."""
        entry_type = "article" if self.journal else "misc"
        authors_str = " and ".join(self.authors) if self.authors else "Unknown"

        lines = [
            f"@{entry_type}{{{self.bibkey},",
            f'    author = {{{authors_str}}},',
            f'    title = {{{self.title or "Untitled"}}},',
            f'    year = {{{self.year or "n.d."}}},',
        ]

        if self.journal:
            lines.append(f'    journal = {{{self.journal}}},')
        if self.volume:
            lines.append(f'    volume = {{{self.volume}}},')
        if self.issue:
            lines.append(f'    number = {{{self.issue}}},')
        if self.pages:
            lines.append(f'    pages = {{{self.pages}}},')
        if self.publisher:
            lines.append(f'    publisher = {{{self.publisher}}},')
        lines.append(f'    doi = {{{self.doi}}},')
        lines.append("}")

        return "\n".join(lines)


class DOICache:
    """SQLite-based cache for DOI resolutions."""

    def __init__(self, cache_path: Path):
        """Initialize the DOI cache.

        Args:
            cache_path: Path to cache database
        """
        self.db_path = cache_path
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self) -> None:
        """Initialize database schema."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("""
                CREATE TABLE IF NOT EXISTS doi_cache (
                    doi TEXT PRIMARY KEY,
                    data TEXT NOT NULL,
                    resolved_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    expires_at TIMESTAMP
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_expires
                ON doi_cache(expires_at)
            """)

    def get(self, doi: str) -> dict[str, Any] | None:
        """Get cached DOI resolution."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "SELECT data, expires_at FROM doi_cache WHERE doi = ?",
                (doi.lower(),),
            )
            row = cursor.fetchone()
            if row:
                expires_at = datetime.fromisoformat(row[1]) if row[1] else None
                if expires_at is None or expires_at > datetime.now():
                    return json.loads(row[0])
        return None

    def set(self, doi: str, data: dict[str, Any], ttl_days: int = 30) -> None:
        """Cache DOI resolution."""
        expires_at = datetime.now() + timedelta(days=ttl_days)
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """INSERT OR REPLACE INTO doi_cache (doi, data, expires_at)
                   VALUES (?, ?, ?)""",
                (doi.lower(), json.dumps(data), expires_at.isoformat()),
            )

    def clear_expired(self) -> int:
        """Clear expired cache entries."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "DELETE FROM doi_cache WHERE expires_at < ?",
                (datetime.now().isoformat(),),
            )
            return cursor.rowcount


class DOIService:
    """Service for resolving DOIs to bibliographic metadata."""

    # CrossRef API endpoint
    CROSSREF_API = "https://api.crossref.org/works"

    # DOI regex pattern
    DOI_PATTERN = re.compile(
        r'\b(10\.\d{4,}/[^\s\]>"]+)',
        re.IGNORECASE,
    )

    def __init__(
        self,
        cache_path: Path | None = None,
        user_agent: str | None = None,
        rate_limit: float = 0.1,  # Seconds between requests
    ):
        """Initialize the DOI service.

        Args:
            cache_path: Path to cache database (default: ~/.neurosynth/doi_cache.db)
            user_agent: User agent for CrossRef API (include email for polite pool)
            rate_limit: Minimum seconds between API requests
        """
        settings = get_settings()
        cache_path = cache_path or (settings.data_dir / "doi_cache.db")
        self.cache = DOICache(cache_path)
        self.rate_limit = rate_limit
        self._last_request = 0.0

        # CrossRef asks for email in user agent for polite pool
        self.user_agent = user_agent or "NeuroSynth/1.0 (mailto:support@neurosynth.dev)"

        self.client = httpx.AsyncClient(
            headers={"User-Agent": self.user_agent},
            timeout=30.0,
        )

    async def close(self) -> None:
        """Close the HTTP client."""
        await self.client.aclose()

    @staticmethod
    def extract_dois(text: str) -> list[str]:
        """Extract DOIs from text.

        Args:
            text: Text to search for DOIs

        Returns:
            List of unique DOIs found
        """
        matches = DOIService.DOI_PATTERN.findall(text)
        # Clean and deduplicate
        dois = []
        seen = set()
        for doi in matches:
            # Remove trailing punctuation
            doi = doi.rstrip(".,;:)")
            doi_lower = doi.lower()
            if doi_lower not in seen:
                seen.add(doi_lower)
                dois.append(doi)
        return dois

    async def resolve(self, doi: str) -> BibliographicRecord | None:
        """Resolve a DOI to bibliographic metadata.

        Args:
            doi: DOI to resolve (with or without https://doi.org/ prefix)

        Returns:
            BibliographicRecord or None if resolution fails
        """
        # Normalize DOI
        doi = self._normalize_doi(doi)

        # Check cache first
        cached = self.cache.get(doi)
        if cached:
            logger.debug(f"DOI cache hit: {doi}")
            return self._parse_crossref_response(cached, doi)

        # Rate limiting
        await self._respect_rate_limit()

        # Query CrossRef
        try:
            url = f"{self.CROSSREF_API}/{doi}"
            response = await self.client.get(url)

            if response.status_code == 200:
                data = response.json()
                work = data.get("message", {})

                # Cache the result
                self.cache.set(doi, work)

                return self._parse_crossref_response(work, doi)

            elif response.status_code == 404:
                logger.warning(f"DOI not found: {doi}")
                return None
            else:
                logger.warning(f"CrossRef API error {response.status_code}: {doi}")
                return None

        except Exception as e:
            logger.error(f"DOI resolution failed for {doi}: {e}")
            return None

    async def resolve_batch(
        self,
        dois: list[str],
        concurrency: int = 5,
    ) -> dict[str, BibliographicRecord | None]:
        """Resolve multiple DOIs concurrently.

        Args:
            dois: List of DOIs to resolve
            concurrency: Maximum concurrent requests

        Returns:
            Dict mapping DOI -> BibliographicRecord (or None)
        """
        semaphore = asyncio.Semaphore(concurrency)
        results = {}

        async def resolve_with_semaphore(doi: str) -> tuple[str, BibliographicRecord | None]:
            async with semaphore:
                record = await self.resolve(doi)
                return doi, record

        tasks = [resolve_with_semaphore(doi) for doi in dois]
        for coro in asyncio.as_completed(tasks):
            doi, record = await coro
            results[doi] = record

        return results

    def _normalize_doi(self, doi: str) -> str:
        """Normalize DOI to bare format (no URL prefix)."""
        doi = doi.strip()
        # Remove URL prefixes
        for prefix in ["https://doi.org/", "http://doi.org/", "doi:"]:
            if doi.lower().startswith(prefix):
                doi = doi[len(prefix) :]
        return doi

    def _parse_crossref_response(
        self,
        work: dict[str, Any],
        doi: str,
    ) -> BibliographicRecord:
        """Parse CrossRef API response to BibliographicRecord."""
        # Extract authors
        authors = []
        for author in work.get("author", []):
            given = author.get("given", "")
            family = author.get("family", "")
            if family:
                name = f"{given} {family}".strip() if given else family
                authors.append(name)

        # Extract year
        year = None
        for date_field in ["published-print", "published-online", "issued"]:
            date_parts = work.get(date_field, {}).get("date-parts", [[]])
            if date_parts and date_parts[0]:
                year = date_parts[0][0]
                break

        # Extract journal
        journal = None
        container = work.get("container-title", [])
        if container:
            journal = container[0]

        return BibliographicRecord(
            doi=doi,
            title=work.get("title", [None])[0],
            authors=authors,
            year=year,
            journal=journal,
            volume=work.get("volume"),
            issue=work.get("issue"),
            pages=work.get("page"),
            publisher=work.get("publisher"),
            abstract=work.get("abstract"),
            keywords=work.get("subject", []),
            citation_count=work.get("is-referenced-by-count"),
            raw_data=work,
        )

    async def _respect_rate_limit(self) -> None:
        """Respect rate limiting between requests."""
        import time

        now = time.time()
        elapsed = now - self._last_request
        if elapsed < self.rate_limit:
            await asyncio.sleep(self.rate_limit - elapsed)
        self._last_request = time.time()


async def resolve_doi(doi: str) -> BibliographicRecord | None:
    """Convenience function to resolve a single DOI."""
    service = DOIService()
    try:
        return await service.resolve(doi)
    finally:
        await service.close()


async def generate_bibliography(
    dois: list[str],
) -> str:
    """Generate BibTeX bibliography from DOIs.

    Args:
        dois: List of DOIs

    Returns:
        BibTeX formatted string
    """
    service = DOIService()
    try:
        records = await service.resolve_batch(dois)
        entries = []
        for doi, record in records.items():
            if record:
                entries.append(record.to_bibtex())
            else:
                # Create placeholder
                entries.append(f"% Could not resolve: {doi}")
        return "\n\n".join(entries)
    finally:
        await service.close()
