# Image Pipeline Implementation Plan (Code-First Strategy)

## Goal Description
Implement the critical logic bridging the Image Search Engine and Synthesis modules. This will enable the application to *code-wise* handle images in outlines and sections, without requiring an immediate, destructive data reset. We will also add health checks and indexing scripts to support future data operations.

## User Review Required
> [!NOTE]
> **Deferred Data Reset**: As requested, we are **SKIPPING** the "Fresh Extraction" (Phase 0.5) for now. The pipeline will be implemented in code, but might not produce visual results in the app until the underlying data is eventually refreshed or backfilled using the new scripts.

## Proposed Changes

### Synthesis Integration
#### [MODIFY] [category_outline.py](file:///Users/ramihatoum/neurosynth/src/neurosynth/synthesis/category_outline.py)
- **Add function**: `assign_images_to_outline`
- **Logic**:
    - Takes `OutlineNode` list, `Database`, and `BiomedCLIPSearcher`.
    - Embeds node title/description.
    - Searches existing image embeddings (even if stale/incomplete) or returns empty if none.
    - Assigns top-k images to nodes.

#### [MODIFY] [section.py](file:///Users/ramihatoum/neurosynth/src/neurosynth/synthesis/section.py)
- **Update method**: `_prepare_source_content`
- **Logic**:
    - Add handling for `source["type"] == "image"`.
    - Format image metadata (caption, ID, relevance) into the text prompt sent to the LLM.

### Utility Scripts
#### [NEW] [reindex_images.py](file:///Users/ramihatoum/neurosynth/scripts/reindex_images.py)
- Script to iterate over existing images in SQLite.
- Computes embeddings using `BiomedCLIPSearcher` if missing.
- Upserts to Qdrant.
- Allows "fixing" the data without start-from-scratch extraction.

#### [NEW] [image_pipeline_health.py](file:///Users/ramihatoum/neurosynth/scripts/image_pipeline_health.py)
- Diagnostic script to check:
    - SQLite image counts.
    - Qdrant collection status.
    - Vision search functionality.
    - Integration function availability.

## Verification Plan

### Automated Tests
1.  **Health Check**: Run `python scripts/image_pipeline_health.py` to verify components are wire-connected.
2.  **Import Test**: Verify `assign_images_to_outline` can be imported and run (even with empty data).

### Manual Verification
1.  **Dry Run Re-index**: Run `python scripts/reindex_images.py --dry-run` to see if it correctly identifies images needing embeddings.
2.  **Synthesis Flow**: (Optional) Attempt a synthesis generation. Even if no images appear (due to data context), the synthesis should complete without error.
