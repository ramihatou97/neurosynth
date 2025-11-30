# NeuroSynth Image Handling: Comprehensive Assessment & Improvement Plan v3.1

> **Document Version:** 3.1
> **Generated:** 2025-11-30
> **Scope:** Full pipeline analysis with **Enhancement Module v3.1** integration
> **Source Files:** `/Users/ramihatoum/Downloads/neurosynth_enhancements_v3.1/`
> **Key v3.1 Change:** All weights centralized in `config.py` with validation

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [Current State Assessment](#part-1-current-state-assessment)
3. [Architecture Analysis](#part-2-architecture-analysis)
4. [Enhancement Module v3.1 Overview](#part-3-enhancement-module-v31-overview)
5. [Weight Configuration Reference](#part-4-weight-configuration-reference) ← **NEW in v3.1**
6. [Module Deep Dive](#part-5-module-deep-dive)
7. [Prioritized Improvement Plan](#part-6-prioritized-improvement-plan)
8. [Implementation Roadmap](#part-7-implementation-roadmap)
9. [Testing Strategy](#part-8-testing-strategy)
10. [Code Integration Guide](#part-9-code-integration-guide)
11. [v3.1 File Reference](#part-10-v31-file-reference)

---

## Executive Summary

This document provides a comprehensive analysis of NeuroSynth's image handling capabilities and presents a detailed integration plan for the new **Enhancement Module v3.1**, which includes:

### Core v3.1 Components

| Module | Purpose | Key v3.1 Innovation |
|--------|---------|---------------------|
| **ResilientImageFilter** | 3-tier fallback image filtering | PIL-optional, never loses images |
| **EnhancedCaptionDetector** | Multi-directional caption search | Confidence weights in config |
| **EnhancedVisualClusterAssociator** | Neurosurgical keyword scoring | Association weights in config |
| **ProceduralSequenceDetector** | Surgical step detection | Dedicated sequence module |
| **UnifiedExtractionPipeline** | 7-stage orchestrator | Full async support |
| **EnhancedLaTeXFigureGenerator** | Publication-quality output | Auto-pagination, validation |
| **VectorGraphicsExtractor** | Drawing command analysis | Flowchart/diagram classification |
| **NeuroSynthEnhancedConfig** | **ALL weights centralized** | Single source of truth |

### Key v3.1 Improvements Over v3.0

- **Weight Centralization:** ALL scoring weights now in `config.py` ONLY
- **Weight Validation:** Automatic validation ensures weights sum to 1.0
- **AssociationWeightConfig:** NEW dataclass for image-text association scoring
- **CaptionConfidenceConfig:** NEW dataclass for caption detection confidence
- **print_weights_summary():** Debug method to verify all weights
- **No Hardcoded Weights:** Other modules import weights from config

### v3.1 Critical Rule

> ⚠️ **NEVER hardcode weights in modules other than `config.py`**
>
> All weights MUST be defined in `NeuroSynthEnhancedConfig` and accessed via:
> - `config.keyword_weights.*`
> - `config.association_weights.*`
> - `config.caption_confidence.*`

---

## Part 1: Current State Assessment

### 1.1 Existing Strengths

| Component | Current Implementation | Strength Level |
|-----------|----------------------|----------------|
| **Image Extraction** | Hybrid approach (raw + snapshot) | ✅ Strong |
| **Medical Filtering** | Multi-rule heuristics | ⚠️ Adequate |
| **Caption Detection** | Pattern + proximity | ⚠️ Adequate |
| **Classification** | Pattern-based ImageType | ⚠️ Adequate |
| **Deduplication** | 8x8 perceptual hash | ⚠️ Adequate |
| **Visual Models** | Well-designed dataclasses | ✅ Strong |
| **Pipeline Integration** | Async/await architecture | ✅ Strong |
| **LaTeX Output** | Basic figure support | ⚠️ Limited |

### 1.2 Identified Issues & Gaps

#### Critical Issues

| Issue | Location | Impact | Enhancement Solution |
|-------|----------|--------|---------------------|
| **Image path type mismatch** | `section.py` | Figures fail to render | `UnifiedExtractionPipeline` path management |
| **Duplicate `_is_medical_image`** | `neurosynth_bridge.py` | Inconsistent filtering | `EnhancedImageFilter` unification |
| **FigurePlate property error** | `output.py:75` | Runtime AttributeError | Direct fix required |
| **Bbox fallback too coarse** | `image_extractor.py:475` | Wrong caption association | `CaptionDetector` spatial analysis |

#### Moderate Issues

| Issue | Enhancement Module Solution |
|-------|----------------------------|
| Caption multi-match ambiguity | `CaptionDetector._calculate_caption_confidence()` with bbox proximity |
| No secondary classification for UNKNOWN | `MedicalImageClassifier` with color/entropy analysis |
| Snapshot extraction bypasses filter | `EnhancedImageFilter.should_extract()` integration |
| Visual hash collision risk (64 bits) | Enhancement module uses MD5 + complexity scoring |
| No vector graphics support | `VectorGraphicsExtractor` for drawing commands |
| Missing embedding-based association | `VisualClusterAssociator` semantic scoring |

#### Minor Issues

| Issue | Enhancement Module Solution |
|-------|----------------------------|
| FLOWCHART type missing patterns | `VectorRegionType.FLOWCHART` classification |
| Context text truncation varies | Unified 300-500 char context in `UnifiedExtractionPipeline` |
| No cross-reference tracking | `cross_ref_index` in enhancement module |

---

## Part 2: Architecture Analysis

### 2.1 Current Visual Pipeline Flow

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                          CURRENT EXTRACTION PHASE                            │
├──────────────────────────────────────────────────────────────────────────────┤
│  PDF Document                                                                 │
│       │                                                                       │
│       ▼                                                                       │
│  ImageExtractor.extract_images() ──or── extract_images_hybrid()              │
│       │                                                                       │
│       ├── _extract_page_images() [raw extraction]                            │
│       │       ├── get_images(full=True)                                      │
│       │       ├── _get_image_bbox() [often fails → coarse fallback] ◀─ ISSUE │
│       │       ├── _find_caption() [pattern + proximity]                      │
│       │       ├── _classify_image_type() [pattern matching only]             │
│       │       ├── _is_medical_image() [basic heuristics]                    │
│       │       └── _compute_visual_hash() [8x8 average hash]                 │
│       │                                                                       │
│       └── _extract_page_snapshots() [rendered figures]                       │
│               └── ◀── NO FILTER APPLIED ─────────────────────────── ISSUE   │
│       │                                                                       │
│       ▼                                                                       │
│  List[VisualElement]                                                         │
└──────────────────────────────────────────────────────────────────────────────┘

### 2.2 Enhanced Pipeline Flow (With Enhancement Module)

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                    ENHANCED EXTRACTION PHASE (New)                           │
├──────────────────────────────────────────────────────────────────────────────┤
│  PDF Document                                                                 │
│       │                                                                       │
│       ▼                                                                       │
│  NeurosurgicalImageExtractor.extract_from_pdf()                              │
│       │                                                                       │
│       ├── Phase 1: Document Structure Analysis                               │
│       │       └── _analyze_document_structure() → TOC/heading detection      │
│       │                                                                       │
│       ├── Phase 2: Context Window Expansion                                  │
│       │       └── _calculate_scan_window() → ±2 pages around matches         │
│       │                                                                       │
│       ├── Phase 3: Enhanced Filtering                                        │
│       │       └── EnhancedImageFilter.should_extract()                       │
│       │               ├── MedicalImageClassifier.analyze_image()             │
│       │               │       ├── Color distribution analysis                │
│       │               │       ├── Entropy calculation                        │
│       │               │       ├── Edge density detection                     │
│       │               │       └── Surgical color signatures                  │
│       │               └── Context text boost                                 │
│       │                                                                       │
│       ├── Phase 4: Vector Graphics Detection (NEW)                           │
│       │       └── VectorGraphicsExtractor.analyze_page_for_vectors()         │
│       │               ├── Drawing command clustering                         │
│       │               ├── Complexity scoring                                 │
│       │               └── Region type classification                         │
│       │                                                                       │
│       ├── Phase 5: Caption Detection                                         │
│       │       └── CaptionDetector.detect_captions_on_page()                  │
│       │               ├── Multi-pattern matching (figure/table/plate/step)   │
│       │               ├── Subfigure extraction (a), (b), (c)                 │
│       │               ├── Cross-reference parsing                            │
│       │               └── Confidence scoring with bbox proximity             │
│       │                                                                       │
│       ├── Phase 6: Cluster Association                                       │
│       │       └── VisualClusterAssociator.associate_images_with_clusters()   │
│       │               ├── Text cluster extraction with semantic type         │
│       │               ├── Neurosurgical keyword scoring                      │
│       │               │       ├── anatomy keywords (0.3 weight)              │
│       │               │       ├── pathology keywords (0.3 weight)            │
│       │               │       ├── procedure keywords (0.45 weight)           │
│       │               │       └── imaging keywords (0.25 weight)             │
│       │               └── Spatial proximity calculation                      │
│       │                                                                       │
│       └── Phase 7: Chapter Embedding                                         │
│               └── _embed_images_in_chapters() → procedural sequencing        │
│                                                                               │
│       ▼                                                                       │
│  EnhancedExtractionResult                                                    │
│       ├── images: List[ExtractedImage]                                       │
│       ├── captions: List[DetectedCaption]                                    │
│       ├── associations: List[ImageClusterAssociation]                        │
│       ├── vector_regions: List[VectorRegion]                                 │
│       ├── figure_index: Dict[str, Any]                                       │
│       └── cross_references: Dict[str, List[str]]                             │
└──────────────────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────────────────┐
│                    ENHANCED OUTPUT PHASE (New)                               │
├──────────────────────────────────────────────────────────────────────────────┤
│  LaTeXFigureGenerator                                                        │
│       │                                                                       │
│       ├── generate_figure() → Standard figure environment                    │
│       │       └── Proper float placement [htbp], label sanitization          │
│       │                                                                       │
│       ├── generate_subfigures() → Multi-panel figures                        │
│       │       └── Subcaption package support, column layout                  │
│       │                                                                       │
│       ├── generate_procedural_sequence() → Step-by-step layouts              │
│       │       └── Auto-pagination for long procedures                        │
│       │                                                                       │
│       └── generate_comparison_figure() → Side-by-side comparisons            │
│                                                                               │
│  DocumentLaTeXExporter                                                       │
│       └── export_chapter() → Full chapter with inline figure refs            │
└──────────────────────────────────────────────────────────────────────────────┘
```

### 2.3 Integration Points

```
Reference Library                         Enhancement Module
─────────────────                         ─────────────────

NeuroSynthBridge.process_document()
       │
       ├── UnifiedExtractionPipeline
       │   │
       │   ├── Global document_index
       │   ├── Global image_index (MD5 dedup)
       │   ├── Global figure_index
       │   └── cross_ref_index
       │
       ├── MedicalImageClassifier         NeuroSynth Core
       │   │                              ───────────────
       │   └── Unified filter for both
       │       ├── Reference Library extraction
       │       └── Core pipeline extraction
       │
       └── NeuroSynthConfig
           └── Unified settings for all components
```

---

## Part 3: Enhancement Module v3.0 Overview

### 3.1 v3.1 Architecture Summary

The v3.1 enhancement module introduces **centralized weight management** with automatic validation, building on v3.0's resilient architecture:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    v3.1 ENHANCEMENT MODULE ARCHITECTURE                      │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  NeuroSynthEnhancedConfig (Master Configuration)                            │
│       │                                                                      │
│       ├── NeurosurgicalKeywords (5 categories, 100+ terms each)             │
│       ├── KeywordWeightConfig (procedure: 0.30, anatomy: 0.25, ...)         │
│       │       └── ✓ auto-validates sum = 1.0                                │
│       ├── AssociationWeightConfig (spatial: 0.50, keyword: 0.30, ...)  NEW! │
│       │       └── ✓ auto-validates sum = 1.0                                │
│       ├── CaptionConfidenceConfig (pattern: 0.40, proximity: 0.30, ...) NEW!│
│       │       └── ✓ auto-validates sum = 1.0                                │
│       ├── ImageFilterConfig (thresholds, color ranges)                      │
│       ├── CaptionDetectionConfig (patterns, search radii)                   │
│       ├── VectorGraphicsConfig (DPI, detection thresholds)                  │
│       ├── LaTeXConfig (placement, sizes, subfigure limits)                  │
│       ├── PerformanceConfig (thread pool, batch size, timeouts)             │
│       └── print_weights_summary() method for debugging                  NEW!│
│                                                                              │
│  UnifiedExtractionPipeline (7-Stage Orchestrator)                           │
│       │                                                                      │
│       ├── Stage 1: Batch page processing with caching                       │
│       ├── Stage 2: Resilient image filtering (3-tier fallback)              │
│       ├── Stage 3: Enhanced caption detection (uses caption_confidence)     │
│       ├── Stage 4: Visual-text association (uses association_weights)       │
│       ├── Stage 5: Procedural sequence detection                            │
│       ├── Stage 6: Vector graphics extraction                               │
│       └── Stage 7: LaTeX generation                                         │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 3.2 Key v3.1 Innovations

| Feature | v3.0 | v3.1 |
|---------|------|------|
| **Weight Location** | In config, some hardcoded | **ALL in `config.py` ONLY** |
| **Weight Validation** | Manual | Auto-validates sum = 1.0 |
| **Association Weights** | Hardcoded | **NEW** `AssociationWeightConfig` |
| **Caption Weights** | Hardcoded | **NEW** `CaptionConfidenceConfig` |
| **Debug Tools** | None | `print_weights_summary()` |
| **Documentation** | In-code comments | **NEW** `WEIGHTS_REFERENCE.md` |
| **Scoring Formulas** | Undocumented | Fully documented with examples |

### 3.3 ResilientImageFilter (NEW in v3.0)

**Purpose:** Three-tier fallback chain ensuring images are never lost due to analysis failures.

```
FilterFallbackLevel Enum:
├── ENHANCED   → Full color/entropy/edge analysis (requires PIL)
├── BASIC      → Simple heuristics (PyMuPDF only)
├── PERMISSIVE → Size-only filtering (always works)
└── FAILED     → All methods failed

Fallback Chain:
┌─────────────────────────────────────────────────────────────────┐
│  EnhancedMedicalClassifier                                      │
│  ├── ColorAnalyzer (PIL → PyMuPDF → bytes fallback)            │
│  ├── EntropyCalculator (Shannon entropy)                        │
│  ├── SurgicalColorDetector (blood, tissue, drape, instruments) │
│  └── EdgeDensityAnalyzer (diagram vs photo)                     │
│                                                                  │
│  If PIL unavailable or analysis fails:                          │
│       ↓                                                          │
│  BasicImageFilter                                                │
│  ├── Size thresholds (min 50x50, max 4000x4000)                 │
│  ├── Aspect ratio limits (0.125 to 8.0)                         │
│  └── Basic color count estimation                               │
│                                                                  │
│  If basic filter fails:                                          │
│       ↓                                                          │
│  PermissiveFilter                                                │
│  └── Size-only: accept if > 100x100 pixels                      │
└─────────────────────────────────────────────────────────────────┘
```

### 3.4 MedicalImageClassifier (Enhanced in v3.0)

**Purpose:** Advanced image analysis using color, entropy, and edge detection.

**Key Features:**
- **Surgical Color Detection:** Identifies blood (red), tissue (pink), drape (green), instruments (steel gray)
- **Radiological Signatures:** Grayscale ratio, dynamic range, contrast
- **Entropy Analysis:** Distinguishes detailed anatomy (high) from icons (low)
- **Edge Density:** Identifies diagrams vs photographs

```python
# Signature color ranges (from config.py)
SURGICAL_FIELD_COLORS = {
    'blood': ((150, 0, 0), (255, 100, 100)),
    'tissue': ((200, 150, 150), (255, 220, 200)),
    'drape': ((0, 80, 0), (100, 180, 100)),
    'instrument': ((180, 180, 180), (220, 220, 220)),
}
```

**Classification Logic:**
```
Score Components:
├── Grayscale + High Entropy → +0.3 (radiological)
├── Dynamic Range > 150 → +0.2
├── Surgical Color Score > 0.3 → +0.4 (surgical_photo)
├── Low Entropy + High Edge Density → +0.3 (diagram)
├── Area > 100,000px → +0.1
└── Area > 250,000px → +0.1

Rejection Criteria:
├── Entropy < 3.0 AND Area < 10,000 AND Colors < 32 → likely_icon
├── Aspect Ratio > 8 OR < 0.125 → extreme_aspect_ratio
└── Dimensions < 50px → too_small_dimensions
```

### 3.5 EnhancedCaptionDetector (v3.0)

**Purpose:** Multi-directional caption search with confidence scoring and cross-reference tracking.

**Key v3.0 Features:**
- **Multi-directional search:** Below, above, left, right (not just below)
- **Direction priority:** Based on image position on page
- **Multi-line caption reconstruction**
- **Cross-reference extraction**
- **Formatting detection:** Italic, bold, font size

**Search Region Strategy:**
```
Image Position → Search Priority Order
─────────────────────────────────────────
Top of page    → BELOW, RIGHT, ABOVE
Middle of page → BELOW, ABOVE, RIGHT
Bottom of page → ABOVE, BELOW, RIGHT

SearchRegion Dataclass:
├── rect: fitz.Rect (search area)
├── position: CaptionPosition enum
└── priority: int (lower = higher priority)
```

**Patterns Supported:**
```python
FIGURE_PATTERNS = [
    r'fig(?:ure)?\.?\s*(\d+[\.\-]?\d*[a-z]?)',  # Figure 3.2, Fig. 3-2
    r'\(([A-Za-z]|\d+)\)',                        # (A), (a), (1)
    r'step\s*(\d+)',                              # Step 1
    r'panel\s*([A-Za-z])',                        # Panel A
]

TABLE_PATTERNS = [r'table\.?\s*(\d+[\.\-]?\d*)']

XREF_PATTERNS = [
    r'(?:see|cf\.?)\s+(?:fig(?:ure)?\.?\s*)?(\d+[\.\-]?\d*)',
    r'(?:as shown in)\s+(?:fig(?:ure)?\.?\s*)?(\d+[\.\-]?\d*)',
]
```

**Confidence Calculation (v3.0 Enhanced):**
```
Base: 0.5 (pattern match)
├── Standard figure ID format → +pattern_weight (configurable)
├── Italic formatting → +0.5 × formatting_weight
├── Bold formatting → +0.25 × formatting_weight
├── Distance < 0.5 × image_height → +proximity_weight
├── Distance < image_height → +0.5 × proximity_weight
├── Caption length > 50 chars → +length_weight
├── Caption length > 20 chars → +0.5 × length_weight
└── Multiple candidates → ×0.9 (competition penalty)
```

**DetectedCaption Dataclass:**
```python
@dataclass
class DetectedCaption:
    text: str
    figure_id: Optional[str]
    subfigure_ids: List[str]      # ['a', 'b', 'c']
    caption_type: str             # figure, table, plate, step, panel
    page_number: int
    bbox: Tuple[float, float, float, float]
    position: CaptionPosition     # BELOW, ABOVE, LEFT, RIGHT, UNKNOWN
    confidence: float
    cross_references: List[str]   # Referenced figure IDs
    is_italic: bool
    is_bold: bool
    font_size: float
```

### 3.6 EnhancedVisualClusterAssociator (v3.0)

**Purpose:** Semantic binding between images and text clusters using neurosurgical domain knowledge.

**v3.0 Architecture:**
```
EnhancedVisualClusterAssociator
├── SpatialProximityCalculator (actual bbox distance)
├── NeurosurgicalKeywordScorer (weighted 5-category)
├── ContextAnalyzer (figure refs, demonstrative patterns)
└── ClusterBuilder (grouping related images/text)
```

**Keyword Categories (100+ terms per category):**
```python
# From config.py - NeurosurgicalKeywords dataclass
ANATOMY_KEYWORDS = [
    'cortex', 'ventricle', 'cerebellum', 'brainstem', 'sulcus', 'gyrus',
    'cranial', 'nerve', 'artery', 'vein', 'carotid', 'vertebral',
    'thalamus', 'hypothalamus', 'hippocampus', 'amygdala', 'basal ganglia',
    'corpus callosum', 'dura', 'arachnoid', 'pia mater', ...
]  # weight: 0.25

PATHOLOGY_KEYWORDS = [
    'tumor', 'glioma', 'meningioma', 'hematoma', 'aneurysm', 'malformation',
    'lesion', 'cyst', 'edema', 'herniation', 'hemorrhage', 'infarct',
    'abscess', 'metastasis', 'schwannoma', 'pituitary adenoma', ...
]  # weight: 0.25

PROCEDURE_KEYWORDS = [
    'craniotomy', 'resection', 'dissection', 'retraction', 'coagulation',
    'incision', 'exposure', 'clip', 'suture', 'hemostasis', 'decompression',
    'fenestration', 'microsurgical', 'endoscopic', 'stereotactic', ...
]  # weight: 0.30 (highest - most relevant for surgical content)

IMAGING_KEYWORDS = [
    'MRI', 'CT', 'angiography', 'T1', 'T2', 'FLAIR', 'contrast', 'axial',
    'sagittal', 'coronal', 'intraoperative', 'fluoroscopy', 'ultrasound', ...
]  # weight: 0.15

INSTRUMENTS_KEYWORDS = [
    'forceps', 'retractor', 'drill', 'microscope', 'endoscope', 'bipolar',
    'monopolar', 'suction', 'irrigator', 'clip applier', 'scissors', ...
]  # weight: 0.05
```

**v3.0 Association Scoring Formula:**
```
Total = (spatial_proximity × 0.5) + (neuro_relevance × 0.3) + (context × 0.2) + caption_boost

Spatial Proximity Score:
├── Calculate actual bbox distance (not just page overlap)
├── Normalize by page dimensions
└── Score = 1.0 - (distance / max_distance)

Neurosurgical Relevance Score:
├── For each keyword category:
│   └── category_score = (matches / total_keywords) × category_weight
├── Sum all category scores
└── Normalize to 0.0-1.0

Context Score:
├── Figure reference detection ("Figure X shows...")
├── Demonstrative patterns ("as shown", "illustrated")
└── Proximity to caption text

Caption Boost:
└── +0.2 if image has associated caption mentioning cluster keywords
```

**AssociationScore Dataclass:**
```python
@dataclass
class AssociationScore:
    spatial_score: float      # 0.0-1.0
    keyword_score: float      # 0.0-1.0
    context_score: float      # 0.0-1.0
    caption_boost: float      # 0.0-0.2
    total_score: float        # Weighted combination
    matched_keywords: List[str]
    category_breakdown: Dict[str, float]
```

### 3.7 ProceduralSequenceDetector (NEW in v3.0)

**Purpose:** Detect and organize procedural step sequences from images and captions.

**Sequence Types:**
```python
class SequenceType(Enum):
    NUMBERED_STEPS = "numbered_steps"      # Step 1, Step 2, ...
    SUBFIGURES = "subfigures"              # (a), (b), (c), ...
    LETTERED_PANELS = "lettered_panels"    # Panel A, Panel B, ...
    STAGED_PROCEDURE = "staged_procedure"  # Stage I, Stage II, ...
    IMPLICIT = "implicit"                  # Detected by context, no explicit numbering
```

**Detection Components:**
```
ProceduralSequenceDetector
├── StepNumberExtractor
│   ├── Pattern: r'step\s*(\d+)'
│   ├── Pattern: r'stage\s*(\d+)'
│   └── Pattern: r'^(\d+)\.\s+'
│
├── ProcedureKeywordDetector
│   ├── Sequence indicators: "first", "then", "next", "finally"
│   ├── Procedure verbs: "incise", "retract", "expose", "close"
│   └── Temporal markers: "before", "after", "during"
│
└── SequenceValidator
    ├── Minimum 2 elements
    ├── Consistent numbering
    └── Logical ordering
```

**SequenceElement Dataclass:**
```python
@dataclass
class SequenceElement:
    image_id: str
    step_number: Optional[int]
    caption: str
    bbox: Tuple[float, float, float, float]
    page_number: int
    sequence_type: SequenceType
    confidence: float
```

**Export Formats:**
```python
SequenceExporter.export_to_markdown(sequence)  # Numbered list
SequenceExporter.export_to_json(sequence)      # Structured data
SequenceExporter.export_to_latex(sequence)     # Subfigure environment
```

### 3.8 VectorGraphicsExtractor

**Purpose:** Extract and classify vector diagrams from PDF drawing commands.

**Region Types:**
```python
class VectorRegionType(Enum):
    FLOWCHART = "flowchart"
    ANATOMICAL_DIAGRAM = "anatomical_diagram"
    TIMELINE = "timeline"
    ALGORITHM = "algorithm"
    ANATOMICAL_CROSS_SECTION = "anatomical_cross_section"
    GENERIC_DIAGRAM = "generic_diagram"
```

**Classification Heuristics:**
```
Drawing Command Analysis:
├── "re" (rectangle) commands → possible_flowchart
├── "l" (line) with arrow patterns → directional_flow
├── "c" (curve) commands → possible_anatomical
└── "s" (stroke) with text → labeled_diagram

Region Classification:
├── High rect/text ratio → FLOWCHART or ALGORITHM
├── High curve density → ANATOMICAL_DIAGRAM
├── Linear arrangement → TIMELINE
└── Complex path commands → ANATOMICAL_CROSS_SECTION
```

### 3.9 UnifiedExtractionPipeline (v3.0)

**Purpose:** 7-stage orchestrator for complete image extraction workflow.

**v3.0 Pipeline Stages:**
```
UnifiedExtractionPipeline.extract_from_pdf()
│
├── Stage 1: Batch Page Processing
│   ├── Parallel page iteration
│   ├── Page-level caching
│   └── Memory-efficient streaming
│
├── Stage 2: Resilient Image Filtering
│   ├── ResilientImageFilter (3-tier fallback)
│   └── FilterResult with fallback_level tracking
│
├── Stage 3: Enhanced Caption Detection
│   ├── EnhancedCaptionDetector
│   ├── Multi-directional search
│   └── Cross-reference extraction
│
├── Stage 4: Visual-Text Association
│   ├── EnhancedVisualClusterAssociator
│   ├── Neurosurgical keyword scoring
│   └── Spatial proximity calculation
│
├── Stage 5: Procedural Sequence Detection
│   ├── ProceduralSequenceDetector
│   ├── Step number extraction
│   └── Sequence validation
│
├── Stage 6: Vector Graphics Extraction
│   ├── VectorGraphicsExtractor
│   ├── Drawing command analysis
│   └── Region classification
│
└── Stage 7: LaTeX Generation
    ├── EnhancedLaTeXFigureGenerator
    ├── Layout selection (single/subfigure/procedural/comparison)
    └── LaTeXValidator validation
```

**ExtractionResult Dataclass:**
```python
@dataclass
class ExtractionResult:
    images: List[ExtractedImage]
    captions: List[DetectedCaption]
    associations: List[Association]
    sequences: List[ProceduralSequence]
    vector_regions: List[VectorRegion]
    latex_figures: List[GeneratedFigure]

    # Statistics
    total_pages: int
    images_extracted: int
    images_filtered: int
    captions_detected: int
    sequences_found: int

    # Timing
    extraction_time_ms: float
    filtering_time_ms: float
    association_time_ms: float
```

**Convenience Functions:**
```python
# Quick extraction with defaults
result = extract_images_from_pdf(pdf_path)

# Async extraction
result = await quick_extract(pdf_path, config)

# Full pipeline with custom config
pipeline = UnifiedExtractionPipeline(config)
result = pipeline.extract_from_pdf(pdf_path)
```

### 3.10 EnhancedLaTeXFigureGenerator (v3.0)

**Purpose:** Publication-quality LaTeX figure generation with validation.

**v3.0 Features:**
- **FigureLayout Enum:** SINGLE, SUBFIGURES, PROCEDURAL, COMPARISON, GRID
- **Auto-pagination:** Long sequences split across pages with "(continued)"
- **LaTeXValidator:** Validates generated code before output
- **Label sanitization:** `sanitize_label()` for safe LaTeX labels

**Builder Classes:**
```
EnhancedLaTeXFigureGenerator
├── SingleFigureBuilder
├── SubfigureBuilder
├── ProceduralSequenceBuilder (with auto-pagination)
└── ComparisonFigureBuilder
```

**FigureSpec Dataclass:**
```python
@dataclass
class FigureSpec:
    images: List[FigureImage]
    main_caption: str
    main_label: str
    layout: FigureLayout
    columns: int = 2
    placement: str = "htbp"
    figure_number: Optional[str] = None
    chapter: Optional[str] = None
```

**GeneratedFigure Dataclass:**
```python
@dataclass
class GeneratedFigure:
    latex_code: str
    spec: FigureSpec
    is_valid: bool
    validation_errors: List[str]
    page_breaks: int  # For multi-page sequences
```

**Output Types:**

#### Standard Figure
```latex
\begin{figure}[htbp]
    \centering
    \includegraphics[width=0.8\textwidth]{figures/fig_01.png}
    \caption{Intraoperative view showing cortical exposure}
    \label{fig:cortical-exposure}
\end{figure}
```

#### Subfigure Layout
```latex
\begin{figure}[htbp]
    \centering
    \begin{subfigure}[b]{0.45\textwidth}
        \includegraphics[width=\textwidth]{figures/fig_01a.png}
        \caption{Pre-operative MRI}
        \label{fig:pre-op-mri}
    \end{subfigure}
    \hfill
    \begin{subfigure}[b]{0.45\textwidth}
        \includegraphics[width=\textwidth]{figures/fig_01b.png}
        \caption{Post-operative CT}
        \label{fig:post-op-ct}
    \end{subfigure}
    \caption{Imaging comparison}
    \label{fig:imaging-comparison}
\end{figure}
```

#### Procedural Sequence (Auto-Paginated)
```latex
% Page 1
\begin{figure}[p]
    \centering
    \begin{subfigure}[b]{0.47\textwidth}
        \includegraphics[width=\textwidth]{figures/step_1.png}
        \caption{Step 1: Initial incision}
    \end{subfigure}
    \hfill
    \begin{subfigure}[b]{0.47\textwidth}
        \includegraphics[width=\textwidth]{figures/step_2.png}
        \caption{Step 2: Craniotomy}
    \end{subfigure}
    % ... more steps ...
    \caption{Surgical procedure: Pterional craniotomy}
    \label{fig:pterional-craniotomy}
\end{figure}

\clearpage

% Page 2
\begin{figure}[p]
    \centering
    % ... continued steps ...
    \caption{Surgical procedure: Pterional craniotomy (continued)}
\end{figure}
```

#### Comparison Figure
```latex
\begin{figure}[htbp]
    \centering
    \begin{subfigure}[b]{0.48\textwidth}
        \centering
        \includegraphics[width=\textwidth]{figures/pre_op.png}
        \caption{Pre-operative}
        \label{fig:comparison_a}
    \end{subfigure}
    \hfill
    \begin{subfigure}[b]{0.48\textwidth}
        \centering
        \includegraphics[width=\textwidth]{figures/post_op.png}
        \caption{Post-operative}
        \label{fig:comparison_b}
    \end{subfigure}
    \caption{Pre- and post-operative comparison}
    \label{fig:comparison}
\end{figure}
```

**Convenience Methods:**
```python
generator = EnhancedLaTeXFigureGenerator(config)

# Single figure
result = generator.generate_single(image_path, caption, label, width=0.8)

# Subfigures
result = generator.generate_subfigures(images, main_caption, main_label, columns=2)

# Procedural sequence
result = generator.generate_procedural_sequence(steps, procedure_title, label)

# Comparison
result = generator.generate_comparison(image_a, image_b, main_caption, label)

# Required packages
packages = generator.get_required_packages()
# Returns: [r"\usepackage{graphicx}", r"\usepackage{subcaption}", r"\usepackage{float}"]
```

---

## Part 4: Weight Configuration Reference (NEW in v3.1)

> ⚠️ **CRITICAL RULE:** All weights are defined in `config.py` ONLY.
> Never hardcode weights in other modules.

### 4.1 Keyword Category Weights (`KeywordWeightConfig`)

**Purpose:** Score text blocks by neurosurgical relevance.

**Weights MUST sum to 1.0 (±0.05 tolerance):**

| Category | Weight | Rationale |
|----------|--------|-----------|
| `procedure` | **0.30** | Highest — surgical actions are most discriminative |
| `anatomy` | 0.25 | Critical anatomical structure identification |
| `pathology` | 0.25 | Disease/condition context |
| `imaging` | 0.15 | Useful but secondary |
| `instruments` | 0.05 | Lowest — present in most surgical images |
| **TOTAL** | **1.00** | ✓ |

**Context Multipliers:**
```python
caption_context_boost: float = 1.5    # Keywords in captions worth 50% more
heading_context_boost: float = 1.3    # Keywords in headings worth 30% more
body_context_boost: float = 1.0       # Standard body text (no boost)
figure_id_boost: float = 1.2          # Keywords in figure IDs
```

**Usage:** `visual_cluster_associator.py` → `NeurosurgicalKeywordScorer`

### 4.2 Association Weights (`AssociationWeightConfig`)

**Purpose:** Score image-text associations.

**Weights MUST sum to 1.0:**

| Component | Weight | Description |
|-----------|--------|-------------|
| `spatial_weight` | **0.50** | Physical proximity to image |
| `keyword_weight` | 0.30 | Neurosurgical keyword relevance |
| `context_weight` | 0.20 | References, demonstratives |
| **TOTAL** | **1.00** | ✓ |

**Boost Values (added after weighted sum):**
```python
caption_boost: float = 0.15     # If text is a caption
direct_ref_boost: float = 0.20  # If text directly references figure
```

**Association Formula:**
```
total = (spatial × 0.50) + (keyword × 0.30) + (context × 0.20) + boosts
```

**Usage:** `visual_cluster_associator.py` → `EnhancedVisualClusterAssociator`

### 4.3 Caption Confidence Weights (`CaptionConfidenceConfig`)

**Purpose:** Score caption detection confidence.

**Weights MUST sum to 1.0:**

| Component | Weight | Description |
|-----------|--------|-------------|
| `pattern_weight` | **0.40** | Pattern match quality (Fig X format) |
| `proximity_weight` | 0.30 | Distance from image |
| `formatting_weight` | 0.20 | Italic/bold formatting |
| `length_weight` | 0.10 | Caption text length |
| **TOTAL** | **1.00** | ✓ |

**Scoring Bonuses:**
```python
standard_figure_id_bonus: float = 0.10    # "Figure X" format
italic_bonus: float = 0.10
bold_bonus: float = 0.05
close_proximity_bonus: float = 0.20       # Within 50px
adequate_length_bonus: float = 0.10       # >30 chars
```

**Usage:** `enhanced_caption_detector.py` → `EnhancedCaptionDetector._calculate_confidence()`

### 4.4 Weight Validation

**Quick Validation Command:**
```python
from config import NeuroSynthEnhancedConfig

config = NeuroSynthEnhancedConfig()
config.print_weights_summary()
```

**Expected Output:**
```
============================================================
NEUROSYNTH WEIGHT CONFIGURATION SUMMARY
============================================================

[Keyword Category Weights] (must sum to 1.0)
  anatomy:     0.25
  pathology:   0.25
  procedure:   0.30  ← highest
  imaging:     0.15
  instruments: 0.05  ← lowest
  TOTAL:       1.00

[Association Weights] (must sum to 1.0)
  spatial:  0.50
  keyword:  0.30
  context:  0.20
  TOTAL:    1.00

[Caption Confidence Weights] (must sum to 1.0)
  pattern:    0.40
  proximity:  0.30
  formatting: 0.20
  length:     0.10
  TOTAL:      1.00
============================================================
```

### 4.5 Example: Full Scoring Trace

**Input:** Image with nearby caption text

```
Caption: "Figure 3. Pterional craniotomy approach showing the
sylvian fissure and MCA bifurcation after dural opening."
```

#### Keyword Scoring

| Keyword | Category | Weight |
|---------|----------|--------|
| craniotomy | procedure | 0.30 |
| approach | procedure | 0.30 |
| sylvian fissure | anatomy | 0.25 |
| MCA | anatomy | 0.25 |
| dural | anatomy | 0.25 |

**Category scores (with diminishing returns):**
- procedure: 2 keywords → 0.30 × (1 - 0.5²) = 0.30 × 0.75 = 0.225
- anatomy: 3 keywords → 0.25 × (1 - 0.5³) = 0.25 × 0.875 = 0.219

**Raw score:** 0.225 + 0.219 = 0.444

**Context multiplier (caption):** 0.444 × 1.5 = **0.666**

#### Association Scoring

| Component | Score | Weight | Contribution |
|-----------|-------|--------|--------------|
| Spatial | 0.90 (very close) | 0.50 | 0.450 |
| Keyword | 0.666 | 0.30 | 0.200 |
| Context | 0.70 (has "Fig 3") | 0.20 | 0.140 |
| Caption boost | | | 0.150 |
| **TOTAL** | | | **0.940** |

---

## Part 5: Module Deep Dive

### 5.1 ImageCategory Enum (v3.1 Classification Taxonomy)

```python
class ImageCategory(Enum):
    ANATOMICAL_DIAGRAM = "anatomical_diagram"
    INTRAOPERATIVE = "intraoperative"
    RADIOLOGICAL = "radiological"
    PROCEDURAL_STEP = "procedural_step"
    THREE_D_RECONSTRUCTION = "3d_reconstruction"
    FLOWCHART = "flowchart"
    INSTRUMENT = "instrument"
    CADAVERIC = "cadaveric"
    HISTOLOGICAL = "histological"
    COMPARISON = "comparison"
    UNKNOWN = "unknown"
```

### 5.2 Configuration Hierarchy (config.py v3.1)

```python
@dataclass
class NeuroSynthEnhancedConfig:
    # Sub-configurations
    keywords: NeurosurgicalKeywords
    keyword_weights: KeywordWeightConfig           # Category weights
    association_weights: AssociationWeightConfig   # NEW in v3.1
    caption_confidence: CaptionConfidenceConfig    # NEW in v3.1
    image_filter: ImageFilterConfig
    caption_detection: CaptionDetectionConfig
    vector_graphics: VectorGraphicsConfig
    latex: LaTeXConfig
    performance: PerformanceConfig

    # Feature flags
    enable_enhanced_filtering: bool = True
    enable_caption_detection: bool = True
    enable_procedural_detection: bool = True
    enable_vector_extraction: bool = True
    enable_latex_validation: bool = False  # Requires pdflatex

    # Paths
    output_base_dir: str = "./neurosynth_output"
    images_subdir: str = "images"
    metadata_subdir: str = "metadata"
    latex_subdir: str = "latex"

    def __post_init__(self):
        # Create directories and validate all weights
        self._create_directories()
        self._validate()

    def print_weights_summary(self):
        """Print all weights for debugging."""
        ...
```

### 5.3 CrossReferenceTracker (v3.1)

```python
class CrossReferenceTracker:
    """Track cross-references between figures across a document."""

    references: Dict[str, List[str]]      # source_fig → [target_figs]
    figure_locations: Dict[str, Tuple]    # fig_id → (page, bbox)

    def add_caption(self, caption: DetectedCaption): ...
    def get_references_from(self, figure_id: str) -> List[str]: ...
    def get_references_to(self, figure_id: str) -> List[str]: ...
    def get_figure_location(self, figure_id: str) -> Optional[Tuple]: ...
    def build_reference_graph(self) -> Dict[str, Dict[str, List[str]]]: ...
```

---

## Part 6: Prioritized Improvement Plan

### Priority 1: Critical Fixes (Week 1)

| # | Issue | Solution | Files | Effort |
|---|-------|----------|-------|--------|
| 1.1 | Image path type mismatch | Add `str(image_path)` wrapper | `synthesis/section.py:317` | 1h |
| 1.2 | Duplicate filter functions | Replace bridge filter with import | `neurosynth_bridge.py` | 2h |
| 1.3 | FigurePlate property error | Change `.elements` to `.figures` | `models/output.py:75` | 30m |
| 1.4 | Snapshot bypass filter | Add filter call to snapshot extraction | `image_extractor.py:620+` | 2h |

### Priority 2: Core Enhancements (Weeks 2-3)

| # | Enhancement | Components | Files | Effort |
|---|-------------|------------|-------|--------|
| 2.1 | Replace basic filter with MedicalImageClassifier | Color/entropy analysis | `image_extractor.py` | 4h |
| 2.2 | Upgrade caption detection | Multi-pattern with confidence | `image_extractor.py` | 4h |
| 2.3 | Add cross-reference tracking | XREF pattern parsing | `image_extractor.py`, `models/visual.py` | 3h |
| 2.4 | Integrate vector graphics extraction | VectorGraphicsExtractor | New module + `image_extractor.py` | 8h |

### Priority 3: Association Improvements (Week 4)

| # | Enhancement | Components | Files | Effort |
|---|-------------|------------|-------|--------|
| 3.1 | Add neurosurgical keyword scoring | VisualClusterAssociator keywords | `dedup/clustering.py` | 4h |
| 3.2 | Integrate embedding-based similarity | ColPali embedding comparison | `dedup/clustering.py` | 6h |
| 3.3 | Improve spatial proximity calculation | Actual bbox distance | `dedup/clustering.py` | 2h |

### Priority 4: Output Enhancements (Week 5)

| # | Enhancement | Components | Files | Effort |
|---|-------------|------------|-------|--------|
| 4.1 | Add subfigure support | LaTeXFigureGenerator.generate_subfigures() | `latex/generator.py` | 4h |
| 4.2 | Add procedural sequences | Auto-pagination for procedures | `latex/generator.py` | 4h |
| 4.3 | Add comparison figures | Side-by-side pre/post imaging | `latex/generator.py` | 2h |

---

## Part 7: Implementation Roadmap

### Phase 1: Critical Fixes (3 days)

```
Day 1: Path and Property Fixes
├── Fix image_path type in section.py (1.1)
├── Fix FigurePlate.figures property (1.3)
└── Run existing tests to verify no regressions

Day 2: Filter Unification
├── Import MedicalImageClassifier to neurosynth_bridge.py (1.2)
├── Remove duplicate _is_medical_image function
└── Test Reference Library integration

Day 3: Snapshot Filter Integration
├── Add filter call to snapshot extraction (1.4)
├── Verify hybrid extraction still works
└── Run full pipeline test
```

### Phase 2: Enhanced Filtering (5 days)

```
Days 4-5: MedicalImageClassifier Integration
├── Add enhancement module to project structure
│   └── src/neurosynth/enhancements/medical_classifier.py
├── Integrate with _is_medical_image() wrapper
├── Add configuration options
└── Unit tests for classification accuracy

Days 6-7: Caption Detection Upgrade
├── Integrate CaptionDetector patterns
├── Add confidence scoring to caption selection
├── Update VisualElement model for confidence field
└── Test against varied PDF samples

Day 8: Vector Graphics (Optional)
├── Add VectorGraphicsExtractor module
├── Integrate with page processing loop
└── Add VectorRegion to output models
```

### Phase 3: Association Enhancements (4 days)

```
Days 9-10: Keyword Scoring
├── Add neurosurgical keyword dictionaries to clustering.py
├── Implement _calculate_keyword_score() method
├── Integrate with association scoring
└── Test with varied neurosurgical content

Days 11-12: Embedding Integration
├── Add _calculate_embedding_similarity() method
├── Cache embeddings during visual embedding stage
├── Weight embedding score in total association
└── Performance testing
```

### Phase 4: LaTeX Output (3 days)

```
Days 13-14: Subfigure Support
├── Implement generate_subfigures() method
├── Add subcaption package to preamble
├── Detect multi-panel figures
└── Test compilation

Day 15: Procedural Sequences
├── Implement generate_procedural_sequence()
├── Add auto-pagination logic
├── Test with long procedures
└── Final integration testing
```

---

## Part 8: Testing Strategy

### Unit Tests

```python
# test_medical_classifier.py
def test_surgical_photo_detection():
    """Test that surgical photos score high."""
    classifier = MedicalImageClassifier()
    # Load test image with surgical colors
    result = classifier.analyze_image(surgical_image)
    assert result.is_medical
    assert result.confidence > 0.7
    assert 'surgical_color_detected' in result.rejection_reasons or result.is_medical

def test_icon_rejection():
    """Test that small icons are rejected."""
    classifier = MedicalImageClassifier()
    # 32x32 low-entropy icon
    result = classifier.analyze_image(icon_image)
    assert not result.is_medical
    assert 'likely_icon' in result.rejection_reasons

def test_radiological_signature():
    """Test MRI/CT detection."""
    classifier = MedicalImageClassifier()
    result = classifier.analyze_image(mri_image)
    assert result.is_medical
    assert result.image_type == 'radiological'
```

```python
# test_caption_detector.py
def test_figure_pattern_matching():
    """Test various figure caption patterns."""
    detector = CaptionDetector()

    assert detector.extract_figure_id("Figure 3.2: Axial view") == "3.2"
    assert detector.extract_figure_id("Fig. 3-2. Coronal view") == "3-2"
    assert detector.extract_figure_id("(A) Pre-operative") == "A"
    assert detector.extract_figure_id("Step 5: Closure") == "5"

def test_cross_reference_extraction():
    """Test cross-reference pattern detection."""
    detector = CaptionDetector()
    text = "As shown in Figure 3.2, the tumor extends (see also Fig. 4.1)"

    refs = detector.extract_cross_references(text)
    assert "3.2" in refs
    assert "4.1" in refs

def test_caption_confidence_scoring():
    """Test confidence calculation."""
    detector = CaptionDetector()

    # High confidence: proper format, italic, near image
    high_conf = detector.calculate_confidence(
        text="Figure 3.2: Intraoperative photograph showing cortical exposure",
        is_italic=True,
        distance_to_image=30
    )

    # Low confidence: short, no format, far from image
    low_conf = detector.calculate_confidence(
        text="See figure 1",
        is_italic=False,
        distance_to_image=200
    )

    assert high_conf > low_conf
    assert high_conf > 0.7
    assert low_conf < 0.5
```

```python
# test_visual_associator.py
def test_keyword_scoring():
    """Test neurosurgical keyword detection."""
    associator = VisualClusterAssociator()

    # Anatomy text
    anatomy_text = "The frontal cortex and middle cerebral artery were identified"
    score = associator._calculate_keyword_score(anatomy_text)
    assert score > 0.2

    # Non-medical text
    generic_text = "The results were analyzed using statistical methods"
    score = associator._calculate_keyword_score(generic_text)
    assert score < 0.1

def test_association_ranking():
    """Test that relevant clusters rank higher."""
    associator = VisualClusterAssociator()

    image = create_test_image(caption="MRI showing glioma")

    clusters = [
        create_cluster(text="Statistical analysis methods..."),
        create_cluster(text="Tumor resection and MRI imaging..."),
        create_cluster(text="Bibliography and references..."),
    ]

    associations = associator.associate_images_with_clusters([image], clusters)

    # Cluster 2 should rank highest (tumor, resection, MRI)
    assert associations[0].cluster_idx == 1
```

### Integration Tests

```python
# test_pipeline_integration.py
@pytest.mark.asyncio
async def test_extraction_to_latex_pipeline():
    """Test full pipeline: extract → synthesize → latex."""
    config = SynthesizerConfig(
        enable_visual_extraction=True,
        visual_association_threshold=0.3,
    )

    # Process test PDF
    result = await run_pipeline(
        source=TEST_PDF_PATH,
        config=config,
    )

    # Verify figures reach LaTeX output
    assert len(result.sections) > 0
    for section in result.sections:
        if section.figures:
            for fig in section.figures:
                assert Path(fig.image_path).exists()
                assert fig.caption is not None

@pytest.mark.asyncio
async def test_visual_association_with_embeddings():
    """Test that visuals with embeddings associate better."""
    # Create clusters with embeddings
    clusters = create_clusters_with_embeddings()

    # Create visuals with and without embeddings
    visual_with_emb = create_visual(embedding=np.random.rand(128))
    visual_without_emb = create_visual(embedding=None)

    associator = VisualClusterAssociator()

    # Run association
    with_emb_score = associator.calculate_association_score(
        visual_with_emb, clusters[0]
    )
    without_emb_score = associator.calculate_association_score(
        visual_without_emb, clusters[0]
    )

    # Embedding-based should be more confident
    assert with_emb_score.confidence > without_emb_score.confidence

@pytest.mark.asyncio
async def test_reference_library_integration():
    """Test enhancement module with Reference Library."""
    bridge = NeuroSynthBridge(config=NeuroSynthConfig())

    result = await bridge.process_document(TEST_PDF_PATH)

    assert result.images is not None
    assert result.captions is not None
    assert result.associations is not None

    # Verify global indices
    assert len(bridge.pipeline.image_index) > 0
    assert len(bridge.pipeline.figure_index) > 0
```

---

## Part 9: Code Integration Guide

### 9.1 File Changes Summary

| File | Change Type | Changes |
|------|-------------|---------|
| `src/neurosynth/synthesis/section.py` | Fix | Line 317: `str(image_path)` |
| `src/neurosynth/models/output.py` | Fix | Line 75: `.figures` not `.elements` |
| `src/neurosynth/parsers/image_extractor.py` | Enhance | Add classifier, patterns, vector support |
| `src/neurosynth/dedup/clustering.py` | Enhance | Add keyword scoring, embedding similarity |
| `src/neurosynth/latex/generator.py` | Enhance | Add subfigures, sequences |
| `src/neurosynth/models/visual.py` | Enhance | Add confidence, cross_refs fields |
| `reference-library/src/integration/neurosynth_bridge.py` | Refactor | Remove duplicate, use shared filter |

### 9.2 New Files

```
src/neurosynth/enhancements/
├── __init__.py
├── medical_classifier.py      # MedicalImageClassifier
├── caption_detector.py        # CaptionDetector
├── vector_extractor.py        # VectorGraphicsExtractor
└── visual_associator.py       # VisualClusterAssociator
```

### 9.3 Configuration Additions

```python
# Add to SynthesizerConfig
@dataclass
class VisualEnhancementConfig:
    # Medical classifier
    use_enhanced_classifier: bool = True
    min_medical_confidence: float = 0.5
    enable_surgical_color_detection: bool = True

    # Caption detection
    use_enhanced_captions: bool = True
    caption_confidence_threshold: float = 0.6
    track_cross_references: bool = True

    # Association
    use_keyword_scoring: bool = True
    use_embedding_similarity: bool = True
    embedding_weight: float = 0.3

    # Vector graphics
    extract_vector_graphics: bool = False
    min_vector_complexity: float = 0.3

    # LaTeX output
    enable_subfigures: bool = True
    enable_procedural_sequences: bool = True
    max_subfigures_per_row: int = 3
```

### 9.4 Dependencies

```
# requirements.txt additions
opencv-python>=4.5.0  # For edge detection (optional)
scikit-image>=0.18.0  # For entropy calculation (optional)
```

---

## Part 10: v3.1 File Reference

### 10.1 Enhancement Module Files

| File | Size | Purpose | v3.1 Changes |
|------|------|---------|--------------|
| `WEIGHTS_REFERENCE.md` | 5KB | Weight documentation | **NEW** |
| `__init__.py` | 4KB | Module exports | Updated exports |
| `config.py` | 27KB | Master configuration | **+AssociationWeightConfig, +CaptionConfidenceConfig** |
| `resilient_filter.py` | 29KB | 3-tier fallback filtering | No changes |
| `enhanced_caption_detector.py` | 26KB | Multi-directional caption | Uses `config.caption_confidence` |
| `visual_cluster_associator.py` | 27KB | Keyword scoring | Uses `config.association_weights` |
| `procedural_detector.py` | 26KB | Procedural sequences | No changes |
| `unified_pipeline.py` | 24KB | 7-stage orchestrator | No changes |
| `latex_figure_generator.py` | 20KB | LaTeX output | No changes |
| `latex_validator.py` | 21KB | LaTeX validation | No changes |
| `vector_extractor.py` | 22KB | Vector graphics | No changes |
| `async_wrappers.py` | 20KB | Async wrappers | No changes |
| `batch_processor.py` | 21KB | Batch processing | No changes |
| `neurosurgical_image_extractor.py` | 43KB | Domain extraction | No changes |
| `neurosurgical_visualization_module.py` | 33KB | Visualization | No changes |
| `neurosynth_bridge.py` | 26KB | Reference Library | No changes |
| `neurosynth_enhancements_v2.py` | 58KB | Legacy v2 (reference) | Deprecated |

### 10.2 Key Classes by File

```
config.py (v3.1)
├── NeuroSynthEnhancedConfig (master)
├── NeurosurgicalKeywords
├── KeywordWeightConfig           # Category weights (MUST SUM TO 1.0)
├── AssociationWeightConfig       # NEW: Association scoring weights
├── CaptionConfidenceConfig       # NEW: Caption confidence weights
├── ImageFilterConfig
├── CaptionDetectionConfig
├── VectorGraphicsConfig
├── LaTeXConfig
├── PerformanceConfig
├── ImageCategory (enum)
├── CaptionPosition (enum)
├── FilterFallbackLevel (enum)
└── print_weights_summary()       # NEW: Debug method

resilient_filter.py
├── FilterResult
├── ColorAnalysisResult
├── ColorAnalyzer
├── EntropyCalculator
├── SurgicalColorDetector
├── EdgeDensityAnalyzer
├── EnhancedMedicalClassifier
├── BasicImageFilter
├── PermissiveFilter
└── ResilientImageFilter

enhanced_caption_detector.py
├── DetectedCaption
├── SearchRegion
├── CaptionMatch
├── CaptionPatternMatcher
├── EnhancedCaptionDetector
├── BatchCaptionProcessor
└── CrossReferenceTracker

visual_cluster_associator.py
├── TextBlock
├── ImageBlock
├── AssociationScore
├── Association
├── SpatialProximityCalculator
├── NeurosurgicalKeywordScorer
├── ContextAnalyzer
├── EnhancedVisualClusterAssociator
└── ClusterBuilder

procedural_detector.py
├── SequenceType (enum)
├── SequenceElement
├── ProceduralSequence
├── StepNumberExtractor
├── ProcedureKeywordDetector
├── ProceduralSequenceDetector
├── SequenceValidator
└── SequenceExporter

unified_pipeline.py
├── ExtractedImage
├── ExtractionResult
├── UnifiedExtractionPipeline
├── AsyncExtractionPipeline
├── extract_images_from_pdf()
└── quick_extract()

latex_figure_generator.py
├── FigureLayout (enum)
├── FigureImage
├── FigureSpec
├── GeneratedFigure
├── SingleFigureBuilder
├── SubfigureBuilder
├── ProceduralSequenceBuilder
├── ComparisonFigureBuilder
├── EnhancedLaTeXFigureGenerator
└── BatchFigureGenerator
```

### 10.3 Integration Path

```
Step 1: Copy v3.1 files to project
────────────────────────────────────
cp -r /Users/ramihatoum/Downloads/neurosynth_enhancements_v3.1/* \
      src/neurosynth/enhancements/

Step 2: Verify weight configuration
────────────────────────────────────
python -c "from config import NeuroSynthEnhancedConfig; NeuroSynthEnhancedConfig().print_weights_summary()"

Step 3: Update imports in existing code
────────────────────────────────────
# In image_extractor.py
from neurosynth.enhancements.resilient_filter import ResilientImageFilter
from neurosynth.enhancements.enhanced_caption_detector import EnhancedCaptionDetector

# In clustering.py
from neurosynth.enhancements.visual_cluster_associator import EnhancedVisualClusterAssociator

# In latex/generator.py
from neurosynth.enhancements.latex_figure_generator import EnhancedLaTeXFigureGenerator

Step 4: Initialize with config (weights auto-validated)
────────────────────────────────────
from neurosynth.enhancements.config import NeuroSynthEnhancedConfig

config = NeuroSynthEnhancedConfig(
    enable_enhanced_filtering=True,
    enable_caption_detection=True,
    enable_procedural_detection=True,
)

# Weights are automatically validated on init
# Access weights via:
#   config.keyword_weights.procedure  # 0.30
#   config.association_weights.spatial_weight  # 0.50
#   config.caption_confidence.pattern_weight  # 0.40

pipeline = UnifiedExtractionPipeline(config)
result = pipeline.extract_from_pdf(pdf_path)
```

---

## Summary

### v3.1 Improvement Categories

| Category | v3.0 | v3.1 |
|----------|------|------|
| **Weight Management** | In config but scattered | ALL weights centralized with validation |
| **Keyword Weights** | `KeywordWeightConfig` | Same + validation |
| **Association Scoring** | Hardcoded in module | **NEW** `AssociationWeightConfig` |
| **Caption Confidence** | Hardcoded in module | **NEW** `CaptionConfidenceConfig` |
| **Weight Validation** | Manual | Auto-validated on init |
| **Debug Tools** | None | `print_weights_summary()` method |
| **Documentation** | In code | **NEW** `WEIGHTS_REFERENCE.md` |

### Risk Mitigation

All v3.1 changes are designed to be:
- **Validated** - Weights auto-validate to sum to 1.0 (±0.05)
- **Centralized** - Single source of truth in `config.py`
- **Documented** - Complete weight reference with examples
- **Debuggable** - `print_weights_summary()` for verification
- **Backward Compatible** - No API changes, just weight consolidation

### v3.1 Critical Rules

1. **NEVER hardcode weights** outside of `config.py`
2. **ALL weights MUST sum to 1.0** (within tolerance)
3. **Access weights via config object**, not hardcoded values
4. **Validate weights** after any modification

### Next Steps

1. **Copy v3.1 files** to `src/neurosynth/enhancements/`
2. **Run `print_weights_summary()`** to verify all weights
3. **Review `WEIGHTS_REFERENCE.md`** for scoring formulas
4. **Integrate modules** — weights are auto-validated
5. **Tune weights** by modifying `KeywordWeightConfig`, `AssociationWeightConfig`, `CaptionConfidenceConfig` in `config.py`

---

*Document Version: 3.1*
*Last Updated: 2025-11-30*
*Source Files: `/Users/ramihatoum/Downloads/neurosynth_enhancements_v3.1/`*
*Key Change: Weight centralization with validation*
*Author: Augment Agent*
