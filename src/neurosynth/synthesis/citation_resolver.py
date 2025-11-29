"""XML Citation to LaTeX resolver.

Converts XML-style citation anchors from LLM output to proper LaTeX citations.
This ensures every claim can be traced back to its source.

XML Input Format:
    <claim source_id="Smith2020">The mortality rate is 2.3%</claim>
    <conflict type="quantitative">
        <perspective source_id="A">5% mortality</perspective>
        <perspective source_id="B">8% mortality</perspective>
    </conflict>

LaTeX Output Format:
    The mortality rate is 2.3% \\citep{Smith2020}
    Studies report mortality rates of 5% \\citep{A} to 8% \\citep{B}
"""

import re
from dataclasses import dataclass, field
from typing import Any

from rich.console import Console

from neurosynth import get_logger

console = Console()
logger = get_logger("synthesis.citation_resolver")


@dataclass
class SourceMapping:
    """Mapping from source_id to bibliography information."""

    source_id: str
    bibkey: str  # LaTeX bibliography key
    author: str | None = None
    year: str | None = None
    title: str | None = None
    doi: str | None = None


@dataclass
class CitationStats:
    """Statistics about citation resolution."""

    total_claims: int = 0
    resolved_claims: int = 0
    unresolved_claims: int = 0
    total_conflicts: int = 0
    unique_sources: set[str] = field(default_factory=set)


class XMLToLatexResolver:
    """Convert XML citation anchors to LaTeX citations.

    This class handles the conversion of XML-tagged synthesis output
    to properly formatted LaTeX with citations.
    """

    # Regex patterns for XML tags
    CLAIM_PATTERN = re.compile(
        r'<claim\s+source_id=["\']([^"\']+)["\']>(.*?)</claim>',
        re.DOTALL,
    )
    CONFLICT_PATTERN = re.compile(
        r'<conflict\s+type=["\']([^"\']+)["\']>(.*?)</conflict>',
        re.DOTALL,
    )
    PERSPECTIVE_PATTERN = re.compile(
        r'<perspective\s+source_id=["\']([^"\']+)["\']>(.*?)</perspective>',
        re.DOTALL,
    )

    def __init__(
        self,
        source_mappings: dict[str, SourceMapping] | None = None,
        citation_style: str = "citep",  # citep, citet, or cite
        warn_unresolved: bool = True,
    ):
        """Initialize the resolver.

        Args:
            source_mappings: Dict mapping source_id to SourceMapping
            citation_style: LaTeX citation command (citep, citet, cite)
            warn_unresolved: If True, warn about unresolved source_ids
        """
        self.source_mappings = source_mappings or {}
        self.citation_style = citation_style
        self.warn_unresolved = warn_unresolved
        self.stats = CitationStats()

    def add_mapping(self, source_id: str, mapping: SourceMapping) -> None:
        """Add a source mapping."""
        self.source_mappings[source_id] = mapping

    def add_mappings_from_chunks(self, chunks: list[dict[str, Any]]) -> None:
        """Build source mappings from chunk metadata.

        Args:
            chunks: List of chunk dicts with 'source_id', 'source', etc.
        """
        for chunk in chunks:
            source_id = chunk.get("source_id")
            if not source_id:
                continue

            # Try to extract author/year from source name
            source_name = chunk.get("source", "")
            author, year = self._parse_author_year(source_name)

            # Create bibkey from source_id or construct from author/year
            bibkey = self._normalize_bibkey(source_id)

            mapping = SourceMapping(
                source_id=source_id,
                bibkey=bibkey,
                author=author,
                year=year,
                title=chunk.get("title"),
            )
            self.source_mappings[source_id] = mapping

    def resolve(self, xml_text: str) -> str:
        """Convert XML citation tags to LaTeX.

        Args:
            xml_text: Text with XML citation anchors

        Returns:
            Text with LaTeX citations
        """
        self.stats = CitationStats()  # Reset stats

        # First, resolve conflicts (they may contain claims)
        result = self._resolve_conflicts(xml_text)

        # Then resolve individual claims
        result = self._resolve_claims(result)

        # Log statistics
        if self.stats.total_claims > 0:
            logger.info(
                f"Citation resolution: {self.stats.resolved_claims}/{self.stats.total_claims} "
                f"claims resolved, {self.stats.total_conflicts} conflicts, "
                f"{len(self.stats.unique_sources)} unique sources"
            )

        return result

    def _resolve_claims(self, text: str) -> str:
        """Resolve <claim> tags to LaTeX citations."""

        def replace_claim(match: re.Match) -> str:
            source_id = match.group(1)
            content = match.group(2).strip()

            self.stats.total_claims += 1
            self.stats.unique_sources.add(source_id)

            # Look up bibkey
            bibkey = self._get_bibkey(source_id)

            if bibkey:
                self.stats.resolved_claims += 1
                return f"{content} \\{self.citation_style}{{{bibkey}}}"
            else:
                self.stats.unresolved_claims += 1
                if self.warn_unresolved:
                    logger.warning(f"Unresolved source_id: {source_id}")
                # Keep source_id as bibkey if no mapping
                return f"{content} \\{self.citation_style}{{{source_id}}}"

        return self.CLAIM_PATTERN.sub(replace_claim, text)

    def _resolve_conflicts(self, text: str) -> str:
        """Resolve <conflict> blocks to formatted LaTeX."""

        def replace_conflict(match: re.Match) -> str:
            conflict_type = match.group(1)
            content = match.group(2)

            self.stats.total_conflicts += 1

            # Extract perspectives
            perspectives = self.PERSPECTIVE_PATTERN.findall(content)

            if not perspectives:
                # No perspectives found, return content as-is
                return content.strip()

            # Format based on conflict type
            if conflict_type == "quantitative":
                # Format: "Studies report X (Author1) to Y (Author2)"
                parts = []
                for source_id, claim in perspectives:
                    self.stats.unique_sources.add(source_id)
                    bibkey = self._get_bibkey(source_id)
                    parts.append(f"{claim.strip()} \\{self.citation_style}{{{bibkey}}}")

                if len(parts) == 2:
                    return f"Studies report {parts[0]} to {parts[1]}"
                else:
                    return "Different sources report: " + "; ".join(parts)

            elif conflict_type == "approach":
                # Format alternatives
                parts = []
                for source_id, claim in perspectives:
                    self.stats.unique_sources.add(source_id)
                    bibkey = self._get_bibkey(source_id)
                    parts.append(f"{claim.strip()} \\{self.citation_style}{{{bibkey}}}")

                return (
                    "Different approaches have been described: "
                    + ", while ".join(parts)
                )

            elif conflict_type == "temporal":
                # Earlier vs later findings
                parts = []
                for source_id, claim in perspectives:
                    self.stats.unique_sources.add(source_id)
                    bibkey = self._get_bibkey(source_id)
                    parts.append(f"{claim.strip()} \\{self.citation_style}{{{bibkey}}}")

                if len(parts) >= 2:
                    return f"Earlier studies suggested {parts[0]}, while more recent work indicates {parts[1]}"
                return "; ".join(parts)

            else:
                # Generic conflict formatting
                parts = []
                for source_id, claim in perspectives:
                    self.stats.unique_sources.add(source_id)
                    bibkey = self._get_bibkey(source_id)
                    parts.append(f"{claim.strip()} \\{self.citation_style}{{{bibkey}}}")

                return "Conflicting reports exist: " + "; however, ".join(parts)

        return self.CONFLICT_PATTERN.sub(replace_conflict, text)

    def _get_bibkey(self, source_id: str) -> str:
        """Get bibliography key for a source_id."""
        if source_id in self.source_mappings:
            return self.source_mappings[source_id].bibkey
        # Return normalized source_id as fallback
        return self._normalize_bibkey(source_id)

    def _normalize_bibkey(self, source_id: str) -> str:
        """Normalize source_id to valid LaTeX bibkey."""
        # Replace spaces and special chars
        bibkey = re.sub(r"[^a-zA-Z0-9_]", "", source_id.replace(" ", "_"))
        return bibkey

    def _parse_author_year(self, source_name: str) -> tuple[str | None, str | None]:
        """Try to extract author and year from source name.

        Examples:
            "Smith et al. 2020" -> ("Smith et al.", "2020")
            "Smith2020" -> ("Smith", "2020")
        """
        # Try pattern: "Author et al. YYYY" or "Author YYYY"
        match = re.search(r"(.+?)\s*(\d{4})", source_name)
        if match:
            author = match.group(1).strip()
            year = match.group(2)
            return author, year

        return None, None

    def get_bibliography_entries(self) -> list[dict[str, Any]]:
        """Get bibliography entries for all resolved sources.

        Returns:
            List of dicts with bibliographic information
        """
        entries = []
        for source_id in self.stats.unique_sources:
            if source_id in self.source_mappings:
                mapping = self.source_mappings[source_id]
                entries.append({
                    "bibkey": mapping.bibkey,
                    "author": mapping.author,
                    "year": mapping.year,
                    "title": mapping.title,
                    "doi": mapping.doi,
                })
            else:
                # Create placeholder entry
                entries.append({
                    "bibkey": self._normalize_bibkey(source_id),
                    "author": source_id,
                    "year": None,
                    "title": None,
                    "doi": None,
                })

        return entries

    def generate_bibtex(self) -> str:
        """Generate BibTeX entries for all resolved sources.

        Returns:
            BibTeX formatted string
        """
        entries = []
        for entry in self.get_bibliography_entries():
            bibkey = entry["bibkey"]
            author = entry.get("author") or "Unknown"
            year = entry.get("year") or "n.d."
            title = entry.get("title") or "Untitled"

            bibtex = f"""@article{{{bibkey},
    author = {{{author}}},
    year = {{{year}}},
    title = {{{title}}},
}}"""
            entries.append(bibtex)

        return "\n\n".join(entries)


def resolve_xml_to_latex(
    xml_text: str,
    chunks: list[dict[str, Any]] | None = None,
    citation_style: str = "citep",
) -> tuple[str, CitationStats]:
    """Convenience function to resolve XML to LaTeX.

    Args:
        xml_text: Text with XML citation anchors
        chunks: Optional chunks to build source mappings
        citation_style: LaTeX citation command

    Returns:
        Tuple of (resolved text, citation stats)
    """
    resolver = XMLToLatexResolver(citation_style=citation_style)

    if chunks:
        resolver.add_mappings_from_chunks(chunks)

    result = resolver.resolve(xml_text)
    return result, resolver.stats
