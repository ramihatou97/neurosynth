# Pre-Migration Baseline Tests

**Date**: 2025-12-07
**Branch**: monorepo-migration
**Commit**: 62a9d36

## Directory Structure (Before Migration)

```
/Users/ramihatoum/neurosynth/     (50GB - git repo)
├── src/neurosynth/               (Core synthesis engine)
├── src/deep_dx/                  (Deep-DX module)
├── reference-library/            (STALE - to be archived)
│   ├── main.py                   (Entry point)
│   ├── src/                      (Old implementation)
│   └── data/library.db           (May need migration)
├── neurosynth.db                 (Deep-DX database)
├── data/                         (Assets, Qdrant)
└── docker-compose.yml

/Users/ramihatoum/neuroLi/        (3.2MB - git repo)
└── reference-library/
    └── src/                      (ACTIVE implementation)
        ├── ui/app.py             (run_app() entry point)
        ├── search/               (Search modules)
        ├── cache/                (Database cache)
        └── utils/                (neurosynth_imports.py - import hack)

/Users/ramihatoum/cvu/            (56KB - no git)
└── library_to_deepdx_bridge.py   (ETL bridge)
```

## Current Import Patterns (TO FIX)

### neuroLi uses sys.path hacks:
```python
# In neuroLi/reference-library/src/utils/neurosynth_imports.py
import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "src"))
from neurosynth.parsers.image_extractor import ImageExtractor
```

### 35 files need import fixes:
- src/reference_library/ui/*.py (10 files)
- src/reference_library/search/*.py (15 files)
- src/reference_library/utils/*.py (7 files)
- src/reference_library/cache/*.py (3 files)

## Baseline Functionality Tests

### ✅ Test 1: Deep-DX Tests Pass
```bash
cd /Users/ramihatoum/neurosynth
./venv/bin/pytest tests/test_deep_dx/ -v
```
**Expected**: 40/40 tests pass (85-91% coverage)

### ✅ Test 2: Reference Library GUI Launches (neuroLi)
```bash
cd /Users/ramihatoum/neuroLi/reference-library
python src/ui/app.py
```
**Expected**: GUI launches, can search PDFs

### ✅ Test 3: Bridge Sync Works
```bash
cd /Users/ramihatoum/cvu
python library_to_deepdx_bridge.py
```
**Expected**: Syncs Reference Library → Deep-DX successfully

### ✅ Test 4: Docker Services Start
```bash
cd /Users/ramihatoum/neurosynth
docker-compose up -d
curl http://localhost:8000/health
```
**Expected**: API returns 200

## Post-Migration Success Criteria

After migration, ALL of the above tests should still pass, WITH:

1. ✅ No `sys.path.append()` calls in src/
2. ✅ Reference Library code in `src/reference_library/`
3. ✅ Bridge script in `src/bridges/library_to_deepdx.py`
4. ✅ Databases in `data/library.db`
5. ✅ Entry point: `python apps/reference-library.py`
6. ✅ Imports: `from reference_library.ui.app import run_app`

## Backup Files Created

- `~/neurosynth-backup-20251207.tar.gz` (excluding venv, htmlcov)
- `~/neuroLi-backup-20251207.tar.gz` (excluding venv)
- `~/cvu-backup-20251207.tar.gz`
- `~/neuroLi-patches.patch` (1.4MB git history)
- `~/neuroLi-commits.txt` (commit log)

## Rollback Plan

If migration fails:
```bash
cd /Users/ramihatoum
rm -rf neurosynth
tar -xzf neurosynth-backup-20251207.tar.gz
cd neurosynth
git checkout main
git branch -D monorepo-migration
```
