"""Master Index parser for COMPREHENSIVE.ini.

Parses the comprehensive neurosurgical index with 2,632 terms
and provides authority-boosted search integration.
"""

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

# Text abbreviations with authority scores (higher = more authoritative for topic)
# Based on specificity and depth of coverage
TEXT_AUTHORITY = {
    # Primary specialized texts (authority 100)
    "L7": 100,  # Lawton Seven Aneurysms - definitive for aneurysms
    "SA": 100,  # Samii Acoustic Neurinomas
    "AM": 100,  # Al-Mefty Meningiomas
    "OT": 100,  # Ojemann Epilepsy Surgery
    "LM": 100,  # Lawton Seven AVMs
    "SB": 100,  # Spetzler-Barrow Cerebrovascular
    # Major comprehensive references (authority 90)
    "YW": 90,  # Youmans & Winn
    "SS": 90,  # Schmidek & Sweet
    "CN": 90,  # Connolly Operative Neurosurgery
    # Handbooks and atlases (authority 80)
    "GH": 80,  # Greenberg Handbook
    "RH": 85,  # Rhoton Anatomy (high for anatomy)
    "AT-B": 80,  # Atlas Brain
    "AT-S": 80,  # Atlas Spine
    # Subspecialty texts (authority 85 in their domain)
    "BS": 85,  # Benzel Spine
    "AO1": 85,  # AO Spine Vol 1
    "AO2": 85,  # AO Spine Vol 2
    "FU": 85,  # Lozano Functional
    "PN": 85,  # Albright Pediatric
    "BT": 85,  # Brain Tumors
    "EP": 85,  # Epilepsy Comprehensive
    "CB": 85,  # Cerebrovascular
    # Standard texts (authority 70)
    "DEFAULT": 70,
}


@dataclass
class IndexEntry:
    """A single entry from the master index."""

    term: str
    references: list[str]  # Full reference strings: ["L7 Ch.5", "CB Ch.17"]
    primary_sources: list[str]  # Just abbreviations: ["L7", "CB"]
    authority: int  # Highest authority score from sources
    related_terms: list[str] = field(default_factory=list)

    @property
    def display_refs(self) -> str:
        """Human-readable reference string."""
        return ", ".join(self.references[:3])


class MasterIndex:
    """Parser and lookup for COMPREHENSIVE.ini master index.

    File Format (TAB-separated):
        Term<TAB>Ref1, Ref2, Ref3, ...

    Examples:
        Aneurysm (basilar apex/tip)	L7 Ch.5, CB Ch.17, GH p.1377-1382
        Acoustic neuroma - see Vestibular schwannoma	GH p.699
    """

    def __init__(self, ini_path: Path | None = None):
        self.entries: dict[str, IndexEntry] = {}
        self._term_index: dict[str, list[str]] = {}  # word -> [terms containing word]

        if ini_path is None:
            # Default location
            ini_path = Path(__file__).parent / "COMPREHENSIVE.ini"

        if ini_path.exists():
            self._parse(ini_path)

    def _parse(self, path: Path) -> None:
        """Parse COMPREHENSIVE.ini file."""
        in_index = False

        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()

            # Skip empty lines and headers
            if not line:
                continue
            if line.startswith("TEXT ABBREVIATIONS"):
                continue
            if line.startswith("ALPHABETICAL INDEX"):
                in_index = True
                continue
            if line.startswith("INDEX STATISTICS"):
                break
            if not in_index:
                continue

            # Skip category headers like "  A  "
            if re.match(r"^[A-Z]\s*$", line.strip()):
                continue

            # Parse term line: "Term<TAB>Refs" or "Term — Refs"
            # Handle both TAB and em-dash separators
            if "\t" in line:
                parts = line.split("\t", 1)
            elif " — " in line:
                parts = line.split(" — ", 1)
            elif "\u2014" in line:  # Unicode em-dash
                parts = line.split("\u2014", 1)
            else:
                # No separator - might be a cross-reference
                if " - see " in line.lower():
                    # Cross-reference: "Term - see OtherTerm"
                    term = line.split(" - see ")[0].strip()
                    self._add_entry(term, [], is_crossref=True)
                continue

            if len(parts) != 2:
                continue

            term = parts[0].strip()
            refs_str = parts[1].strip()

            if not term or not refs_str:
                continue

            # Parse references: "L7 Ch.5, CB Ch.17, GH p.1377-1382"
            refs = [r.strip() for r in refs_str.split(",")]

            self._add_entry(term, refs)

        # Build word index for fuzzy matching
        self._build_word_index()

    def _add_entry(self, term: str, refs: list[str], is_crossref: bool = False) -> None:
        """Add an entry to the index."""
        # Extract primary source abbreviations
        primary_sources = []
        for ref in refs[:3]:  # First 3 are usually most authoritative
            # Extract abbreviation (first word): "L7 Ch.5" -> "L7"
            match = re.match(r"^([A-Z][A-Z0-9\-]+)", ref)
            if match:
                primary_sources.append(match.group(1))

        # Calculate authority score (use highest)
        authority = (
            max(
                TEXT_AUTHORITY.get(src, TEXT_AUTHORITY["DEFAULT"])
                for src in primary_sources
            )
            if primary_sources
            else TEXT_AUTHORITY["DEFAULT"]
        )

        entry = IndexEntry(
            term=term,
            references=refs,
            primary_sources=primary_sources,
            authority=authority,
        )

        # Store by lowercase for case-insensitive lookup
        self.entries[term.lower()] = entry

    def _build_word_index(self) -> None:
        """Build inverted index for word-based lookup."""
        for term_lower, entry in self.entries.items():
            # Extract words (alphanumeric only)
            words = re.findall(r"[a-z0-9]+", term_lower)
            for word in words:
                if len(word) >= 3:  # Skip short words
                    if word not in self._term_index:
                        self._term_index[word] = []
                    self._term_index[word].append(term_lower)

    def find_term(self, query: str) -> list[IndexEntry]:
        """Find index entries matching a query.

        Uses simple substring matching - no fuzzy logic for MVP.
        Returns entries sorted by match quality and authority.
        """
        query_lower = query.lower().strip()
        matches: list[IndexEntry] = []

        # 1. Exact match
        if query_lower in self.entries:
            matches.append(self.entries[query_lower])

        # 2. Substring match (query is in term)
        for term_lower, entry in self.entries.items():
            if entry in matches:
                continue
            if query_lower in term_lower:
                matches.append(entry)

        # 3. Word-based match (any query word in term)
        query_words = set(re.findall(r"[a-z0-9]+", query_lower))
        for word in query_words:
            if word in self._term_index:
                for term_lower in self._term_index[word]:
                    entry = self.entries[term_lower]
                    if entry not in matches:
                        matches.append(entry)

        # Sort by: exact match first, then by authority
        def sort_key(entry: IndexEntry) -> tuple:
            is_exact = entry.term.lower() == query_lower
            return (not is_exact, -entry.authority)

        return sorted(matches, key=sort_key)[:10]  # Limit to top 10

    def get_authority_boost(self, pdf_path: Path) -> int:
        """Get authority boost for a PDF based on filename matching.

        Matches PDF filenames to text abbreviations.
        """
        name_lower = pdf_path.stem.lower()

        # Common filename patterns
        patterns = {
            "lawton": 100,  # Lawton Seven
            "youmans": 90,
            "greenberg": 80,
            "rhoton": 85,
            "schmidek": 90,
            "benzel": 85,
            "sekhar": 80,
            "samii": 100,
            "lumbar": 85,  # High authority for validation library
        }

        for pattern, authority in patterns.items():
            if pattern in name_lower:
                return authority

        return TEXT_AUTHORITY["DEFAULT"]

    def get_related_terms(self, query: str, max_terms: int = 5) -> list[str]:
        """Get related terms from master index for 'Did you mean?' suggestions.

        Finds terms that share words with the query but are different,
        useful for suggesting alternatives when search returns few results.

        Args:
            query: Search query string
            max_terms: Maximum number of related terms to return

        Returns:
            List of related term strings
        """
        query_lower = query.lower().strip()
        query_words = set(re.findall(r"[a-z0-9]+", query_lower))

        # Skip very short queries
        if len(query_lower) < 3:
            return []

        related: list[str] = []
        seen_terms = {query_lower}  # Don't suggest the exact query

        # Find terms that share words but are different
        for word in query_words:
            if len(word) < 3:
                continue

            if word in self._term_index:
                for term_lower in self._term_index[word]:
                    if term_lower in seen_terms:
                        continue

                    entry = self.entries.get(term_lower)
                    if entry is None:
                        continue

                    # Skip if it's just a substring match of the query
                    if query_lower in term_lower or term_lower in query_lower:
                        # Allow if significantly different in length
                        if abs(len(term_lower) - len(query_lower)) < 5:
                            continue

                    related.append(entry.term)
                    seen_terms.add(term_lower)

                    if len(related) >= max_terms * 2:  # Get extras for filtering
                        break

            if len(related) >= max_terms * 2:
                break

        # Sort by authority (higher authority = better suggestion)
        related_with_auth = []
        for term in related:
            entry = self.entries.get(term.lower())
            if entry:
                related_with_auth.append((term, entry.authority))
            else:
                related_with_auth.append((term, 50))

        related_with_auth.sort(key=lambda x: -x[1])

        return [term for term, _ in related_with_auth[:max_terms]]

    def expand_query(
        self,
        query: str,
        expand_synonyms: bool = True,
        expand_orthographic: bool = True,
        max_expansions: int = 10,
    ) -> list[str]:
        """Expand query with synonyms and orthographic variants.

        Args:
            query: Original search query
            expand_synonyms: Include related terms from master index
            expand_orthographic: Include disc/disk, -ectomy/-otomy variants
            max_expansions: Maximum number of expansions to return

        Returns:
            List of expanded query terms (including original)
        """
        expansions = [query.lower().strip()]
        query_lower = query.lower().strip()

        # Orthographic variants (common medical spelling variations)
        if expand_orthographic:
            orthographic_pairs = [
                ("disc", "disk"),
                ("haemorrhage", "hemorrhage"),
                ("anaesthesia", "anesthesia"),
                ("oedema", "edema"),
                ("tumour", "tumor"),
                ("colour", "color"),
                ("centre", "center"),
                ("fibre", "fiber"),
                ("grey", "gray"),
                ("oesophagus", "esophagus"),
                ("paediatric", "pediatric"),
                ("orthopaedic", "orthopedic"),
                ("foetus", "fetus"),
                ("caecum", "cecum"),
            ]

            for brit, amer in orthographic_pairs:
                if brit in query_lower:
                    variant = query_lower.replace(brit, amer)
                    if variant not in expansions:
                        expansions.append(variant)
                elif amer in query_lower:
                    variant = query_lower.replace(amer, brit)
                    if variant not in expansions:
                        expansions.append(variant)

        # Synonym expansion from master index (use pre-indexed terms for speed)
        if expand_synonyms and len(expansions) < max_expansions:
            query_words = set(re.findall(r"[a-z0-9]+", query_lower))

            # Use the term_index to find related terms efficiently (O(1) lookups)
            seen = set(expansions)
            for word in query_words:
                if len(word) < 3:
                    continue
                if word in self._term_index:
                    for term_lower in self._term_index[word]:
                        if term_lower in seen or term_lower == query_lower:
                            continue
                        # Only add if it's meaningfully different
                        if (
                            query_lower not in term_lower
                            and term_lower not in query_lower
                        ):
                            expansions.append(term_lower)
                            seen.add(term_lower)
                            if len(expansions) >= max_expansions:
                                break
                if len(expansions) >= max_expansions:
                    break

        return expansions[:max_expansions]

    def get_primary_sources_for_query(self, query: str) -> list[str]:
        """Get primary source abbreviations for a query.

        Useful for showing which textbooks are authoritative for a topic.

        Args:
            query: Search query string

        Returns:
            List of source abbreviations (e.g., ['L7', 'CB'])
        """
        matches = self.find_term(query)
        if not matches:
            return []

        # Get unique primary sources from top matches
        sources = []
        for match in matches[:3]:
            for src in match.primary_sources:
                if src not in sources:
                    sources.append(src)

        return sources[:5]


# Module-level singleton for easy access
_master_index: MasterIndex | None = None


def get_master_index() -> MasterIndex:
    """Get the singleton MasterIndex instance."""
    global _master_index
    if _master_index is None:
        _master_index = MasterIndex()
    return _master_index
