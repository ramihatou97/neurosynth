# NeuroSynth Coding Guidelines

**Version:** 1.0
**Last Updated:** 2025-12-02

---

## Purpose

This document establishes coding standards, architectural principles, and development workflows for the NeuroSynth project. These guidelines ensure code quality, maintainability, and consistency across the codebase—whether written by humans or AI assistants.

---

## Table of Contents

1. [Workflow & Process](#1-workflow--process)
2. [Architecture & Design Principles](#2-architecture--design-principles)
3. [Type Safety & Robustness](#3-type-safety--robustness)
4. [Syntax & Conventions](#4-syntax--conventions)
5. [Python-Specific Guidelines](#5-python-specific-guidelines)
6. [Testing & Quality Assurance](#6-testing--quality-assurance)
7. [AI Assistant Configuration](#7-ai-assistant-configuration)

---

## 1. Workflow & Process

### 1.1 Iterative Implementation

**Principle:** Build incrementally, test frequently, commit often.

- **Small Commits:** Each commit should represent a single logical unit of work
- **Immediate Testing:** Test functionality after each implementation step to prevent regression
- **Incremental Delivery:** Avoid large, monolithic changes—break features into small, deliverable pieces

**Example Workflow:**
```bash
# Bad: Implement entire feature → test → commit
git commit -m "Add user authentication with OAuth, JWT, Redis sessions, and email verification"

# Good: Incremental approach
git commit -m "Add User model with basic fields"
git commit -m "Add JWT token generation utilities"
git commit -m "Add authentication endpoints"
git commit -m "Add session management with Redis"
```

### 1.2 Prioritize End-to-End Flows

**Principle:** Always keep the user workflow in mind.

- Code should facilitate seamless user experiences, not just pass unit tests
- Consider the complete data flow from user input → processing → output
- Validate that features work in production-like scenarios

**Example:**
```python
# When implementing a PDF extraction feature:
# 1. Test with real PDF files from data/sources/
# 2. Verify output quality in data/processed/
# 3. Ensure error handling for corrupted PDFs
# 4. Check memory usage with large files (100+ MB)
```

### 1.3 Parity Between Components

**Principle:** Logic, validation rules, and data structures must be consistent.

- Backend changes must be reflected in frontend/CLI interfaces
- Validation rules should match across all layers
- Error messages should be consistent

**Example:**
```python
# Backend validation
def validate_chapter_title(title: str) -> None:
    if len(title) < 3:
        raise ValueError("Chapter title must be at least 3 characters")
    if len(title) > 200:
        raise ValueError("Chapter title cannot exceed 200 characters")

# CLI should enforce same rules BEFORE making API call
```

---

## 2. Architecture & Design Principles

### 2.1 Simplicity First (KISS)

**Principle:** Write refactored, non-over-engineered code.

- Avoid premature optimization
- Prefer readable code over "clever" code
- Don't add features "just in case"—implement only what's needed now

**Example:**
```python
# Bad: Over-engineered abstraction factory
class DocumentParserFactory:
    _parsers = {}

    @classmethod
    def register_parser(cls, file_type: str, parser_class: Type[BaseParser]):
        cls._parsers[file_type] = parser_class

    @classmethod
    def create_parser(cls, file_type: str) -> BaseParser:
        return cls._parsers[file_type]()

# Good: Simple, direct approach
def get_parser(file_path: str) -> BaseParser:
    ext = file_path.suffix.lower()
    if ext == '.pdf':
        return PDFParser()
    elif ext == '.epub':
        return EPUBParser()
    elif ext == '.docx':
        return DOCXParser()
    else:
        raise ValueError(f"Unsupported file type: {ext}")
```

### 2.2 Composition Over Inheritance

**Principle:** Favor functional composition and modular components.

- Avoid deep inheritance hierarchies
- Use composition, mixins, or protocols instead
- Prefer small, focused functions that can be combined

**Example:**
```python
# Bad: Deep inheritance
class BaseParser:
    def parse(self): pass

class PDFParser(BaseParser):
    def parse(self): pass

class EnhancedPDFParser(PDFParser):
    def parse_with_ocr(self): pass

# Good: Composition
class PDFParser:
    def __init__(self, text_extractor: TextExtractor, image_extractor: ImageExtractor):
        self.text_extractor = text_extractor
        self.image_extractor = image_extractor

    def parse(self, pdf_path: Path) -> Document:
        text = self.text_extractor.extract(pdf_path)
        images = self.image_extractor.extract(pdf_path)
        return Document(text=text, images=images)
```

### 2.3 Pragmatic DRY (Don't Repeat Yourself)

**Principle:** Avoid duplicating business logic, but prefer minor duplication over complex abstractions.

- Don't abstract after the first duplication—wait for 3+ instances
- Sometimes duplication is better than the wrong abstraction
- Prioritize readability over strict adherence to DRY

**Example:**
```python
# Acceptable duplication (2 instances, different contexts)
def validate_pdf_source(path: Path) -> bool:
    return path.exists() and path.suffix == '.pdf' and path.stat().st_size > 0

def validate_epub_source(path: Path) -> bool:
    return path.exists() and path.suffix == '.epub' and path.stat().st_size > 0

# Abstraction justified (3+ instances with identical logic)
def validate_source_file(path: Path, expected_suffix: str) -> bool:
    return path.exists() and path.suffix == expected_suffix and path.stat().st_size > 0
```

### 2.4 Seamless Integration

**Principle:** Components should snap together easily without heavy "glue code."

- Design clear interfaces between modules
- Use well-defined contracts (type hints, protocols)
- Minimize coupling between components

---

## 3. Type Safety & Robustness

### 3.1 Strict Type Safety

**Principle:** Use Python type hints rigorously. Avoid `Any`.

- All function signatures must have type hints
- Use `mypy` in strict mode
- Explicitly type return values

**Configuration:**
```ini
# mypy.ini (or pyproject.toml)
[mypy]
python_version = 3.11
warn_return_any = True
warn_unused_configs = True
disallow_untyped_defs = True
disallow_any_explicit = True
disallow_any_generics = True
```

**Example:**
```python
# Bad: No type hints
def process_document(doc):
    return extract_text(doc)

# Good: Explicit types
def process_document(doc: Document) -> ProcessedText:
    """Extract and clean text from a document.

    Args:
        doc: Source document to process

    Returns:
        Processed text with metadata
    """
    return extract_text(doc)
```

### 3.2 Explicit Contracts

**Principle:** Document all inputs, outputs, and side effects.

- Use docstrings for all public functions
- Specify exceptions that can be raised
- Document side effects (file I/O, API calls, etc.)

**Example:**
```python
def synthesize_chapter(
    sources: list[Document],
    outline: ChapterOutline,
    api_key: str
) -> SynthesizedChapter:
    """Synthesize a chapter from multiple source documents.

    Args:
        sources: List of parsed source documents
        outline: Target chapter outline structure
        api_key: Anthropic API key for Claude

    Returns:
        Synthesized chapter with citations and metadata

    Raises:
        APIError: If Anthropic API request fails
        ValueError: If sources list is empty

    Side Effects:
        - Makes API calls to Anthropic Claude
        - Writes progress logs to logs/synthesis.log
    """
    if not sources:
        raise ValueError("sources list cannot be empty")
    # Implementation...
```

### 3.3 Safe Access Patterns

**Principle:** Prevent `None`/`AttributeError` crashes with defensive coding.

- Use optional chaining pattern (`.get()` for dicts)
- Provide sensible defaults with `or` operator
- Validate inputs at function boundaries

**Example:**
```python
# Bad: Unsafe access
def get_author_name(metadata: dict) -> str:
    return metadata['authors'][0]['name']  # Can crash!

# Good: Safe access with defaults
def get_author_name(metadata: dict) -> str:
    """Extract primary author name from metadata.

    Returns:
        Author name, or "Unknown" if not found
    """
    authors = metadata.get('authors', [])
    if authors and len(authors) > 0:
        return authors[0].get('name', 'Unknown')
    return 'Unknown'

# Even better: Use Pydantic models
from pydantic import BaseModel, Field

class Author(BaseModel):
    name: str = "Unknown"

class Metadata(BaseModel):
    authors: list[Author] = Field(default_factory=list)

def get_author_name(metadata: Metadata) -> str:
    return metadata.authors[0].name if metadata.authors else "Unknown"
```

---

## 4. Syntax & Conventions

### 4.1 Naming Conventions

Follow [PEP 8](https://peps.python.org/pep-0008/) strictly:

| Element | Convention | Example |
|---------|------------|---------|
| **Variables** | `snake_case` | `chapter_title`, `pdf_path` |
| **Functions** | `snake_case` | `parse_document()`, `extract_images()` |
| **Classes** | `PascalCase` | `PDFParser`, `DocumentSynthesizer` |
| **Constants** | `UPPER_SNAKE_CASE` | `MAX_FILE_SIZE`, `API_TIMEOUT` |
| **Private** | `_leading_underscore` | `_internal_helper()`, `_cache` |
| **Modules** | `snake_case` | `pdf_parser.py`, `synthesis_engine.py` |

**Example:**
```python
# Constants
MAX_RETRIES = 3
DEFAULT_TIMEOUT = 30

# Class
class ChapterSynthesizer:
    """Synthesizes chapters from multiple sources."""

    def __init__(self, api_key: str):
        self._api_client = AnthropicClient(api_key)  # Private attribute

    def synthesize_chapter(self, sources: list[Document]) -> Chapter:
        """Public method."""
        return self._process_sources(sources)  # Private method

    def _process_sources(self, sources: list[Document]) -> Chapter:
        """Internal helper method."""
        # Implementation...
```

### 4.2 Impeccable Syntax

**Principle:** Maintain clean, linted code at all times.

- Use **Black** for automatic formatting (line length: 88)
- Use **isort** for import sorting
- Use **flake8** for linting
- Remove unused imports and variables immediately

**Configuration:**
```toml
# pyproject.toml
[tool.black]
line-length = 88
target-version = ['py311']

[tool.isort]
profile = "black"
line_length = 88

[tool.flake8]
max-line-length = 88
extend-ignore = E203, W503
```

**Pre-commit Hook:**
```bash
# Install pre-commit
pip install pre-commit

# .pre-commit-config.yaml
repos:
  - repo: https://github.com/psf/black
    rev: 23.3.0
    hooks:
      - id: black

  - repo: https://github.com/PyCQA/isort
    rev: 5.12.0
    hooks:
      - id: isort

  - repo: https://github.com/PyCQA/flake8
    rev: 6.0.0
    hooks:
      - id: flake8
```

---

## 5. Python-Specific Guidelines

### 5.1 Modern Python Features

Use Python 3.11+ features:

```python
# Type unions with |
def parse(file_path: str | Path) -> Document:
    ...

# Structural pattern matching
match file_type:
    case "pdf":
        return PDFParser()
    case "epub":
        return EPUBParser()
    case _:
        raise ValueError(f"Unsupported: {file_type}")

# Exception groups (Python 3.11+)
try:
    process_batch(documents)
except* APIError as eg:
    log_api_errors(eg.exceptions)
except* ValidationError as eg:
    log_validation_errors(eg.exceptions)
```

### 5.2 Path Handling

Always use `pathlib.Path`, never raw strings:

```python
from pathlib import Path

# Bad
source_dir = "data/sources"
pdf_file = source_dir + "/document.pdf"

# Good
source_dir = Path("data/sources")
pdf_file = source_dir / "document.pdf"

# Validation
if not pdf_file.exists():
    raise FileNotFoundError(f"PDF not found: {pdf_file}")
```

### 5.3 Error Handling

Use specific exceptions and provide context:

```python
# Bad: Generic exception
def load_config(path):
    try:
        with open(path) as f:
            return json.load(f)
    except Exception as e:
        print(f"Error: {e}")
        return None

# Good: Specific exceptions with context
from pathlib import Path
import json

class ConfigError(Exception):
    """Raised when configuration loading fails."""
    pass

def load_config(config_path: Path) -> dict:
    """Load configuration from JSON file.

    Args:
        config_path: Path to config.json

    Returns:
        Configuration dictionary

    Raises:
        ConfigError: If file doesn't exist or JSON is invalid
    """
    try:
        with config_path.open('r') as f:
            return json.load(f)
    except FileNotFoundError:
        raise ConfigError(f"Config file not found: {config_path}")
    except json.JSONDecodeError as e:
        raise ConfigError(f"Invalid JSON in {config_path}: {e}")
```

---

## 6. Testing & Quality Assurance

### 6.1 Test Coverage

Maintain minimum 80% test coverage:

```bash
# Run tests with coverage
pytest --cov=src --cov-report=html --cov-report=term-missing

# Coverage configuration
[tool.pytest.ini_options]
testpaths = ["tests"]
python_files = ["test_*.py"]
python_functions = ["test_*"]
addopts = "--cov=src --cov-report=html --cov-report=term-missing --cov-fail-under=80"
```

### 6.2 Test Organization

```
tests/
├── unit/               # Fast, isolated tests
│   ├── test_parsers.py
│   └── test_extractors.py
├── integration/        # Tests with external dependencies
│   ├── test_api_integration.py
│   └── test_pdf_processing.py
└── fixtures/           # Test data
    ├── sample.pdf
    └── mock_responses.json
```

### 6.3 Test Examples

```python
import pytest
from pathlib import Path
from neurosynth.parsers import PDFParser

class TestPDFParser:
    """Test suite for PDF parsing functionality."""

    @pytest.fixture
    def sample_pdf(self) -> Path:
        """Provide path to test PDF."""
        return Path("tests/fixtures/sample.pdf")

    @pytest.fixture
    def parser(self) -> PDFParser:
        """Create PDFParser instance."""
        return PDFParser()

    def test_parse_valid_pdf(self, parser, sample_pdf):
        """Should successfully parse valid PDF."""
        result = parser.parse(sample_pdf)

        assert result.text is not None
        assert len(result.text) > 0
        assert result.metadata.page_count > 0

    def test_parse_missing_file(self, parser):
        """Should raise FileNotFoundError for missing file."""
        with pytest.raises(FileNotFoundError):
            parser.parse(Path("nonexistent.pdf"))

    def test_parse_corrupted_pdf(self, parser):
        """Should handle corrupted PDF gracefully."""
        corrupted_pdf = Path("tests/fixtures/corrupted.pdf")

        with pytest.raises(PDFParseError) as exc_info:
            parser.parse(corrupted_pdf)

        assert "corrupted" in str(exc_info.value).lower()
```

---

## 7. AI Assistant Configuration

### 7.1 System Prompt for AI Coding Assistants

Use this prompt with Cursor, Copilot, or ChatGPT:

```markdown
## CODING RULES & BEHAVIORS

**1. PHILOSOPHY**
- **Refactored & Pragmatic:** Avoid over-engineering. Write code that is simple to read and easy to delete.
- **Incremental:** Generate code in small, testable chunks. Do not hallucinate massive files in one go.

**2. ARCHITECTURE**
- **Composition > Inheritance:** Use functional patterns over class hierarchies.
- **Component Parity:** Ensure data structures and validation rules match across all layers.

**3. SYNTAX & TYPING**
- **Strict Typing:** No `any`. Explicitly define return types. Use type hints for all functions.
- **Safety:** Always validate inputs and provide defaults for optional values.
- **Naming:**
  - `PascalCase`: Classes, Types
  - `snake_case`: Variables, Functions
  - `UPPER_SNAKE_CASE`: Constants

**4. INTEGRATION**
- Ensure all new logic seamlessly integrates with existing components.
- Break down complex workflows into step-by-step logic before writing code.
- Test end-to-end flows, not just isolated units.

**5. BEFORE CODING**
- Read existing code before proposing changes
- Check for existing similar implementations
- Verify integration points
- Consider the complete user workflow
```

### 7.2 Code Review Checklist

Before submitting code (human or AI-generated):

- [ ] Type hints on all functions
- [ ] Docstrings on all public functions/classes
- [ ] No unused imports or variables
- [ ] Passes `black`, `isort`, `flake8`
- [ ] Passes `mypy --strict`
- [ ] Tests written and passing
- [ ] Integration tested with real data
- [ ] Error handling for edge cases
- [ ] Logging added for debugging
- [ ] Updated relevant documentation

---

## 8. Enforcement

### 8.1 Automated Checks

```bash
# Run all checks before committing
make check

# Makefile
.PHONY: check
check: format lint type-check test

.PHONY: format
format:
	black src/ tests/
	isort src/ tests/

.PHONY: lint
lint:
	flake8 src/ tests/

.PHONY: type-check
type-check:
	mypy src/

.PHONY: test
test:
	pytest --cov=src --cov-fail-under=80
```

### 8.2 CI/CD Pipeline

```yaml
# .github/workflows/ci.yml
name: CI

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3

      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: |
          pip install -e .[dev]

      - name: Format check
        run: |
          black --check src/ tests/
          isort --check src/ tests/

      - name: Lint
        run: flake8 src/ tests/

      - name: Type check
        run: mypy src/

      - name: Test
        run: pytest --cov=src --cov-fail-under=80
```

---

## 9. References

- [PEP 8 – Style Guide for Python Code](https://peps.python.org/pep-0008/)
- [PEP 257 – Docstring Conventions](https://peps.python.org/pep-0257/)
- [Google Python Style Guide](https://google.github.io/styleguide/pyguide.html)
- [Black Code Style](https://black.readthedocs.io/en/stable/the_black_code_style/)
- [mypy Documentation](https://mypy.readthedocs.io/)

---

## 10. Revision History

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | 2025-12-02 | Initial guidelines established |

---

**Questions or suggestions?** Open an issue or submit a PR to improve these guidelines.
