# Embedding Models for Semantic Search

The Reference Library supports multiple embedding models optimized for different use cases.

## Available Models

### 1. Medical (Default) - **Recommended for Neurosurgical Content**
- **Model**: `pritamdeka/S-PubMedBert-MS-MARCO`
- **Type**: `medical`
- **Description**: Fine-tuned on PubMed biomedical literature
- **Best for**: Medical and neurosurgical terminology
- **Size**: ~420MB
- **Speed**: Medium
- **Quality**: High for medical content

**When to use**: Default choice for neurosurgical reference libraries. Understands medical terminology, anatomical terms, and clinical concepts better than general models.

### 2. General - Fast & Lightweight
- **Model**: `all-MiniLM-L6-v2`
- **Type**: `general`
- **Description**: General-purpose sentence transformer
- **Best for**: Quick searches, general text
- **Size**: ~80MB
- **Speed**: Fast
- **Quality**: Good for general content

**When to use**: If you need faster indexing and search, or have limited disk space.

### 3. Retrieval - Optimized for Search
- **Model**: `BAAI/bge-small-en-v1.5`
- **Type**: `retrieval`
- **Description**: Optimized for retrieval tasks
- **Best for**: Balanced performance and quality
- **Size**: ~130MB
- **Speed**: Medium-Fast
- **Quality**: Very good

**When to use**: Good middle ground between speed and quality for general retrieval.

### 4. Large - Highest Quality
- **Model**: `BAAI/bge-large-en-v1.5`
- **Type**: `large`
- **Description**: Large model with best retrieval quality
- **Best for**: Maximum search accuracy
- **Size**: ~1.3GB
- **Speed**: Slower
- **Quality**: Excellent

**When to use**: When search quality is paramount and you have sufficient resources.

## Switching Models

### Method 1: Environment Variable (Recommended)
Set the `NEUROSYNTH_EMBEDDING_MODEL` environment variable before launching:

```bash
# Use medical model (default)
export NEUROSYNTH_EMBEDDING_MODEL=medical
python -m reference-library

# Use general model for faster performance
export NEUROSYNTH_EMBEDDING_MODEL=general
python -m reference-library

# Use large model for best quality
export NEUROSYNTH_EMBEDDING_MODEL=large
python -m reference-library
```

### Method 2: Edit config.py
Edit `reference-library/src/config.py`:

```python
EMBEDDING_MODEL_TYPE = "medical"  # Change to: general, medical, retrieval, or large
```

## Re-indexing After Model Change

**Important**: When you switch models, you need to re-index your library because embeddings from different models are not compatible.

1. Switch to the new model (using one of the methods above)
2. Launch the Reference Library
3. Go to **Tools → Index Semantic Search**
4. Wait for indexing to complete

The system automatically creates separate collections for each model type, so you can switch back and forth without losing your indexes.

## Performance Comparison

| Model Type | Index Speed | Search Speed | Quality (Medical) | Disk Space |
|-----------|-------------|--------------|-------------------|------------|
| General   | ⚡⚡⚡       | ⚡⚡⚡        | ⭐⭐⭐           | 80MB       |
| Medical   | ⚡⚡         | ⚡⚡          | ⭐⭐⭐⭐⭐       | 420MB      |
| Retrieval | ⚡⚡         | ⚡⚡          | ⭐⭐⭐⭐         | 130MB      |
| Large     | ⚡           | ⚡            | ⭐⭐⭐⭐⭐       | 1.3GB      |

## Recommendations by Use Case

### Neurosurgical Textbooks (Recommended)
```bash
export NEUROSYNTH_EMBEDDING_MODEL=medical
```
Best understanding of anatomical terms, surgical procedures, and clinical concepts.

### General Medical Literature
```bash
export NEUROSYNTH_EMBEDDING_MODEL=medical
```
or
```bash
export NEUROSYNTH_EMBEDDING_MODEL=retrieval
```

### Mixed Content (Medical + General)
```bash
export NEUROSYNTH_EMBEDDING_MODEL=retrieval
```

### Resource-Constrained Systems
```bash
export NEUROSYNTH_EMBEDDING_MODEL=general
```

### Maximum Accuracy (Research/Analysis)
```bash
export NEUROSYNTH_EMBEDDING_MODEL=large
```

## Technical Details

- **Collection Naming**: Each model type uses a separate ChromaDB collection (e.g., `neurosurgery_pages_medical`)
- **Embedding Dimensions**: 
  - General: 384
  - Medical: 768
  - Retrieval: 384
  - Large: 1024
- **Similarity Metric**: Cosine similarity for all models
- **First Run**: Models are downloaded automatically on first use

## Troubleshooting

### Model Download Fails
If model download fails, check your internet connection and try again. Models are cached in `~/.cache/huggingface/`.

### Out of Memory
If indexing fails with memory errors, try:
1. Switch to a smaller model (`general` or `retrieval`)
2. Close other applications
3. Index in smaller batches

### Search Quality Issues
If search results are poor:
1. Ensure you're using the `medical` model for neurosurgical content
2. Re-index your library
3. Try the `large` model for maximum quality

