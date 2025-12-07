"""Integration tests for monorepo migration.

Validates that the consolidation of neurosynth, neuroLi, and cvu
directories into a unified monorepo structure works correctly.
"""

import subprocess
from pathlib import Path

import pytest


# Test fixtures
@pytest.fixture
def repo_root():
    """Get repository root directory."""
    return Path(__file__).parent.parent.parent


def test_import_reference_library(repo_root):
    """Test that reference_library modules can be imported."""
    # Config and logger
    from reference_library.config import DATA_DIR
    from reference_library.logger import get_logger
    from reference_library.ui.app import run_app

    assert callable(run_app)
    assert callable(get_logger)
    assert DATA_DIR.name == "data"


def test_import_bridges(repo_root):
    """Test that bridge scripts can be imported."""
    from bridges.library_to_deepdx import LibraryToDeepDxBridge

    assert LibraryToDeepDxBridge is not None


def test_database_paths_exist(repo_root):
    """Test that database files exist at expected paths."""
    data_dir = repo_root / "data"

    # Check directory exists
    assert data_dir.exists(), f"data/ directory not found at {data_dir}"

    # Check database files exist (created by migration script)
    neurosynth_db = data_dir / "neurosynth.db"
    library_db = data_dir / "library.db"

    assert (
        neurosynth_db.exists()
    ), f"neurosynth.db not found at {neurosynth_db} (run migration script first)"
    assert (
        library_db.exists()
    ), f"library.db not found at {library_db} (run migration script first)"


def test_no_sys_path_hacks():
    """Test that sys.path manipulation has been removed from codebase."""
    result = subprocess.run(
        ["grep", "-r", "sys.path.append", "src/reference_library/", "src/bridges/"],
        capture_output=True,
        text=True,
    )

    # grep returns exit code 1 when no matches found (what we want)
    assert result.returncode == 1, f"Found sys.path.append in code:\n{result.stdout}"

    result = subprocess.run(
        ["grep", "-r", "sys.path.insert", "src/reference_library/", "src/bridges/"],
        capture_output=True,
        text=True,
    )

    assert result.returncode == 1, f"Found sys.path.insert in code:\n{result.stdout}"


def test_package_structure(repo_root):
    """Test that monorepo package structure exists."""
    src = repo_root / "src"

    # Core packages
    assert (src / "neurosynth").exists(), "src/neurosynth/ missing"
    assert (src / "deep_dx").exists(), "src/deep_dx/ missing"

    # Migrated packages
    assert (src / "reference_library").exists(), "src/reference_library/ missing"
    assert (src / "bridges").exists(), "src/bridges/ missing"

    # Entry points
    apps = repo_root / "apps"
    assert apps.exists(), "apps/ directory missing"
    assert (apps / "reference-library.py").exists(), "apps/reference-library.py missing"


def test_docker_configs(repo_root):
    """Test that Docker configurations use monorepo paths."""
    docker_compose = repo_root / "docker-compose.yml"
    assert docker_compose.exists(), "docker-compose.yml missing"

    content = docker_compose.read_text()

    # Should use ./data volume mount
    assert "./data:/data" in content, "Docker config doesn't mount ./data:/data"

    # Should NOT use old reference-library mount
    assert (
        "./reference-library:" not in content
    ), "Docker config still references ./reference-library"


def test_gitignore_updated(repo_root):
    """Test that .gitignore reflects monorepo structure."""
    gitignore = repo_root / ".gitignore"
    assert gitignore.exists(), ".gitignore missing"

    content = gitignore.read_text()

    # Should ignore old directories
    assert (
        "reference-library/" in content
    ), ".gitignore doesn't ignore reference-library/"

    # Should have data/ directory rules
    assert "data/images/" in content, ".gitignore doesn't ignore data/images/"
    assert "data/qdrant/" in content, ".gitignore doesn't ignore data/qdrant/"


def test_pyproject_has_all_dependencies(repo_root):
    """Test that pyproject.toml has merged all dependencies."""
    pyproject = repo_root / "pyproject.toml"
    assert pyproject.exists(), "pyproject.toml missing"

    content = pyproject.read_text()

    # GUI dependencies (from neuroLi)
    assert "customtkinter" in content, "customtkinter dependency missing"
    assert "chromadb" in content, "chromadb dependency missing"
    assert "sentence-transformers" in content, "sentence-transformers missing"

    # API dependencies (from neurosynth)
    assert "fastapi" in content, "fastapi dependency missing"
    assert "redis" in content, "redis dependency missing"

    # Visual processing dependencies
    assert "colpali-engine" in content, "colpali-engine dependency missing"
    assert "qdrant-client" in content, "qdrant-client dependency missing"

    # Entry points
    assert "neuro-ref" in content, "neuro-ref entry point missing"
    assert "neuro-bridge" in content, "neuro-bridge entry point missing"


def test_config_paths_use_monorepo_structure():
    """Test that config files use correct monorepo paths."""
    from reference_library.config import DATA_DIR, DATABASE_PATH, PROJECT_ROOT

    # PROJECT_ROOT should be repo root (3 levels up from config.py)
    # config.py is at src/reference_library/config.py
    assert PROJECT_ROOT.name == "neurosynth", f"PROJECT_ROOT incorrect: {PROJECT_ROOT}"

    # DATA_DIR should be at repo_root/data
    assert DATA_DIR == PROJECT_ROOT / "data", f"DATA_DIR incorrect: {DATA_DIR}"

    # DATABASE_PATH should be at data/library.db
    assert (
        DATABASE_PATH == DATA_DIR / "library.db"
    ), f"DATABASE_PATH incorrect: {DATABASE_PATH}"


def test_bridge_imports_work():
    """Test that bridge scripts can import both neurosynth and reference_library."""
    # This validates that the import path fixes worked
    from pathlib import Path

    from bridges.library_to_deepdx import LibraryToDeepDxBridge

    # Check that bridge can access both sides
    # (import will fail if paths are wrong)
    bridge = LibraryToDeepDxBridge(
        source_db=Path("data/library.db"),
        target_db=Path("data/neurosynth.db"),
        skip_qdrant=True,  # Skip Qdrant in tests
    )

    assert bridge is not None
    assert bridge.source_db_path == Path("data/library.db")


@pytest.mark.skipif(
    not Path("data/neurosynth.db").exists(),
    reason="Requires migrated neurosynth.db",
)
def test_deep_dx_tests_still_pass(repo_root):
    """Test that original Deep-DX tests still pass after migration."""
    result = subprocess.run(
        [
            "./venv/bin/pytest",
            "tests/test_deep_dx/",
            "-v",
            "--no-cov",  # Skip coverage for this integration test
        ],
        capture_output=True,
        text=True,
        cwd=repo_root,
    )

    # Check if tests passed (look for "40 passed" in output)
    assert (
        "40 passed" in result.stdout
    ), f"Expected 40 Deep-DX tests to pass, but got:\n{result.stdout}\n{result.stderr}"
