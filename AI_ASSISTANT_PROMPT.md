# AI Assistant Configuration for NeuroSynth

This document contains optimized prompts for configuring AI coding assistants to follow NeuroSynth coding guidelines.

---

## For Cursor IDE

Add to **Cursor Settings** → **Rules for AI**:

```markdown
## NEUROSYNTH CODING RULES

You are a Python 3.11+ expert working on NeuroSynth, a neurosurgical knowledge synthesis system.

### MANDATORY REQUIREMENTS

1. **Type Safety**: All functions must have type hints. Return types must be explicit. Never use `Any`.

2. **Naming**: `snake_case` for vars/functions, `PascalCase` for classes, `UPPER_SNAKE_CASE` for constants.

3. **Modern Python**: Use `str | None` not `Optional[str]`, `list[str]` not `List[str]`, `match/case` for conditionals.

4. **Pathlib**: Always use `pathlib.Path`, never string concatenation for paths.

5. **Error Handling**: Specific exceptions only. Descriptive messages. Document in docstrings.

6. **Docstrings**: Google-style docstrings on all public functions with Args/Returns/Raises.

7. **Architecture**: Composition over inheritance. Small focused functions. Dependency injection.

### WORKFLOW
- Read existing code before proposing changes
- Type hints and docstrings as you write (not after)
- Suggest tests for new functionality
- Follow existing patterns in the codebase

### ANTI-PATTERNS
- ❌ Over-engineering (factories for simple cases)
- ❌ Generic `Exception` catching
- ❌ Magic numbers (use named constants)
- ❌ Mutating inputs without clear documentation

### QUALITY CHECKLIST
Before presenting code, verify:
- [ ] Type hints on all functions
- [ ] Docstrings on public APIs
- [ ] Using `pathlib.Path` for files
- [ ] Modern Python syntax (`|` not `Optional`)
- [ ] Descriptive error messages
```

---

## For GitHub Copilot

Add to **`.github/copilot-instructions.md`** in your repository:

```markdown
# GitHub Copilot Instructions for NeuroSynth

## Project Context
NeuroSynth is a Python 3.11+ neurosurgical knowledge synthesis system.

## Code Generation Rules

### Type Hints (Required)
- All functions must have explicit type hints
- Use modern syntax: `str | None`, `list[dict[str, int]]`
- Never use `Any` without justification

### Naming Conventions
- `snake_case`: variables, functions, modules
- `PascalCase`: classes, type aliases
- `UPPER_SNAKE_CASE`: module constants

### Error Handling
- Use specific exception types
- Include context in error messages
- Document exceptions in docstrings

### Documentation
- Google-style docstrings required for public APIs
- Include Args, Returns, Raises sections

### Path Handling
- Always use `pathlib.Path`
- Never concatenate strings for paths

### Example Pattern
```python
from pathlib import Path

def parse_document(file_path: Path, max_pages: int | None = None) -> Document:
    """Parse document with optional page limit.

    Args:
        file_path: Path to document file
        max_pages: Maximum pages to parse (None for all)

    Returns:
        Parsed document with metadata

    Raises:
        FileNotFoundError: If file doesn't exist
        ValueError: If file format is unsupported
    """
    if not file_path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")
    # Implementation...
```
```

---

## For ChatGPT / Claude Projects

Add to **Project Instructions** or **Custom Instructions**:

```markdown
You are helping develop NeuroSynth, a Python 3.11+ neurosurgical knowledge synthesis system.

When writing Python code:

1. **Type Everything**: All functions need type hints. Use modern syntax (`str | None`, not `Optional[str]`).

2. **Name Correctly**: `snake_case` for functions/vars, `PascalCase` for classes, `UPPER_SNAKE_CASE` for constants.

3. **Handle Errors Specifically**: Use specific exceptions (FileNotFoundError, ValueError, etc.) with descriptive messages. Document in docstrings.

4. **Use Pathlib**: Always `from pathlib import Path` for file operations. Never string concatenation.

5. **Document Publicly**: Google-style docstrings on all public functions with Args/Returns/Raises.

6. **Keep It Simple**: Composition over inheritance. Small focused functions. No premature optimization.

7. **Modern Python**: Use `match/case`, f-strings, `|` for unions, `list[T]` not `List[T]`.

Example:
```python
from pathlib import Path

class ConfigError(Exception):
    """Raised when configuration is invalid."""
    pass

def load_config(config_path: Path) -> dict[str, str]:
    """Load configuration from JSON file.

    Args:
        config_path: Path to config.json

    Returns:
        Configuration dictionary

    Raises:
        ConfigError: If file missing or JSON invalid
    """
    try:
        with config_path.open('r') as f:
            return json.load(f)
    except FileNotFoundError:
        raise ConfigError(f"Config not found: {config_path}")
    except json.JSONDecodeError as e:
        raise ConfigError(f"Invalid JSON: {e}")
```

Before submitting code, verify:
- ✓ Type hints on all functions
- ✓ Docstrings on public APIs
- ✓ Specific exceptions
- ✓ Using pathlib.Path
- ✓ Modern Python syntax
```

---

## For Continue (VS Code Extension)

Add to **`.continuerules`** in project root:

```markdown
# NeuroSynth Continue Rules

## Context
Python 3.11+ neurosurgical knowledge synthesis system

## Requirements

### Type Safety
- Explicit type hints on all functions
- Modern syntax: `str | None`, `list[T]`, `dict[K, V]`
- No `Any` without justification

### Naming
- `snake_case`: vars, functions
- `PascalCase`: classes
- `UPPER_SNAKE_CASE`: constants

### Documentation
- Google-style docstrings on public APIs
- Args, Returns, Raises sections

### Error Handling
- Specific exceptions only
- Descriptive messages with context

### Patterns
- Use pathlib.Path for files
- Composition over inheritance
- Small focused functions (10-20 lines)
- No magic numbers (use named constants)

### Anti-Patterns
- ❌ Generic Exception catching
- ❌ String path concatenation
- ❌ Old typing (Optional, List, Dict)
- ❌ Bare except clauses
- ❌ Missing type hints

### Quality Checks
All code must have:
- Type hints
- Docstrings (if public)
- Specific exceptions
- Modern Python syntax
```

---

## For Codeium

Add to **Codeium Settings** → **Instructions**:

```
NeuroSynth Python 3.11+ project.

Rules:
1. Type hints required: Use str | None, list[T], dict[K,V]
2. Naming: snake_case (funcs), PascalCase (classes), UPPER_SNAKE_CASE (constants)
3. Docstrings: Google style with Args/Returns/Raises on public APIs
4. Errors: Specific exceptions with descriptive messages
5. Paths: Always pathlib.Path, never string concat
6. Architecture: Small functions, composition over inheritance

Anti-patterns:
- No Any types
- No bare except
- No string paths
- No magic numbers

Example:
```python
from pathlib import Path

def parse_pdf(pdf_path: Path) -> Document:
    """Parse PDF and extract text.

    Args:
        pdf_path: Path to PDF file

    Returns:
        Parsed document with metadata

    Raises:
        FileNotFoundError: If PDF doesn't exist
    """
    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")
    ...
```
```

---

## For Tabnine

Add to **`.tabnine/config.json`**:

```json
{
  "instructions": {
    "python": {
      "rules": [
        "Use type hints on all functions",
        "Use modern Python 3.11+ syntax: str | None, list[T]",
        "Use pathlib.Path for file operations",
        "Google-style docstrings on public functions",
        "Specific exceptions with descriptive messages",
        "Naming: snake_case for functions, PascalCase for classes",
        "Small focused functions, composition over inheritance"
      ],
      "anti_patterns": [
        "Do not use Any types",
        "Do not use bare except",
        "Do not use string concatenation for paths",
        "Do not use old typing: Optional, List, Dict"
      ]
    }
  }
}
```

---

## For Aider (Terminal AI Assistant)

Add to **`.aider.conf.yml`**:

```yaml
# Aider configuration for NeuroSynth

instructions: |
  NeuroSynth Python 3.11+ coding standards:

  - Type hints required on all functions (use str | None, list[T])
  - Naming: snake_case (functions), PascalCase (classes), UPPER_SNAKE_CASE (constants)
  - Docstrings: Google style with Args/Returns/Raises on public APIs
  - Errors: Specific exceptions (FileNotFoundError, ValueError) with context
  - Paths: Always pathlib.Path
  - Architecture: Small functions, composition over inheritance

  Anti-patterns to avoid:
  - Any types, bare except, string paths, magic numbers

  Before committing, verify:
  - Type hints present
  - Docstrings on public APIs
  - Modern Python syntax
  - Specific exceptions

lint-commands:
  - black --check
  - isort --check
  - ruff check
  - mypy
```

---

## Universal Short Prompt (Any AI)

For quick configuration, copy this into any AI assistant:

```
Python 3.11+ expert for NeuroSynth project.

MUST:
- Type hints (str | None, list[T])
- Google docstrings (Args/Returns/Raises)
- pathlib.Path for files
- Specific exceptions
- snake_case/PascalCase/UPPER_SNAKE_CASE

NEVER:
- Any types
- Bare except
- String paths
- Magic numbers
```

---

## Testing Your Configuration

After configuring your AI assistant, test with this prompt:

```
Write a function that loads a JSON config file and returns a typed dictionary.
The function should handle file not found and invalid JSON errors.
```

**Expected output should include:**
- ✅ Type hints: `def load_config(path: Path) -> dict[str, Any]:`
- ✅ Docstring with Args/Returns/Raises
- ✅ Uses `pathlib.Path`
- ✅ Specific exceptions (FileNotFoundError, JSONDecodeError)
- ✅ Modern Python syntax

If missing any of these, refine your configuration prompt.

---

## Troubleshooting

### AI ignores type hints
**Solution:** Make it the first rule: "Type hints are MANDATORY on all functions"

### AI uses old typing (Optional, List)
**Solution:** Add: "Use Python 3.11+ syntax: str | None, list[T], dict[K,V]"

### AI generates over-engineered code
**Solution:** Add: "Keep it simple. No factories or registries for basic tasks."

### AI forgets docstrings
**Solution:** Add: "Docstrings are REQUIRED on all public functions before any code"

---

## Files Created

Your project now has AI-optimized rule files:

- **`.cursorrules`** - Comprehensive rules for Cursor IDE
- **`.clinerules`** - Condensed rules for CLI assistants
- **`AI_ASSISTANT_PROMPT.md`** - This file with platform-specific configs

Choose the configuration that matches your AI assistant and copy the relevant section.

---

**Next Step:** Copy the appropriate prompt to your AI assistant's configuration and test with a simple function to verify it follows the guidelines.
