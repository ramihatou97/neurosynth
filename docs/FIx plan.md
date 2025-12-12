Phase 1: Critical Path Fixes (Days 1-2)
1.1 Path Resolution Bug (P0 — Blocks Everything Downstream)
Location: page_extractor.py:230
Problem:
python# Current query passes extracted mini-PDF path:
page_figures = database.get_page_figures(pdf_path, page_num)
# Passes: "output/Differentiating_Lumbar_p1-11.pdf"

# But library.db has ORIGINAL paths:
# "/Users/ramihatoum/Desktop/NeuroLi copy/02_MULTI_CHAPTER_BOOKS/AOSpine..."
Fix — page_extractor.py:
python# Line ~230: Pass original source path, not extracted path
page_figures = database.get_page_figures(
    original_path=search_result.pdf_path,  # From SearchResult metadata
    page_number=page_num
)
Fix — database.py:1076:
pythondef get_page_figures(self, original_path: str, page_number: int):
    """Query with path normalization for cross-extraction compatibility."""
    # Normalize to filename for fuzzy matching
    filename = Path(original_path).stem

    query = """
        SELECT * FROM visual_elements
        WHERE (pdf_path = ? OR pdf_path LIKE '%' || ? || '%')
        AND page_number = ?
    """
    return conn.execute(query, [original_path, filename, page_number]).fetchall()
Validation:
bashsqlite3 library.db "SELECT COUNT(*) FROM visual_elements WHERE pdf_path LIKE '%AOSpine%'"
# Expected: 1,604 (not 0)

1.2 Ingestor Silent Failure → Fatal (P0)
Location: src/neurosynth/ai/ingestor.py:50-64
Current (Broken):
pythonexcept Exception as e:
    logger.warning(f"Could not check/create collection: {e}")  # Continues!
Fix:
pythonexcept Exception as e:
    logger.error(f"❌ CRITICAL: Qdrant collection creation failed: {e}")
    self.client = None
    raise RuntimeError(f"Qdrant initialization failed: {e}") from e
Validation:
bashcurl http://localhost:6333/collections | grep neurosurgical_figures_hybrid
# Should exist after fix + rerun

1.3 Backfill 18,378 Existing Images (P0)
Create: src/scripts/reindex_images.py
python"""Backfill embeddings for images already in neurosynth.db."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from index.database import Database
from neurosynth.ai.biomed_searcher import BiomedCLIPSearcher
from neurosynth.ai.ingestor import BiomedIngestor


def main():
    db = Database()
    embedder = BiomedCLIPSearcher()
    ingestor = BiomedIngestor()  # Will create collection (after 1.2 fix)

    # Fetch all images (add method below)
    all_images = db.get_all_images()
    print(f"Reindexing {len(all_images)} images...")

    batch_size = 32
    for i in range(0, len(all_images), batch_size):
        batch = all_images[i:i+batch_size]

        # Generate embeddings
        paths = [str(img.file_path) for img in batch if img.file_path.exists()]
        if not paths:
            continue

        vectors = embedder.embed_image(paths)

        # Update SQLite with embeddings
        for img, vec in zip(batch, vectors):
            img.embedding = vec.tolist()
            db.update_image_embedding(img.id, img.embedding)

        # Upsert to Qdrant
        ingestor.ingest_batch(batch, vectors)

        print(f"  ✅ {min(i+batch_size, len(all_images))}/{len(all_images)}")

if __name__ == "__main__":
    main()
Add to database.py:
pythondef get_all_images(self) -> list[ExtractedImage]:
    """Get all images regardless of embedding status."""
    with self._get_conn() as conn:
        rows = conn.execute("SELECT * FROM images").fetchall()
        return [self._row_to_image(row) for row in rows]

def update_image_embedding(self, image_id: str, embedding: list[float]):
    """Update embedding for existing image."""
    with self._get_conn() as conn:
        conn.execute(
            "UPDATE images SET embedding = ? WHERE id = ?",
            [self._serialize_embedding(embedding), image_id]
        )
Runtime: ~2-4 hours for 18k images

Phase 2: Retrieval Implementation (Days 2-3)
2.1 UnifiedSearchEngine Vision Search
Location: unified_search.py:256-263
Current (Stub):
pythonif mode in [SearchMode.DEEP, SearchMode.REASONING]:
    # TODO: Unified image search logic
    pass
Fix:
pythonif mode in [SearchMode.DEEP, SearchMode.REASONING]:
    try:
        # Query BiomedCLIP for relevant images
        image_results = self.biomed_searcher.search(
            query=query,
            collection_name="neurosurgical_figures_hybrid",
            top_k=min(20, config.max_images if hasattr(config, 'max_images') else 20),
            score_threshold=0.25
        )

        # Convert to ExtractedImage format
        retrieved_images = []
        for result in image_results:
            img = self.database.get_image_by_id(result.id)
            if img:
                img.relevance_score = result.score
                retrieved_images.append(img)

        logger.info(f"Retrieved {len(retrieved_images)} images for '{query[:50]}...'")

    except Exception as e:
        logger.warning(f"Image search failed: {e}")
        retrieved_images = []
Update return statement (~line 296):
pythonreturn RetrievalResult(
    chunks=final_chunks,
    images=retrieved_images,  # Was: images=[]
    ...
)

2.2 BiomedCLIPSearcher.search() Method
Add to biomed_searcher.py:
pythondef search(
    self,
    query: str,
    collection_name: str,
    top_k: int = 10,
    score_threshold: float = 0.2
) -> list[SearchResult]:
    """Search images by text query using BiomedCLIP."""
    # Embed query text
    query_vector = self.embed_text(query)

    # Search Qdrant
    results = self.qdrant_client.search(
        collection_name=collection_name,
        query_vector=("biomed", query_vector),
        limit=top_k,
        score_threshold=score_threshold,
        with_payload=True
    )

    return [
        SearchResult(
            id=r.payload.get("image_id"),
            score=r.score,
            metadata=r.payload
        )
        for r in results
    ]

Phase 3: Synthesis Integration (Days 3-4)
3.1 Image Assignment to Outline Sections
Location: category_outline.py
Add method:
pythonasync def assign_images_to_sections(
    self,
    outline: list[OutlineNode],
    available_images: list[ExtractedImage]
) -> list[OutlineNode]:
    """Assign relevant images to each outline section using semantic similarity."""
    if not available_images:
        return outline

    embedder = BiomedCLIPSearcher()

    for node in outline:
        # Get section text for matching
        section_text = f"{node.title} {node.description}"
        section_embedding = embedder.embed_text(section_text)

        # Score all images against this section
        scored_images = []
        for img in available_images:
            if img.embedding:
                similarity = cosine_similarity(section_embedding, img.embedding)
                if similarity > 0.3:  # Relevance threshold
                    scored_images.append((img, similarity))

        # Assign top N images (avoid duplicates across sections later)
        scored_images.sort(key=lambda x: x[1], reverse=True)
        node.assigned_images = [img for img, _ in scored_images[:5]]

        logger.debug(f"Section '{node.title}': {len(node.assigned_images)} images assigned")

    # Deduplicate: each image appears in at most 2 sections
    image_usage = defaultdict(int)
    for node in outline:
        node.assigned_images = [
            img for img in node.assigned_images
            if image_usage[img.id] < 2
        ]
        for img in node.assigned_images:
            image_usage[img.id] += 1

    return outline

3.2 SectionSynthesizer Figure Injection
Location: section_synthesizer.py
Update _prepare_source_content():
pythondef _prepare_source_content(self, section: OutlineNode) -> str:
    content_parts = []

    # ... existing text cluster handling ...

    # Structured figure injection (not just text list)
    if section.assigned_images:
        content_parts.append("\n## AVAILABLE FIGURES FOR THIS SECTION\n")
        for i, img in enumerate(section.assigned_images, 1):
            figure_block = f"""
[FIGURE-{i}]
- ID: {img.id}
- Source: {img.source_id}
- Page: {img.page}
- Caption: {img.caption or 'No caption'}
- Context: {img.surrounding_text[:200] if img.surrounding_text else 'N/A'}
- Relevance: {img.relevance_score:.2f}
"""
            content_parts.append(figure_block)

        content_parts.append("""
INSTRUCTION: Reference figures using [FIGURE-N] tags where contextually appropriate.
Each figure reference should add value to the narrative.
""")

    return "\n".join(content_parts)
Add post-synthesis validation:
pythondef _validate_figure_references(self, output: str, assigned_images: list) -> str:
    """Ensure figure references are valid and add missing citations."""
    import re

    # Find all figure references in output
    refs = re.findall(r'\[FIGURE-(\d+)\]', output)
    valid_refs = set(range(1, len(assigned_images) + 1))

    # Flag invalid references
    for ref in refs:
        if int(ref) not in valid_refs:
            logger.warning(f"Invalid figure reference: FIGURE-{ref}")
            output = output.replace(f"[FIGURE-{ref}]", "[FIGURE-INVALID]")

    return output

Phase 4: Database Consolidation (Week 2)
4.1 Problem: Dual Image Databases
DatabaseImagesEmbeddingsPDFs Coveredlibrary.db:visual_elements69,407N/A1,127neurosynth.db:images18,3780 → 18,378203
4.2 Recommended Solution: Federated Query Layer
Create: src/index/unified_image_db.py
pythonclass UnifiedImageDatabase:
    """Federated query across both image databases."""

    def __init__(self):
        self.library_db = sqlite3.connect("library.db")
        self.neurosynth_db = sqlite3.connect("data/neurosynth.db")

    def query_images(
        self,
        source_path: str = None,
        page_number: int = None,
        embedding_query: list[float] = None,
        limit: int = 50
    ) -> list[UnifiedImage]:
        """Query both databases and merge results."""
        results = []

        # Query library.db (visual_elements)
        if source_path or page_number:
            library_results = self._query_library(source_path, page_number)
            results.extend(library_results)

        # Query neurosynth.db (images with embeddings)
        if embedding_query:
            neurosynth_results = self._query_neurosynth_by_embedding(
                embedding_query, limit
            )
            results.extend(neurosynth_results)

        # Deduplicate by content hash
        return self._deduplicate(results)

    def _query_library(self, path: str, page: int) -> list:
        filename = Path(path).stem
        query = """
            SELECT * FROM visual_elements
            WHERE pdf_path LIKE ? AND page_number = ?
        """
        return self.library_db.execute(query, [f"%{filename}%", page]).fetchall()
4.3 Long-term: Single Source of Truth
Migration plan:

Add embedding column to library.db:visual_elements
Run BiomedCLIP on all 69,407 images
Deprecate neurosynth.db:images table
Update all queries to use library.db


Phase 5: Verification & Monitoring
5.1 Health Check Commands
bash# Text Pipeline (should all pass)
sqlite3 data/neurosynth.db "SELECT COUNT(*), SUM(CASE WHEN embedding IS NOT NULL THEN 1 ELSE 0 END) FROM chunks"
# Expected: 36919|36919

curl -s 'http://localhost:6333/collections/deep_dx_collection' | jq '.result.points_count'
# Expected: 11135

# Image Pipeline (verify after fixes)
sqlite3 data/neurosynth.db "SELECT COUNT(*), SUM(CASE WHEN embedding IS NOT NULL THEN 1 ELSE 0 END) FROM images"
# Before: 18378|0
# After:  18378|18378

curl -s 'http://localhost:6333/collections' | jq '.result.collections[].name'
# Should include: "neurosurgical_figures_hybrid"

# Path Resolution
sqlite3 library.db "SELECT COUNT(*) FROM visual_elements"
# Expected: 69407

# Manifest Population
cat output/manifest.json | jq '.sources[0].figures | length'
# Before: 0
# After: >0
5.2 Integration Test Script
Create: tests/test_image_pipeline_e2e.py
pythondef test_full_image_pipeline():
    """End-to-end image pipeline verification."""

    # 1. Path resolution
    from index.database import Database
    db = Database()
    figures = db.get_page_figures("AOSpine", 5)  # Fuzzy match
    assert len(figures) > 0, "Path resolution failed"

    # 2. Embedding exists
    images = db.get_all_images()
    embedded = [i for i in images if i.embedding]
    assert len(embedded) == len(images), f"Only {len(embedded)}/{len(images)} embedded"

    # 3. Qdrant collection exists
    from qdrant_client import QdrantClient
    client = QdrantClient("localhost", port=6333)
    collections = [c.name for c in client.get_collections().collections]
    assert "neurosurgical_figures_hybrid" in collections

    # 4. Retrieval returns images
    from engines.unified_search import SearchMode, UnifiedSearchEngine
    engine = UnifiedSearchEngine()
    result = engine.search("lumbar stenosis MRI", mode=SearchMode.DEEP)
    assert len(result.images) > 0, "Vision search returned no images"

    # 5. Synthesis includes figures
    # (Manual verification or add synthesis test)

    print("✅ All image pipeline tests passed")

Implementation Timeline
PhaseDurationDeliverablesValidation1Days 1-2Path fix, ingestor fix, backfill script18,378 images embedded2Days 2-3UnifiedSearchEngine vision searchImages in RetrievalResult3Days 3-4Outline assignment, synthesis injection[FIGURE-N] tags in output4Week 2Federated DB layerSingle query interface5OngoingHealth checks, monitoringAutomated alerts

Additional Enhancements
A. Image Quality Filtering
Add to ingestor.py:
pythondef _filter_low_quality(self, images: list) -> list:
    """Exclude images unlikely to be clinically useful."""
    return [
        img for img in images
        if img.width >= 200 and img.height >= 200  # Min resolution
        and img.file_size > 10_000  # >10KB
        and not self._is_decorative(img)  # Skip logos, icons
    ]
B. Caption Enhancement
If captions are missing, use VLM to generate:
pythonasync def enhance_caption(self, image: ExtractedImage) -> str:
    if image.caption and len(image.caption) > 20:
        return image.caption

    # Generate caption using vision model
    prompt = "Describe this medical image in one sentence, focusing on anatomical structures and pathology visible."
    return await self.vlm_client.describe_image(image.file_path, prompt)
C. Figure Deduplication
Add hash-based deduplication during extraction:
pythonimport hashlib
from PIL import Image


def compute_perceptual_hash(image_path: Path) -> str:
    img = Image.open(image_path).resize((8, 8)).convert('L')
    pixels = list(img.getdata())
    avg = sum(pixels) / len(pixels)
    bits = ''.join('1' if p > avg else '0' for p in pixels)
    return hashlib.md5(bits.encode()).hexdigest()

Summary: 7 Files to Modify

page_extractor.py — Path resolution fix
database.py — Fuzzy path query + get_all_images()
ingestor.py — Fatal failure on collection creation
unified_search.py — Implement vision search (lines 256-263)
biomed_searcher.py — Add search() method
category_outline.py — Add image assignment logic
section_synthesizer.py — Structured figure injection + validation

New Files:

src/scripts/reindex_images.py
src/index/unified_image_db.py (Phase 4)
tests/test_image_pipeline_e2e.py
RetryPotential improvements.
1. Unified Search Engine (src/index/unified_search.py)
Function: The central "Brain" for information retrieval. It acts as a single point of entry for all search needs.
- Modes:
  - Fast: Pure Vector Search (Qdrant) - <200ms
  - Balanced: Vector + Keyword (BM25) - ~500ms
  - pastedassess analyse combine  these upgrade and fix plans into one unified exhaustive accurate  plan for neurosynth:Synthesized diagnostic findings into unified, prioritized remediation strategy.17sThe user wants me to analyze and combine all the diagnostic documents and fix plans into one unified, exhaustive, and accurate plan for NeuroSynth. Let me carefully review all the documents and the previous response I gave to create a comprehensive, non-redundant plan.
Key findings from the documents:

Text Pipeline: FULLY OPERATIONAL

36,919 chunks with 100% embeddings
Qdrant deep_dx_collection has 11,135 points with vectors
LibraryToDeepDxBridge is the active pipeline (NOT DeepDxIngestor)


Image Pipeline: BROKEN at multiple points

18,378 images in neurosynth.db with 0 embeddings
69,407 images in library.db (separate system)
Missing Qdrant collection: neurosurgical_figures_hybrid
Silent failure in BiomedIngestor
Path mismatch between databases
UnifiedSearchEngine has TODO stub for vision search
No image assignment logic in outline generator


Critical Failures Identified:

Path mismatch between Reference Library and NeuroSynth
Dual image databases with no sync
Silent failure in ingestor.py:50-64
UnifiedSearchEngine vision search is a TODO stub
Missing image assignment in CategoryOutlineGenerator
Fragile figure integration in SectionSynthesizer


Proposed Improvements (from Doc 3):

Graph Reasoning enhancement
Query Expansion (HyDE)
Active Retrieval (agentic loop)
Citation Granularity
YOLOv8 fine-tuning



Let me create a unified plan that:

Consolidates all fixes without redundancy
Prioritizes correctly (P0 blocking issues first)
Includes all enhancements
Provides exact file locations and code
Has clear validation steps

I'll develop a comprehensive repair strategy targeting the image pipeline's critical infrastructure. The plan will focus on resolving database synchronization, implementing robust image embedding processes, and integrating vision search capabilities. Specific interventions include:

Database Reconciliation (/src/database/sync_manager.py)

Merge neurosynth.db and library.db image collections
Implement bidirectional sync mechanism
Create unified image tracking schema


Image Embedding Pipeline (/src/ingestors/image_embedder.py)

Replace silent failures with explicit error handling
Implement YOLOv8 fine-tuned embedding generation
Add comprehensive logging for embedding processes


Vision Search Integration (/src/search/unified_search_engine.py)

Replace TODO stub with full implementation
Develop multi-modal retrieval logic
Create hybrid text-image search capabilities


Outline Generation Improvements (/src/generators/category_outline_generator.py)

Add robust image assignment algorithm
Implement context-aware figure selection
Enhance semantic matching between text and images



Validation will involve comprehensive test suites, performance benchmarking, and incremental rollout strategies to ensure system stability.NeuroSynth Unified Fix & Enhancement Plan
Executive Summary
PipelineStatusRoot CauseFix ComplexityText✅ 100% OperationalN/ANone neededImage❌ Multi-point failureSilent ingestor failure → 0 embeddings → no retrieval → text-only synthesisMedium (7 files, ~400 LOC)
Verified State:
SQLite: 226 sources, 36,919 chunks (100% embedded), 18,378 images (0% embedded)
Qdrant: deep_dx_collection ✅ (11,135 pts) | neurosurgical_figures_hybrid ❌ (MISSING)

Architecture: The Communication Breakdown
TEXT PIPELINE ✅                          IMAGE PIPELINE ❌
─────────────────                         ─────────────────
PDF → PropositionChunker                  PDF → SmartImageExtractor
  ↓                                         ↓
VoyageClient.embed_texts() ✅             BiomedIngestor.ingest_figures()
  ↓                                         ↓ ❌ SILENT FAILURE (line 64)
SQLite chunks + Qdrant ✅                 SQLite images (no embeddings)
  ↓                                         ↓ ❌ NO QDRANT COLLECTION
UnifiedSearchEngine ✅                    UnifiedSearchEngine
  ↓                                         ↓ ❌ TODO STUB (line 260)
SectionSynthesizer ✅                     SectionSynthesizer
  ↓                                         ↓ ❌ NO IMAGE ASSIGNMENT
Chapter with citations ✅                 TEXT-ONLY output ❌

Phase 1: Critical Infrastructure (Days 1-2)
1.1 Ingestor Fatal Error Handling (P0)
File: src/neurosynth/ai/ingestor.py:50-64
Problem: Silent failure allows execution to continue without Qdrant collection
Fix:
pythondef _ensure_collection_exists(self):
    """Ensure Qdrant collection exists. FATAL on failure."""
    try:
        collections = self.client.get_collections().collections
        exists = any(c.name == self.COLLECTION_NAME for c in collections)
        if not exists:
            self.client.create_collection(
                collection_name=self.COLLECTION_NAME,
                vectors_config={
                    "biomed": VectorParams(size=512, distance=Distance.COSINE),
                },
            )
            logger.info(f"✅ Created Qdrant collection: {self.COLLECTION_NAME}")
    except Exception as e:
        self.client = None
        logger.error(
            f"❌ CRITICAL: Qdrant initialization failed\n"
            f"   Collection: {self.COLLECTION_NAME}\n"
            f"   Error: {e}\n"
            f"   Action: docker-compose up -d qdrant"
        )
        raise RuntimeError(
            f"Qdrant initialization failed for '{self.COLLECTION_NAME}'. "
            f"Cannot proceed with image indexing."
        ) from e
Validation:
bash./venv/bin/python -c "from neurosynth.ai.ingestor import BiomedIngestor; BiomedIngestor()"
curl http://localhost:6333/collections | grep neurosurgical_figures_hybrid

1.2 Database Methods for Image Processing (P0)
File: src/index/database.py (add after ~line 530)
pythondef get_all_images(self) -> list[ExtractedImage]:
    """Get ALL images regardless of embedding status."""
    with self._get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM images ORDER BY source_id, page"
        ).fetchall()
        return [self._row_to_image(row) for row in rows]

def get_images_without_embeddings(self) -> list[ExtractedImage]:
    """Get images needing embedding generation."""
    with self._get_conn() as conn:
        rows = conn.execute(
            """SELECT * FROM images
               WHERE embedding IS NULL OR embedding = ''
               ORDER BY source_id, page"""
        ).fetchall()
        return [self._row_to_image(row) for row in rows]

def update_image_embedding(self, image_id: str, embedding: list[float]):
    """Update embedding for existing image."""
    with self._get_conn() as conn:
        conn.execute(
            "UPDATE images SET embedding = ? WHERE id = ?",
            (self._serialize_embedding(embedding), image_id)
        )
        conn.commit()
Validation:
bash./venv/bin/python -c "
from index.database import Database
db = Database()
print(f'Images without embeddings: {len(db.get_images_without_embeddings())}')
# Expected: 18378
"

1.3 Path Resolution Fix (P0)
File: src/reference_library/cache/database.py:1068-1101
Problem: Path mismatch between original PDFs and extracted mini-PDFs causes 0 figures returned
Fix:
pythondef get_page_figures(
    self, pdf_path: Path, page_number: int, checksum: Optional[str] = None
) -> list[dict]:
    """Get figures with 3-tier path resolution."""
    with self._get_connection() as conn:
        # Tier 1: Exact match
        query = "SELECT * FROM visual_elements WHERE pdf_path = ? AND page_number = ?"
        params = [str(pdf_path), page_number]
        if checksum:
            query += " AND file_checksum = ?"
            params.append(checksum)

        cursor = conn.execute(query + " ORDER BY id", params)
        figures = self._hydrate_figures(cursor)
        if figures:
            return figures

        # Tier 2: Filename fuzzy match (handles mini-PDFs)
        query = """SELECT * FROM visual_elements
                   WHERE pdf_path LIKE '%' || ? || '%' AND page_number = ?"""
        params = [pdf_path.name, page_number]
        if checksum:
            query += " AND file_checksum = ?"
            params.append(checksum)

        cursor = conn.execute(query + " ORDER BY id", params)
        figures = self._hydrate_figures(cursor)
        if figures:
            return figures

        # Tier 3: Stem match (handles paper.v1.pdf → paper)
        filename_stem = pdf_path.stem.split('.')[0]
        cursor = conn.execute(query + " ORDER BY id", [filename_stem, page_number])
        return self._hydrate_figures(cursor)

def _hydrate_figures(self, cursor) -> list[dict]:
    """Convert cursor to figure dicts with JSON parsing."""
    figures = []
    for row in cursor:
        fig = dict(row)
        if fig.get("bbox"):
            try:
                fig["bbox"] = tuple(json.loads(fig["bbox"]))
            except (json.JSONDecodeError, TypeError):
                fig["bbox"] = None
        figures.append(fig)
    return figures
Validation:
bashsqlite3 library.db "SELECT COUNT(*) FROM visual_elements WHERE pdf_path LIKE '%AOSpine%' AND page_number BETWEEN 1 AND 11"
# Expected: 1604

Phase 2: Backfill Pipeline (Days 2-3)
2.1 Production Reindexing Script
File: src/scripts/reindex_images.py (CREATE NEW)
python#!/usr/bin/env python3
"""
Image Embedding Backfill with Checkpoint Resumption
Features: 4-tier path resolution, atomic checkpoints, tqdm progress, error categorization
"""
import argparse
import json
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

import numpy as np
from tqdm import tqdm

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from index.database import Database
from neurosynth.ai.biomed_searcher import BiomedCLIPSearcher
from neurosynth.ai.ingestor import BiomedIngestor

# Configuration
DB_PATH = Path("data/neurosynth.db")
CHECKPOINT_FILE = Path("data/reindex_checkpoint.json")
BATCH_SIZE = 32
BASE_PATHS = [
    Path("/Users/ramihatoum/neurosynth/assets/extracted_images"),
    Path("/Users/ramihatoum/neurosynth/reference-library/data/images"),
    Path("assets/extracted_images"),
]

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("logs/reindex_images.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class CheckpointManager:
    """Atomic checkpoint management for resumable processing."""

    def __init__(self, filepath: Path):
        self.filepath = filepath
        self.state = self._load()
        self.dirty = False

    def _load(self) -> dict:
        if self.filepath.exists():
            with open(self.filepath) as f:
                state = json.load(f)
                logger.info(f"📂 Resuming: {len(state['processed_ids'])} already done")
                return state
        return {
            "processed_ids": [],
            "failed": {"path": [], "embed": [], "db": []},
            "stats": {"success": 0, "fail_path": 0, "fail_embed": 0, "fail_db": 0},
            "started_at": datetime.now().isoformat()
        }

    def save(self):
        if not self.dirty:
            return
        self.state["last_updated"] = datetime.now().isoformat()
        temp = self.filepath.with_suffix(".tmp")
        with open(temp, "w") as f:
            json.dump(self.state, f, indent=2)
        temp.replace(self.filepath)
        self.dirty = False

    def mark_success(self, img_id: str):
        self.state["processed_ids"].append(img_id)
        self.state["stats"]["success"] += 1
        self.dirty = True

    def mark_failed(self, img_id: str, category: str):
        self.state["processed_ids"].append(img_id)
        self.state["failed"][category].append(img_id)
        self.state["stats"][f"fail_{category}"] += 1
        self.dirty = True

    def is_processed(self, img_id: str) -> bool:
        return img_id in self.state["processed_ids"]


def resolve_path(stored_path: Path) -> Optional[Path]:
    """4-tier path resolution strategy."""
    # Tier 1: Direct
    if stored_path.exists():
        return stored_path

    filename = stored_path.name

    # Tier 2: Base paths
    for base in BASE_PATHS:
        candidate = base / filename
        if candidate.exists():
            return candidate

    # Tier 3: Recursive glob
    for base in BASE_PATHS:
        if base.exists():
            matches = list(base.rglob(filename))
            if matches:
                return matches[0]

    # Tier 4: Extension variants
    stem = stored_path.stem
    for base in BASE_PATHS:
        for ext in ['.png', '.jpg', '.jpeg']:
            candidate = base / f"{stem}{ext}"
            if candidate.exists():
                return candidate

    return None


class ImageAdapter:
    """Duck-type adapter for BiomedIngestor compatibility."""
    def __init__(self, img, resolved_path: Path):
        self.local_path = resolved_path
        self.image_filename = img.id
        self.source_pdf = img.source_id
        self.caption = img.caption or ""
        self.context = img.surrounding_text or ""
        self.page_num = img.page or 1


def main():
    parser = argparse.ArgumentParser(description="Reindex images with BiomedCLIP")
    parser.add_argument("--dry-run", action="store_true", help="Process first 32 only")
    parser.add_argument("--fresh", action="store_true", help="Ignore checkpoint")
    parser.add_argument("--limit", type=int, help="Limit total images")
    args = parser.parse_args()

    # Fresh start
    if args.fresh and CHECKPOINT_FILE.exists():
        CHECKPOINT_FILE.unlink()
        logger.info("🗑️ Checkpoint cleared")

    # Initialize
    db = Database(str(DB_PATH))
    embedder = BiomedCLIPSearcher()
    ingestor = BiomedIngestor()
    ckpt = CheckpointManager(CHECKPOINT_FILE)

    # Get images
    images = db.get_images_without_embeddings()
    total = len(images)
    logger.info(f"Found {total:,} images without embeddings")

    if total == 0:
        logger.info("✅ All images already have embeddings!")
        return

    if args.dry_run:
        images = images[:BATCH_SIZE]
        logger.info(f"🧪 Dry run: {len(images)} images")
    elif args.limit:
        images = images[:args.limit]

    # Process
    with tqdm(total=len(images), desc="Reindexing") as pbar:
        batch_imgs, batch_paths = [], []

        for img in images:
            if ckpt.is_processed(img.id):
                pbar.update(1)
                continue

            resolved = resolve_path(img.file_path)
            if not resolved:
                ckpt.mark_failed(img.id, "path")
                pbar.update(1)
                continue

            batch_imgs.append(img)
            batch_paths.append(resolved)

            if len(batch_imgs) >= BATCH_SIZE:
                _process_batch(batch_imgs, batch_paths, db, embedder, ingestor, ckpt)
                pbar.update(len(batch_imgs))
                batch_imgs, batch_paths = [], []
                ckpt.save()

        # Final batch
        if batch_imgs:
            _process_batch(batch_imgs, batch_paths, db, embedder, ingestor, ckpt)
            pbar.update(len(batch_imgs))
            ckpt.save()

    # Report
    stats = ckpt.state["stats"]
    logger.info("=" * 50)
    logger.info("📊 COMPLETE")
    logger.info(f"   Success:     {stats['success']:,}")
    logger.info(f"   Failed path: {stats['fail_path']:,}")
    logger.info(f"   Failed embed:{stats['fail_embed']:,}")
    logger.info(f"   Failed DB:   {stats['fail_db']:,}")


def _process_batch(imgs, paths, db, embedder, ingestor, ckpt):
    """Process a batch of images."""
    try:
        vectors = embedder.embed_image([str(p) for p in paths])

        for img, vec in zip(imgs, vectors):
            try:
                db.update_image_embedding(img.id, vec.tolist())
                ckpt.mark_success(img.id)
            except Exception as e:
                logger.error(f"DB error {img.id}: {e}")
                ckpt.mark_failed(img.id, "db")

        # Qdrant upsert
        adapted = [ImageAdapter(img, path) for img, path in zip(imgs, paths)]
        ingestor.ingest_figures(adapted)

    except Exception as e:
        logger.error(f"Batch embedding failed: {e}")
        for img in imgs:
            ckpt.mark_failed(img.id, "embed")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logger.warning("\n⚠️ Interrupted - progress saved to checkpoint")
        sys.exit(130)
Execution:
bash# Dry run (test 32 images)
./venv/bin/python src/scripts/reindex_images.py --dry-run

# Full run (~2-4 hours for 18k images)
./venv/bin/python src/scripts/reindex_images.py

# Resume if interrupted
./venv/bin/python src/scripts/reindex_images.py

# Fresh start
./venv/bin/python src/scripts/reindex_images.py --fresh
Validation:
bashsqlite3 data/neurosynth.db "SELECT COUNT(*) FROM images WHERE embedding IS NOT NULL"
# Expected: 18378

curl -s http://localhost:6333/collections/neurosurgical_figures_hybrid | jq '.result.points_count'
# Expected: 18378

Phase 3: Search & Synthesis Integration (Days 3-4)
3.1 Vision Search Implementation
File: src/index/unified_search.py:256-263
Replace TODO stub:
python# 3. Image Search (Vision Mode)
images = []
if self.vision and mode in [SearchMode.DEEP, SearchMode.REASONING]:
    try:
        query_vec = self.vision.embed_text(query)
        if len(query_vec) > 0:
            # CLIP text-image scores are lower than text-text (use 0.15 threshold)
            limit = 10 if mode == SearchMode.DEEP else 20

            hits = self.qdrant.client.search(
                collection_name="neurosurgical_figures_hybrid",
                query_vector=("biomed", query_vec[0].tolist()),
                limit=limit,
                score_threshold=0.15,
                with_payload=True,
            )

            for hit in hits:
                p = hit.payload
                img = ExtractedImage(
                    id=p.get("filename", "unknown"),
                    source_id=p.get("source_pdf", "unknown"),
                    page=p.get("page_num", 0),
                    file_path=Path(p.get("path", "")),
                    caption=p.get("caption", ""),
                    surrounding_text=p.get("context", ""),
                    image_type=ImageType.ILLUSTRATION,
                    modality=p.get("modality", "unknown"),
                    detected_regions=p.get("detected_regions", []),
                    region_confidence=p.get("region_confidence", 0.0),
                )
                images.append((img, hit.score))

            images.sort(key=lambda x: x[1], reverse=True)
            logger.info(f"Vision search: {len(images)} images")

    except Exception as e:
        warnings.append(f"Vision search failed: {e}")
        logger.warning(f"Vision search error: {e}")
Update return (~line 296):
pythonreturn RetrievalResult(
    chunks=final_chunks,
    images=[img for img, _ in images],  # Was: images=[]
    ...
)

3.2 Image Assignment to Outline Sections
File: src/neurosynth/synthesis/category_outline.py (add after ~line 223)
pythondef assign_images_to_outline(
    self,
    nodes: list[OutlineNode],
    db: Database,
    vision_searcher: "BiomedCLIPSearcher",
    top_k: int = 3,
    score_threshold: float = 0.2,
) -> list[OutlineNode]:
    """
    Assign relevant images to sections using semantic similarity.

    Uses Top-K strategy with lowered threshold (0.2) because
    CLIP text-image scores are naturally lower than text-text.
    """
    from collections import defaultdict

    import numpy as np

    all_images = db.get_all_images_with_embeddings()
    if not all_images:
        logger.warning("No embedded images available")
        return nodes

    image_usage = defaultdict(int)
    max_reuse = 2

    for node in nodes:
        section_query = f"{node.title}. {node.description or ''}"
        query_vec = vision_searcher.embed_text(section_query)

        if len(query_vec) == 0:
            continue

        query_vec = query_vec[0]
        scored = []

        for img in all_images:
            if image_usage[img.id] >= max_reuse:
                continue
            if img.embedding is None:
                continue

            img_vec = np.array(img.embedding)
            sim = np.dot(query_vec, img_vec) / (
                np.linalg.norm(query_vec) * np.linalg.norm(img_vec)
            )

            if sim > score_threshold:
                scored.append((img, float(sim)))

        scored.sort(key=lambda x: x[1], reverse=True)

        for img, score in scored[:top_k]:
            node.assigned_sources.append({
                "type": "image",
                "id": img.id,
                "source_id": img.source_id,
                "page": img.page,
                "file_path": str(img.file_path),
                "caption": img.caption or "No caption",
                "modality": getattr(img, 'modality', 'unknown'),
                "relevance_score": round(score, 3),
            })
            image_usage[img.id] += 1

        if scored[:top_k]:
            logger.info(f"'{node.title}': {len(scored[:top_k])} images assigned")

    return nodes
Integration in generate() method:
python# After outline generation, before return:
try:
    from neurosynth.ai.biomed_searcher import BiomedCLIPSearcher
    vision = BiomedCLIPSearcher()
    outline = self.assign_images_to_outline(outline, db, vision)
except Exception as e:
    logger.warning(f"Image assignment skipped: {e}")

return outline

3.3 Section Synthesizer Figure Integration
File: src/neurosynth/synthesis/section.py
Update _prepare_source_content():
pythondef _prepare_source_content(self, assigned_sources: list[dict]) -> str:
    """Prepare source content with separated text and image handling."""
    text_sources = []
    image_sources = []

    for source in assigned_sources:
        if source.get("type") == "image":
            image_sources.append(source)
        else:
            text_sources.append(source)

    content_parts = []

    # Text sources (existing logic)
    for source in text_sources:
        content_parts.append(self._format_text_source(source))

    # Image sources (structured format)
    if image_sources:
        content_parts.append("\n## AVAILABLE FIGURES\n")
        for i, img in enumerate(image_sources, 1):
            content_parts.append(
                f"[FIGURE-{i}] (ID: {img['id']}, Type: {img.get('modality', 'unknown')})\n"
                f"Caption: {img.get('caption', 'No caption')}\n"
                f"Relevance: {img.get('relevance_score', 'N/A')}\n"
            )
        content_parts.append(
            "\nINSTRUCTION: Reference figures using [FIGURE-N] tags where appropriate.\n"
        )

    return "\n\n".join(content_parts)
Add validation method:
pythondef _validate_figure_references(self, content: str, num_figures: int) -> str:
    """Replace invalid [FIGURE-N] references."""
    import re

    def replace_invalid(match):
        num = int(match.group(1))
        if num > num_figures:
            logger.warning(f"LLM hallucinated FIGURE-{num} (max: {num_figures})")
            return "[FIGURE-INVALID]"
        return match.group(0)

    return re.sub(r'\[FIGURE-(\d+)\]', replace_invalid, content)

Phase 4: Database Consolidation (Week 2)
4.1 The Dual Database Problem
DatabaseTableCountEmbeddedPDFslibrary.dbvisual_elements69,407N/A1,127neurosynth.dbimages18,3780→18,378203
Recommended Solution: Federated Query Layer
File: src/index/unified_image_db.py (CREATE NEW)
python"""Federated query layer for dual image databases."""
import sqlite3
from pathlib import Path
from typing import Optional


class UnifiedImageDatabase:
    """Query both image databases with unified interface."""

    def __init__(self):
        self.library_db = sqlite3.connect("library.db")
        self.library_db.row_factory = sqlite3.Row
        self.neurosynth_db = sqlite3.connect("data/neurosynth.db")
        self.neurosynth_db.row_factory = sqlite3.Row

    def query_by_source(
        self,
        source_path: str,
        page: Optional[int] = None
    ) -> list[dict]:
        """Query both databases by source path."""
        results = []
        filename = Path(source_path).stem.split('.')[0]

        # Query library.db
        query = """
            SELECT *, 'library' as db_source
            FROM visual_elements
            WHERE pdf_path LIKE ?
        """
        params = [f"%{filename}%"]
        if page:
            query += " AND page_number = ?"
            params.append(page)

        results.extend([dict(r) for r in self.library_db.execute(query, params)])

        # Query neurosynth.db
        query = """
            SELECT *, 'neurosynth' as db_source
            FROM images
            WHERE source_id LIKE ?
        """
        params = [f"%{filename}%"]
        if page:
            query += " AND page = ?"
            params.append(page)

        results.extend([dict(r) for r in self.neurosynth_db.execute(query, params)])

        return self._deduplicate(results)

    def _deduplicate(self, results: list[dict]) -> list[dict]:
        """Remove duplicates by content hash or filename."""
        seen = set()
        unique = []
        for r in results:
            key = r.get("file_checksum") or r.get("id") or r.get("file_path")
            if key not in seen:
                seen.add(key)
                unique.append(r)
        return unique

Phase 5: Enhancements (Week 3+)
5.1 Search Engine Improvements
EnhancementDescriptionFilePriorityHyDEHypothetical Document Embeddings for ambiguous queriesunified_search.pyP2Multi-hop ReasoningRAPTOR integration for "Why/How" questionsunified_search.pyP2Query ExpansionSynonym/concept expansionunified_search.pyP3
HyDE Implementation Sketch:
pythonasync def hyde_search(self, query: str) -> list[Chunk]:
    """Generate hypothetical answer, embed it, search for similar real content."""
    # 1. Generate hypothetical answer
    hypothetical = await self.llm.generate(
        f"Write a detailed paragraph answering: {query}"
    )

    # 2. Embed the hypothetical
    hyde_vec = self.embedder.embed_texts([hypothetical])[0]

    # 3. Search with hypothetical embedding
    return self.vector_search(hyde_vec)
5.2 Synthesis Engine Improvements
EnhancementDescriptionFilePriorityActive RetrievalAgentic loop for insufficient chunkssection.pyP2Citation GranularitySentence-level [SourceID:PageNum] tagssection.pyP2Conflict DetectionIdentify contradicting sourcessection.pyP3
Active Retrieval Sketch:
pythonasync def synthesize_with_retrieval(self, section: OutlineNode) -> str:
    """Synthesize with ability to request more information."""
    chunks = section.assigned_clusters

    for iteration in range(3):  # Max 3 retrieval rounds
        result = await self.llm.generate(
            prompt=self._build_prompt(section, chunks),
            tools=[{"name": "request_more_info", "description": "..."}]
        )

        if not result.tool_calls:
            return result.content

        # Handle retrieval request
        new_query = result.tool_calls[0].arguments["query"]
        new_chunks = await self.search_engine.search(new_query)
        chunks.extend(new_chunks)

    return result.content
5.3 Vision Pipeline Improvements
EnhancementDescriptionFilePriorityYOLOv8 Fine-tuningTrain on neurosurgical datasetobject_detector.pyP3Caption EnhancementVLM-generated captions for missingbiomed_searcher.pyP2Quality FilteringFilter decorative/low-res imagesingestor.pyP3
Caption Enhancement:
pythonasync def enhance_caption(self, image: ExtractedImage) -> str:
    """Generate caption if missing using VLM."""
    if image.caption and len(image.caption) > 20:
        return image.caption

    return await self.vlm.describe_image(
        image.file_path,
        "Describe this medical image in one sentence, focusing on anatomical structures and pathology."
    )

Validation Checklist
Phase 1 Complete
bash# Ingestor doesn't fail silently
./venv/bin/python -c "from neurosynth.ai.ingestor import BiomedIngestor; BiomedIngestor()"

# Database methods exist
./venv/bin/python -c "from index.database import Database; db=Database(); print(len(db.get_images_without_embeddings()))"

# Path resolution works
sqlite3 library.db "SELECT COUNT(*) FROM visual_elements WHERE pdf_path LIKE '%AOSpine%'"
Phase 2 Complete
bash# All images embedded
sqlite3 data/neurosynth.db "SELECT COUNT(*) FROM images WHERE embedding IS NOT NULL"
# Expected: 18378

# Qdrant populated
curl -s http://localhost:6333/collections/neurosurgical_figures_hybrid | jq '.result.points_count'
# Expected: 18378
Phase 3 Complete
bash# Vision search returns images
./venv/bin/python -c "
from index.unified_search import UnifiedSearchEngine, SearchMode
from index.database import Database
engine = UnifiedSearchEngine(Database())
result = engine.search('spinal cord MRI', mode=SearchMode.DEEP)
print(f'Images: {len(result.images)}')
assert len(result.images) > 0
"

# Synthesis includes figures
neurosynth generate --topic "Lumbar Discectomy" --output test_chapter.md
grep -c "FIGURE-" test_chapter.md
# Expected: > 0
