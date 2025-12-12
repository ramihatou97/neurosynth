# Project Health & Optimization Log

**Last Updated**: 2025-12-12
**Status**: Living Document

This document tracks all identified errors, architectural concerns, deficits, and suboptimal processes encountered during development and testing. It serves as a roadmap for future optimization and technical debt repayment.

## 🔴 Critical Failures & Errors (Resolved)

### 1. Ingestion Pipeline OOM (Exit Code 137)
*   **Issue**: `docker-compose` worker container crashed silently with Exit Code 137 during ingestion of large textbooks (`Phakomatoses.pdf`, >800 images).
*   **Root Cause**: Not strictly a memory leak, but **ColPali's late-interaction architecture** generating multi-vector embeddings for hundreds of images simultaneously exhausted the 4GB/8GB container limit.
*   **Resolution**:
    1.  Switched image embedding model to **BiomedCLIP** (Contrastive, single-vector, lighter).
    2.  Implemented **batch processing** (batch size 32) in `_embed_images_biomed_clip` to cap peak memory usage.
*   **Future Action**: If switching back to heavier models (ColPali v2), strictly enforce batching or implement a queue-based external embedding service.

### 2. Missing Qdrant Data Sync
*   **Issue**: Ingestion logs showed "Generated embeddings" but Qdrant collection `neurosurgical_figures_hybrid` remained non-existent/empty.
*   **Root Cause**: `scripts/run_ingestion.py` initialized the `DocumentProcessor` and `Database` (SQLite) but completely **lacked code to initialize `QdrantClient`** or perform vector upserts.
*   **Resolution**: Patched `run_ingestion.py` to initialize Qdrant, check collection existence, and upsert image vectors during the processing loop.

### 3. Docker Networking Mismatch (`Connection Refused`)
*   **Issue**: `run_ingestion.py` failed with `[Errno 111] Connection refused` when trying to connect to Qdrant.
*   **Root Cause**: The script used `http://localhost:6333`. Inside a Docker container, `localhost` refers to the container itself, not the sibling `qdrant` service.
*   **Resolution**: Updated script to use the Docker service name: `http://qdrant:6333`.
*   **Optimization**: Move this URL to `src/config.py` environment variables instead of hardcoding in scripts.

### 4. Frontend State Crash (`clinical_qa`)
*   **Issue**: Streamlit `BadGateway` / Script Runner error in Clinical QA panel.
*   **Root Cause**: `st.button` callback attempted to modify `st.session_state.question` *after* the `st.text_area` widget with that key was already rendered for the frame.
*   **Resolution**: (Pending/Workaround) Refactored to use a temporary variable or callback function to set state before render.

### 5. Visual Search Vector Mismatch (`400 Bad Request`)
*   **Issue**: Visual search failed with `Wrong input: Not existing vector name error: biomed`.
*   **Root Cause**: `UnifiedSearchEngine` was querying Qdrant with `using="biomed"`, but `run_ingestion.py` populated the default unnamed vector.
*   **Resolution**: Patched `unified_search.py` to remove the `using="biomed"` argument, aligning search with ingestion schema.

### 6. BM25 Index Serialization Failure
*   **Issue**: `BM25Retriever.save()` failed with `Object of type Chunk is not JSON serializable`.
*   **Root Cause**: Special `Chunk` dataclasses inside the index were not compatible with standard JSON dumping.
*   **Resolution**: Implemented custom serialization logic in `BM25Retriever.save()` to convert dataclasses to dicts, and reconstruction logic in `load()`. Verified with `scripts/verify_bm25_serialization.py`.

### 7. Hardcoded Configuration
*   **Issue**: Scripts used hardcoded model names and URLs.
*   **Resolution**: Refactored `run_ingestion.py` to import from `src.config.settings` and updated `docker-compose.yml` with proper env vars (e.g. `QDRANT_URL`).

### 8. Visual Region Detection Yield (Zero Visual Tags)
*   **Issue**: `VisualRegionDetector` consistently reported `visual: 0` tags, relying entirely on keywords.
*   **Root Cause**: `SmartImageExtractor` tried to access `fig.file_path` (which didn't exist) instead of `fig.local_path`, causing it to skip the visual embedding block entirely. Also, `ImageExtractor` failed to copy `detected_regions` to the database model.
*   **Resolution**: Fixed attribute access in `smart_extractor.py` and added metadata copy logic in `image_extractor.py`.
*   **Verification**: Ingestion logs now show `Region detection: 8/9 tagged (visual: 8)` for spine surgery PDFs.

### 9. Generic Metadata Quality (Index specificity)
*   **Issue**: Many documents had generic titles like "Slide 1", "Untitled", or "Microsoft Word...".
*   **Root Cause**: PDF metadata is often poor for non-standard documents.
*   **Resolution**: Implemented `TitleGenerator` (LLM-based) to read first page content and generate specific neurosurgical titles (e.g. "Pterional Craniotomy...").
*   **Verification**: `test_title_generator.py` confirmed accurate extraction of titles from raw text.

## 🔴 Critical Failures & Errors (Active)

<!-- No active critical failures -->

### 2. "Ghost" Features
*   **Observation**: Several features appear in documentation or `docker-compose.yml` env vars but lack implementation:
    *   **Latex Figures**: `ENABLE_LATEX_GENERATION` flag exists, but no ingestion logic generates `.tex` files.
    *   **Exam Frequency Boost**: Mentioned in requirements, but no search logic implements weighting by exam frequency.
    *   **Authority Ranking**: No logic found to rank search results by author authority.
*   **Impact**: Misleading configuration; users expect features that don't run.
*   **Recommendation**: Remove unused flags or implement the features (Synthesis-stage implementation for Latex).

### 3. Synchronous Ingestion Blocking
*   **Observation**: `run_ingestion.py` processes PDFs serially. If one file hangs (e.g. on a complex figure extraction), the entire pipeline stalls.
*   **Recommendation**: Implement `AsyncIngestionManager` (outlined in `src/ingest/async_ingestor.py` but not fully utilized) to process files in parallel or independent tasks.

### 4. Error Logging Visibility
*   **Observation**: When `run_ingestion.py` fails (e.g. Qdrant connection), it logs to stdout but doesn't persist the error state in the SQLite `sources` table (which just says "processed" or nothing).
*   **Impact**: Hard to trace which individual file failed without grepping massive docker logs.
*   **Recommendation**: Add a `status` and `error_message` column to the `sources` table to track per-file ingestion health.

## 📉 Suboptimal Performance

### 1. Duplicate Image Extraction
*   **Observation**: The `SmartImageExtractor` runs Perceptual Hashing (PHash) but the deduplication logic's effectiveness validation is sparse in logs.
*   **Concerns**: We see "Extracting 800 images" for single books. Many might be decorative elements, page headers, or duplicates not caught by PHash.
*   **Recommendation**: Tune `entropy_threshold` (currently 4.5) and implement stricter "Medical Figure" classification (using the YOLO `object_detector` more aggressively) to discard non-clinical images *before* embedding.

### 2. Startup Latency
*   **Observation**: `neurosynth-worker` takes significant time to start because it loads ML models (BiomedCLIP, LayoutLM) into memory on boot or first access.
*   **Recommendation**: Keep models loaded in a dedicated "Model Service" container (e.g. TorchServe or just a persistent FastAPI wrapper) rather than loading them inside the worker process, allowing the worker to be lighter.
