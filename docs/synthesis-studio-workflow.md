# Synthesis Studio Workflow Documentation

> **File**: `src/ui/synthesis_page.py`  
> **Module**: Streamlit-based chapter synthesis UI  
> **Type**: Legacy Streamlit-compatible path (vs. production async pipeline)

---

## 1. Architecture Overview

### Component Initialization Pattern

Synthesis Studio uses **lazy loading** via Streamlit's `session_state` to persist components across page reruns:

```python
if ("db" not in st.session_state or
    "search" not in st.session_state or
    "engine" not in st.session_state or
    "templates" not in st.session_state):
    try:
        st.session_state.db = Database()
        st.session_state.search = SearchEngine(st.session_state.db)
        st.session_state.engine = SynthesisEngine(
            st.session_state.db,
            st.session_state.search,
            None  # AIClient instantiated per-request
        )
        st.session_state.templates = TemplateManager()
    except Exception as e:
        st.error(f"Failed to initialize engine: {e}")
        return
```

**Why check ALL components?** Streamlit reruns the entire script on every interaction. By checking all four components together, we ensure atomic initialization and avoid partial state corruption.

### Component Dependency Chain

```
┌──────────────────────────────────────────────────────────────────┐
│                    INITIALIZATION ORDER                          │
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│   Database()          ← SQLite/Qdrant connection                 │
│       ↓                                                          │
│   SearchEngine(db)    ← Vector similarity search                 │
│       ↓                                                          │
│   SynthesisEngine(db, search, ai_client=None)                    │
│       ↓               ↑                                          │
│   TemplateManager()   │                                          │
│                       │                                          │
│   AIClient() ─────────┘  ← Created per-request (async context)   │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
```

### Why AIClient is Per-Request

AIClient is **NOT** stored in session state. Instead, it's instantiated per-request via async context manager:

```python
async with AIClient() as ai_async:
    emb = await ai_async.get_embedding(query_str)
    content = await ai_async.synthesize(prompt, system_prompt=s_prompt)
```

**Design Rationale**:

| Reason | Explanation |
|--------|-------------|
| **Connection Pooling** | AIClient manages httpx connection pools; creating fresh ensures no stale connections |
| **API Key Rotation** | Allows reading latest API keys from environment on each request |
| **Resource Cleanup** | `async with` guarantees proper cleanup via `__aexit__` |
| **Streamlit Compatibility** | Avoids serialization issues with async clients in session_state |

---

## 2. Three-Step Workflow

### Step 1: Chapter Configuration

**Purpose**: Capture the core topic and establish synthesis standards.

```python
# Widget uses temporary key
col1.text_input("Core Topic", default_topic, key="widget_syn_topic")

# On button click, persist to permanent session state
if st.button("Initialize Studio"):
    st.session_state.syn_topic = st.session_state.widget_syn_topic
    st.session_state.syn_audience = "Expert Neurosurgeon/Fellow"
    st.session_state.syn_standards = [
        "Rhoton Anatomy",
        "Greenberg Handbook",
        "Youmans Neurological Surgery",
        "Ojemann"
    ]
    st.session_state.studio_step = 2
    st.rerun()
```

**Session State After Step 1**:
```python
st.session_state = {
    "syn_topic": "Vestibular Schwannoma",
    "syn_audience": "Expert Neurosurgeon/Fellow",
    "syn_standards": ["Rhoton Anatomy", "Greenberg Handbook", ...],
    "studio_step": 2
}
```

### Step 2: Outline Selection

**Purpose**: Allow user to select which sections to synthesize.

```python
default_sections = [
    "Epidemiology & Natural History",
    "Clinical Presentation",
    "Diagnostic Evaluation",
    "Differential Diagnosis",
    "Surgical Anatomy",
    "Operative Technique",
    "Complications & Avoidance",
    "Outcomes & Prognosis"
]

selected_sections = []
for sec in default_sections:
    if st.checkbox(sec, value=True, key=f"sec_{sec}"):
        selected_sections.append(sec)
```

**Key Pattern**: Checkbox keys use `f"sec_{sec}"` prefix to avoid collision with other widget keys.

### Step 3: Synthesis & Review

**Purpose**: Generate content for each selected section with tab-based navigation.

```python
tabs = st.tabs(st.session_state.selected_sections)

for i, section_title in enumerate(st.session_state.selected_sections):
    with tabs[i]:
        btn_key = f"gen_btn_{i}"  # Unique button key per section
        res_key = f"res_{i}"       # Unique result key per section

        if st.button(f"⚡ Synthesize '{section_title}'", key=btn_key):
            # ... synthesis logic ...
            st.session_state[res_key] = {"content": ..., "sources": ...}
```

---

## 3. Key Technical Patterns

### Widget Keys vs. Persistent Keys

Streamlit has a quirk: widget values are tied to their `key` and reset on rerun. To persist user input:

```python
# PATTERN: widget_* keys are temporary, syn_* keys are persistent

# 1. Widget reads from persistent key (or default)
default_topic = st.session_state.get("syn_topic", "Vestibular Schwannoma")

# 2. Widget writes to temporary key
col1.text_input("Core Topic", default_topic, key="widget_syn_topic")

# 3. On action, copy temporary → persistent
st.session_state.syn_topic = st.session_state.widget_syn_topic
```

### Section Type Detection

Template rendering adapts based on section content:

```python
section_type = "IMPERATIVE" if "Technique" in section_title else "DESCRIPTIVE"
```

| Section Title | Type | Template Behavior |
|---------------|------|-------------------|
| "Operative Technique" | IMPERATIVE | Step-by-step surgical instructions |
| "Clinical Presentation" | DESCRIPTIVE | Narrative explanation |
| "Surgical Anatomy" | DESCRIPTIVE | Anatomical description |

### Template Path Resolution

```python
template_path = "synthesis/section.md.j2"

# TemplateManager loads from: src/neurosynth/templates/synthesis/section.md.j2
s_prompt, u_prompt = tm_mgr.render_prompt(template_path, ctx)
```

The template uses `---SYSTEM---` and `---USER---` markers to split the prompt.

---

## 4. Data Flow

### Complete Synthesis Pipeline

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         USER INTERACTION → OUTPUT                           │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  [UI Widget]           [Session State]           [Async Handler]            │
│                                                                             │
│  text_input ──────────► widget_syn_topic                                    │
│       ↓                      ↓                                              │
│  "Initialize" btn ────► syn_topic, syn_audience, syn_standards              │
│       ↓                      ↓                                              │
│  checkbox[] ──────────► selected_sections                                   │
│       ↓                      ↓                                              │
│  "Synthesize" btn ────► generate_section() ─────────────────────────────►   │
│                              │                                              │
│                              ▼                                              │
│                    ┌─────────────────────┐                                  │
│                    │ async with AIClient │                                  │
│                    └─────────────────────┘                                  │
│                              │                                              │
│                    ┌─────────▼─────────┐                                    │
│                    │ 1. get_embedding() │  ← Voyage AI                      │
│                    └─────────┬─────────┘                                    │
│                              │                                              │
│                    ┌─────────▼─────────┐                                    │
│                    │ 2. retrieve_for_  │  ← SearchEngine (sync)             │
│                    │    topic()        │                                    │
│                    └─────────┬─────────┘                                    │
│                              │                                              │
│                    ┌─────────▼─────────┐                                    │
│                    │ 3. render_prompt()│  ← TemplateManager                 │
│                    └─────────┬─────────┘                                    │
│                              │                                              │
│                    ┌─────────▼─────────┐                                    │
│                    │ 4. synthesize()   │  ← Claude API                      │
│                    └─────────┬─────────┘                                    │
│                              │                                              │
│                    ◄─────────┘                                              │
│       ↓                                                                     │
│  st.session_state[res_key] = {content, sources, figures, context}           │
│       ↓                                                                     │
│  st.markdown(content) ← Display to user                                     │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Context Object Structure

The template receives a deeply nested context object:

```python
ctx = {
    "ctx": {
        "section_title": "Operative Technique",
        "section_type": "IMPERATIVE",
        "chapter_context": "Vestibular Schwannoma",
        "audience": "Expert Neurosurgeon/Fellow",
        "standards": ["Rhoton Anatomy", "Greenberg Handbook", ...],
        "word_target": 1000,
        "sources": [
            {"source_id": "...", "source_name": "...", "content": "..."},
            ...
        ],
        "figures": [
            {"id": "...", "image_type": "...", "caption": "..."},
            ...
        ],
    }
}
```

### Error Handling & Defensive Checks

```python
async def generate_section():
    # Defensive check: ensure search engine is initialized
    if "search" not in st.session_state:
        raise RuntimeError("SearchEngine not initialized. Please refresh the page.")

    async with AIClient() as ai_async:
        # ... synthesis logic ...
```

**Why this check?** Streamlit's session_state can be cleared by browser refresh or session timeout. This prevents cryptic `KeyError` exceptions.

---

## 5. Integration Points

### Connection to Broader NeuroSynth Architecture

```
┌────────────────────────────────────────────────────────────────────────────┐
│                         NEUROSYNTH ARCHITECTURE                            │
├────────────────────────────────────────────────────────────────────────────┤
│                                                                            │
│  ┌──────────────────┐     ┌──────────────────┐    ┌──────────────────┐    │
│  │  SYNTHESIS       │     │  STUDY SUITE     │    │  REFERENCE       │    │
│  │  STUDIO          │     │  (brain.py)      │    │  LIBRARY         │    │
│  │  (this file)     │     │                  │    │                  │    │
│  └────────┬─────────┘     └────────┬─────────┘    └────────┬─────────┘    │
│           │                        │                       │               │
│           └────────────────────────┼───────────────────────┘               │
│                                    │                                       │
│                          ┌─────────▼─────────┐                             │
│                          │   SHARED CORE     │                             │
│                          ├───────────────────┤                             │
│                          │ • AIClient        │ ← Voyage + Claude           │
│                          │ • TemplateManager │ ← Jinja2 templates          │
│                          │ • SearchEngine    │ ← Vector similarity         │
│                          │ • Database        │ ← SQLite + Qdrant           │
│                          └───────────────────┘                             │
│                                                                            │
└────────────────────────────────────────────────────────────────────────────┘
```

### Legacy vs. Production Paths

| Aspect | Synthesis Studio (Legacy) | Production Pipeline |
|--------|---------------------------|---------------------|
| **File** | `src/ui/synthesis_page.py` | `src/neurosynth/synthesis/section.py` |
| **Entry** | Streamlit UI | FastAPI / CLI |
| **Async** | `asyncio.run()` wrapper | Native async/await |
| **AI Client** | Per-request `async with` | Injected dependency |
| **Search** | Sync `SearchEngine` | Async with ColBERT reranking |
| **State** | `st.session_state` | Redis / Checkpoints |
| **Use Case** | Interactive exploration | Batch chapter generation |

### Why Two Paths Exist

1. **Streamlit Limitation**: Streamlit's execution model (full script rerun on interaction) doesn't play well with long-running async operations. The `asyncio.run()` wrapper bridges this gap.

2. **Development Speed**: Synthesis Studio allows rapid prototyping of synthesis workflows without setting up the full API/Worker infrastructure.

3. **Migration Path**: Features prototyped in Synthesis Studio can be "promoted" to the production pipeline in `src/neurosynth/synthesis/`.

---

## 6. Session State Reference

| Key | Type | Set By | Purpose |
|-----|------|--------|---------|
| `db` | `Database` | Step 1 init | SQLite/Qdrant connection |
| `search` | `SearchEngine` | Step 1 init | Vector search |
| `engine` | `SynthesisEngine` | Step 1 init | Orchestration (unused currently) |
| `templates` | `TemplateManager` | Step 1 init | Jinja2 rendering |
| `studio_step` | `int` | Workflow nav | Current step (1, 2, or 3) |
| `widget_syn_topic` | `str` | Text input | Temporary widget value |
| `syn_topic` | `str` | "Initialize" btn | Persisted topic |
| `syn_audience` | `str` | "Initialize" btn | Target audience |
| `syn_standards` | `list[str]` | "Initialize" btn | Reference standards |
| `selected_sections` | `list[str]` | Step 2 | Sections to generate |
| `res_{i}` | `dict` | Synthesis | Generated content per section |

---

## 7. Template Integration Example

The `synthesis/section.md.j2` template receives the context and produces split prompts:

```jinja2
---SYSTEM---
You are an expert neurosurgical knowledge synthesizer.
Target Audience: {{ ctx.audience }}
Reference Standards: {{ ctx.standards | join(", ") }}

---USER---
## Section: {{ ctx.section_title }}
## Chapter: {{ ctx.chapter_context }}
## Type: {{ ctx.section_type }}

### Source Materials:
{% for source in ctx.sources %}
#### {{ source.source_name }}
{{ source.content }}
{% endfor %}

Synthesize a {{ ctx.word_target }}-word {{ ctx.section_type | lower }} section.
```

The `TemplateManager.render_prompt()` splits this into `(system_prompt, user_prompt)` for the Claude API call.

---

## 8. Visual Intelligence Pipeline

NeuroSynth includes a sophisticated multi-stage visual processing system that extracts, analyzes, embeds, and associates images with text content.

### 8.1 Image Extraction Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    VISUAL INTELLIGENCE PIPELINE                             │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  PDF Input                                                                  │
│      │                                                                      │
│      ▼                                                                      │
│  ┌────────────────────────────────────────────────────────────────────┐    │
│  │ STAGE 1: Hybrid Extraction                                          │    │
│  │ ├─ Raw Image Extraction (PyMuPDF xref scan)                        │    │
│  │ ├─ Snapshot Rendering (captures labels, arrows)                     │    │
│  │ └─ Perceptual Hash Deduplication (64-bit average hash)             │    │
│  └────────────────────────────────────────────────────────────────────┘    │
│      │                                                                      │
│      ▼                                                                      │
│  ┌────────────────────────────────────────────────────────────────────┐    │
│  │ STAGE 2: Intelligent Filtering (3-Tier Fallback)                    │    │
│  │ ├─ Enhanced: Color analysis, entropy, edge density, surgical RGB   │    │
│  │ ├─ Basic: Simple heuristics (size, aspect ratio)                   │    │
│  │ └─ Permissive: Size-only fallback (never lose images)              │    │
│  └────────────────────────────────────────────────────────────────────┘    │
│      │                                                                      │
│      ▼                                                                      │
│  ┌────────────────────────────────────────────────────────────────────┐    │
│  │ STAGE 3: Caption Detection (Multi-Directional)                      │    │
│  │ ├─ Below image scan (most common)                                   │    │
│  │ ├─ Above image scan                                                 │    │
│  │ ├─ Side caption detection                                           │    │
│  │ └─ Cross-reference linking (Fig. 1 → actual figure)                │    │
│  └────────────────────────────────────────────────────────────────────┘    │
│      │                                                                      │
│      ▼                                                                      │
│  ┌────────────────────────────────────────────────────────────────────┐    │
│  │ STAGE 4: Type Classification                                        │    │
│  │ ├─ Radiological (grayscale, high entropy, CT/MRI patterns)         │    │
│  │ ├─ Intraoperative (surgical RGB colors, blood/tissue detection)    │    │
│  │ ├─ Anatomical Diagram (low entropy, high edge density)             │    │
│  │ ├─ Flowchart (vector graphics, arrow detection)                    │    │
│  │ └─ Histological (cellular patterns)                                 │    │
│  └────────────────────────────────────────────────────────────────────┘    │
│      │                                                                      │
│      ▼                                                                      │
│  ┌────────────────────────────────────────────────────────────────────┐    │
│  │ STAGE 5: Embedding Generation                                       │    │
│  │ ├─ ColPali (Document-aware visual embedding, 128-dim)              │    │
│  │ ├─ BiomedCLIP (Text-image alignment for medical imagery)           │    │
│  │ └─ Voyage AI (Context text embedding, 1024-dim)                    │    │
│  └────────────────────────────────────────────────────────────────────┘    │
│      │                                                                      │
│      ▼                                                                      │
│  ┌────────────────────────────────────────────────────────────────────┐    │
│  │ STAGE 6: Cluster Association                                        │    │
│  │ ├─ Spatial proximity scoring                                        │    │
│  │ ├─ Neurosurgical keyword relevance (340+ medical terms)            │    │
│  │ ├─ Context analysis (demonstratives: "this figure shows...")       │    │
│  │ └─ Cross-reference linking                                          │    │
│  └────────────────────────────────────────────────────────────────────┘    │
│      │                                                                      │
│      ▼                                                                      │
│  Qdrant Vector DB (visual embeddings + text embeddings)                    │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 8.2 Hybrid Image Extraction

**File**: `src/neurosynth/parsers/image_extractor.py`

Combines two extraction methods for maximum accuracy:

```python
async def extract_images_hybrid(pdf_path: Path, output_dir: Path) -> list[VisualElement]:
    """
    Hybrid approach:
    1. Raw extraction (fast, catches embedded images)
    2. Snapshot rendering (accurate, captures labels/arrows)

    Deduplicates using perceptual hashing.
    """
```

**Why Hybrid?**
- **Raw extraction** finds embedded JPEGs/PNGs directly in the PDF stream
- **Snapshot rendering** captures vector overlays, annotations, and labels that aren't embedded as separate images

### 8.3 Perceptual Hashing for Deduplication

```python
def _compute_visual_hash(self, image: Image.Image) -> str:
    """
    Average hash algorithm:
    1. Resize to 8x8
    2. Convert to grayscale
    3. Compare each pixel to average
    4. Generate 64-bit hash
    """
    small = image.resize((8, 8), Image.Resampling.LANCZOS).convert("L")
    pixels = list(small.getdata())
    avg = sum(pixels) / len(pixels)
    bits = "".join("1" if p > avg else "0" for p in pixels)
    return hex(int(bits, 2))[2:].zfill(16)
```

This allows detecting duplicate images even if they're at different resolutions or have minor compression artifacts.

### 8.4 Resilient 3-Tier Image Filtering

**File**: `src/neurosynth/enhancements/resilient_filter.py`

```python
class ResilientImageFilter:
    """
    Tries in order:
    1. Enhanced classifier (full analysis)
    2. Basic filter (simple heuristics)
    3. Permissive filter (size-only)

    Gracefully handles failures at each level.
    """
```

**Enhanced Classification Features**:

| Feature | Detection Method | Use Case |
|---------|------------------|----------|
| **Entropy** | Shannon entropy from histogram | Distinguishes photos vs. diagrams |
| **Grayscale Ratio** | % of achromatic pixels | Identifies radiological images |
| **Edge Density** | Canny edge detection | Detects diagrams/line drawings |
| **Surgical RGB** | Blood/tissue color detection | Identifies intraoperative photos |
| **Dynamic Range** | Max-min pixel values | Quality assessment |

### 8.5 Embedding Models

#### ColPali (Document-Aware Visual Embeddings)

**File**: `src/neurosynth/llm/colpali.py`

```python
class ColPaliClient:
    """
    Document-aware visual embeddings.

    Unlike CLIP (trained on natural images), ColPali understands:
    - Medical diagrams and annotations
    - Figure labels and captions
    - Document layout context
    """

    async def embed_visual_elements(self, elements: list[VisualElement]) -> list[VisualElement]:
        # Generates 128-dim embeddings for visual similarity search
```

#### BiomedCLIP (Text-Image Alignment)

**File**: `src/neurosynth/ai/biomed_searcher.py`

```python
class BiomedCLIPSearcher:
    """
    Microsoft's BiomedCLIP for medical image-text alignment.

    Enables:
    - Text → Image search ("show me glioblastoma MRI")
    - Image → Text similarity
    - Cross-modal retrieval
    """
    MODEL_NAME = "hf-hub:microsoft/BiomedCLIP-PubMedBERT_256-vit_base_patch16_224"

    def embed_text(self, text: str) -> np.ndarray:
        # Text embedding in shared image space

    def embed_image(self, image_path: Path) -> np.ndarray:
        # Image embedding in shared text space
```

### 8.6 Visual-Text Association

**File**: `src/neurosynth/enhancements/visual_cluster_associator.py`

Associates images with text chunks using multiple scoring methods:

```python
class EnhancedVisualClusterAssociator:
    """
    Multi-factor scoring:
    1. Spatial proximity (bbox distance)
    2. Neurosurgical keyword relevance (340+ weighted terms)
    3. Context analysis (demonstratives, references)
    4. Cross-reference linking
    """
```

**5-Category Keyword Weights** (from config):

| Category | Weight | Example Keywords |
|----------|--------|------------------|
| Imaging | 3.0 | MRI, CT, angiography |
| Anatomy | 2.5 | cortex, brainstem, ventricle |
| Surgical | 2.0 | craniotomy, resection, approach |
| Pathology | 1.5 | tumor, hemorrhage, lesion |
| Clinical | 1.0 | patient, symptom, outcome |

### 8.7 Procedural Sequence Detection

**File**: `src/neurosynth/enhancements/procedural_detector.py`

Detects surgical step sequences (Step 1 → 2 → 3):

```python
class ProceduralSequenceDetector:
    """
    Identifies numbered procedural sequences in images.

    Detects:
    - Numbered step labels (1, 2, 3 or A, B, C)
    - Surgical progression sequences
    - Multi-panel figures with implicit ordering
    """
```

### 8.8 Vector Graphics Extraction

**File**: `src/neurosynth/enhancements/vector_extractor.py`

Extracts diagrams rendered as vector graphics (not raster images):

```python
class VectorGraphicsExtractor:
    """
    Algorithm:
    1. Extract drawing commands from page
    2. Filter by complexity (min paths threshold)
    3. Spatial clustering using grid-based grouping
    4. Type classification via keyword matching
    5. Arrow detection for flowchart identification
    6. Render clusters to PNG images
    """
```

---

## 9. Intelligent Document Parsing

### 9.1 Layout-Aware Text Extraction

**File**: `src/neurosynth/parsers/pdf_parser.py`

```python
async def extract_text(self, path: Path) -> str:
    """
    Extraction hierarchy:
    1. pymupdf4llm (preserves layout, tables, headings as Markdown)
    2. PyMuPDF fallback (basic text extraction with page markers)
    """
    if self._use_pymupdf4llm:
        text = pymupdf4llm.to_markdown(str(path))  # Layout-preserved
        return text

    # Fallback: basic extraction
    for page in pdf:
        text_parts.append(f"[Page {page_num + 1}]\n{page.get_text('text')}")
```

**Why pymupdf4llm?**
- Preserves table structure as Markdown tables
- Converts headings to Markdown `#` syntax
- Maintains reading order for multi-column layouts
- Extracts images with contextual placement

### 9.2 Structural Chunking with TOC Awareness

**File**: `src/neurosynth/chunking/chunker.py`

```python
class SemanticChunker:
    """
    Chunking strategies:
    - STRUCTURAL: Uses TOC/headings for semantic boundaries
    - FIXED: Fixed-size chunks with overlap
    - HYBRID: Structural first, then split/merge
    - SEMANTIC: AI-guided boundaries
    """
```

**TOC-Guided Chunking**:

```python
async def _chunk_structural(self, doc: Document) -> list[ContentChunk]:
    if doc.toc:
        # Use PDF's embedded Table of Contents
        toc_positions = self._find_toc_positions(text, doc.toc)
        for start, entry in toc_positions:
            chunk = doc.add_chunk(
                content=text[start:end],
                section_title=entry.get("title", ""),
            )
    else:
        # Fallback to heading pattern detection
        chunks = self._chunk_by_headings(doc)
```

**Heading Pattern Detection**:

```python
# Matches: "## Section Title", "1.2.3 Subsection", etc.
self._heading_pattern = re.compile(
    r"^(#{1,4}|\d+\.[\d.]*)\s+[A-Z]",
    re.MULTILINE,
)

# Medical section markers
self._section_markers = [
    r"^Introduction\s*$",
    r"^Surgical Technique\s*$",
    r"^Complications?\s*$",
    r"^Anatomy\s*$",
    r"^Pathophysiology\s*$",
    # ... more patterns
]
```

### 9.3 Hybrid Chunking (Split Large, Merge Small)

```python
async def _chunk_hybrid(self, doc: Document) -> list[ContentChunk]:
    """
    1. Start with structural chunks (TOC/headings)
    2. Split chunks > 1.5x target size
    3. Merge adjacent chunks < 0.3x target size
    """
    for chunk in structural_chunks:
        if chunk.word_count > self.target_size * 1.5:
            sub_chunks = self._split_large_chunk(chunk, doc)
        elif chunk.word_count < self.target_size * 0.3:
            chunk.cluster_id = "small"  # Mark for merging
```

### 9.4 Metadata Extraction

**File**: `src/neurosynth/chunking/metadata.py`

```python
class MetadataExtractor:
    """
    Rule-based + LLM-enhanced metadata extraction.
    """

    # Section classification keywords
    SECTION_KEYWORDS = {
        "introduction": ["introduction", "overview", "background"],
        "anatomy": ["anatomy", "anatomical", "neuroanatomy"],
        "surgical_technique": ["technique", "procedure", "approach"],
        "complications": ["complication", "risk", "adverse"],
        # ...
    }

    def extract(self, chunk: ContentChunk) -> ChunkMetadata:
        # Rule-based: keyword matching
        metadata.section_type = self._classify_section(text)
        metadata.medical_entities = self._extract_entities(text)

    async def extract_with_llm(self, chunk: ContentChunk) -> ChunkMetadata:
        # LLM-enhanced: Gemini for topic identification
        result = await gemini.identify_chunk_topic(chunk.content)
```

### 9.5 The Complete Parsing Pipeline

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         DOCUMENT PARSING PIPELINE                           │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  PDF Input                                                                  │
│      │                                                                      │
│      ├──► Metadata Extraction (title, authors, year, publisher)            │
│      │                                                                      │
│      ├──► TOC Extraction (embedded PDF outline)                            │
│      │                                                                      │
│      ├──► Layout-Aware Text (pymupdf4llm → Markdown)                       │
│      │         │                                                            │
│      │         └──► Heading Detection (regex patterns)                     │
│      │                    │                                                 │
│      │                    └──► Structural Chunking                         │
│      │                              │                                       │
│      │                              ├──► Split Large Chunks (>1.5x)        │
│      │                              └──► Merge Small Chunks (<0.3x)        │
│      │                                        │                             │
│      │                                        ▼                             │
│      │                              Semantic Chunks with:                   │
│      │                              • section_title                         │
│      │                              • chapter_title                         │
│      │                              • word_count                            │
│      │                              • page_range                            │
│      │                                                                      │
│      └──► Image Extraction (hybrid: raw + snapshot)                        │
│                  │                                                          │
│                  └──► VisualElement with:                                  │
│                       • image_path                                          │
│                       • caption                                             │
│                       • context_text                                        │
│                       • image_type                                          │
│                       • visual_hash                                         │
│                                                                             │
│      ▼                                                                      │
│  Document Object (parsed, chunked, with visual elements)                   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 10. End-to-End Data Flow Summary

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    NEUROSYNTH: COMPLETE DATA FLOW                          │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  1. INGEST           2. INDEX              3. RETRIEVE       4. SYNTHESIZE │
│  ─────────           ────────              ──────────        ──────────────│
│                                                                             │
│  PDF Files           Text Embeddings       Query Expansion   Template       │
│      │               (Voyage AI)           (topic + section) Rendering     │
│      ▼                   │                      │            (Jinja2)      │
│  PDFParser ──────►       ▼                      ▼                │         │
│      │           ┌───────────────┐        SearchEngine           ▼         │
│      ├──► Text   │   Qdrant DB   │◄────── (vector sim)    ┌──────────────┐│
│      │           │  ┌─────────┐  │             │          │  AIClient    ││
│      ├──► TOC    │  │ Chunks  │  │             ▼          │  (Claude)    ││
│      │           │  └─────────┘  │      RetrievalResult   └──────────────┘│
│      └──► Images │  ┌─────────┐  │        │       │              │         │
│             │    │  │ Images  │  │        ▼       ▼              ▼         │
│             ▼    │  └─────────┘  │     Chunks   Images    SynthesizedSection
│      VisualElement└──────────────┘        │       │              │         │
│             │                             └───┬───┘              │         │
│             ▼                                 │                  │         │
│      ColPali/                                 ▼                  ▼         │
│      BiomedCLIP                        Context + Figures → LaTeX/Markdown │
│      Embeddings                                                            │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```
