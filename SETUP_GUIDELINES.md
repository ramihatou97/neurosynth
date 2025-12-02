# Coding Guidelines Setup & Integration Guide

This guide walks you through implementing the NeuroSynth coding guidelines in your development workflow.

---

## Quick Start (5 minutes)

```bash
# 1. Install development dependencies
make dev-install

# 2. Verify everything works
make check

# 3. Start coding with automated quality checks!
```

---

## Detailed Setup

### Step 1: Install Development Tools

```bash
# Option A: Using make (recommended)
make dev-install

# Option B: Manual installation
pip install -e ".[dev]"
pre-commit install
```

This installs:
- `black` - Code formatter
- `isort` - Import sorter
- `ruff` - Fast linter
- `flake8` - Additional linting
- `mypy` - Type checker
- `pytest` + `pytest-cov` - Testing framework
- `pre-commit` - Git hook manager

### Step 2: Verify Installation

```bash
# Run all quality checks
make check
```

This will:
1. Auto-format your code with `black` and `isort`
2. Run linting checks with `ruff` and `flake8`
3. Perform type checking with `mypy`
4. Execute test suite with coverage report

---

## Development Workflow

### Daily Development

```bash
# Before starting work
git checkout -b feature/your-feature-name

# Write code...

# Run checks frequently (auto-fixes formatting)
make check

# Commit (pre-commit hooks run automatically)
git add .
git commit -m "Add feature XYZ"

# If pre-commit hooks fail, fix issues and retry
make format  # Auto-fix formatting
git add .
git commit -m "Add feature XYZ"
```

### Individual Commands

```bash
# Format code only
make format

# Lint only
make lint

# Type check only
make type-check

# Test only
make test

# Run everything
make check
```

---

## Pre-commit Hooks

Pre-commit hooks automatically run before each commit. They will:

✅ **Auto-fix:**
- Code formatting (black)
- Import sorting (isort)
- Trailing whitespace
- File endings

⚠️ **Block commits if:**
- Type checking fails
- Linting errors found
- Large files detected (>1MB)
- Secrets/credentials detected
- Tests fail

### Bypass Pre-commit (Emergency Only)

```bash
# Skip pre-commit hooks (NOT RECOMMENDED)
git commit --no-verify -m "Emergency fix"
```

**Note:** CI/CD will still run all checks, so bypassing locally just delays the inevitable.

---

## IDE Integration

### VS Code

Create `.vscode/settings.json`:

```json
{
  "python.linting.enabled": true,
  "python.linting.pylintEnabled": false,
  "python.linting.flake8Enabled": true,
  "python.linting.mypyEnabled": true,
  "python.formatting.provider": "black",
  "python.sortImports.provider": "isort",
  "editor.formatOnSave": true,
  "editor.codeActionsOnSave": {
    "source.organizeImports": true
  },
  "[python]": {
    "editor.defaultFormatter": "ms-python.black-formatter",
    "editor.formatOnSave": true,
    "editor.rulers": [88]
  }
}
```

**Recommended Extensions:**
- Python (ms-python.python)
- Black Formatter (ms-python.black-formatter)
- Mypy Type Checker (ms-python.mypy-type-checker)
- Ruff (charliermarsh.ruff)

### PyCharm/IntelliJ IDEA

1. **Black Formatter:**
   - Settings → Tools → Black → Enable
   - Set line length to 88

2. **MyPy:**
   - Settings → Tools → External Tools → Add MyPy
   - Program: `mypy`
   - Arguments: `$FilePath$`

3. **File Watchers:**
   - Settings → Tools → File Watchers → Add
   - Add watchers for `black`, `isort`, `ruff`

---

## Configuration Files Reference

### `pyproject.toml`

All tool configurations are centralized in `pyproject.toml`:

```toml
[tool.black]
line-length = 88
target-version = ['py311']

[tool.isort]
profile = "black"
line_length = 88

[tool.mypy]
python_version = "3.11"
disallow_untyped_defs = true

[tool.pytest.ini_options]
addopts = ["--cov=src/neurosynth", "--cov-fail-under=80"]
```

### `.pre-commit-config.yaml`

Defines git hooks that run before commits:

```yaml
repos:
  - repo: https://github.com/psf/black
    rev: 24.1.0
    hooks:
      - id: black

  - repo: https://github.com/pre-commit/mirrors-mypy
    rev: v1.8.0
    hooks:
      - id: mypy
```

### `Makefile`

Convenience commands for common tasks:

```makefile
check: format lint type-check test
    @echo "✅ All checks passed!"
```

---

## Troubleshooting

### Issue: Pre-commit hooks too slow

**Solution:** Skip slow hooks during development:

```bash
# Only run fast hooks
SKIP=mypy,pytest git commit -m "WIP: feature"

# Run full check before pushing
make check
```

### Issue: MyPy errors in existing code

**Solution:** Gradually adopt strict typing:

```python
# Add type: ignore comments temporarily
result = legacy_function()  # type: ignore[no-untyped-call]
```

Then create issues to fix them properly.

### Issue: Black reformatted too much code

**Solution:** Stage changes in smaller chunks:

```bash
# Format only staged files
git diff --cached --name-only | xargs black

# Or commit file-by-file
git add src/neurosynth/specific_file.py
git commit -m "Refactor specific_file"
```

### Issue: Tests fail with coverage <80%

**Solution:** Write tests or exclude non-critical files:

```toml
# pyproject.toml
[tool.coverage.run]
omit = [
    "*/tests/*",
    "*/migrations/*",
    "*/config.py",
]
```

---

## CI/CD Integration

### GitHub Actions (`.github/workflows/ci.yml`)

```yaml
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
        run: make dev-install

      - name: Run checks
        run: make check

      - name: Upload coverage
        uses: codecov/codecov-action@v3
        with:
          files: ./coverage.xml
```

---

## Enforcement Strategy

### Phase 1: Soft Enforcement (Weeks 1-2)

- ✅ Install tools and pre-commit hooks
- ⚠️ Warnings only, no blocking
- 📊 Generate reports to identify issues

```bash
# Run checks but don't fail on errors
make format || true
make lint || true
make type-check || true
```

### Phase 2: Gradual Enforcement (Weeks 3-4)

- ✅ Block commits with formatting errors
- ✅ Block commits with linting errors
- ⚠️ Type checking warnings only

```yaml
# .pre-commit-config.yaml
- id: mypy
  args: ['--warn-only']  # Don't fail, just warn
```

### Phase 3: Full Enforcement (Week 5+)

- ✅ All checks must pass before commit
- ✅ CI/CD fails on any violation
- ✅ 80%+ test coverage required

---

## Team Onboarding

### New Developer Checklist

- [ ] Clone repository
- [ ] Run `make dev-install`
- [ ] Read `CODING_GUIDELINES.md`
- [ ] Run `make check` to verify setup
- [ ] Configure IDE settings (VS Code/PyCharm)
- [ ] Make first commit to test pre-commit hooks
- [ ] Review example PRs for code style

### Quick Reference Card

Print this for your desk:

```
┌─────────────────────────────────────┐
│   NeuroSynth Development Cheat Sheet │
├─────────────────────────────────────┤
│ make dev-install  → Setup env       │
│ make format       → Auto-format     │
│ make lint         → Check style     │
│ make type-check   → Verify types    │
│ make test         → Run tests       │
│ make check        → Run everything  │
│ make clean        → Remove artifacts│
├─────────────────────────────────────┤
│ Naming Conventions:                 │
│   snake_case  → variables, functions│
│   PascalCase  → classes, types      │
│   UPPER_SNAKE → constants           │
├─────────────────────────────────────┤
│ Line Length: 88 characters          │
│ Python Version: 3.11+               │
│ Test Coverage: 80% minimum          │
└─────────────────────────────────────┘
```

---

## Maintenance

### Update Dependencies

```bash
# Update pre-commit hooks
pre-commit autoupdate

# Update Python packages
pip install --upgrade black isort mypy ruff flake8

# Test everything still works
make check
```

### Review Configuration Quarterly

- Are linting rules too strict/loose?
- Are there new Python features to adopt?
- Can type checking be stricter?
- Is test coverage sufficient?

---

## Getting Help

- **Documentation:** See `CODING_GUIDELINES.md`
- **Makefile help:** Run `make help`
- **Pre-commit docs:** https://pre-commit.com
- **Tool-specific help:**
  - Black: https://black.readthedocs.io
  - MyPy: https://mypy.readthedocs.io
  - Ruff: https://docs.astral.sh/ruff

---

## Summary

✅ **You now have:**
- Automated code formatting
- Strict type checking
- Comprehensive linting
- Pre-commit quality gates
- Test coverage enforcement
- Consistent development workflow

🎯 **Next Steps:**
1. Run `make dev-install` to set up your environment
2. Review `CODING_GUIDELINES.md` for coding standards
3. Start coding with `make check` as your safety net
4. Configure your IDE for optimal experience

**Remember:** The goal is code quality and consistency, not perfection. Use these tools to help you write better code, not to frustrate you. If a rule doesn't make sense for your situation, let's discuss adjusting it.
