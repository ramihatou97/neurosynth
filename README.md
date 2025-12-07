# NeuroSynth Monorepo

**Neurosurgical Knowledge Synthesis System** - A unified repository containing the core synthesis engine, reference library GUI, Deep-DX diagnostic knowledge base, and ETL bridges.

## Overview

This monorepo consolidates three previously separate tools into a unified codebase:

1. **NeuroSynth CLI & API** - Core synthesis engine that processes neurosurgical reference documents (PDF, EPUB, DOCX, TXT) and synthesizes them into well-structured academic chapters using AI
2. **Reference Library** - Desktop GUI application for searching and managing neurosurgical PDF references with semantic search
3. **Deep-DX** - Diagnostic knowledge synthesis module with vector search
4. **ETL Bridges** - Data synchronization between Reference Library and Deep-DX

### Core Features

- Multi-document parsing and semantic analysis
- AI-powered deduplication and conflict detection
- Knowledge synthesis and outline generation
- Academic output generation (LaTeX/PDF and Markdown)
- Desktop GUI for PDF library management
- Semantic and visual search capabilities
- Vector-based knowledge retrieval

## Prerequisites

- **Python 3.11+**
- **LaTeX** (for PDF output) - install via:
  - macOS: `brew install --cask mactex`
  - Ubuntu: `apt install texlive-latex-extra`
  - Windows: [MiKTeX](https://miktex.org/download)
- **API Keys** (required):
  - [Anthropic Claude](https://console.anthropic.com/) - for synthesis
  - [Google Gemini](https://makersuite.google.com/app/apikey) - for extraction
  - [Voyage AI](https://www.voyageai.com/) - for embeddings

## Monorepo Structure

```
neurosynth/                      # Root
├── src/
│   ├── neurosynth/              # Core synthesis engine
│   ├── deep_dx/                 # Deep diagnostic module
│   ├── reference_library/       # Reference Library GUI
│   └── bridges/                 # ETL scripts
├── apps/                        # Entry points
│   ├── reference-library.py     # GUI launcher
│   ├── api.py                   # FastAPI app
│   └── worker.py                # Worker service
├── data/                        # Centralized data
│   ├── library.db               # Reference Library cache
│   ├── neurosynth.db            # Deep-DX database
│   └── qdrant/                  # Vector storage
├── tests/                       # All tests
└── docker-compose.yml           # Multi-service deployment
```

## Installation

### Core Installation (CLI only)

```bash
# Clone the repository
git clone https://github.com/yourusername/neurosynth.git
cd neurosynth

# Create and activate virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install core dependencies
pip install -e .

# Configure API keys
cp .env.example .env
# Edit .env with your API keys
```

### Full Installation (All Components)

```bash
# Install all components including GUI, API, worker, and visual processing
pip install -e ".[full]"
```

### Component-Specific Installation

```bash
# API service only
pip install -e ".[api]"

# Reference Library GUI only
pip install -e ".[gui]"

# Worker service only
pip install -e ".[worker]"

# Visual processing (ColPali) only
pip install -e ".[visual]"
```

## Quick Start

```bash
# 1. Initialize a new project
neurosynth init "Vestibular Schwannoma"

# 2. Add source documents
cd vestibular_schwannoma
neurosynth add ../references/*.pdf

# 3. Process documents (parse, chunk, deduplicate)
neurosynth process

# 4. Synthesize the chapter
neurosynth synthesize

# Or run the full pipeline in one command:
neurosynth run "Vestibular Schwannoma" --sources ./references/ --output chapter.pdf
```

## CLI Commands

| Command | Description |
|---------|-------------|
| `neurosynth init TOPIC` | Initialize a new synthesis project |
| `neurosynth add FILES` | Add source documents to project |
| `neurosynth process` | Parse, chunk, and deduplicate documents |
| `neurosynth synthesize` | Generate chapter from processed data |
| `neurosynth run TOPIC` | Full pipeline (process + synthesize) |
| `neurosynth status` | Show project status |
| `neurosynth version` | Show version information |

### Command Options

```bash
# Process with cache disabled
neurosynth process --no-cache

# Synthesize to markdown instead of LaTeX
neurosynth synthesize --format markdown

# Full pipeline with custom output
neurosynth run "Topic Name" --sources ./docs/ --output result.pdf
```

## Additional Components

### Reference Library GUI

Desktop application for searching and managing your neurosurgical PDF library:

```bash
# Launch the Reference Library GUI
python apps/reference-library.py

# Or if installed with GUI dependencies:
neuro-ref
```

**Features:**
- Semantic search across PDF content
- Visual search using ColPali embeddings
- Automatic PDF indexing and caching
- Category-based organization
- Export search results to PDF

### ETL Bridge (Reference Library → Deep-DX)

Sync data from Reference Library to the Deep-DX knowledge base:

```bash
# Run the bridge sync
python -m bridges.library_to_deepdx

# Or if installed with entry point:
neuro-bridge
```

**What it does:**
- Extracts PDF text from Reference Library cache (library.db)
- Aggregates pages into semantic chunks
- Generates embeddings using Voyage AI
- Loads into Deep-DX database (neurosynth.db) and Qdrant vector store

### API Service (Production Deployment)

Run the FastAPI service for programmatic access:

```bash
# Development mode
uvicorn neurosynth.api.main:app --reload

# Production mode (with Docker)
docker-compose up -d api worker
```

**Endpoints:**
- `POST /synthesize` - Create synthesis job
- `GET /status/{job_id}` - Check job status
- `GET /health` - Health check

## Configuration

### Environment Variables

Create a `.env` file in your project root:

```bash
# Required API Keys
ANTHROPIC_API_KEY=sk-ant-...
GOOGLE_API_KEY=...
VOYAGE_API_KEY=pa-...

# Optional: Override default models
GEMINI_MODEL=gemini-2.0-flash-exp
CLAUDE_MODEL=claude-sonnet-4-20250514
VOYAGE_MODEL=voyage-large-2-instruct
```

### Processing Parameters

These can be configured in `neurosynth.yaml` (created by `init`):

| Parameter | Default | Description |
|-----------|---------|-------------|
| `chunk_size` | 1000 | Target chunk size in words |
| `chunk_overlap` | 100 | Overlap between chunks |
| `similarity_threshold` | 0.92 | Cosine similarity for deduplication |
| `output_format` | latex | Output format (latex/markdown) |

## Project Structure

After initialization, your project will have:

```
project_name/
├── sources/          # Source documents (PDF, EPUB, etc.)
├── processed/        # Processed data (clusters.pkl)
├── output/           # Generated chapters (LaTeX, PDF, Markdown)
└── neurosynth.yaml   # Project configuration
```

## Supported Formats

| Format | Extensions | Notes |
|--------|------------|-------|
| PDF | `.pdf` | Full text extraction with PyMuPDF |
| EPUB | `.epub` | E-book format support |
| Word | `.docx`, `.doc` | Microsoft Word documents |
| Text | `.txt`, `.md` | Plain text and Markdown |

## Troubleshooting

### "API key not found" error
Ensure your `.env` file exists and contains valid API keys. Check that you're running commands from the project directory.

### PDF compilation fails
Ensure LaTeX is installed:
```bash
pdflatex --version
```
If not installed, the tool will output `.tex` files that you can compile manually.

### Out of memory during processing
For large document sets, process in smaller batches or increase system memory. Consider using `--no-cache` if embeddings are causing issues.

### Rate limiting from APIs
The tool makes multiple API calls. If you hit rate limits, wait a few minutes and retry. Consider adding delays between large batch operations.

## Development

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run tests
pytest tests/

# Format code
black src/
ruff check src/
```

## License

MIT License - see LICENSE file for details.

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Run tests and linting
5. Submit a pull request
