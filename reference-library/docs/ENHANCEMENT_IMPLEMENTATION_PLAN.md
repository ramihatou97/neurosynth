# 🎯 ENHANCEMENT IMPLEMENTATION PLAN

## Overview

This plan implements the partially-implemented and missing features from the enhanced search strategy.

---

## 📋 PHASE 1: CORE COMPONENTS (Backend)

### Task 1.1: Create `search_strategy.py`

**File**: `reference-library/src/search/search_strategy.py`

**Purpose**: Define STRICT / STANDARD / BROAD search strategy configurations.

```python
@dataclass
class SearchStrategy:
    name: str
    # Query Expansion
    expand_synonyms: bool
    expand_orthographic: bool  # disc/disk variants
    # Intent Detection
    use_intent_detection: bool
    use_ai_intent: bool  # Use Claude API for complex cases
    # Authority
    authority_threshold: int  # Min authority to include (0-100)
    prefer_primary_sources: bool
    # Results
    max_results: int
    min_relevance_score: float
```

**Configurations**:
| Mode | Expansion | AI Intent | Authority Threshold | Max Results |
|------|-----------|-----------|---------------------|-------------|
| STRICT | None | No | 90 | 20 |
| STANDARD | Full | Lean only | 50 | 50 |
| BROAD | Maximum | Lean + AI | 0 | 100 |

---

### Task 1.2: Hybrid Intent Detection

**File**: `reference-library/src/search/intent_classifier.py`

**Purpose**: Unified intent detection that:
1. Uses lean keyword detection first (fast, free)
2. Falls back to Claude API for ambiguous cases (when confidence < 0.7)

```python
class HybridIntentClassifier:
    def classify(self, query: str, use_ai: bool = False) -> IntentResult:
        # 1. Try lean detection first
        lean_result = self.lean_detector.detect(query)
        
        # 2. If confident or AI disabled, return lean result
        if not use_ai or lean_result.intent != QueryIntent.GENERAL:
            return lean_result
        
        # 3. Use AI for ambiguous GENERAL intent
        ai_result = self.ai_classifier.classify(query)
        return self._merge_results(lean_result, ai_result)
```

---

### Task 1.3: Add Related Terms to Master Index

**File**: `reference-library/src/search/master_index.py`

**Add method**:
```python
def get_related_terms(self, query: str, max_terms: int = 5) -> List[str]:
    """Get related terms from master index for 'Did you mean?' suggestions."""
    matches = self.find_term(query)
    related = []
    
    for match in matches[:3]:
        # Extract terms that share words with query but are different
        for term in self._term_index.get(word, []):
            if term != match.term.lower() and term not in related:
                related.append(self.entries[term].term)
                
    return related[:max_terms]
```

---

## 📋 PHASE 2: UI ENHANCEMENTS

### Task 2.1: Strategy Selector in Search Panel

**File**: `reference-library/src/ui/search_panel.py`

**Add dropdown** between History and Mode selector:
```python
# Strategy selector (STRICT/STANDARD/BROAD)
self.strategy_var = ctk.StringVar(value="standard")
self.strategy_selector = ctk.CTkOptionMenu(
    search_frame,
    values=["strict", "standard", "broad"],
    variable=self.strategy_var,
    width=100,
    font=FONTS["small"]
)
```

**Visual design**:
```
[Search Subject: ________] [History] [🎯 Standard ▾] [keyword|semantic|hybrid] [Search]
```

---

### Task 2.2: Related Terms Display

**File**: `reference-library/src/ui/search_panel.py`

**Add below search bar** (initially hidden):
```python
# Related terms suggestion frame
self.related_frame = ctk.CTkFrame(self, fg_color="transparent")
# Don't pack initially - shown when related terms found

self.related_label = ctk.CTkLabel(
    self.related_frame,
    text="Also try:",
    font=FONTS["small"],
    text_color="gray"
)
```

**Display format**:
```
Also try: basilar tip aneurysm | BA apex | posterior circulation aneurysm
```

---

### Task 2.3: Section/Authority Badges in Results

**File**: `reference-library/src/ui/rich_results_tree.py`

**Enhance `_create_chapter_result_widget`**:
```python
# Authority badge (if from primary source)
if chapter.authority_score >= 80:
    source_badge = ctk.CTkLabel(
        header,
        text=f"⭐ {chapter.index_source}" if chapter.index_source else "⭐ Authority",
        font=FONTS["small"],
        fg_color="#f39c12",
        corner_radius=8
    )
    source_badge.pack(side="right", padx=2)

# Section type badge (if section detected)
if chapter.matched_sections:
    section_type = chapter.matched_sections[0].section_type
    section_badge = ctk.CTkLabel(
        header,
        text=f"📑 {section_type}",
        font=FONTS["small"],
        fg_color="#9b59b6",
        corner_radius=8
    )
    section_badge.pack(side="right", padx=2)
```

---

## 📋 PHASE 3: INTEGRATION

### Task 3.1: Integrate Strategy into Searcher

**File**: `reference-library/src/search/pdf_searcher.py`

**Modify `search_library_chapters`**:
```python
def search_library_chapters(
    self,
    query: str,
    mode: str = "keyword",
    strategy: str = "standard",  # NEW
    progress_callback: ...
) -> Generator[ChapterResult, None, None]:
    
    # Load strategy config
    strat = STRATEGIES[strategy]
    
    # Use strategy for intent detection
    if strat.use_intent_detection:
        intent_result = self.intent_classifier.classify(
            query, use_ai=strat.use_ai_intent
        )
```

### Task 3.2: Wire UI to Backend

**File**: `reference-library/src/ui/app.py`

**Pass strategy from UI to searcher**:
```python
def _on_search(self, query: str, mode: str):
    strategy = self.search_panel.get_strategy()  # NEW
    
    # Start search with strategy
    self._search_worker(query, mode, strategy)
```

---

## 📅 IMPLEMENTATION ORDER

1. **search_strategy.py** - Foundation for all other features
2. **intent_classifier.py** - Unified intent detection
3. **master_index.py update** - Related terms method
4. **search_panel.py** - Strategy selector + related terms UI
5. **rich_results_tree.py** - Authority/section badges
6. **pdf_searcher.py** - Integrate strategy
7. **app.py** - Wire everything together
8. **Testing** - Verify all features work

---

## ⏱️ ESTIMATED EFFORT

| Phase | Tasks | Hours |
|-------|-------|-------|
| Phase 1 | 1.1-1.3 | 4h |
| Phase 2 | 2.1-2.3 | 3h |
| Phase 3 | 3.1-3.2 | 2h |
| Testing | 4.0 | 1h |
| **Total** | | **10h** |

