# Image Pipeline Enhancement: Comprehensive Analysis & Implementation Plan

> **Document Version:** 1.0  
> **Generated:** 2025-12-09  
> **Status:** ✅ Complete Analysis  
> **Scope:** NeuroSynth Image Pipeline vs Deep-DX Reference Architecture

---

## Executive Summary

This analysis compares NeuroSynth's current image handling pipeline against the Deep-DX reference architecture to identify gaps, assess implementation quality, and provide actionable recommendations.

### Current State (Post-Enhancement)
- **1,379 spine figures** freshly extracted with enhanced pipeline
- **88.5%** caption quality (vs 14% before)
- **86.5%** context coverage
- **7.8%** region tagging rate (needs improvement)
- **56,624 total points** in Qdrant collection

### Critical Finding
NeuroSynth has **most Deep-DX features implemented**, but with **integration gaps** that reduce effectiveness. The main issues are:
1. **Region detection relies on keywords only** (no visual/embedding-based tagging)
2. **Caption scoring uses basic keyword overlap** (not semantic similarity)
3. **Image type preferences are hardcoded** (not configurable via templates)
4. **No LLM-driven citation loop** (single-pass figure selection)

---

## Part 1: Feature Comparison Matrix

### 1.1 Extraction Layer ("The Eyes")

| Deep-DX Feature | NeuroSynth Status | Implementation Location | Quality |
|-----------------|-------------------|------------------------|---------|
| **Context-aware extraction** | ✅ Implemented | `SmartImageExtractor._parse_markdown_content()` | 86.5% coverage |
| **Shannon Entropy quality gating** | ✅ Implemented | `SmartImageExtractor._is_medically_relevant()` | Default 4.5 threshold |
| **Size/aspect filtering** | ✅ Implemented | `SmartImageExtractor._is_medically_relevant()` | 70px min, 10:1 max ratio |
| **Perceptual deduplication (pHash)** | ✅ Implemented | `SmartImageExtractor._compute_perceptual_hash()` | Hamming ≤5 threshold |
| **Consecutive page detection** | ✅ Implemented | `SmartImageExtractor.deduplicate_figures()` | 3+ pages = header/footer |
| **Hybrid caption parsing** | ✅ Implemented | `SmartImageExtractor._extract_caption_enhanced()` | Regex + proximity + OCR fallback |
| **OCR fallback extraction** | ✅ Implemented | `SmartImageExtractor._apply_ocr_extraction()` | Tesseract via OCRCaptionExtractor |
| **Figure number parsing** | ✅ Implemented | `ExtractedFigure` dataclass | Prefix, number, parsed_caption fields |
| **Vector graphics extraction** | ✅ Implemented | `VectorGraphicsExtractor` | Phase 4 enhancement |
| **3-tier fallback filtering** | ✅ Implemented | `ResilientImageFilter` | Enhanced→Basic→Permissive |

### 1.2 Intelligence Layer ("The Brain")

| Deep-DX Feature | NeuroSynth Status | Implementation Location | Quality |
|-----------------|-------------------|------------------------|---------|
| **BiomedCLIP embeddings** | ✅ Implemented | `BiomedCLIPSearcher.embed_image()` | 512-dim vectors, MPS-optimized |
| **Zero-shot modality classification** | ✅ Implemented | `ModalityClassifier.classify()` | 6 categories with CLIP prompts |
| **Anatomical region tagging** | ⚠️ Partial | `AnatomicalRegionDetector.detect_regions()` | Keyword-only (7.8% coverage) |
| **Context-boosted region scoring** | ✅ Implemented | `AnatomicalRegionDetector._apply_context_boosts()` | Caption weight=1.0, context=0.5 |
| **Neurosurgical keyword scoring** | ✅ Implemented | `NeurosurgicalKeywordScorer` | Centralized weights in config |
| **Caption confidence scoring** | ✅ Implemented | `CaptionConfidenceConfig` | Pattern/proximity/formatting weights |
| **Visual-semantic alignment** | ✅ Implemented | `BiomedIngestor.ingest_figures()` | BiomedCLIP joint embedding |

### 1.3 Retrieval Layer ("The Output")

| Deep-DX Feature | NeuroSynth Status | Implementation Location | Quality |
|-----------------|-------------------|------------------------|---------|
| **Multi-modal text→image search** | ✅ Implemented | `PrecisionSearchEngine._search_images_ai()` | BiomedCLIP text query→Qdrant |
| **Visual similarity search** | ✅ Implemented | `VisualSearcher.search_by_image()` | ColPali image→image |
| **Hybrid fusion (dense+sparse)** | ✅ Implemented | `PrecisionSearchEngine.retrieve_for_topic()` | 7-system stack |
| **Domain-aware image prioritization** | ⚠️ Hardcoded | `SynthesisEngine._get_preferred_image_types()` | Section→ImageType mapping |
| **Semantic caption scoring** | ❌ Missing | `SynthesisEngine._select_images_for_section()` | Uses keyword overlap only |
| **LLM-driven citation loop** | ❌ Missing | N/A | Single-pass selection |
| **Citation bonus scoring** | ✅ Implemented | `SynthesisEngine._select_images_for_section()` | +2.0 bonus if ID in content |
| **Duplicate detection in selection** | ✅ Implemented | `SynthesisEngine._images_similar()` | Source+page+embedding check |

---

## Part 2: Gap Analysis

### 2.1 Critical Gaps

#### Gap 1: Keyword-Only Region Detection (7.8% coverage)
**Current**: `AnatomicalRegionDetector` scans caption/context for keywords like "cervical", "lumbar"
**Problem**: Misses images with:
- Generic captions ("Image showing surgical field")
- No anatomical keywords in context
- Visual-only anatomical content

**Target**: 35%+ region coverage via:
- BiomedCLIP embedding clustering by region
- Visual similarity to region exemplar images
- Caption embedding semantic match to region descriptions

#### Gap 2: Basic Keyword Caption Scoring
**Current**: `_select_images_for_section()` line 669-672:
```python
section_words = set(section_name.lower().split())
caption_words = set(img.caption.lower().split())
overlap = len(section_words & caption_words)
caption_score = min(overlap / 3, 1.0)
```
**Problem**: "Surgical anatomy of the internal carotid artery" won't match "ICA exposure technique"
**Target**: Use BiomedCLIP text embeddings for semantic similarity

#### Gap 3: Hardcoded Image Type Preferences
**Current**: `_get_preferred_image_types()` has fixed section→type mappings
**Problem**: No customization per template or topic
**Target**: Move to template config with override capability

#### Gap 4: No LLM Citation Loop
**Current**: Single-pass figure selection before LLM call
**Problem**: LLM can't request specific figures it needs
**Target**: 2-pass system:
1. Initial retrieval → LLM drafts with `[FIGURE: description]` placeholders
2. Resolve placeholders → retrieve matching figures
3. Final pass with resolved figures

---

## Part 3: Critical Weaknesses Assessment

### 3.1 Hardcoded Heuristics Assessment
| Component | Status | Details |
|-----------|--------|---------|
| Image type preferences | ❌ Hardcoded | `_get_preferred_image_types()` in engine.py |
| Entropy threshold | ⚠️ Config | Passed to SmartImageExtractor but default 4.5 |
| Scoring weights | ✅ Configurable | All in `NeuroSynthEnhancedConfig` |
| Region keywords | ✅ Configurable | `anatomical_regions.py` taxonomy |

### 3.2 Keyword Overlap Limitations
**Location**: `src/synthesize/engine.py:666-672`
- Uses basic `set()` intersection
- No stemming, synonyms, or semantic matching
- Caption "MRI of cervical spine" won't match section "Cervical Imaging"

### 3.3 Context Injection to LLM
**Current state** (prompts.py):
```
Source material includes available figures with IDs (e.g., [FIGURE_ID: 1234])
```
**What's passed**: ID, image_type, caption (see engine.py:406-415)
**What's missing**: detected_regions, modality, ocr_caption, region_confidence, context

---

## Part 4: Prioritized Recommendations

### Priority 1: Enrich LLM Context with Full Metadata (Impact: High, Effort: Simple)

**Problem**: LLM only sees `{id, image_type, caption}` but Qdrant has rich metadata
**Solution**: Pass full metadata to synthesis prompts

**Files to modify**:
- `src/synthesize/engine.py:406-415` - Add detected_regions, modality, ocr_caption
- `src/neurosynth/synthesis/prompts.py` - Update FIGURE INTEGRATION section

**Code change**:
```python
# engine.py:406-415 - Add to fmt_figures
for img in retrieval_res.images:
    fmt_figures.append({
        "id": img.id,
        "image_type": img.image_type.value,
        "caption": img.caption,
        "preselected": False,
        # NEW: Rich metadata
        "modality": getattr(img, 'modality', 'unknown'),
        "detected_regions": getattr(img, 'detected_regions', []),
        "ocr_caption": getattr(img, 'ocr_caption', ''),
        "context": getattr(img, 'surrounding_text', '')[:200],
    })
```

**Expected improvement**: LLM makes better figure selections with anatomical context

---

### Priority 2: Semantic Caption Scoring (Impact: High, Effort: Moderate)

**Problem**: Keyword overlap misses semantic matches
**Solution**: Use BiomedCLIP text embeddings for caption→section similarity

**Files to modify**:
- `src/synthesize/engine.py:_select_images_for_section()`
- Add BiomedCLIPSearcher dependency to SynthesisEngine

**Code change**:
```python
# Replace keyword overlap with embedding similarity
def _score_caption_semantic(self, caption: str, section_name: str) -> float:
    """Semantic similarity between caption and section using BiomedCLIP."""
    if not caption or not self.vision_embedder:
        return 0.0
    caption_vec = self.vision_embedder.embed_text(caption)
    section_vec = self.vision_embedder.embed_text(section_name)
    if caption_vec.size == 0 or section_vec.size == 0:
        return 0.0
    return float(np.dot(caption_vec[0], section_vec[0]))
```

**Expected improvement**: +20-30% figure relevance in selected images

---

### Priority 3: Visual Region Tagging (Impact: High, Effort: Complex)

**Problem**: Region detection is keyword-only (7.8% coverage)
**Solution**: Use BiomedCLIP visual similarity to region exemplars

**Approach**:
1. Create exemplar image set per anatomical region (5-10 images each)
2. Embed exemplars with BiomedCLIP
3. For each new image, compute similarity to all region centroids
4. Tag regions above threshold (e.g., cosine > 0.7)

**Files to modify**:
- `src/neurosynth/enhancements/region_detector.py` - Add `VisualRegionDetector` class
- `src/ingest/smart_extractor.py:_apply_region_detection()` - Use visual + keyword hybrid

**Expected improvement**: Region tagging from 7.8% → 35%+

---

### Priority 4: Configurable Image Type Preferences (Impact: Medium, Effort: Simple)

**Problem**: Section→ImageType mapping is hardcoded in `_get_preferred_image_types()`
**Solution**: Move to template config

**Files to modify**:
- `src/neurosynth/models/template.py` - Add `preferred_image_types` field
- `src/synthesize/engine.py:_get_preferred_image_types()` - Read from template

**Template example**:
```yaml
sections:
  - name: "Surgical Technique"
    preferred_image_types: ["surgical", "diagram", "radiology"]
  - name: "Anatomy"
    preferred_image_types: ["diagram", "anatomical", "illustration"]
```

---

### Priority 5: LLM Citation Loop (Impact: High, Effort: Complex)

**Problem**: Single-pass figure selection can't adapt to LLM's actual needs
**Solution**: 2-pass synthesis with figure resolution

**Workflow**:
1. **Pass 1**: LLM drafts with `[FIGURE: description]` placeholders
2. **Resolution**: Use FigurePlaceholderResolver + semantic search to find matches
3. **Pass 2**: Re-run with resolved figure IDs for final output

**Files to modify**:
- `src/neurosynth/synthesis/figure_resolver.py` - Already has `[FIGURE: ID]` resolution
- `src/synthesize/engine.py` - Add 2-pass logic
- `src/neurosynth/synthesis/prompts.py` - Update instructions for placeholder usage

**Expected improvement**: LLM cites exactly the figures it needs, not pre-selected pool

---

## Part 5: Enhanced Workflow Diagram

### 5.1 Current Pipeline vs Target Pipeline

```
CURRENT PIPELINE (Single-pass):
PDF → Extract → Filter → Dedupe → Embed → Store → Retrieve → Score → Select → Synthesize
                                                    ↓
                                            (fixed pool to LLM)

TARGET PIPELINE (2-pass with citation loop):
PDF → Extract → [Quality Gate] → [Dedupe] → [Caption Enrich] →
                      ↓               ↓            ↓
                  Entropy         pHash      OCR + Regex
                      ↓               ↓            ↓
                  [Embed] → [Region Tag] → [Modality Classify] → [Vector Store]
                                ↓                   ↓
                        Visual + Keyword      Zero-shot CLIP
                                               ↓
                                    [Semantic Retrieval]
                                          ↓
                              [LLM Pass 1: Draft with placeholders]
                                          ↓
                              [Figure Resolution: Semantic match]
                                          ↓
                              [LLM Pass 2: Final with resolved figures]
                                          ↓
                                    Synthesis Output
```

---

## Part 6: Implementation Specifications (Top 3 Priorities)

### 6.1 Priority 1: Enrich LLM Context

**Estimated effort**: 2-4 hours
**Risk**: Low (additive change)

**Step 1**: Modify `src/synthesize/engine.py` around line 406-415

```python
# BEFORE
fmt_figures.append({
    "id": img.id,
    "image_type": img.image_type.value if hasattr(img.image_type, 'value') else str(img.image_type),
    "caption": img.caption,
    "preselected": False,
})

# AFTER
fmt_figures.append({
    "id": img.id,
    "image_type": img.image_type.value if hasattr(img.image_type, 'value') else str(img.image_type),
    "caption": img.caption,
    "preselected": False,
    # Rich metadata for LLM context
    "modality": getattr(img, 'modality', 'unknown'),
    "detected_regions": getattr(img, 'detected_regions', []),
    "ocr_caption": getattr(img, 'ocr_caption', ''),
    "context_snippet": (getattr(img, 'surrounding_text', '') or '')[:150],
})
```

**Step 2**: Update prompt template in `src/neurosynth/synthesis/prompts.py`

Add to FIGURE INTEGRATION section:
```
Each figure includes:
- id: Unique identifier (use in [FIGURE: id] tags)
- image_type: Category (surgical, radiology, diagram, etc.)
- caption: Original caption from source
- modality: Imaging modality (MRI, CT, intraoperative, etc.)
- detected_regions: Anatomical regions shown (e.g., ["cervical_spine", "C5-C6"])
- context_snippet: Surrounding text from source document

Prefer figures whose detected_regions match the section's anatomical focus.
```

---

### 6.2 Priority 2: Semantic Caption Scoring

**Estimated effort**: 4-6 hours
**Risk**: Medium (requires BiomedCLIP dependency in engine)

**Step 1**: Add BiomedCLIPSearcher to SynthesisEngine.__init__

```python
# src/synthesize/engine.py
from src.neurosynth.ai.embedder import BiomedCLIPSearcher

class SynthesisEngine:
    def __init__(self, ...):
        ...
        # Add vision embedder for semantic scoring
        self._vision_embedder: BiomedCLIPSearcher | None = None

    @property
    def vision_embedder(self) -> BiomedCLIPSearcher | None:
        if self._vision_embedder is None:
            try:
                self._vision_embedder = BiomedCLIPSearcher()
            except Exception:
                pass
        return self._vision_embedder
```

**Step 2**: Replace keyword scoring in `_select_images_for_section()`

```python
# BEFORE (line 666-672)
section_words = set(section_name.lower().split())
caption_words = set(img.caption.lower().split())
overlap = len(section_words & caption_words)
caption_score = min(overlap / 3, 1.0)

# AFTER
caption_score = self._score_caption_semantic(img.caption, section_name)

def _score_caption_semantic(self, caption: str, section_name: str) -> float:
    """Semantic similarity using BiomedCLIP text embeddings."""
    if not caption or not self.vision_embedder:
        # Fallback to keyword overlap
        section_words = set(section_name.lower().split())
        caption_words = set(caption.lower().split())
        overlap = len(section_words & caption_words)
        return min(overlap / 3, 1.0)

    try:
        caption_vec = self.vision_embedder.embed_text(caption)
        section_vec = self.vision_embedder.embed_text(section_name)
        if caption_vec.size == 0 or section_vec.size == 0:
            return 0.0
        # Cosine similarity (vectors are normalized)
        similarity = float(np.dot(caption_vec[0], section_vec[0]))
        # Scale to 0-1 range (cosine can be negative)
        return max(0.0, min(1.0, (similarity + 1) / 2))
    except Exception:
        return 0.0
```

---

### 6.3 Priority 3: Visual Region Tagging

**Estimated effort**: 8-12 hours
**Risk**: Medium-High (requires exemplar dataset curation)

**Step 1**: Create region exemplar dataset

```
assets/region_exemplars/
├── cervical_spine/
│   ├── exemplar_001.jpg
│   ├── exemplar_002.jpg
│   └── ...
├── lumbar_spine/
├── skull_base/
└── ...
```

**Step 2**: Add VisualRegionDetector class

```python
# src/neurosynth/enhancements/visual_region_detector.py
from dataclasses import dataclass
from pathlib import Path
import numpy as np
from src.neurosynth.ai.embedder import BiomedCLIPSearcher

@dataclass
class RegionCentroid:
    region_id: str
    centroid: np.ndarray
    exemplar_count: int

class VisualRegionDetector:
    """Detect anatomical regions using visual similarity to exemplars."""

    def __init__(self, exemplar_dir: Path, similarity_threshold: float = 0.7):
        self.embedder = BiomedCLIPSearcher()
        self.threshold = similarity_threshold
        self.centroids: dict[str, RegionCentroid] = {}
        self._load_exemplars(exemplar_dir)

    def _load_exemplars(self, exemplar_dir: Path):
        """Load and embed exemplar images, compute centroids."""
        for region_dir in exemplar_dir.iterdir():
            if not region_dir.is_dir():
                continue
            region_id = region_dir.name
            embeddings = []
            for img_path in region_dir.glob("*.jpg"):
                vec = self.embedder.embed_image([str(img_path)])
                if vec.size > 0:
                    embeddings.append(vec[0])
            if embeddings:
                centroid = np.mean(embeddings, axis=0)
                centroid = centroid / np.linalg.norm(centroid)  # Normalize
                self.centroids[region_id] = RegionCentroid(
                    region_id=region_id,
                    centroid=centroid,
                    exemplar_count=len(embeddings)
                )

    def detect_regions(self, image_path: str) -> list[tuple[str, float]]:
        """Detect regions in image by similarity to centroids."""
        vec = self.embedder.embed_image([image_path])
        if vec.size == 0:
            return []

        vec = vec[0] / np.linalg.norm(vec[0])
        matches = []
        for region_id, centroid in self.centroids.items():
            similarity = float(np.dot(vec, centroid.centroid))
            if similarity >= self.threshold:
                matches.append((region_id, similarity))

        return sorted(matches, key=lambda x: x[1], reverse=True)
```

**Step 3**: Integrate into SmartImageExtractor

```python
# src/ingest/smart_extractor.py:_apply_region_detection()
def _apply_region_detection(self, figures: list[ExtractedFigure]) -> list[ExtractedFigure]:
    """Apply hybrid region detection: keyword + visual."""
    # Existing keyword detection
    keyword_detector = AnatomicalRegionDetector()

    # NEW: Visual detection (if exemplars available)
    visual_detector = None
    exemplar_dir = Path("assets/region_exemplars")
    if exemplar_dir.exists():
        visual_detector = VisualRegionDetector(exemplar_dir)

    for fig in figures:
        # Keyword-based detection
        keyword_regions = keyword_detector.detect_regions(fig.caption, fig.context)

        # Visual-based detection
        visual_regions = []
        if visual_detector and fig.local_path.exists():
            visual_regions = visual_detector.detect_regions(str(fig.local_path))

        # Merge results (union with max confidence)
        all_regions = {}
        for region, conf in keyword_regions:
            all_regions[region] = max(all_regions.get(region, 0), conf)
        for region, conf in visual_regions:
            all_regions[region] = max(all_regions.get(region, 0), conf * 0.9)  # Slight discount

        fig.detected_regions = list(all_regions.keys())
        fig.region_confidence = max(all_regions.values()) if all_regions else 0.0

    return figures
```

---

## Part 7: Migration Strategy for Existing Data

### 7.1 Qdrant Collection (56,624 points)

**Option A: Full Re-extraction** (Recommended for quality)
1. Delete collection `neurosurgical_figures_hybrid`
2. Delete `assets/extracted_images/`
3. Re-run extraction on all 1,505 PDFs with enhanced pipeline
4. Estimated time: 4-6 hours

**Option B: Metadata Enrichment** (Faster, partial improvement)
1. Keep existing embeddings
2. Iterate through points, re-run region detection on stored images
3. Update payloads with new metadata
4. Estimated time: 1-2 hours

### 7.2 Critical Constraint

> ⚠️ **NEVER extract images from already-extracted images**
>
> All extraction MUST use original PDF files from:
> `/Users/ramihatoum/Desktop/NeuroLi/reference library`
>
> The `assets/extracted_images/` folder contains OUTPUT only.

---

## Part 8: Expected Improvements Summary

| Enhancement | Current | Target | Improvement |
|-------------|---------|--------|-------------|
| Region tagging coverage | 7.8% | 35%+ | +350% |
| Caption-section relevance | ~40% | 70%+ | +75% |
| Figure citation accuracy | ~60% | 85%+ | +40% |
| LLM figure utilization | ~50% | 80%+ | +60% |

---

## Appendix A: File Reference

| File | Purpose | Key Functions |
|------|---------|---------------|
| `src/ingest/smart_extractor.py` | Image extraction | `process_pdf()`, `_is_medically_relevant()` |
| `src/neurosynth/ai/ingestor.py` | Qdrant ingestion | `ingest_figures()`, `_process_batch()` |
| `src/neurosynth/ai/embedder.py` | BiomedCLIP embeddings | `embed_image()`, `embed_text()` |
| `src/neurosynth/ai/classifier.py` | Modality classification | `classify()`, `classify_batch()` |
| `src/neurosynth/enhancements/region_detector.py` | Region tagging | `detect_regions()` |
| `src/synthesize/engine.py` | Synthesis orchestration | `_select_images_for_section()` |
| `src/neurosynth/synthesis/prompts.py` | LLM prompts | Figure integration instructions |
| `src/neurosynth/synthesis/figure_resolver.py` | Placeholder resolution | `resolve_placeholders()` |
| `src/index/precision_search.py` | Image retrieval | `_search_images_ai()` |

---

## Appendix B: Qdrant Schema Reference

Current payload fields in `neurosurgical_figures_hybrid`:

```python
{
    "filename": str,           # Image filename
    "source_pdf": str,         # Source PDF name
    "caption": str,            # Extracted caption
    "context": str,            # Surrounding text
    "modality": str,           # Zero-shot classification result
    "path": str,               # Local image path
    "detected_regions": list,  # Anatomical regions (keyword-based)
    "region_confidence": float,# Detection confidence
    "ocr_caption": str,        # OCR-extracted caption
    "caption_source": str,     # "proximity" | "ocr" | "parsed"
    "figure_number": str,      # Parsed figure number
    "parsed_caption": str,     # Cleaned caption text
    "page_num": int,           # PDF page number
}
```

Vector: `{"biomed": [512-dim float array]}`
