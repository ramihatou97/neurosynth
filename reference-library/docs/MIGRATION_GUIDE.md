# Migration Guide: Neurosurgical Enhancements

## Overview

This guide helps existing Reference Library users migrate to the enhanced neurosurgery-aware version.

## What's New?

The search system now understands the difference between:
- **🔴 Surgical/Procedural content** (how to perform operations)
- **🔵 Clinical/Theoretical content** (disease knowledge, diagnosis, management)

## Database Migration

### Automatic Migration

The database schema is **automatically updated** on first launch. No manual intervention required.

**New tables created**:
- `query_intent_cache` - Stores AI-powered query intent classifications

**Existing tables updated**:
- `search_history` - Enhanced with category tracking columns

### What Happens to Existing Data?

- ✅ **All existing data is preserved**
- ✅ **Existing searches remain in history**
- ✅ **Cached text and categorizations are retained**
- ✅ **New columns are added with default values**

### Verify Migration

After first launch, check the database:

```bash
sqlite3 reference-library/data/library.db
.schema query_intent_cache
.schema search_history
```

You should see the new columns in `search_history`:
- `surgical_count`
- `theoretical_count`
- `dominant_category`
- `search_mode`

## Semantic Search Index

### Medical Embedding Model (Recommended)

The default embedding model has changed from `general` to `medical` for better neurosurgical terminology understanding.

**Option 1: Re-index with Medical Model (Recommended)**

1. Launch the application
2. Go to **Tools → Index Semantic Search**
3. Wait for indexing to complete (~2x slower than before, but better quality)

**Option 2: Keep Using General Model**

If you prefer the faster general model:

```bash
export NEUROSYNTH_EMBEDDING_MODEL=general
python -m reference-library
```

Your existing index will be used automatically.

### Collection Naming

Collections are now named by model type:
- Old: `neurosurgery_pages`
- New: `neurosurgery_pages_medical` (or `_general`, `_retrieval`, `_large`)

**Your old collection is preserved** and will be used if you set `NEUROSYNTH_EMBEDDING_MODEL=general`.

## New Features to Try

### 1. Intent-Based Search

When searching, select your intent:
- **🔴 Surgical Technique** - For operative procedures, approaches, techniques
- **🔵 Clinical Knowledge** - For disease info, diagnosis, management
- **Both** - No filtering (default behavior)

**Example**:
- Query: "vestibular schwannoma"
- Intent: Surgical → Returns retrosigmoid approach, tumor resection techniques
- Intent: Clinical → Returns presentation, imaging, outcomes

### 2. Query Expansion

Searches now automatically include synonyms:
- "acoustic neuroma" → also searches "vestibular schwannoma", "VS", "CPA tumor"
- "aneurysm clipping" → also searches "microsurgical clipping", "clip ligation"

**No configuration needed** - works automatically!

### 3. Smart Template Recommendations

When synthesizing a chapter:
1. Select your sources
2. Click "Synthesize Chapter"
3. System analyzes your selection and recommends:
   - **Surgical** template if ≥70% surgical sources
   - **Clinical** template if ≥70% clinical sources
   - Notes mixed content otherwise

### 4. Visual Category Indicators

Results now show category badges:
- 🔴 = Surgical/Anatomical content
- 🔵 = Clinical/Theoretical content
- ⚪ = Not yet categorized

### 5. Analytics Dashboard

Click the **📊** button to view:
- Search patterns and trends
- Category distribution
- Most searched terms
- Search mode usage

## Configuration Options

### Environment Variables

```bash
# Embedding model selection
export NEUROSYNTH_EMBEDDING_MODEL=medical  # or: general, retrieval, large

# Disable query expansion (not recommended)
# Edit pdf_searcher.py: enable_query_expansion=False
```

### Config File

Edit `reference-library/src/config.py`:

```python
# Change default embedding model
EMBEDDING_MODEL_TYPE = "medical"  # or: general, retrieval, large
```

## Performance Considerations

### Indexing Speed

| Model   | Speed vs Old | Quality | Recommendation |
|---------|--------------|---------|----------------|
| General | Same         | Good    | Fast systems   |
| Medical | ~2x slower   | Best    | **Recommended**|
| Large   | ~4x slower   | Excellent | Research use |

### Search Speed

- **Intent filtering** may actually speed up searches by reducing result set
- **Query expansion** adds negligible overhead (<1ms)
- **Medical model** search speed is similar to general model

### Disk Space

| Model   | Additional Space |
|---------|------------------|
| General | 80MB             |
| Medical | 420MB            |
| Large   | 1.3GB            |

## Troubleshooting

### "No module named 'query_intent'"

**Solution**: Restart the application. The new module should be auto-detected.

### Search results seem different

**Cause**: You may be using a different embedding model or intent filter.

**Solution**: 
1. Check which model is active (see Analytics → Cache Statistics)
2. Ensure intent is set to "Both" for unfiltered results
3. Re-index if you switched models

### Analytics button not showing

**Solution**: Update to the latest version and restart.

### Query expansion not working

**Verify**: Search for "acoustic neuroma" and check if results include "vestibular schwannoma"

**Solution**: Ensure `enable_query_expansion=True` in PDFSearcher initialization.

## Rollback (If Needed)

If you need to revert to the previous version:

1. **Database**: No rollback needed - new columns don't affect old functionality
2. **Code**: Checkout previous git commit
3. **Index**: Old semantic index is preserved in `neurosurgery_pages` collection

## Getting Help

- **Documentation**: See `NEUROSURGICAL_ENHANCEMENTS.md` for detailed feature descriptions
- **Embedding Models**: See `EMBEDDING_MODELS.md` for model comparison
- **Issues**: Check existing GitHub issues or create a new one

## Recommended Migration Path

### For Most Users (Recommended)

```bash
# 1. Update code (git pull or download)
# 2. Set medical model (default, but explicit is good)
export NEUROSYNTH_EMBEDDING_MODEL=medical

# 3. Launch application
python -m reference-library

# 4. Re-index semantic search (one-time, ~30 min for 100 PDFs)
# Tools → Index Semantic Search

# 5. Try new features!
```

### For Fast Migration (Keep General Model)

```bash
# 1. Update code
# 2. Keep general model
export NEUROSYNTH_EMBEDDING_MODEL=general

# 3. Launch application
python -m reference-library

# No re-indexing needed - uses existing index
```

### For Maximum Quality (Research/Analysis)

```bash
# 1. Update code
# 2. Use large model
export NEUROSYNTH_EMBEDDING_MODEL=large

# 3. Launch application
python -m reference-library

# 4. Re-index (slower, but best quality)
# Tools → Index Semantic Search
```

## Post-Migration Checklist

- [ ] Application launches without errors
- [ ] Database migration completed (check logs)
- [ ] Intent selector visible in search panel
- [ ] Category badges showing in results (🔴/🔵)
- [ ] Analytics button (📊) visible in toolbar
- [ ] Semantic search working (if re-indexed)
- [ ] Query expansion working (test with "acoustic neuroma")
- [ ] Template recommendation working (test synthesis)

## Questions?

All enhancements are **backward compatible**. If you don't use the new features, the system behaves exactly as before.

**New features are opt-in through the UI** - no forced changes to your workflow!

