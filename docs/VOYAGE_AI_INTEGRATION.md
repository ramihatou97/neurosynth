# Voyage AI Integration in NeuroSynth

This document explains how Voyage AI is integrated into NeuroSynth, its specific role, the value it provides, and potential alternatives.

## Overview

Voyage AI is a semantic embedding service that converts text into high-dimensional numerical vectors (embeddings). NeuroSynth uses Voyage AI's `voyage-large-2-instruct` model to power its **semantic deduplication** and **document clustering** features.

## Role in NeuroSynth

### Primary Function: Text Embeddings

Voyage AI's core function in NeuroSynth is to generate semantic embeddings for document chunks. These embeddings enable:

1. **Semantic Similarity Detection**: Identify when two text chunks convey similar information even if worded differently
2. **Deduplication**: Remove redundant content from multiple source documents
3. **Clustering**: Group related content together for coherent chapter synthesis

### Integration Points

Voyage AI is integrated in the following components:

| Component | File | Usage |
|-----------|------|-------|
| VoyageClient | `src/neurosynth/llm/voyage.py` | Main client for embedding generation |
| EmbeddingGenerator | `src/neurosynth/dedup/embeddings.py` | Generates embeddings for content chunks |
| SemanticClusterer | `src/neurosynth/dedup/clustering.py` | Clusters chunks based on embedding similarity |
| PersistentEmbeddingCache | `src/neurosynth/llm/voyage.py` | SQLite-based cache for embeddings |

### Workflow

```
┌─────────────┐     ┌──────────────┐     ┌─────────────────┐
│  Document   │────▶│   Chunking   │────▶│  Voyage AI API  │
│  Processing │     │ (1000 words) │     │  (Embeddings)   │
└─────────────┘     └──────────────┘     └────────┬────────┘
                                                  │
                                                  ▼
┌─────────────┐     ┌──────────────┐     ┌─────────────────┐
│  Synthesis  │◀────│  Clustering  │◀────│ Similarity      │
│  (Claude)   │     │ (sklearn)    │     │ Matrix          │
└─────────────┘     └──────────────┘     └─────────────────┘
```

1. **Document Parsing**: PDFs, EPUBs, and other documents are parsed into text
2. **Chunking**: Text is split into ~1000-word chunks with 100-word overlap
3. **Embedding Generation**: Each chunk is sent to Voyage AI for embedding
4. **Similarity Computation**: Cosine similarity between embeddings creates a similarity matrix
5. **Agglomerative Clustering**: sklearn clusters similar chunks together
6. **Synthesis**: Claude AI synthesizes each cluster into coherent content

## Added Value

### Why Voyage AI?

1. **Instruction-Tuned Model**: `voyage-large-2-instruct` is specifically optimized for document retrieval and semantic similarity, making it ideal for deduplication tasks

2. **High-Quality Embeddings**: Voyage AI produces dense, semantically meaningful vectors that accurately capture document meaning

3. **Large Context Window**: Can handle chunks up to 8000 characters, suitable for academic/medical text

4. **Fast API Response**: Batch embedding support with configurable batch sizes (default: 32)

5. **Reliability**: Built-in retry logic with exponential backoff for rate limits and transient errors

### Cost-Benefit Analysis

| Aspect | Benefit |
|--------|---------|
| Deduplication | Reduces redundant synthesis (fewer Claude API calls) |
| Accuracy | Better semantic matching than keyword-based approaches |
| Caching | Persistent SQLite cache eliminates redundant embedding calls |
| Batch Processing | Efficient API usage with configurable batch sizes |

### Caching System

NeuroSynth includes a sophisticated embedding cache:

```python
# Cache is keyed by:
# - content_hash: MD5 of text content
# - model_name: "voyage-large-2-instruct"
# - chunk_config_hash: Hash of chunk_size + chunk_overlap
```

Features:
- **Persistent Storage**: SQLite with WAL mode for concurrent access
- **Memory Cache**: Hot path optimization with in-memory LRU
- **Size Management**: Automatic eviction when exceeding `embedding_cache_max_size_mb` (default: 500MB)
- **Model Invalidation**: Cache is automatically invalidated when model changes

## Configuration

### Environment Variables

```bash
# Required
VOYAGE_API_KEY=pa-...

# Optional (defaults shown)
VOYAGE_MODEL=voyage-large-2-instruct
```

### Settings (in `neurosynth.yaml`)

```yaml
# Similarity threshold for deduplication (0.0-1.0)
similarity_threshold: 0.92

# Chunk parameters affect embedding cache validity
chunk_size: 1000
chunk_overlap: 100
```

### Advanced Settings

| Setting | Default | Description |
|---------|---------|-------------|
| `voyage_batch_size` | 32 | Texts per API call |
| `embedding_concurrency` | 5 | Max concurrent API batches |
| `embedding_cache_enabled` | true | Enable persistent cache |
| `embedding_cache_path` | `~/.neurosynth/embedding_cache` | Cache location |
| `embedding_cache_max_size_mb` | 500 | Max cache size (0=unlimited) |

## Alternatives

### Open-Source Alternatives

| Model | Pros | Cons |
|-------|------|------|
| **sentence-transformers (HuggingFace)** | Free, local execution, many models | Requires GPU for speed, self-hosted |
| **OpenAI Embeddings (`text-embedding-3-large`)** | High quality, good docs | Paid API, different embedding space |
| **Cohere Embed v3** | Good quality, multilingual | Paid API |
| **BGE / E5 Models** | Open-source, competitive quality | Self-hosted, requires infrastructure |
| **Nomic Embed** | Open weights, long context | Newer, less battle-tested |

### Comparison Matrix

| Feature | Voyage AI | OpenAI | sentence-transformers | Cohere |
|---------|-----------|--------|----------------------|--------|
| Cost | Paid | Paid | Free* | Paid |
| Quality | Excellent | Excellent | Good-Excellent | Excellent |
| Local Execution | No | No | Yes | No |
| Instruction-Tuned | Yes | Yes | Some | Yes |
| Max Tokens | 16K | 8K | 512-8K | 96K |
| Batch API | Yes | Yes | N/A | Yes |

*Free to run but requires compute resources

### Migration Considerations

To switch embedding providers:

1. **Clear Existing Cache**: Embeddings are model-specific
2. **Update VoyageClient**: Implement alternative client interface
3. **Adjust Similarity Threshold**: Different models may need different thresholds
4. **Test Clustering Quality**: Ensure deduplication accuracy is maintained

### Implementing an Alternative

If you want to use a different embedding provider, create a new client that implements:

```python
class EmbeddingClient:
    async def embed_texts(self, texts: list[str]) -> list[np.ndarray]:
        """Generate embeddings for multiple texts."""
        pass
    
    async def embed_text(self, text: str) -> np.ndarray:
        """Generate embedding for a single text."""
        pass
```

Then update `EmbeddingGenerator` in `src/neurosynth/dedup/embeddings.py` to use your client.

## Troubleshooting

### Rate Limiting

Voyage AI has rate limits. If you encounter rate limit errors:

```bash
# Reduce batch size
VOYAGE_BATCH_SIZE=16

# Or reduce concurrency
EMBEDDING_CONCURRENCY=3
```

### Cache Issues

To clear the embedding cache:

```bash
rm -rf ~/.neurosynth/embedding_cache
```

Or use the CLI:

```bash
neurosynth cache clear
```

### API Key Issues

Ensure your API key is set:

```bash
export VOYAGE_API_KEY=pa-your-key-here
# Or add to .env file
```

## Cost Estimation

Voyage AI pricing (as of 2024):
- `voyage-large-2-instruct`: ~$0.12 per million tokens

Typical project costs:
- 10 PDFs (~500 pages): ~50,000 tokens → ~$0.006
- 50 PDFs (~2,500 pages): ~250,000 tokens → ~$0.03
- With caching, repeat runs cost nothing

## Summary

Voyage AI provides the semantic intelligence that enables NeuroSynth to:

1. **Intelligently deduplicate** content from multiple sources
2. **Cluster related information** for coherent synthesis
3. **Reduce Claude API costs** by eliminating redundant content

The integration includes robust error handling, persistent caching, and configurable parameters to balance quality and cost. While alternatives exist, Voyage AI's instruction-tuned model and purpose-built embedding quality make it well-suited for NeuroSynth's document synthesis workflow.
