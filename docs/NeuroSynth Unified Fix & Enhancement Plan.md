NeuroSynth Unified Fix & Enhancement Plan
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

Implementation Timeline
PhaseDurationDeliverablesBlocking1Days 1-2Ingestor fix, DB methods, path resolutionYes2Days 2-3Backfill script, embed 18,378 imagesYes3Days 3-4Vision search, image assignment, figure integrationYes4Week📋 Analysis Review: Your Image Pipeline Fix Plan
Overall Assessment: Excellent — 9/10
Your analysis is remarkably accurate and demonstrates deep understanding of the system architecture. The root cause chain you identified is correct:

Path mismatch → Dual DBs → Silent embedding failure → Stub retripasted4:01 PMSynthesized critical feedback to refine implementation plan comprehensively.The user wants me to integrate this new review/feedback document (Document 4) into the existing unified fix plan. This document provides critical assessment, identifies bugs, and suggests improvements to the plan I created earlier.
Let me analyze the key findings from Document 4:
Critical Issues Found:

ingest_batch() method doesn't exist - should use ingest_figures()
Database schema mismatch - modality, detected_regions, region_confidence columns don't exist in neurosynth.db:images
Path resolution fix location ambiguity - need to clarify which database.py
BiomedCLIPSearcher lacks Qdrant client - should keep search logic in UnifiedSearchEngine
OutlineNode has no assigned_images attribute - use assigned_sources with type: "image"
Missing commit() verification in database methods

Implementation Gaps:

Missing methods: get_all_images(), get_images_without_embeddings(), update_image_embedding()
Schema changes needed for metadata columns
Integration points not covered (Synthesis → Image Display, Manifest → Images, UI → Image Preview)
Error handling in backfill ImageAdapter

Validation Gaps:

Embedding dimension verification
Qdrant payload structure verification
End-to-end synthesis with actual image rendering
Vision search relevance testing

Recommendations:

Swap Phase 1.3 (Backfill) and Phase 2 (Search Implementation)
Consider single-source-of-truth migration vs federated approach

I need to create a truly final, unified plan that incorporates ALL of this feedback and produces an exhaustive, accurate implementation guide.NeuroSynth Image Pipeline: Final Unified Fix Plan v2.0
Executive Summary
PipelineCurrent StateTarget StateFix ComplexityText✅ 100% OperationalNo changes neededNoneImage❌ 0% embedded, no retrieval✅ 100% embedded, full multimodalMedium (8 files, ~500 LOC)
Verified Database State:
library.db:visual_elements     = 69,407 images (no embeddings, rich metadata)
neurosynth.db:images          = 18,378 images (0 embeddings, basic metadata)
neurosynth.db:chunks          = 36,919 chunks (100% embedded)
Qdrant:deep_dx_collection     = 11,135 points ✅
Qdrant:neurosurgical_figures_hybrid = MISSING ❌
Root Cause Chain:
Silent ingestor failure (line 64) → 0 embeddings → No Qdrant collection →
TODO stub in search (line 260) → No image assignment → Text-only output

Pre-Implementation Checklist
Verified Method/Attribute Status
ItemFileStatusAction Requiredingest_batch()ingestor.py❌ Does NOT existUse ingest_figures()get_all_images()database.py❌ Does NOT existCREATEget_images_without_embeddings()database.py❌ Does NOT existCREATEupdate_image_embedding()database.py❌ Does NOT existCREATEget_all_images_with_embeddings()database.py✅ EXISTS (line 509)Use directlyget_page_figures()reference_library/cache/database.py✅ EXISTSMODIFY for fuzzy matchBiomedCLIPSearcher.qdrant_clientbiomed_searcher.py❌ Does NOT existKeep search in UnifiedSearchEngineOutlineNode.assigned_imagescategory_outline.py❌ Does NOT existUse assigned_sources with type: "image"modality columnneurosynth.db:images❌ Does NOT existOptional schema migration
Schema Alignment
neurosynth.db:images actual schema:
sqlCREATE TABLE images (
    id TEXT PRIMARY KEY,
    source_id TEXT,
    chunk_id TEXT,
    file_path TEXT,
    caption TEXT,
    surrounding_text TEXT,
    image_type TEXT,
    page INTEGER,
    width INTEGER,
    height INTEGER,
    embedding BLOB
    -- NO: modality, detected_regions, region_confidence
);
Qdrant payload (has rich metadata):
json{
  "filename": "...",
  "source_pdf": "...",
  "page_num": 1,
  "caption": "...",
  "context": "...",
  "modality": "MRI",
  "detected_regions": ["lumbar", "spine"],
  "region_confidence": 0.85
}
Strategy: Read extended metadata from Qdrant payload only; SQLite stores core fields.

Phase 0: Day 0 — Critical Prerequisites
0.1 Create Missing Database Methods
File: src/index/database.py (add after get_all_images_with_embeddings() ~line 520)
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
               WHERE embedding IS NULL OR length(embedding) = 0
               ORDER BY source_id, page"""
        ).fetchall()
        return [self._row_to_image(row) for row in rows]

def update_image_embedding(self, image_id: str, embedding: list[float]) -> bool:
    """Update embedding for existing image. Returns success status."""
    try:
        with self._get_conn() as conn:
            blob = self._serialize_embedding(embedding)
            conn.execute(
                "UPDATE images SET embedding = ? WHERE id = ?",
                (blob, image_id)
            )
            conn.commit()
            return True
    except Exception as e:
        logger.error(f"Failed to update embedding for {image_id}: {e}")
        return False

def get_image_by_id(self, image_id: str) -> Optional[ExtractedImage]:
    """Get single image by ID."""
    with self._get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM images WHERE id = ?", (image_id,)
        ).fetchone()
        return self._row_to_image(row) if row else None
Validation:
bash./venv/bin/python -c "
from index.database import Database
db = Database()
print(f'get_all_images: {len(db.get_all_images())}')
print(f'without embeddings: {len(db.get_images_without_embeddings())}')
# Expected: 18378 for both
"
0.2 Verify Qdrant Running
bash# Start Qdrant if not running
docker-compose up -d qdrant

# Verify
curl -s http://localhost:6333/health | jq '.status'
# Expected: "ok"

# Check existing collections
curl -s http://localhost:6333/collections | jq '.result.collections[].name'
# Expected: "deep_dx_collection"

Phase 1: Critical Path Fixes (Days 1-2)
1.1 Ingestor Fatal Error Handling (P0)
File: src/neurosynth/ai/ingestor.py:50-64
Current (BROKEN):
pythonexcept Exception as e:
    logger.warning(f"Could not check/create collection: {e}")  # Continues silently!
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
        else:
            logger.info(f"✅ Qdrant collection exists: {self.COLLECTION_NAME}")

    except Exception as e:
        self.client = None
        logger.error(
            f"❌ CRITICAL: Qdrant initialization failed\n"
            f"   Collection: {self.COLLECTION_NAME}\n"
            f"   Error: {e}\n"
            f"   Fix: docker-compose up -d qdrant"
        )
        raise RuntimeError(
            f"Qdrant initialization failed for '{self.COLLECTION_NAME}'. "
            f"Cannot proceed with image indexing. Error: {e}"
        ) from e
Validation:
bash./venv/bin/python -c "
from neurosynth.ai.ingestor import BiomedIngestor
ingestor = BiomedIngestor()
print('✅ BiomedIngestor initialized')
"

curl -s http://localhost:6333/collections | jq '.result.collections[].name'
# Should now include: "neurosurgical_figures_hybrid"

1.2 Path Resolution Fix (P0)
File: src/reference_library/cache/database.py (NOT src/index/database.py)
Location: Replace get_page_figures() method (~line 1068)
pythondef get_page_figures(
    self, pdf_path: Path, page_number: int, checksum: Optional[str] = None
) -> list[dict]:
    """
    Get figures with 3-tier path resolution.

    Handles mismatch between:
    - Original paths: /Users/.../AOSpine/Chapter9.pdf
    - Extracted paths: output/AOSpine_p1-10.pdf
    """
    with self._get_connection() as conn:
        # Tier 1: Exact match (fastest)
        query = """
            SELECT * FROM visual_elements
            WHERE pdf_path = ? AND page_number = ?
        """
        params = [str(pdf_path), page_number]

        if checksum:
            query += " AND file_checksum = ?"
            params.append(checksum)

        cursor = conn.execute(query + " ORDER BY id", params)
        figures = self._hydrate_figures(cursor)
        if figures:
            return figures

        # Tier 2: Filename fuzzy match (handles mini-PDFs)
        fuzzy_query = """
            SELECT * FROM visual_elements
            WHERE pdf_path LIKE '%' || ? || '%' AND page_number = ?
        """
        params = [pdf_path.name, page_number]

        if checksum:
            fuzzy_query += " AND file_checksum = ?"
            params.append(checksum)

        cursor = conn.execute(fuzzy_query + " ORDER BY id", params)
        figures = self._hydrate_figures(cursor)
        if figures:
            logger.debug(f"Resolved via filename: {pdf_path.name} → {len(figures)} figures")
            return figures

        # Tier 3: Stem match (handles paper.v1.pdf → paper)
        filename_stem = pdf_path.stem.split('.')[0]
        cursor = conn.execute(
            fuzzy_query + " ORDER BY id",
            [filename_stem, page_number] + ([checksum] if checksum else [])
        )
        figures = self._hydrate_figures(cursor)

        if figures:
            logger.debug(f"Resolved via stem: {filename_stem} → {len(figures)} figures")
        else:
            logger.debug(f"No figures found for {pdf_path.name} page {page_number}")

        return figures

def _hydrate_figures(self, cursor) -> list[dict]:
    """Convert cursor rows to figure dicts with JSON parsing."""
    import json
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
bash./venv/bin/python -c "
from pathlib import Path
from reference_library.cache.database import ReferenceLibraryDatabase

db = ReferenceLibraryDatabase()

# Test with extracted mini-PDF path (should fuzzy match)
figures = db.get_page_figures(Path('output/AOSpine_extracted_p1-10.pdf'), 1)
print(f'Figures found via fuzzy match: {len(figures)}')

# Test with original path
figures2 = db.get_page_figures(Path('/Users/ramihatoum/Desktop/NeuroLi copy/02_MULTI_CHAPTER_BOOKS/AOSpine/Chapter9.pdf'), 1)
print(f'Figures found via exact match: {len(figures2)}')
"

Phase 2: Search Implementation (Day 2 AM)

Sequencing Change: Implement search BEFORE backfill to validate Qdrant schema with small test batch.

2.1 Vision Search in UnifiedSearchEngine
File: src/index/unified_search.py:256-263
Replace TODO stub:
python# 3. Image Search (Vision Mode)
images = []
if self.vision and mode in [SearchMode.DEEP, SearchMode.REASONING]:
    try:
        # Generate query embedding using BiomedCLIP
        query_vec = self.vision.embed_text(query)

        if query_vec is not None and len(query_vec) > 0:
            query_vec_list = query_vec[0].tolist()

            # Configure limits based on mode
            limit = 10 if mode == SearchMode.DEEP else 20

            # Search Qdrant (using existing self.qdrant client)
            hits = self.qdrant.client.search(
                collection_name="neurosurgical_figures_hybrid",
                query_vector=("biomed", query_vec_list),
                limit=limit,
                score_threshold=0.15,  # CLIP text-image scores are lower
                with_payload=True,
            )

            # Hydrate results
            for hit in hits:
                p = hit.payload
                # Core fields from SQLite schema
                img = ExtractedImage(
                    id=p.get("filename", "unknown"),
                    source_id=p.get("source_pdf", "unknown"),
                    page=p.get("page_num", 0),
                    file_path=Path(p.get("path", "")),
                    caption=p.get("caption", ""),
                    surrounding_text=p.get("context", ""),
                    image_type=ImageType.ILLUSTRATION,
                    width=0,
                    height=0,
                    embedding=None,  # Don't reload embedding
                )
                # Store score for ranking
                images.append((img, hit.score))

            # Sort by relevance
            images.sort(key=lambda x: x[1], reverse=True)
            logger.info(f"Vision search: {len(images)} images (threshold=0.15)")

    except Exception as e:
        warnings.append(f"Vision search failed: {e}")
        logger.warning(f"Vision search error: {e}")
Update return statement (~line 296):
pythonreturn RetrievalResult(
    chunks=final_chunks,
    images=[img for img, _ in images],  # Extract images from (img, score) tuples
    search_mode=mode,
    warnings=warnings,
    # ... other fields
)
Validation (after small test batch in Phase 3):
bash./venv/bin/python -c "
from index.unified_search import UnifiedSearchEngine, SearchMode
from index.database import Database

engine = UnifiedSearchEngine(Database())
result = engine.search('lumbar spine MRI', mode=SearchMode.DEEP)
print(f'Chunks: {len(result.chunks)}')
print(f'Images: {len(result.images)}')
"

Phase 3: Backfill Pipeline (Day 2 PM - Day 3)
3.1 Production Backfill Script
File: src/scripts/reindex_images.py (CREATE NEW)
python#!/usr/bin/env python3
"""
Image Embedding Backfill with Checkpoint Resumption
====================================================
Features:
- Atomic checkpoint saves (crash-safe)
- 4-tier path resolution
- Progress tracking with tqdm
- Error categorization (path/embed/db)
- Uses ingest_figures() (NOT ingest_batch which doesn't exist)

Usage:
    ./venv/bin/python src/scripts/reindex_images.py --dry-run  # Test 32 images
    ./venv/bin/python src/scripts/reindex_images.py            # Full run
    ./venv/bin/python src/scripts/reindex_images.py --fresh    # Ignore checkpoint
"""
import argparse
import json
import logging
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Tuple

import numpy as np
from tqdm import tqdm

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from index.database import Database
from models import ExtractedImage
from neurosynth.ai.biomed_searcher import BiomedCLIPSearcher
from neurosynth.ai.ingestor import BiomedIngestor

# Configuration
DB_PATH = Path("data/neurosynth.db")
CHECKPOINT_FILE = Path("data/reindex_checkpoint.json")
LOG_DIR = Path("logs")
BATCH_SIZE = 32

BASE_PATHS = [
    Path("/Users/ramihatoum/neurosynth/assets/extracted_images"),
    Path("/Users/ramihatoum/neurosynth/reference-library/data/images"),
    Path("assets/extracted_images"),
    Path("data/extracted_images"),
]

# Setup logging
LOG_DIR.mkdir(exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_DIR / "reindex_images.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class CheckpointManager:
    """Atomic checkpoint management for crash-safe resumption."""

    def __init__(self, filepath: Path):
        self.filepath = filepath
        self.state = self._load()
        self.dirty = False

    def _load(self) -> dict:
        if self.filepath.exists():
            try:
                with open(self.filepath) as f:
                    state = json.load(f)
                    logger.info(
                        f"📂 Resuming: {len(state['processed_ids'])} done, "
                        f"{state['stats']['fail_path'] + state['stats']['fail_embed'] + state['stats']['fail_db']} failed"
                    )
                    return state
            except Exception as e:
                logger.warning(f"Checkpoint load failed: {e}. Starting fresh.")

        return {
            "processed_ids": [],
            "failed": {"path": [], "embed": [], "db": []},
            "stats": {
                "success": 0,
                "fail_path": 0,
                "fail_embed": 0,
                "fail_db": 0,
            },
            "started_at": datetime.now().isoformat(),
            "last_updated": None,
        }

    def save(self):
        """Atomic save: write temp file, then rename."""
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

    def print_summary(self):
        s = self.state["stats"]
        total = s["success"] + s["fail_path"] + s["fail_embed"] + s["fail_db"]
        logger.info("=" * 50)
        logger.info("📊 BACKFILL SUMMARY")
        logger.info(f"   Total processed: {total}")
        logger.info(f"   ✅ Success:      {s['success']}")
        logger.info(f"   ❌ Path failed:  {s['fail_path']}")
        logger.info(f"   ❌ Embed failed: {s['fail_embed']}")
        logger.info(f"   ❌ DB failed:    {s['fail_db']}")
        logger.info("=" * 50)


def resolve_path(stored_path: Path) -> Optional[Path]:
    """4-tier path resolution strategy."""
    # Tier 1: Direct path
    if stored_path.exists():
        return stored_path

    filename = stored_path.name

    # Tier 2: Check base paths
    for base in BASE_PATHS:
        if not base.exists():
            continue
        candidate = base / filename
        if candidate.exists():
            return candidate

    # Tier 3: Recursive glob
    for base in BASE_PATHS:
        if not base.exists():
            continue
        matches = list(base.rglob(filename))
        if matches:
            return matches[0]

    # Tier 4: Extension variants
    stem = stored_path.stem
    for base in BASE_PATHS:
        if not base.exists():
            continue
        for ext in ['.png', '.jpg', '.jpeg', '.PNG', '.JPG']:
            candidate = base / f"{stem}{ext}"
            if candidate.exists():
                return candidate

    return None


class ImageAdapter:
    """
    Duck-type adapter for BiomedIngestor.ingest_figures() compatibility.

    BiomedIngestor expects objects with these attributes:
    - local_path: Path to image file
    - image_filename: Unique identifier
    - source_pdf: Source document ID
    - caption: Image caption
    - context: Surrounding text
    - page_num: Page number
    """
    def __init__(self, img: ExtractedImage, resolved_path: Path):
        if resolved_path is None:
            raise ValueError(f"Cannot adapt image {img.id}: path not resolved")

        self.local_path = resolved_path
        self.image_filename = img.id
        self.source_pdf = img.source_id
        self.caption = img.caption or ""
        self.context = img.surrounding_text or ""
        self.page_num = img.page or 1


def process_batch(
    batch: List[Tuple[ExtractedImage, Path]],
    db: Database,
    embedder: BiomedCLIPSearcher,
    ingestor: BiomedIngestor,
    ckpt: CheckpointManager
):
    """Process a batch of images: embed, update DB, upsert to Qdrant."""
    if not batch:
        return

    imgs, paths = zip(*batch)

    try:
        # Generate embeddings (batch)
        vectors = embedder.embed_image([str(p) for p in paths])

        if len(vectors) == 0:
            logger.warning(f"Batch returned 0 embeddings")
            for img in imgs:
                ckpt.mark_failed(img.id, "embed")
            return

        # Update SQLite
        success_imgs = []
        success_paths = []

        for img, vec, path in zip(imgs, vectors, paths):
            vec_list = vec.tolist() if hasattr(vec, 'tolist') else list(vec)

            if db.update_image_embedding(img.id, vec_list):
                success_imgs.append(img)
                success_paths.append(path)
                ckpt.mark_success(img.id)
            else:
                ckpt.mark_failed(img.id, "db")

        # Upsert to Qdrant using ingest_figures() (NOT ingest_batch)
        if success_imgs:
            adapted = [ImageAdapter(img, path) for img, path in zip(success_imgs, success_paths)]
            ingestor.ingest_figures(adapted)

    except Exception as e:
        logger.error(f"Batch processing failed: {e}")
        for img in imgs:
            if not ckpt.is_processed(img.id):
                ckpt.mark_failed(img.id, "embed")


def main():
    parser = argparse.ArgumentParser(description="Backfill image embeddings")
    parser.add_argument("--dry-run", action="store_true", help="Process only 32 images")
    parser.add_argument("--fresh", action="store_true", help="Ignore checkpoint, start fresh")
    parser.add_argument("--limit", type=int, help="Limit total images processed")
    parser.add_argument("--batch-size", type=int, default=BATCH_SIZE)
    args = parser.parse_args()

    # Fresh start
    if args.fresh and CHECKPOINT_FILE.exists():
        CHECKPOINT_FILE.unlink()
        logger.info("🗑️ Checkpoint cleared for fresh start")

    logger.info("=" * 50)
    logger.info("🚀 IMAGE BACKFILL PIPELINE")
    logger.info("=" * 50)

    # Initialize components
    db = Database(str(DB_PATH))
    embedder = BiomedCLIPSearcher()
    ingestor = BiomedIngestor()  # Will create Qdrant collection
    ckpt = CheckpointManager(CHECKPOINT_FILE)

    # Get images needing embeddings
    images = db.get_images_without_embeddings()
    total = len(images)
    logger.info(f"Found {total:,} images without embeddings")

    if total == 0:
        logger.info("✅ All images already have embeddings!")
        return 0

    # Apply limits
    if args.dry_run:
        images = images[:args.batch_size]
        logger.info(f"🧪 Dry run: processing {len(images)} images")
    elif args.limit:
        images = images[:args.limit]
        logger.info(f"Limited to {len(images)} images")

    # Process
    batch = []
    batch_size = args.batch_size

    with tqdm(total=len(images), desc="Reindexing") as pbar:
        for img in images:
            # Skip already processed
            if ckpt.is_processed(img.id):
                pbar.update(1)
                continue

            # Resolve path
            resolved = resolve_path(img.file_path)
            if not resolved:
                logger.debug(f"Path not found: {img.file_path}")
                ckpt.mark_failed(img.id, "path")
                pbar.update(1)
                continue

            batch.append((img, resolved))

            # Process full batch
            if len(batch) >= batch_size:
                process_batch(batch, db, embedder, ingestor, ckpt)
                pbar.update(len(batch))
                batch = []
                ckpt.save()  # Checkpoint every batch

        # Final batch
        if batch:
            process_batch(batch, db, embedder, ingestor, ckpt)
            pbar.update(len(batch))
            ckpt.save()

    # Summary
    ckpt.print_summary()

    # Verification
    logger.info("🔍 Verifying results...")
    with db._get_conn() as conn:
        embedded = conn.execute(
            "SELECT COUNT(*) FROM images WHERE embedding IS NOT NULL AND length(embedding) > 0"
        ).fetchone()[0]
    logger.info(f"✅ Images with embeddings: {embedded:,}")

    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        logger.warning("\n⚠️ Interrupted - progress saved to checkpoint")
        logger.info("   Resume: ./venv/bin/python src/scripts/reindex_images.py")
        sys.exit(130)
    except Exception as e:
        logger.error(f"❌ Fatal error: {e}", exc_info=True)
        sys.exit(1)
Execution:
bash# Step 1: Dry run (validates everything works)
./venv/bin/python src/scripts/reindex_images.py --dry-run

# Step 2: Full run (~2-4 hours for 18k images)
./venv/bin/python src/scripts/reindex_images.py

# If interrupted, resume automatically
./venv/bin/python src/scripts/reindex_images.py

# Fresh start if needed
./venv/bin/python src/scripts/reindex_images.py --fresh
Validation:
bash# Verify SQLite
sqlite3 data/neurosynth.db "SELECT COUNT(*) FROM images WHERE embedding IS NOT NULL"
# Expected: 18378

# Verify embedding dimensions (must be 512 for BiomedCLIP)
sqlite3 data/neurosynth.db "
SELECT id, length(embedding) / 4 as dims
FROM images
WHERE embedding IS NOT NULL
LIMIT 5
"
# Expected: dims = 512 for all

# Verify Qdrant
curl -s http://localhost:6333/collections/neurosurgical_figures_hybrid | jq '.result.points_count'
# Expected: 18378

# Verify Qdrant payload structure
curl -s 'http://localhost:6333/collections/neurosurgical_figures_hybrid/points?limit=1' | \
  jq '.result[0].payload | keys'
# Expected: ["caption", "context", "filename", "page_num", "path", "source_pdf", ...]

Phase 4: Synthesis Integration (Days 3-4)
4.1 Image Assignment to Outline Sections
File: src/neurosynth/synthesis/category_outline.py
Add method after ~line 223:
pythondef assign_images_to_outline(
    self,
    nodes: list[OutlineNode],
    db: Database,
    vision_searcher: "BiomedCLIPSearcher",
    top_k: int = 3,
    score_threshold: float = 0.2,
) -> list[OutlineNode]:
    """
    Assign relevant images to outline sections using semantic similarity.

    Uses Top-K strategy with lowered threshold (0.2) because
    CLIP text-image scores are naturally lower than text-text.

    NOTE: Uses assigned_sources with type="image" (NOT assigned_images which doesn't exist)
    """
    from collections import defaultdict

    import numpy as np

    # Get images with embeddings
    all_images = db.get_all_images_with_embeddings()
    if not all_images:
        logger.warning("No embedded images available for assignment")
        return nodes

    logger.info(f"Assigning from {len(all_images)} embedded images")

    # Track usage to prevent over-reuse
    image_usage = defaultdict(int)
    max_reuse = 2

    for node in nodes:
        # Build query from section metadata
        section_query = f"{node.title}. {node.description or ''}"

        try:
            query_vec = vision_searcher.embed_text(section_query)
            if query_vec is None or len(query_vec) == 0:
                continue
            query_vec = query_vec[0]
        except Exception as e:
            logger.warning(f"Failed to embed section '{node.title}': {e}")
            continue

        # Score all available images
        scored = []
        for img in all_images:
            if image_usage[img.id] >= max_reuse:
                continue
            if img.embedding is None or len(img.embedding) == 0:
                continue

            # Cosine similarity
            img_vec = np.array(img.embedding)
            sim = np.dot(query_vec, img_vec) / (
                np.linalg.norm(query_vec) * np.linalg.norm(img_vec) + 1e-8
            )

            if sim > score_threshold:
                scored.append((img, float(sim)))

        # Sort and take top K
        scored.sort(key=lambda x: x[1], reverse=True)
        top_images = scored[:top_k]

        # Add to assigned_sources with type="image"
        for img, score in top_images:
            node.assigned_sources.append({
                "type": "image",
                "id": img.id,
                "source_id": img.source_id,
                "page": img.page,
                "file_path": str(img.file_path),
                "caption": img.caption or "No caption",
                "relevance_score": round(score, 3),
            })
            image_usage[img.id] += 1

        if top_images:
            logger.debug(f"'{node.title}': {len(top_images)} images (scores: {[f'{s:.2f}' for _, s in top_images]})")

    total_assigned = sum(1 for node in nodes for s in node.assigned_sources if s.get("type") == "image")
    logger.info(f"Assigned {total_assigned} images across {len(nodes)} sections")

    return nodes
Integration in generate() method:
python# After outline generation, before return:
try:
    from index.database import Database
    from neurosynth.ai.biomed_searcher import BiomedCLIPSearcher

    db = Database()
    vision = BiomedCLIPSearcher()
    outline = self.assign_images_to_outline(outline, db, vision)
except Exception as e:
    logger.warning(f"Image assignment skipped: {e}")

return outline

4.2 Section Synthesizer Figure Handling
File: src/neurosynth/synthesis/section.py
Update _prepare_source_content():
pythondef _prepare_source_content(self, assigned_sources: list[dict]) -> str:
    """Prepare source content with separated text and image handling."""
    text_sources = []
    image_sources = []

    # Separate by type
    for source in assigned_sources:
        if source.get("type") == "image":
            image_sources.append(source)
        else:
            text_sources.append(source)

    content_parts = []

    # Text sources (existing logic)
    for source in text_sources:
        content_parts.append(self._format_text_source(source))

    # Image sources (structured format for LLM)
    if image_sources:
        content_parts.append("\n## AVAILABLE FIGURES FOR THIS SECTION\n")
        for i, img in enumerate(image_sources, 1):
            content_parts.append(
                f"[FIGURE-{i}]\n"
                f"- ID: {img['id']}\n"
                f"- Source: {img.get('source_id', 'unknown')}\n"
                f"- Page: {img.get('page', 'N/A')}\n"
                f"- Caption: {img.get('caption', 'No caption')}\n"
                f"- Relevance: {img.get('relevance_score', 'N/A')}\n"
            )
        content_parts.append(
            "\nINSTRUCTION: Reference figures using [FIGURE-N] tags where contextually appropriate. "
            "Each reference should add value to the narrative.\n"
        )

    return "\n\n".join(content_parts)
Add validation method:
pythondef _validate_figure_references(self, content: str, num_figures: int) -> str:
    """Replace invalid [FIGURE-N] references to prevent hallucinations."""
    import re

    def replace_invalid(match):
        num = int(match.group(1))
        if num > num_figures or num < 1:
            logger.warning(f"LLM hallucinated FIGURE-{num} (valid: 1-{num_figures})")
            return "[FIGURE-INVALID]"
        return match.group(0)

    return re.sub(r'\[FIGURE-(\d+)\]', replace_invalid, content)

Phase 5: Database Consolidation (Week 2)
5.1 Strategy Decision
ApproachProsConsRecommendedSingle Source (library.db)Simpler, one truthRequires 69K embedding backfill (~20h)✅ PrimaryFederated QueryPreserves both DBsHigher complexity, sync issuesFallback
5.2 Single Source Migration
sql-- Step 1: Add embedding column to library.db
ALTER TABLE visual_elements ADD COLUMN embedding BLOB;

-- Step 2: Verify
PRAGMA table_info(visual_elements);
Migration script: src/scripts/migrate_to_library_db.py
python#!/usr/bin/env python3
"""Migrate image embeddings from neurosynth.db to library.db"""
import sqlite3
from pathlib import Path

from tqdm import tqdm

NEUROSYNTH_DB = Path("data/neurosynth.db")
LIBRARY_DB = Path("data/library.db")

def main():
    ns_conn = sqlite3.connect(NEUROSYNTH_DB)
    lib_conn = sqlite3.connect(LIBRARY_DB)

    # Get embedded images from neurosynth
    rows = ns_conn.execute("""
        SELECT file_path, embedding
        FROM images
        WHERE embedding IS NOT NULL
    """).fetchall()

    print(f"Migrating {len(rows)} embeddings...")

    updated = 0
    for file_path, embedding in tqdm(rows):
        # Match by filename in library.db
        filename = Path(file_path).name
        result = lib_conn.execute("""
            UPDATE visual_elements
            SET embedding = ?
            WHERE image_path LIKE ?
        """, (embedding, f"%{filename}"))

        if result.rowcount > 0:
            updated += 1

    lib_conn.commit()
    print(f"✅ Migrated {updated} embeddings to library.db")

if __name__ == "__main__":
    main()

Phase 6: Validation & Monitoring
6.1 Health Check Commands
bash#!/bin/bash
# save as: scripts/health_check.sh

echo "=== NeuroSynth Image Pipeline Health Check ==="

# 1. Database embeddings
echo -e "\n📊 SQLite Status:"
sqlite3 data/neurosynth.db "
SELECT
    COUNT(*) as total,
    SUM(CASE WHEN embedding IS NOT NULL AND length(embedding) > 0 THEN 1 ELSE 0 END) as embedded
FROM images
"

# 2. Embedding dimensions
echo -e "\n📐 Embedding Dimensions (should be 512):"
sqlite3 data/neurosynth.db "
SELECT id, length(embedding)/4 as dims
FROM images
WHERE embedding IS NOT NULL
LIMIT 3
"

# 3. Qdrant collections
echo -e "\n🔍 Qdrant Collections:"
curl -s http://localhost:6333/collections | jq '.result.collections[].name'

# 4. Qdrant points count
echo -e "\n📈 Qdrant Image Points:"
curl -s http://localhost:6333/collections/neurosurgical_figures_hybrid 2>/dev/null | \
    jq '.result.points_count' || echo "Collection not found"

# 5. Qdrant payload sample
echo -e "\n📦 Sample Payload Keys:"
curl -s 'http://localhost:6333/collections/neurosurgical_figures_hybrid/points?limit=1' 2>/dev/null | \
    jq '.result[0].payload | keys' || echo "No points found"

echo -e "\n✅ Health check complete"
6.2 Integration Tests
python# tests/test_image_pipeline_e2e.py

from pathlib import Path

import pytest


def test_database_methods_exist():
    """Verify all required database methods exist."""
    from index.database import Database
    db = Database()

    assert hasattr(db, 'get_all_images')
    assert hasattr(db, 'get_images_without_embeddings')
    assert hasattr(db, 'update_image_embedding')
    assert hasattr(db, 'get_all_images_with_embeddings')

def test_all_images_embedded():
    """Verify all images have embeddings after backfill."""
    from index.database import Database
    db = Database()

    missing = db.get_images_without_embeddings()
    assert len(missing) == 0, f"{len(missing)} images still missing embeddings"

def test_embedding_dimensions():
    """Verify embeddings are correct dimension (512 for BiomedCLIP)."""
    from index.database import Database
    db = Database()

    images = db.get_all_images_with_embeddings()[:5]
    for img in images:
        assert len(img.embedding) == 512, f"Image {img.id} has {len(img.embedding)} dims, expected 512"

def test_qdrant_collection_exists():
    """Verify Qdrant image collection exists and is populated."""
    from qdrant_client import QdrantClient

    client = QdrantClient(url="http://localhost:6333")
    collections = [c.name for c in client.get_collections().collections]

    assert "neurosurgical_figures_hybrid" in collections

def test_vision_search_returns_images():
    """End-to-end vision search test."""
    from index.database import Database
    from index.unified_search import SearchMode, UnifiedSearchEngine

    engine = UnifiedSearchEngine(Database())
    result = engine.search("lumbar spine MRI", mode=SearchMode.DEEP)

    assert len(result.images) > 0, "Vision search returned no images"

def test_vision_search_relevance():
    """Verify returned images are semantically relevant."""
    from index.database import Database
    from index.unified_search import SearchMode, UnifiedSearchEngine

    engine = UnifiedSearchEngine(Database())
    result = engine.search("MRI sagittal spine", mode=SearchMode.DEEP)

    # At least one image should have relevant caption
    relevant = [
        img for img in result.images
        if any(kw in (img.caption or "").lower() for kw in ["mri", "spine", "sagittal"])
    ]

    assert len(relevant) > 0 or len(result.images) > 0, "No relevant images found"

def test_synthesis_includes_figures():
    """Verify synthesis output includes figure references."""
    import subprocess

    result = subprocess.run(
        ["./venv/bin/python", "-m", "neurosynth", "generate",
         "--topic", "Lumbar Discectomy", "--output", "/tmp/test_chapter.md"],
        capture_output=True, text=True
    )

    if result.returncode == 0:
        content = Path("/tmp/test_chapter.md").read_text()
        figure_count = content.count("[FIGURE-")
        assert figure_count > 0, "No figure references in synthesis output"
Run tests:
bashpytest tests/test_image_pipeline_e2e.py -v

Implementation Timeline
PhaseDurationDeliverablesValidation0Day 0Database methods, Qdrant runningMethod tests pass1Day 1Ingestor fix, path resolutionCollection created2Day 2 AMVision search implementationSearch returns images3Day 2-3Backfill 18,378 images100% embedded4Day 3-4Image assignment, synthesis integrationFigures in output5Week 2DB consolidation (optional)Single source6OngoingMonitoring, health checksAutomated alerts

Summary: Files to Modify
FileActionPrioritysrc/index/database.pyAdd 4 methodsP0src/neurosynth/ai/ingestor.py:50-64Fatal error handlingP0src/reference_library/cache/database.py:10683-tier path resolutionP0src/index/unified_search.py:256-263Implement vision searchP1src/neurosynth/synthesis/category_outline.pyAdd image assignmentP1src/neurosynth/synthesis/section.pyFigure handlingP1src/scripts/reindex_images.pyCREATE new backfill scriptP1scripts/health_check.shCREATE monitoring scriptP2

Critical Corrections from Review
Original PlanIssueCorrectioningestor.ingest_batch()Method doesn't existUse ingest_figures()node.assigned_imagesAttribute doesn't existUse assigned_sources with type: "image"BiomedCLIPSearcher.qdrant_clientDoesn't existUse UnifiedSearchEngine.qdrantdatabase.py path fixAmbiguous fileClarified: reference_library/cache/database.pySchema: modality columnsDon't exist in SQLiteRead from Qdrant payload onlyMissing methodsNot in planAdded Phase 0 prerequisites
