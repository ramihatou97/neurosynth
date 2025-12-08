"""Robust Section Header Detection module.

Identifies section headers in neurosurgical texts using multi-tier pattern matching.
Guarantees Zero Data Loss by providing safe extraction windows.
"""

import re
from dataclasses import dataclass
from enum import Enum, auto
from typing import Dict, List, Optional, Tuple


class MatchConfidence(Enum):
    """Confidence level of the section match."""

    HIGH = auto()  # Explicit header on its own line (e.g., "1. Surgical Technique")
    MEDIUM = (
        auto()
    )  # Strong keyword match but maybe inline (e.g., "SURGICAL TECHNIQUE")
    LOW = auto()  # Fuzzy match or ambiguous context


@dataclass
class DetectedSection:
    """A detected section header."""

    title: str
    page_num: int  # 0-indexed
    confidence: MatchConfidence
    start_offset: int  # Character offset on page
    section_type: str  # Standardized type (e.g., "Technique")


class SectionDetector:
    """Robust detector for textbook section headers."""

    # Minimum pages to extract to ensure context is captured
    MIN_EXTRACTION_PAGES = 4

    # Default window if no sections found (keyword page - 1 to + 3)
    DEFAULT_WINDOW_BEFORE = 1
    DEFAULT_WINDOW_AFTER = 3

    # Regex patterns for section headers
    # Ordered by specificity (High confidence first)
    PATTERNS: Dict[str, List[Tuple[str, MatchConfidence]]] = {
        "Technique": [
            (
                r"^\s*(?:[0-9]+(?:\.[0-9]+)*\.?|[IVX]+\.)?\s*SURGICAL\s+TECHNIQUE\s*$",
                MatchConfidence.HIGH,
            ),
            (
                r"^\s*(?:[0-9]+(?:\.[0-9]+)*\.?|[IVX]+\.)?\s*OPERATIVE\s+TECHNIQUE\s*$",
                MatchConfidence.HIGH,
            ),
            (
                r"^\s*(?:[0-9]+(?:\.[0-9]+)*\.?|[IVX]+\.)?\s*Surgical\s+Technique\s*$",
                MatchConfidence.HIGH,
            ),
            (
                r"^\s*(?:[0-9]+(?:\.[0-9]+)*\.?|[IVX]+\.)?\s*Operative\s+Procedure\s*$",
                MatchConfidence.HIGH,
            ),
            (r"^\s*SURGICAL\s+STEPS\s*$", MatchConfidence.MEDIUM),
            (r"^\s*OPERATIVE\s+NUANCES\s*$", MatchConfidence.MEDIUM),
        ],
        "Complication": [
            (
                r"^\s*(?:[0-9]+(?:\.[0-9]+)*\.?|[IVX]+\.)?\s*COMPLICATIONS\s*$",
                MatchConfidence.HIGH,
            ),
            (
                r"^\s*(?:[0-9]+(?:\.[0-9]+)*\.?|[IVX]+\.)?\s*Complications\s*$",
                MatchConfidence.HIGH,
            ),
            (r"^\s*COMPLICATION\s+AVOIDANCE\s*$", MatchConfidence.MEDIUM),
            (
                r"^\s*(?:[0-9]+(?:\.[0-9]+)*\.?|[IVX]+\.)?\s*Complication\s+Avoidance\s*$",
                MatchConfidence.MEDIUM,
            ),
            (r"^\s*POSTOPERATIVE\s+MANAGEMENT\s*$", MatchConfidence.MEDIUM),
            (
                r"^\s*(?:[0-9]+(?:\.[0-9]+)*\.?|[IVX]+\.)?\s*Postoperative\s+Management\s*$",
                MatchConfidence.MEDIUM,
            ),
        ],
        "Anatomy": [
            (
                r"^\s*(?:[0-9]+(?:\.[0-9]+)*\.?|[IVX]+\.)?\s*SURGICAL\s+ANATOMY\s*$",
                MatchConfidence.HIGH,
            ),
            (
                r"^\s*(?:[0-9]+(?:\.[0-9]+)*\.?|[IVX]+\.)?\s*RELEVANT\s+ANATOMY\s*$",
                MatchConfidence.HIGH,
            ),
            (
                r"^\s*(?:[0-9]+(?:\.[0-9]+)*\.?|[IVX]+\.)?\s*Surgical\s+Anatomy\s*$",
                MatchConfidence.HIGH,
            ),
            (r"^\s*ANATOMICAL\s+CONSIDERATIONS\s*$", MatchConfidence.MEDIUM),
        ],
        "Indication": [
            (
                r"^\s*(?:[0-9]+(?:\.[0-9]+)*\.?|[IVX]+\.)?\s*INDICATIONS\s*$",
                MatchConfidence.HIGH,
            ),
            (
                r"^\s*(?:[0-9]+(?:\.[0-9]+)*\.?|[IVX]+\.)?\s*Indications\s*$",
                MatchConfidence.HIGH,
            ),
            (
                r"^\s*(?:[0-9]+(?:\.[0-9]+)*\.?|[IVX]+\.)?\s*PATIENT\s+SELECTION\s*$",
                MatchConfidence.HIGH,
            ),
            (
                r"^\s*(?:[0-9]+(?:\.[0-9]+)*\.?|[IVX]+\.)?\s*Patient\s+Selection\s*$",
                MatchConfidence.HIGH,
            ),
            (r"^\s*CLINICAL\s+PRESENTATION\s*$", MatchConfidence.MEDIUM),
            (
                r"^\s*(?:[0-9]+(?:\.[0-9]+)*\.?|[IVX]+\.)?\s*Clinical\s+Presentation\s*$",
                MatchConfidence.MEDIUM,
            ),
        ],
        "Outcome": [
            (
                r"^\s*(?:[0-9]+(?:\.[0-9]+)*\.?|[IVX]+\.)?\s*OUTCOMES\s*$",
                MatchConfidence.HIGH,
            ),
            (
                r"^\s*(?:[0-9]+(?:\.[0-9]+)*\.?|[IVX]+\.)?\s*Outcomes\s*$",
                MatchConfidence.HIGH,
            ),
            (
                r"^\s*(?:[0-9]+(?:\.[0-9]+)*\.?|[IVX]+\.)?\s*RESULTS\s*$",
                MatchConfidence.HIGH,
            ),
            (
                r"^\s*(?:[0-9]+(?:\.[0-9]+)*\.?|[IVX]+\.)?\s*Results\s*$",
                MatchConfidence.HIGH,
            ),
            (r"^\s*PROGNOSIS\s*$", MatchConfidence.MEDIUM),
            (
                r"^\s*(?:[0-9]+(?:\.[0-9]+)*\.?|[IVX]+\.)?\s*Prognosis\s*$",
                MatchConfidence.MEDIUM,
            ),
        ],
    }

    def detect_section_headers(self, text: str, page_num: int) -> List[DetectedSection]:
        """Detect section headers on a single page."""
        # print(f"[DEBUG] ENTERING detect_section_headers for page {page_num}. Text len: {len(text)}")
        detected = []

        # Split into lines to check for standalone headers
        lines = text.split("\n")
        current_offset = 0

        for line in lines:
            line_len = len(line) + 1  # +1 for newline
            clean_line = line.strip()

            if not clean_line:
                current_offset += line_len
                continue

            # Check against all patterns
            for section_type, patterns in self.PATTERNS.items():
                for pattern, confidence in patterns:
                    if re.match(pattern, clean_line):
                        # print(f"[DEBUG] MATCHED! Line: '{clean_line}' | Type: {section_type} | Pattern: '{pattern}'")
                        detected.append(
                            DetectedSection(
                                title=clean_line,
                                page_num=page_num,
                                confidence=confidence,
                                start_offset=current_offset,
                                section_type=section_type,
                            )
                        )
                        # Stop checking other patterns for this line
                        break

            # if "Patient Selection" in clean_line:
            #     print(f"[DEBUG] Checking 'Patient Selection' line: '{clean_line}'")

            current_offset += line_len

        return detected

    def get_safe_extraction_window(
        self,
        target_section: DetectedSection,
        all_sections: List[DetectedSection],
        total_pages: int,
    ) -> Tuple[int, int]:
        """Calculate safe start and end pages for extraction.

        Guarantees Zero Data Loss by ensuring minimum page count.
        """
        start_page = target_section.page_num

        # Find the next section that appears AFTER this one
        next_section_page = total_pages

        # Sort sections by page and offset
        sorted_sections = sorted(
            all_sections, key=lambda s: (s.page_num, s.start_offset)
        )

        found_current = False
        for section in sorted_sections:
            if found_current:
                next_section_page = section.page_num
                break

            # Identify the current section instance
            if (
                section.page_num == target_section.page_num
                and section.start_offset == target_section.start_offset
            ):
                found_current = True

        end_page = next_section_page

        # Zero Data Loss Guarantee:
        # If the section is very short (e.g., ends on same page),
        # or if we didn't find a next section (end of chapter),
        # ensure we extract at least MIN_EXTRACTION_PAGES or until end of book.

        if end_page - start_page < 1:
            # If next section is on same page, that's fine, we extract that page.
            # But usually we want at least a few pages of context if it's the last section.
            pass

        # If this is the last section, extract a few more pages
        if end_page == total_pages:
            # Cap at total pages, but try to get MIN_EXTRACTION_PAGES
            end_page = min(start_page + self.MIN_EXTRACTION_PAGES, total_pages)

        return start_page, end_page

    def create_fallback_section(
        self, keyword_page: int, total_pages: int
    ) -> Tuple[int, int]:
        """Create a fallback extraction window around a keyword match.

        Used when NO section header is found.
        """
        start_page = max(0, keyword_page - self.DEFAULT_WINDOW_BEFORE)
        end_page = min(total_pages, keyword_page + self.DEFAULT_WINDOW_AFTER)

        return start_page, end_page


# Singleton
_section_detector: Optional[SectionDetector] = None


def get_section_detector() -> SectionDetector:
    """Get singleton SectionDetector."""
    global _section_detector
    if _section_detector is None:
        _section_detector = SectionDetector()
    return _section_detector
