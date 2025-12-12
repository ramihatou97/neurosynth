# Codebase Assessment & Implementation Strategy

## Codebase Assessment

### Overall Architecture and Structure Summary
The NeuroSynth image pipeline is designed as a modular system with three main stages: **Ingestion**, **Storage**, and **Retrieval/Synthesis**.
*   **Ingestion:** `SmartImageExtractor` (in `smart_extractor.py`) handles PDF parsing, figure extraction, deduplication, and metadata enrichment (including `VisualRegionDetector` integration).
*   **Storage:** Metadata is stored in SQLite (`database.py`) and vector embeddings are stored in Qdrant (`neurosurgical_figures_hybrid` collection). The `BiomedIngestor` facilitates this dual storage.
*   **Retrieval:** `UnifiedSearchEngine` (`unified_search.py`) orchestrates search, offering a specific "Vision" mode that queries Qdrant using BiomedCLIP embeddings.
*   **Synthesis:** The goal is to dynamically inject relevant images into generated content via `CategoryAwareOutlineGenerator` (`category_outline.py`) and `SectionSynthesizer` (`section.py`).

### Identified Issues
| Category | Issue | Severity | Location |
| :--- | :--- | :--- | :--- |
| **Missing Functionality** | `assign_images_to_outline` function is completely missing. | **Critical** | `src/neurosynth/synthesis/category_outline.py` |
| **Missing Functionality** | `_prepare_source_content` does not handle standalone image sources. | **Critical** | `src/neurosynth/synthesis/section.py` |
| **Missing Scripts** | `scripts/reindex_images.py` for backfilling embeddings is missing. | **High** | `scripts/` |
| **Missing Scripts** | `scripts/image_pipeline_health.py` for validation is missing. | **Medium** | `scripts/` |
| **Data Integrity** | Existing data is likely stale or incomplete (missing embeddings/Qdrant points). | **Critical** | Database/Qdrant |
| **Configuration** | `VisualRegionDetector` is implemented but relies on `assets/region_exemplars` which needs to be verified. | **Low** | `src/neurosynth/enhancements/visual_region_detector.py` |

### Severity Assessment
*   **Critical:** blocking the core feature (images appearing in synthesis).
*   **High:** blocking maintenance or recovery operations.
*   **Medium:** affecting observability/verification.
*   **Low:** potential future content quality issues.

---

## Implementation Strategy

### Step 1: Data Reset & Fresh Extraction (Phase 0.5)
*   **What:** Clear all image data from SQLite and Qdrant, then run a fresh extraction.
*   **Where:** Terminal / Data directories.
*   **Why:** To ensure all images have proper metadata and embeddings from the start, avoiding complex migration issues.
*   **How:**
    1.  Delete Qdrant collection: `curl -X DELETE ...`
    2.  Clear SQLite images table/files.
    3.  Run `python run_background_extraction.py`.
*   **Testing:** Verify counts in SQLite vs Qdrant match after run.

### Step 2: Implement Synthesis Integration (Phase 4)
*   **What:** Add logic to select images for outline nodes and format them for the LLM.
*   **Where:**
    1.  `src/neurosynth/synthesis/category_outline.py`: Add `assign_images_to_outline`.
    2.  `src/neurosynth/synthesis/section.py`: Update `_prepare_source_content` to handle `type="image"` entries.
*   **Why:** This bridges the gap between the search engine (which finds images) and the synthesizer (which writes about them).
*   **How:** Paste the provided code blocks from the implementation plan.
*   **Testing:** Run a dummy synthesis or unit test to verify `Section` objects contain image references.

### Step 3: Create Utility Scripts (Phase 3 & 5)
*   **What:** Create scripts for re-indexing and health monitoring.
*   **Where:** `scripts/reindex_images.py` and `scripts/image_pipeline_health.py`.
*   **Why:** `reindex` is needed if we change embedding models later; `health` is needed for CI/CD and debugging.
*   **How:** Create new files with provided content.
*   **Testing:** Run `python scripts/image_pipeline_health.py` to verify green status.

### Dependencies
*   Step 2 depends on Step 1 (need data to verify synthesis).
*   Step 3 is largely independent but `health.py` is useful for verifying Step 1.

---

## Deployment Readiness

### Checklist
- [ ] Fresh extraction completed successfully (N images indexed).
- [ ] `assign_images_to_outline` implemented and imported.
- [ ] `section.py` handling updated.
- [ ] Health check script passing (SQLite OK, Qdrant OK, Search OK).
- [ ] Visual Region Detector exemplars present (optional but recommended).

### Risks & Limitations
*   **Performance:** Fresh extraction on a large PDF library will take time (hours).
*   **Memory:** `reindex_images.py` and extraction scripts need sufficient RAM for BiomedCLIP model loading.
*   **Concurrency:** Qdrant integration assumes a single local instance; race conditions possible if multiple extractors run (mitigated by sequential batching).
