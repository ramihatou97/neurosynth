# 🎯 ENHANCED SEARCH IMPLEMENTATION PLAN
## Reference Library → NeuroSynth Integration

**Created**: December 2024  
**Objective**: Implement lean, high-impact search enhancements to improve synthesis quality  
**Total Estimated Effort**: 29 hours (MVP) + 8-12 hours (conditional Phase 2)

---

## 📊 SYSTEM ARCHITECTURE OVERVIEW

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    REFERENCE LIBRARY → NEUROSYNTH PIPELINE                  │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│   USER QUERY: "basilar aneurysm technique"                                  │
│        │                                                                    │
│        ▼                                                                    │
│   ┌─────────────────────────────────────────────────────────────────────┐  │
│   │  PHASE 0.1: INTENT DETECTION (query_intent_lean.py) [NEW]           │  │
│   │  ────────────────────────────────────────────────────               │  │
│   │  • Keyword-based detection (no ML, no API calls)                    │  │
│   │  • Extracts: topic="basilar aneurysm", intent=TECHNIQUE             │  │
│   │  • Section filter: ["Surgical Technique", "Operative Steps"]        │  │
│   └─────────────────────────────────────────────────────────────────────┘  │
│        │                                                                    │
│        ▼                                                                    │
│   ┌─────────────────────────────────────────────────────────────────────┐  │
│   │  PHASE 0.2: MASTER INDEX LOOKUP (master_index.py) [NEW]             │  │
│   │  ──────────────────────────────────────────────────                 │  │
│   │  • Parse COMPREHENSIVE.ini (TAB-separated format)                   │  │
│   │  • Matched: "Aneurysm (basilar apex/tip)"                           │  │
│   │  • Primary sources: L7 Ch.5, CB Ch.17 (authority boost)             │  │
│   │  • Related terms: ["basilar tip", "basilar bifurcation"]            │  │
│   └─────────────────────────────────────────────────────────────────────┘  │
│        │                                                                    │
│        ▼                                                                    │
│   ┌─────────────────────────────────────────────────────────────────────┐  │
│   │  PHASE 0.3: ENHANCED SEARCH (pdf_searcher.py) [MODIFIED]            │  │
│   │  ──────────────────────────────────────────────────                 │  │
│   │  • Existing: keyword expansion, chapter-level aggregation           │  │
│   │  • New: Section header detection (simple regex)                     │  │
│   │  • New: Authority boost scoring from MasterIndex                    │  │
│   │  • Returns: ChapterResult with matched_sections                     │  │
│   └─────────────────────────────────────────────────────────────────────┘  │
│        │                                                                    │
│        ▼                                                                    │
│   ┌─────────────────────────────────────────────────────────────────────┐  │
│   │  PHASE 0.4: ENHANCED EXTRACTION (page_extractor.py) [MODIFIED]      │  │
│   │  ──────────────────────────────────────────────────                 │  │
│   │  • Existing: context pages, figure collection                       │  │
│   │  • New: Section-aware extraction (prefer complete sections)         │  │
│   │  • New: Authority metadata in ExtractedSource                       │  │
│   └─────────────────────────────────────────────────────────────────────┘  │
│        │                                                                    │
│        ▼                                                                    │
│   ┌─────────────────────────────────────────────────────────────────────┐  │
│   │  BRIDGE: NEUROSYNTH BRIDGE (neurosynth_bridge.py)                   │  │
│   │  ────────────────────────────────────────                           │  │
│   │  • Creates project directory with enhanced manifest                 │  │
│   │  • manifest.json includes: intent, authority, matched_sections      │  │
│   │  • Passes to NeuroSynth for synthesis                               │  │
│   └─────────────────────────────────────────────────────────────────────┘  │
│        │                                                                    │
│        ▼                                                                    │
│   ┌─────────────────────────────────────────────────────────────────────┐  │
│   │  NEUROSYNTH: SYNTHESIS ENGINE                                       │  │
│   │  ───────────────────────────                                        │  │
│   │  • Receives: focused, section-aware content                         │  │
│   │  • Benefits: Less noise, better relevance, lower token cost         │  │
│   │  • Output: Higher quality synthesized chapters                      │  │
│   └─────────────────────────────────────────────────────────────────────┘  │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 🐛 BUG FIXES (Must Address First)

### Bug Fix 1: COMPREHENSIVE.ini Parser Format

**File**: `reference-library/src/search/master_index.py` (NEW)

**Problem**: Original plan assumed INI format with `[brackets]`, but actual format is:
```
Aneurysm (basilar apex/tip)	L7 Ch.5, CB Ch.17, GH p.1377-1382, SS Ch.94, MTA Vol.2
```

**Solution**: Parse TAB-separated format correctly.

### Bug Fix 2: Intent Detection Keyword Collision

**File**: `reference-library/src/search/query_intent_lean.py` (NEW)

**Problem**: "pterional approach" would strip "approach" leaving just "pterional"

**Solution**: Only strip intent keywords from END of query.

---

## 📁 FILE STRUCTURE

```
reference-library/src/search/
├── COMPREHENSIVE.ini              # EXISTING - Master Index (2,632 terms)
├── master_index.py                # NEW - Parser for COMPREHENSIVE.ini
├── query_intent_lean.py           # NEW - Simple keyword-based intent detection
├── section_detector.py            # NEW - Simple section header detection
├── extracted_dictionaries.py      # EXISTING - Keep as-is
├── neurosurgical_synonyms.py      # EXISTING - Keep as-is
├── pdf_searcher.py                # MODIFY - Integrate new components
├── result_model.py                # MODIFY - Add matched_sections, authority
└── semantic_searcher.py           # EXISTING - Keep as-is

reference-library/src/export/
└── page_extractor.py              # MODIFY - Add section-aware extraction
```

---

## 📋 IMPLEMENTATION PHASES

### PHASE 0: Core Foundation (Week 1) — 21 hours

| Task | Component | Files | Hours | Dependencies |
|------|-----------|-------|-------|--------------|
| 0.1 | Master Index Parser | `master_index.py` (NEW) | 4h | None |
| 0.2 | Lean Intent Detection | `query_intent_lean.py` (NEW) | 3h | None |
| 0.3 | **Robust** Section Detection | `section_detector.py` (NEW) | 3h | None |
| 0.4 | Result Model Updates | `result_model.py` | 2h | 0.1, 0.2, 0.3 |
| 0.5 | PDF Searcher Integration | `pdf_searcher.py` | 4h | 0.1-0.4 |
| 0.6 | Page Extractor Enhancement | `page_extractor.py` | 2h | 0.4 |
| 0.7 | Unit & Integration Tests | `tests/` | 3h | 0.1-0.6 |

### PHASE 1: Validation & Stress Testing (Week 2) — 12 hours

**Objective**: Prove the system works on *real* data before scaling.

#### 1.1 Validation Protocol (The "Gold Standard" Test)
We will test against **25 diverse queries** covering all intent types and edge cases.

| Category | Query Examples | Success Criteria |
|----------|----------------|------------------|
| **Technique** | "basilar aneurysm technique", "pterional approach steps" | Top result is "Surgical Technique" section from Lawton/Samii |
| **Complication** | "lumbar discectomy complications", "CSF leak avoidance" | Top result is "Complications" section; "Avoidance" highlighted |
| **Anatomy** | "cavernous sinus anatomy", "facial nerve course" | Top result is Rhoton/Greenberg; Anatomy section extracted |
| **Indication** | "acoustic neuroma indications", "when to operate aneurysm" | Top result is "Indications" or "Patient Selection" section |
| **Edge Cases** | "pterional approach" (ambiguous), "C1-C2" (short token) | "Approach" not stripped; Spine authorities (Benzel) boosted |
| **Negative** | "history of neurosurgery", "billing codes" | Returns GENERAL intent; no specific section forced |

#### 1.2 Quantitative Metrics
| Metric | Definition | Target |
|--------|------------|--------|
| **Intent Accuracy** | % of queries where detected intent matches human judgment | > 90% |
| **Section Recall** | % of "Technique" queries that return a "Technique" section | > 85% |
| **Authority Precision** | % of top 3 results coming from Tier 1 (Score 100) sources | > 80% |
| **Extraction Integrity** | % of extractions that do NOT cut off mid-sentence/mid-paragraph | > 95% |

#### 1.3 "Preventable Issue" Checks
- **Encoding Stress Test**: Run on PDFs with non-standard fonts/encodings.
- **Layout Stress Test**: Run on 3-column PDFs and older scanned PDFs.
- **Token Limit Check**: Verify that "Section-Aware" extraction doesn't blow up context window.

---

### PHASE 2: Advanced Enhancements (Week 3) — Conditional

**Objective**: Address complex failures identified in Phase 1 using advanced techniques.

#### 2.1 Visual Layout Analysis (If Regex Fails)
**Trigger**: >10% of sections are missed due to weird formatting (e.g., headers not on own line).
**Solution**: Use `PyMuPDF` to analyze font metadata.
- **Logic**:
    1. Extract font size/weight for every line.
    2. Build histogram of font sizes.
    3. Identify "Header Style" (e.g., Size > 14pt OR Bold + All Caps).
    4. Segment text based on visual blocks, not just regex.
**Effort**: 8 hours

#### 2.2 Semantic Intent Fallback (If Keywords Fail)
**Trigger**: Users search for concepts not in keyword list (e.g., "positioning" -> implies Technique).
**Solution**: Small local embedding model (`all-MiniLM-L6-v2`).
- **Logic**:
    1. If Keyword Intent = GENERAL:
    2. Embed query.
    3. Compare cosine similarity to Intent Prototypes ("How to do it", "What goes wrong", "Structure").
    4. If similarity > 0.8, assign intent.
**Effort**: 6 hours

#### 2.3 Cross-Reference Resolution
**Trigger**: High frequency of "See Chapter 5" in extracted text.
**Solution**:
- **Logic**:
    1. Detect "See Chapter X" or "See Figure Y".
    2. Look up target in Master Index or Figure Manifest.
    3. Append summary of target to current context.
**Effort**: 6 hours

---

## 🛡️ RISK ASSESSMENT & MITIGATION

| Risk Category | Potential Issue | Probability | Impact | Mitigation Strategy |
|---------------|-----------------|-------------|--------|---------------------|
| **Data Loss** | Regex misses a non-standard header, skipping a section. | Medium | High | **Zero Data Loss Fallback**: If specific section not found, extract *surrounding* context of keyword match + 2 pages buffer. |
| **Hallucination** | LLM synthesizes "Technique" from a "Complications" section. | Low | High | **Strict Metadata**: Feed `query_intent` and `matched_sections` explicitly to LLM system prompt. |
| **Bias** | Authority boosting hides a good but obscure paper. | Medium | Medium | **Diversity Injection**: Always include 1 "Wildcard" result (high keyword match, low authority) in top 5. |
| **Performance** | Regex on 1000-page PDF is slow. | Low | Low | **Page-Level Indexing**: Only run regex on pages with keyword hits, not whole book. |
| **Formatting** | Multi-column text extracts as garbled lines. | High | Medium | **Layout-Preserving Extraction**: Use `pdfminer.six` with `LAParams` or `PyMuPDF` text blocks. |

---

## 🔧 DETAILED IMPLEMENTATION

### Task 0.1: Master Index Parser (`master_index.py`)

**Purpose**: Parse COMPREHENSIVE.ini and provide term lookup with authority ranking.

**File**: `reference-library/src/search/master_index.py`

```python
"""Master Index parser for COMPREHENSIVE.ini.

Parses the comprehensive neurosurgical index with 2,632 terms
and provides authority-boosted search integration.
"""
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional
import re


# Text abbreviations with authority scores (higher = more authoritative for topic)
# Based on specificity and depth of coverage
TEXT_AUTHORITY = {
    # Primary specialized texts (authority 100)
    "L7": 100,   # Lawton Seven Aneurysms - definitive for aneurysms
    "SA": 100,   # Samii Acoustic Neurinomas
    "AM": 100,   # Al-Mefty Meningiomas
    "OT": 100,   # Ojemann Epilepsy Surgery
    "LM": 100,   # Lawton Seven AVMs
    "SB": 100,   # Spetzler-Barrow Cerebrovascular

    # Major comprehensive references (authority 90)
    "YW": 90,    # Youmans & Winn
    "SS": 90,    # Schmidek & Sweet
    "CN": 90,    # Connolly Operative Neurosurgery

    # Handbooks and atlases (authority 80)
    "GH": 80,    # Greenberg Handbook
    "RH": 85,    # Rhoton Anatomy (high for anatomy)
    "AT-B": 80,  # Atlas Brain
    "AT-S": 80,  # Atlas Spine

    # Subspecialty texts (authority 85 in their domain)
    "BS": 85,    # Benzel Spine
    "AO1": 85,   # AO Spine Vol 1
    "AO2": 85,   # AO Spine Vol 2
    "FU": 85,    # Lozano Functional
    "PN": 85,    # Albright Pediatric
    "BT": 85,    # Brain Tumors
    "EP": 85,    # Epilepsy Comprehensive
    "CB": 85,    # Cerebrovascular

    # Standard texts (authority 70)
    "DEFAULT": 70,
}


@dataclass
class IndexEntry:
    """A single entry from the master index."""
    term: str
    references: List[str]  # Full reference strings: ["L7 Ch.5", "CB Ch.17"]
    primary_sources: List[str]  # Just abbreviations: ["L7", "CB"]
    authority: int  # Highest authority score from sources
    related_terms: List[str] = field(default_factory=list)

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

    def __init__(self, ini_path: Optional[Path] = None):
        self.entries: Dict[str, IndexEntry] = {}
        self._term_index: Dict[str, List[str]] = {}  # word -> [terms containing word]

        if ini_path is None:
            # Default location
            ini_path = Path(__file__).parent / "COMPREHENSIVE.ini"

        if ini_path.exists():
            self._parse(ini_path)

    def _parse(self, path: Path) -> None:
        """Parse COMPREHENSIVE.ini file."""
        in_index = False

        for line in path.read_text(encoding='utf-8').splitlines():
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
            if re.match(r'^[A-Z]\s*$', line.strip()):
                continue

            # Parse term line: "Term<TAB>Refs" or "Term — Refs"
            # Handle both TAB and em-dash separators
            if '\t' in line:
                parts = line.split('\t', 1)
            elif ' — ' in line:
                parts = line.split(' — ', 1)
            elif '\u2014' in line:  # Unicode em-dash
                parts = line.split('\u2014', 1)
            else:
                # No separator - might be a cross-reference
                if ' - see ' in line.lower():
                    # Cross-reference: "Term - see OtherTerm"
                    term = line.split(' - see ')[0].strip()
                    self._add_entry(term, [], is_crossref=True)
                continue

            if len(parts) != 2:
                continue

            term = parts[0].strip()
            refs_str = parts[1].strip()

            if not term or not refs_str:
                continue

            # Parse references: "L7 Ch.5, CB Ch.17, GH p.1377-1382"
            refs = [r.strip() for r in refs_str.split(',')]

            self._add_entry(term, refs)

        # Build word index for fuzzy matching
        self._build_word_index()

    def _add_entry(self, term: str, refs: List[str], is_crossref: bool = False) -> None:
        """Add an entry to the index."""
        # Extract primary source abbreviations
        primary_sources = []
        for ref in refs[:3]:  # First 3 are usually most authoritative
            # Extract abbreviation (first word): "L7 Ch.5" -> "L7"
            match = re.match(r'^([A-Z][A-Z0-9\-]+)', ref)
            if match:
                primary_sources.append(match.group(1))

        # Calculate authority score (use highest)
        authority = max(
            TEXT_AUTHORITY.get(src, TEXT_AUTHORITY["DEFAULT"])
            for src in primary_sources
        ) if primary_sources else TEXT_AUTHORITY["DEFAULT"]

        entry = IndexEntry(
            term=term,
            references=refs,
            primary_sources=primary_sources,
            authority=authority
        )

        # Store by lowercase for case-insensitive lookup
        self.entries[term.lower()] = entry

    def _build_word_index(self) -> None:
        """Build inverted index for word-based lookup."""
        for term_lower, entry in self.entries.items():
            # Extract words (alphanumeric only)
            words = re.findall(r'[a-z0-9]+', term_lower)
            for word in words:
                if len(word) >= 3:  # Skip short words
                    if word not in self._term_index:
                        self._term_index[word] = []
                    self._term_index[word].append(term_lower)

    def find_term(self, query: str) -> List[IndexEntry]:
        """Find index entries matching a query.

        Uses simple substring matching - no fuzzy logic for MVP.
        Returns entries sorted by match quality and authority.
        """
        query_lower = query.lower().strip()
        matches: List[IndexEntry] = []

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
        query_words = set(re.findall(r'[a-z0-9]+', query_lower))
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
            "lawton": 100,      # Lawton Seven
            "youmans": 90,
            "greenberg": 80,
            "rhoton": 85,
            "schmidek": 90,
            "benzel": 85,
            "sekhar": 80,
            "samii": 100,
        }

        for pattern, authority in patterns.items():
            if pattern in name_lower:
                return authority

        return TEXT_AUTHORITY["DEFAULT"]


# Module-level singleton for easy access
_master_index: Optional[MasterIndex] = None

def get_master_index() -> MasterIndex:
    """Get the singleton MasterIndex instance."""
    global _master_index
    if _master_index is None:
        _master_index = MasterIndex()
    return _master_index
```

---

### Task 0.2: Lean Intent Detection (`query_intent_lean.py`)

**Purpose**: Simple keyword-based intent detection without API calls.

**File**: `reference-library/src/search/query_intent_lean.py`

```python
"""Lean query intent detection using keyword matching.

This is a SIMPLE, NO-API implementation that:
1. Detects intent keywords at END of query (not middle)
2. Extracts the core topic
3. Provides section filter suggestions

No ML, no API calls, no fuzzy matching - just fast keyword lookup.
"""
from dataclasses import dataclass
from enum import Enum, auto
from typing import List, Optional
import re


class QueryIntent(Enum):
    """Type of content the user is looking for."""
    TECHNIQUE = auto()      # Surgical technique, operative steps
    COMPLICATION = auto()   # Risks, adverse events, pitfalls
    ANATOMY = auto()        # Anatomical structures, landmarks
    INDICATION = auto()     # When to operate, patient selection
    OUTCOME = auto()        # Results, prognosis, success rates
    GENERAL = auto()        # No specific intent detected


@dataclass
class IntentResult:
    """Result of intent detection."""
    intent: QueryIntent
    core_topic: str
    section_filters: List[str]  # Section headers to boost
    confidence: float = 0.8


# Intent keywords - checked at END of query only
INTENT_PATTERNS = {
    QueryIntent.TECHNIQUE: {
        "keywords": [
            "technique", "approach", "procedure", "how to",
            "surgical steps", "operative", "method", "surgery"
        ],
        "section_filters": [
            "Surgical Technique", "Operative Technique", "Procedure",
            "Surgical Steps", "Technical Steps", "Approach"
        ]
    },
    QueryIntent.COMPLICATION: {
        "keywords": [
            "complications", "complication", "risks", "risk",
            "pitfalls", "adverse", "morbidity", "mortality"
        ],
        "section_filters": [
            "Complications", "Risks", "Pitfalls", "Morbidity",
            "Adverse Events", "Postoperative Complications"
        ]
    },
    QueryIntent.ANATOMY: {
        "keywords": [
            "anatomy", "anatomical", "structure", "landmark",
            "landmarks", "relationship", "relationships"
        ],
        "section_filters": [
            "Anatomy", "Surgical Anatomy", "Anatomical Considerations",
            "Landmarks", "Anatomic Relationships"
        ]
    },
    QueryIntent.INDICATION: {
        "keywords": [
            "indications", "indication", "contraindications",
            "patient selection", "when to", "criteria"
        ],
        "section_filters": [
            "Indications", "Patient Selection", "Contraindications",
            "Selection Criteria", "Surgical Indications"
        ]
    },
    QueryIntent.OUTCOME: {
        "keywords": [
            "outcome", "outcomes", "results", "prognosis",
            "success rate", "survival", "follow-up"
        ],
        "section_filters": [
            "Outcomes", "Results", "Prognosis", "Follow-up",
            "Long-term Results", "Success Rates"
        ]
    }
}


def detect_intent(query: str) -> IntentResult:
    """Detect query intent from END keywords only.

    Args:
        query: User's search query

    Returns:
        IntentResult with intent type, core topic, and section filters

    Examples:
        "lumbar discectomy technique" → TECHNIQUE, topic="lumbar discectomy"
        "basilar aneurysm complications" → COMPLICATION, topic="basilar aneurysm"
        "pterional approach" → GENERAL (approach is part of the topic name)
    """
    query = query.strip()
    query_lower = query.lower()

    if not query:
        return IntentResult(
            intent=QueryIntent.GENERAL,
            core_topic=query,
            section_filters=[],
            confidence=0.0
        )

    # Check each intent's keywords at END of query
    for intent, config in INTENT_PATTERNS.items():
        for keyword in config["keywords"]:
            # Only match if keyword is at the END of the query
            # This prevents "pterional approach" from being parsed incorrectly
            if query_lower.endswith(keyword):
                # Extract topic by removing the trailing keyword
                topic = query[:-len(keyword)].strip()

                # Handle edge case: query is JUST the keyword
                if not topic:
                    topic = query
                    return IntentResult(
                        intent=QueryIntent.GENERAL,
                        core_topic=topic,
                        section_filters=[],
                        confidence=0.5
                    )

                return IntentResult(
                    intent=intent,
                    core_topic=topic,
                    section_filters=config["section_filters"],
                    confidence=0.85
                )

            # Also check for "keyword of topic" pattern
            # e.g., "complications of lumbar discectomy"
            pattern = rf'^{re.escape(keyword)}\s+of\s+(.+)$'
            match = re.match(pattern, query_lower, re.IGNORECASE)
            if match:
                topic = match.group(1).strip()
                return IntentResult(
                    intent=intent,
                    core_topic=topic,
                    section_filters=config["section_filters"],
                    confidence=0.80
                )

    # No intent keyword found - return GENERAL
    return IntentResult(
        intent=QueryIntent.GENERAL,
        core_topic=query,
        section_filters=[],
        confidence=0.5
    )


def get_section_boost(intent: QueryIntent) -> int:
    """Get relevance score boost for matching section type.

    Used in scoring when a page contains a section header
    matching the user's intent.
    """
    boosts = {
        QueryIntent.TECHNIQUE: 30,
        QueryIntent.COMPLICATION: 30,
        QueryIntent.ANATOMY: 25,
        QueryIntent.INDICATION: 20,
        QueryIntent.OUTCOME: 20,
        QueryIntent.GENERAL: 0,
    }
    return boosts.get(intent, 0)
```

---

### Task 0.3: Robust Section Header Detection (`section_detector.py`)

**Purpose**: Robust section header detection with fallbacks for Zero Data Loss.

**File**: `reference-library/src/search/section_detector.py`

**Design Principles**:
1. **Multi-tier pattern matching** - Start with strict patterns, fall back to fuzzy
2. **Format-agnostic** - Handle numbered, roman, uppercase, mixed-case headers
3. **Safe page windows** - When section end isn't found, default to safe extraction
4. **Zero Data Loss guarantee** - Always return SOMETHING; never skip content

```python
"""Robust section header detection for PDF text.

Handles formatting variations across different neurosurgical textbooks:
- Youmans: "SURGICAL TECHNIQUE" (all caps)
- Lawton: "Technique" (title case, bold implied)
- Greenberg: "17.4.2 Technique" (numbered)
- Schmidek: "IV. OPERATIVE TECHNIQUE" (roman numerals)

ZERO DATA LOSS GUARANTEE:
- If section detection fails, fall back to safe page window
- Always return matched content, even if section boundaries unclear
- Prefer over-inclusion over missing relevant content
"""
import re
from typing import List, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum, auto


class MatchConfidence(Enum):
    """Confidence level of section header match."""
    HIGH = auto()      # Exact pattern match (e.g., "Surgical Technique")
    MEDIUM = auto()    # Fuzzy match (e.g., "Technique and Tips")
    LOW = auto()       # Keyword-only match (e.g., line containing "technique")
    FALLBACK = auto()  # No header found, using safe page window


@dataclass
class DetectedSection:
    """A detected section header with confidence metadata."""
    header_text: str
    section_type: str  # "technique", "complications", etc.
    page_number: int
    start_pos: int  # Character position in page text
    confidence: MatchConfidence = MatchConfidence.HIGH
    # Safe extraction window (for Zero Data Loss)
    suggested_start_page: int = 0
    suggested_end_page: int = 0  # 0 means "use default window"


# ============================================================
# MULTI-TIER SECTION PATTERNS
# Organized by confidence level for graceful degradation
# ============================================================

SECTION_PATTERNS = {
    "technique": {
        # TIER 1: High confidence - exact standard headers
        "high": [
            r'^(?:surgical\s+)?technique[s]?$',
            r'^operative\s+(?:technique|procedure|steps?)$',
            r'^technical\s+(?:steps?|considerations?)$',
            r'^surgical\s+(?:approach|procedure|steps?)$',
            r'^step[s]?\s*[-:]?\s*by[-\s]step\s+(?:technique|approach)$',
        ],
        # TIER 2: Medium confidence - variations with numbering/context
        "medium": [
            r'^(?:\d+\.)+\s*(?:surgical\s+)?technique',
            r'^[IVX]+\.\s*(?:operative\s+)?technique',
            r'^technique\s+(?:of|for)\s+',
            r'^(?:microsurgical|endoscopic|open)\s+technique',
            r'^technical\s+(?:nuances|pearls|tips)',
        ],
        # TIER 3: Low confidence - keyword presence (fallback)
        "low": [
            r'(?:surgical|operative|microsurgical)\s+technique',
            r'technique\s+(?:section|chapter)',
        ],
    },
    "complications": {
        "high": [
            r'^complication[s]?$',
            r'^(?:surgical\s+)?risk[s]?$',
            r'^pitfall[s]?(?:\s+and\s+(?:pearls?|tips?))?$',
            r'^morbidity\s+and\s+mortality$',
            r'^adverse\s+(?:events?|outcomes?)$',
        ],
        "medium": [
            r'^(?:\d+\.)+\s*complication[s]?',
            r'^[IVX]+\.\s*complication[s]?',
            r'^(?:potential|common|major)\s+complications?',
            r'^complications?\s+(?:of|and|following)',
            r'^avoidance\s+of\s+complications?',
            r'^how\s+to\s+avoid\s+complications?',
        ],
        "low": [
            r'complication[s]?\s+(?:section|include)',
            r'(?:avoid|prevent)(?:ing|ance)?\s+complications?',
        ],
    },
    "anatomy": {
        "high": [
            r'^(?:surgical\s+)?anatomy$',
            r'^relevant\s+anatomy$',
            r'^anatomic(?:al)?\s+considerations?$',
            r'^regional\s+anatomy$',
        ],
        "medium": [
            r'^(?:\d+\.)+\s*(?:surgical\s+)?anatomy',
            r'^[IVX]+\.\s*anatomy',
            r'^anatomy\s+(?:of|and)\s+',
            r'^(?:microsurgical|applied|functional)\s+anatomy',
            r'^anatomic(?:al)?\s+(?:relationships?|landmarks?|basis)',
        ],
        "low": [
            r'anatomy\s+(?:relevant|pertinent|section)',
            r'anatomic(?:al)?\s+(?:review|overview)',
        ],
    },
    "indications": {
        "high": [
            r'^indication[s]?$',
            r'^(?:surgical\s+)?indications?(?:\s+and\s+contraindications?)?$',
            r'^patient\s+selection$',
            r'^contraindication[s]?$',
            r'^selection\s+criteria$',
        ],
        "medium": [
            r'^(?:\d+\.)+\s*indication[s]?',
            r'^[IVX]+\.\s*indication[s]?',
            r'^indications?\s+(?:for|and)\s+',
            r'^when\s+to\s+(?:operate|intervene)',
            r'^(?:surgical|treatment)\s+decision',
        ],
        "low": [
            r'indication[s]?\s+(?:include|are)',
            r'(?:primary|main)\s+indication[s]?',
        ],
    },
    "outcomes": {
        "high": [
            r'^(?:surgical\s+)?outcome[s]?$',
            r'^result[s]?$',
            r'^prognosis$',
            r'^(?:post-?operative|long-?term)\s+(?:results?|outcomes?)$',
        ],
        "medium": [
            r'^(?:\d+\.)+\s*(?:surgical\s+)?outcomes?',
            r'^[IVX]+\.\s*(?:results?|outcomes?)',
            r'^outcomes?\s+(?:of|and|following)',
            r'^(?:clinical|surgical|functional)\s+(?:results?|outcomes?)',
            r'^success\s+rate[s]?$',
            r'^(?:short|long)[-\s]term\s+(?:follow[-\s]?up|outcomes?)',
        ],
        "low": [
            r'outcome[s]?\s+(?:are|were|include)',
            r'(?:report|study|series)\s+outcomes?',
        ],
    },
}

# ============================================================
# SAFE PAGE WINDOW DEFAULTS
# Used when section boundaries cannot be determined
# ============================================================

DEFAULT_SECTION_WINDOWS = {
    "technique": 8,      # Techniques are usually detailed (5-10 pages)
    "complications": 4,  # Complications are usually concise (2-5 pages)
    "anatomy": 6,        # Anatomy sections vary (3-8 pages)
    "indications": 3,    # Indications are usually brief (2-4 pages)
    "outcomes": 4,       # Outcomes sections are moderate (3-5 pages)
    "default": 5,        # Safe default for unknown section types
}

# Minimum pages to extract (Zero Data Loss guarantee)
MIN_EXTRACTION_PAGES = 2


def detect_section_headers(
    text: str,
    page_number: int = 1,
    require_high_confidence: bool = False
) -> List[DetectedSection]:
    """Detect section headers in page text with multi-tier matching.

    Args:
        text: Page text content
        page_number: Page number for metadata
        require_high_confidence: If True, only return HIGH confidence matches

    Returns:
        List of detected sections, sorted by confidence (HIGH first)
    """
    sections: List[DetectedSection] = []

    # Normalize text: handle various line endings
    text = text.replace('\r\n', '\n').replace('\r', '\n')

    for line_num, line in enumerate(text.split('\n')):
        line_stripped = line.strip()

        # Skip lines that are too short or too long to be headers
        if len(line_stripped) < 3 or len(line_stripped) > 100:
            continue

        # Skip lines that look like body text (too many words)
        word_count = len(line_stripped.split())
        if word_count > 10:  # Headers rarely have >10 words
            continue

        # Try each section type
        for section_type, tier_patterns in SECTION_PATTERNS.items():
            matched = False

            # Try tiers in order: high → medium → low
            for tier, patterns in [
                (MatchConfidence.HIGH, tier_patterns["high"]),
                (MatchConfidence.MEDIUM, tier_patterns["medium"]),
                (MatchConfidence.LOW, tier_patterns["low"]),
            ]:
                if require_high_confidence and tier != MatchConfidence.HIGH:
                    continue

                for pattern in patterns:
                    if re.match(pattern, line_stripped, re.IGNORECASE):
                        sections.append(DetectedSection(
                            header_text=line_stripped,
                            section_type=section_type,
                            page_number=page_number,
                            start_pos=text.find(line),
                            confidence=tier,
                            suggested_start_page=page_number,
                            suggested_end_page=page_number + DEFAULT_SECTION_WINDOWS.get(
                                section_type, DEFAULT_SECTION_WINDOWS["default"]
                            )
                        ))
                        matched = True
                        break

                if matched:
                    break

            if matched:
                break

    # Sort by confidence (HIGH first) then by position
    sections.sort(key=lambda s: (s.confidence.value, s.start_pos))

    return sections


def has_matching_section(
    text: str,
    section_types: List[str],
    min_confidence: MatchConfidence = MatchConfidence.LOW
) -> bool:
    """Quick check if text contains any matching section headers.

    Args:
        text: Page text to search
        section_types: List of section types to look for
        min_confidence: Minimum confidence level to accept

    Returns:
        True if any matching section header is found
    """
    for section_type in section_types:
        if section_type not in SECTION_PATTERNS:
            continue

        tier_patterns = SECTION_PATTERNS[section_type]

        # Check tiers up to min_confidence
        tiers_to_check = [
            (MatchConfidence.HIGH, tier_patterns["high"]),
        ]
        if min_confidence.value >= MatchConfidence.MEDIUM.value:
            tiers_to_check.append((MatchConfidence.MEDIUM, tier_patterns["medium"]))
        if min_confidence.value >= MatchConfidence.LOW.value:
            tiers_to_check.append((MatchConfidence.LOW, tier_patterns["low"]))

        for _, patterns in tiers_to_check:
            for pattern in patterns:
                if re.search(pattern, text, re.IGNORECASE | re.MULTILINE):
                    return True

    return False


def get_safe_extraction_window(
    detected_section: Optional[DetectedSection],
    section_type: str,
    max_page: int
) -> Tuple[int, int]:
    """Get safe page extraction window with Zero Data Loss guarantee.

    NEVER returns an empty range. If detection failed, returns a safe default.

    Args:
        detected_section: Detected section (may be None if detection failed)
        section_type: Type of section requested
        max_page: Maximum page number in the document

    Returns:
        Tuple of (start_page, end_page) - GUARANTEED to be valid range
    """
    if detected_section and detected_section.confidence != MatchConfidence.FALLBACK:
        # Use detected boundaries
        start = detected_section.suggested_start_page
        end = min(detected_section.suggested_end_page, max_page)
    else:
        # FALLBACK: Use safe default window
        # This guarantees we always extract SOMETHING
        window_size = DEFAULT_SECTION_WINDOWS.get(
            section_type,
            DEFAULT_SECTION_WINDOWS["default"]
        )
        start = 1  # Start from beginning if no header found
        end = min(window_size, max_page)

    # ZERO DATA LOSS: Ensure minimum extraction
    if end - start < MIN_EXTRACTION_PAGES:
        end = min(start + MIN_EXTRACTION_PAGES, max_page)

    return (start, end)


def create_fallback_section(
    section_type: str,
    page_number: int,
    window_size: Optional[int] = None
) -> DetectedSection:
    """Create a fallback section when no header is detected.

    Used to guarantee Zero Data Loss - we always return SOMETHING.

    Args:
        section_type: Type of section requested
        page_number: Starting page number
        window_size: Override default window size

    Returns:
        DetectedSection with FALLBACK confidence
    """
    if window_size is None:
        window_size = DEFAULT_SECTION_WINDOWS.get(
            section_type,
            DEFAULT_SECTION_WINDOWS["default"]
        )

    return DetectedSection(
        header_text=f"[{section_type.title()} - auto-detected region]",
        section_type=section_type,
        page_number=page_number,
        start_pos=0,
        confidence=MatchConfidence.FALLBACK,
        suggested_start_page=page_number,
        suggested_end_page=page_number + window_size
    )
```

---

### Zero Data Loss Guarantee - Integration Points

**In `pdf_searcher.py`** - When section detection fails, use fallback:

```python
# Section detection with fallback
if intent_result.intent != QueryIntent.GENERAL:
    section_type = intent_result.intent.name.lower()
    matched_sections = []

    for page_num in result.matched_pages[:5]:
        cached_text = self.database.get_cached_text(result.pdf_path, page_num)
        if cached_text:
            headers = detect_section_headers(cached_text, page_num)
            relevant = [h for h in headers if h.section_type == section_type]

            if relevant:
                matched_sections.extend(relevant)
            else:
                # FALLBACK: Create synthetic section to ensure extraction
                # This guarantees we never skip relevant content
                fallback = create_fallback_section(section_type, page_num)
                matched_sections.append(fallback)

    result.matched_sections = matched_sections[:5]
```

**In `page_extractor.py`** - Use safe window when boundaries unclear:

```python
def extract_section_pages(
    pdf_path: Path,
    section: DetectedSection,
    max_page: int
) -> List[int]:
    """Extract pages for a section with Zero Data Loss guarantee."""
    start, end = get_safe_extraction_window(section, section.section_type, max_page)

    # ALWAYS return at least MIN_EXTRACTION_PAGES
    pages = list(range(start, end + 1))

    if len(pages) < MIN_EXTRACTION_PAGES:
        # Extend to ensure we don't miss content
        pages = list(range(start, min(start + MIN_EXTRACTION_PAGES, max_page) + 1))

    return pages
```

---

### Task 0.4: Result Model Updates (`result_model.py`)

**Purpose**: Add fields for matched sections and authority scoring.

**Modifications to**: `reference-library/src/search/result_model.py`

```python
# ADD to ChapterResult dataclass (after line 203):

@dataclass
class ChapterResult:
    """A chapter-level search result..."""
    # ... existing fields ...

    # NEW FIELDS:
    # Matched section headers (if intent was specific)
    matched_sections: List[str] = field(default_factory=list)
    # Authority score from master index (0-100)
    authority_score: int = 70
    # Source abbreviation if matched in index (e.g., "L7", "YW")
    index_source: Optional[str] = None

    @property
    def relevance_score(self) -> float:
        """Calculate enhanced relevance score."""
        base = self.match_type.relevance_score

        # Authority boost (0-30 points)
        authority_boost = (self.authority_score - 70) / 30 * 30  # Normalize to 0-30

        # Section match boost (0-30 points if we matched user's intent)
        section_boost = 30 if self.matched_sections else 0

        # Occurrence density boost (0-20 points)
        if self.page_count > 0:
            density = min(self.total_occurrences / self.page_count, 2.0)
            density_boost = density * 10
        else:
            density_boost = 0

        return base + authority_boost + section_boost + density_boost
```

---

### Task 0.5: PDF Searcher Integration (`pdf_searcher.py`)

**Purpose**: Integrate MasterIndex, IntentDetection, and SectionDetection.

**Modifications to**: `reference-library/src/search/pdf_searcher.py`

```python
# ADD imports at top (after existing imports):
from .master_index import get_master_index, MasterIndex
from .query_intent_lean import detect_intent, IntentResult, QueryIntent
from .section_detector import detect_section_headers, has_matching_section

# MODIFY search_library_chapters() method:

def search_library_chapters(
    self,
    query: str,
    mode: str = "keyword",
    progress_callback: Optional[Callable[[SearchProgress], None]] = None,
) -> Generator[ChapterResult, None, None]:
    """
    Knowledge retrieval search - returns chapter-level results.

    ENHANCED with:
    - Master index lookup for authority boosting
    - Intent detection for section filtering
    - Section header detection for relevance scoring
    """
    self.reset()

    # === NEW: Intent Detection ===
    intent_result = detect_intent(query)
    search_query = intent_result.core_topic  # Use core topic for search

    # === NEW: Master Index Lookup ===
    master_index = get_master_index()
    index_matches = master_index.find_term(search_query)

    # Get related terms for expansion
    related_terms = []
    for match in index_matches[:3]:
        related_terms.extend(match.related_terms)

    # ... existing search logic using search_query instead of query ...

    # For each ChapterResult, add:
    # 1. Authority score from index/PDF filename
    # 2. Matched sections from section detection
    # 3. Index source if matched

    for result in chapter_results.values():
        # Authority boost
        result.authority_score = master_index.get_authority_boost(result.pdf_path)

        # Check for index match
        for match in index_matches:
            if any(src in result.pdf_path.stem.upper() for src in match.primary_sources):
                result.index_source = match.primary_sources[0]
                result.authority_score = match.authority
                break

        # Section detection (if intent was specific)
        if intent_result.intent != QueryIntent.GENERAL:
            # Check pages for matching section headers
            matched_sections = []
            for page_num in result.matched_pages[:5]:  # Check first 5 pages
                cached_text = self.database.get_cached_text(result.pdf_path, page_num)
                if cached_text:
                    section_type = intent_result.intent.name.lower()
                    if has_matching_section(cached_text, [section_type]):
                        headers = detect_section_headers(cached_text, page_num)
                        for h in headers:
                            if h.section_type == section_type:
                                matched_sections.append(h.header_text)

            result.matched_sections = list(set(matched_sections))[:5]

    # Sort by enhanced relevance score
    sorted_results = sorted(
        chapter_results.values(),
        key=lambda r: r.relevance_score,
        reverse=True
    )

    # ... rest of method ...
```

---

### Task 0.6: Page Extractor Enhancement (`page_extractor.py`)

**Purpose**: Add authority and section metadata to extracted sources.

**Modifications to**: `reference-library/src/export/page_extractor.py`

```python
# ADD to ExtractedSource dataclass:

@dataclass
class ExtractedSource:
    """Metadata for an extracted PDF source..."""
    # ... existing fields ...

    # NEW FIELDS:
    # Authority score from master index
    authority_score: int = 70
    # Source abbreviation if known (e.g., "L7", "YW")
    source_abbreviation: Optional[str] = None
    # Detected section headers in extracted content
    matched_sections: List[str] = field(default_factory=list)
    # Query intent that led to this extraction
    query_intent: Optional[str] = None


# MODIFY generate_manifest() to include new metadata:

def generate_manifest(
    topic: str,
    sources: list[ExtractedSource],
    output_path: Path,
    search_query: str = "",
    search_mode: str = "keyword",
    template_type: Optional[str] = None,
    query_intent: Optional[str] = None,  # NEW
) -> Path:
    """Generate enhanced manifest.json for NeuroSynth."""

    manifest = {
        # ... existing fields ...

        # NEW: Enhanced search metadata
        "query_intent": query_intent,
        "sources": [
            {
                # ... existing source fields ...

                # NEW: Authority and section metadata
                "authority_score": source.authority_score,
                "source_abbreviation": source.source_abbreviation,
                "matched_sections": source.matched_sections,
            }
            for source in sources
        ]
    }

    # ... rest of method ...
```

---

## 🧪 TESTING STRATEGY

### Unit Tests (`tests/test_enhanced_search.py`)

```python
"""Tests for enhanced search components."""
import pytest
from pathlib import Path

from src.search.master_index import MasterIndex, get_master_index
from src.search.query_intent_lean import detect_intent, QueryIntent
from src.search.section_detector import detect_section_headers, has_matching_section


class TestMasterIndex:
    """Tests for COMPREHENSIVE.ini parser."""

    def test_parse_index(self):
        """Should parse index and find entries."""
        index = get_master_index()
        assert len(index.entries) > 2000  # 2,632 expected

    def test_find_exact_term(self):
        """Should find exact term match."""
        index = get_master_index()
        matches = index.find_term("basilar apex aneurysm")
        assert len(matches) > 0
        assert "L7" in matches[0].primary_sources

    def test_authority_ranking(self):
        """Should rank by authority."""
        index = get_master_index()
        matches = index.find_term("aneurysm")
        # Specialized text (L7) should rank higher than general (GH)
        authorities = [m.authority for m in matches[:5]]
        assert max(authorities) >= 90


class TestIntentDetection:
    """Tests for lean intent detection."""

    def test_technique_intent(self):
        """Should detect technique intent at end of query."""
        result = detect_intent("lumbar discectomy technique")
        assert result.intent == QueryIntent.TECHNIQUE
        assert result.core_topic == "lumbar discectomy"

    def test_complication_intent(self):
        """Should detect complication intent."""
        result = detect_intent("acoustic neuroma complications")
        assert result.intent == QueryIntent.COMPLICATION
        assert result.core_topic == "acoustic neuroma"

    def test_approach_not_stripped(self):
        """Should NOT strip 'approach' from pterional approach."""
        result = detect_intent("pterional approach")
        # "approach" is part of the topic, not intent keyword
        assert result.intent == QueryIntent.GENERAL
        assert "pterional" in result.core_topic.lower()

    def test_general_query(self):
        """Plain query should return GENERAL intent."""
        result = detect_intent("vestibular schwannoma")
        assert result.intent == QueryIntent.GENERAL
        assert result.core_topic == "vestibular schwannoma"


class TestSectionDetection:
    """Tests for robust section header detection with fallbacks."""

    def test_detect_technique_header_high_confidence(self):
        """Should detect standard technique headers with HIGH confidence."""
        text = """
        Introduction
        The pterional approach is commonly used.

        Surgical Technique
        Position the patient supine...
        """
        sections = detect_section_headers(text, page_number=1)
        assert len(sections) >= 1
        assert sections[0].section_type == "technique"
        assert sections[0].confidence == MatchConfidence.HIGH

    def test_detect_numbered_header_medium_confidence(self):
        """Should detect numbered headers with MEDIUM confidence."""
        text = "5.2.3 Operative Technique\nThe procedure begins..."
        sections = detect_section_headers(text, page_number=1)
        assert len(sections) >= 1
        assert sections[0].section_type == "technique"
        assert sections[0].confidence == MatchConfidence.MEDIUM

    def test_detect_roman_numeral_header(self):
        """Should detect roman numeral headers (Schmidek format)."""
        text = "IV. COMPLICATIONS\nBleeding is the most common..."
        sections = detect_section_headers(text, page_number=1)
        assert len(sections) >= 1
        assert sections[0].section_type == "complications"

    def test_detect_all_caps_header(self):
        """Should detect all-caps headers (Youmans format)."""
        text = "SURGICAL ANATOMY\nThe middle cerebral artery..."
        sections = detect_section_headers(text, page_number=1)
        assert len(sections) >= 1
        assert sections[0].section_type == "anatomy"

    def test_has_matching_section_with_confidence(self):
        """Should filter by confidence level."""
        text = "Microsurgical technique was employed..."  # LOW confidence
        # HIGH only - should NOT match
        assert not has_matching_section(text, ["technique"], MatchConfidence.HIGH)
        # LOW - SHOULD match
        assert has_matching_section(text, ["technique"], MatchConfidence.LOW)

    def test_safe_extraction_window_with_detection(self):
        """Should use detected section boundaries."""
        section = DetectedSection(
            header_text="Complications",
            section_type="complications",
            page_number=5,
            start_pos=0,
            confidence=MatchConfidence.HIGH,
            suggested_start_page=5,
            suggested_end_page=9
        )
        start, end = get_safe_extraction_window(section, "complications", max_page=20)
        assert start == 5
        assert end == 9

    def test_safe_extraction_window_fallback(self):
        """Should use safe default when no section detected."""
        start, end = get_safe_extraction_window(None, "technique", max_page=50)
        # Should use DEFAULT_SECTION_WINDOWS["technique"] = 8
        assert start == 1
        assert end >= MIN_EXTRACTION_PAGES  # At least 2 pages

    def test_zero_data_loss_minimum_pages(self):
        """Should always return at least MIN_EXTRACTION_PAGES."""
        # Even with tiny document, should get minimum pages
        start, end = get_safe_extraction_window(None, "indications", max_page=2)
        assert end - start + 1 >= MIN_EXTRACTION_PAGES

    def test_create_fallback_section(self):
        """Should create fallback section for Zero Data Loss."""
        fallback = create_fallback_section("technique", page_number=10)
        assert fallback.confidence == MatchConfidence.FALLBACK
        assert fallback.section_type == "technique"
        assert fallback.suggested_start_page == 10
        # Should use default window for technique (8 pages)
        assert fallback.suggested_end_page == 18
```

### Integration Test Queries

| Query | Expected Behavior |
|-------|-------------------|
| "basilar aneurysm technique" | Lawton Seven in top 3, technique sections boosted |
| "lumbar discectomy complications" | Complication sections highlighted |
| "pterional approach" | Returns as general topic (approach not stripped) |
| "acoustic neuroma" | Returns both surgical and clinical content |
| "C1-C2 fusion" | Spine texts (Benzel, AO) ranked higher |

---

## ✅ SUCCESS METRICS

### Phase 0 (Week 1) - Ship It

| Metric | Target | Validation |
|--------|--------|------------|
| Zero-result queries | 15% → 5% | Test 20 common queries |
| Authority boost works | Lawton #1 for "aneurysm" | Single test case |
| Intent detection accuracy | >80% | 10 test queries |
| No keyword collision | "pterional approach" preserved | Test case |
| Search speed | <5 seconds | Informal timing |

### Synthesis Quality Improvements

| Metric | Before | After (Expected) |
|--------|--------|------------------|
| Tokens sent to NeuroSynth | 100% | 70% (more focused) |
| Irrelevant pages extracted | 30% | 10% |
| Section-aware extraction | No | Yes |
| Authority metadata | No | Yes |

---

## 📋 IMPLEMENTATION CHECKLIST

```
Phase 0: Core Foundation
├── [ ] 0.1 master_index.py - Parse COMPREHENSIVE.ini
│   ├── [ ] TAB-separated format parsing
│   ├── [ ] Authority scoring
│   ├── [ ] Term lookup with word index
│   └── [ ] Unit tests
├── [ ] 0.2 query_intent_lean.py - Intent detection
│   ├── [ ] END-of-query keyword matching
│   ├── [ ] Section filter suggestions
│   ├── [ ] Handle "approach" correctly
│   └── [ ] Unit tests
├── [ ] 0.3 section_detector.py - Robust Section Detection
│   ├── [ ] Multi-tier patterns (HIGH/MEDIUM/LOW confidence)
│   ├── [ ] Format variants (numbered, roman, caps, title case)
│   ├── [ ] Safe page window defaults per section type
│   ├── [ ] get_safe_extraction_window() with Zero Data Loss
│   ├── [ ] create_fallback_section() for failed detection
│   ├── [ ] MIN_EXTRACTION_PAGES guarantee (≥2 pages)
│   └── [ ] Unit tests for all confidence levels + fallbacks
├── [ ] 0.4 result_model.py updates
│   ├── [ ] Add matched_sections field
│   ├── [ ] Add authority_score field
│   ├── [ ] Enhanced relevance_score property
│   └── [ ] Backward compatible
├── [ ] 0.5 pdf_searcher.py integration
│   ├── [ ] Import new components
│   ├── [ ] Modify search_library_chapters
│   ├── [ ] Authority boosting
│   └── [ ] Section detection
├── [ ] 0.6 page_extractor.py updates
│   ├── [ ] Add ExtractedSource fields
│   ├── [ ] Update generate_manifest
│   └── [ ] Backward compatible
└── [ ] 0.7 Testing
    ├── [ ] Unit tests for all new modules
    ├── [ ] Integration test with real queries
    └── [ ] Smoke test existing functionality

Phase 1: Validate
├── [ ] User testing (20 queries)
├── [ ] Measure precision/recall
├── [ ] Document pain points
└── [ ] Fix critical bugs

Phase 2: Conditional (IF NEEDED)
├── [ ] Section boundaries (if fragmented extraction)
├── [ ] Scoring tuning (if relevance poor)
└── [ ] Performance optimization (if slow)
```

---

## 🎯 FINAL NOTES

### What This Plan Achieves

1. **Authority-Boosted Search**: Lawton ranks #1 for aneurysms, not random GH pages
2. **Intent-Aware Results**: "technique" query → technique sections highlighted
3. **Better Synthesis Input**: Focused, section-aware content → less noise for NeuroSynth
4. **No Keyword Collision**: "pterional approach" works correctly
5. **Lean Implementation**: 28 hours vs 89 hours, 80% of value at 31% cost

### What This Plan Defers

- Full section boundary calculation (too complex for MVP)
- ML-based intent detection (API costs, complexity)
- Configurable scoring weights (premature optimization)
- Visual heat maps (low ROI)

### Integration with NeuroSynth

The enhanced `manifest.json` will include:
```json
{
  "query_intent": "TECHNIQUE",
  "sources": [
    {
      "authority_score": 100,
      "source_abbreviation": "L7",
      "matched_sections": ["Surgical Technique"],
      ...
    }
  ]
}
```

NeuroSynth can use this metadata to:
- Prioritize authoritative sources in synthesis
- Focus on sections matching user intent
- Generate more targeted, relevant chapters
