#!/usr/bin/env python3
"""
Neurosurgery Reference Library Research System

A desktop application for searching and indexing neurosurgical reference materials
with AI-powered content categorization.

Usage:
    python main.py

Requirements:
    - Python 3.10+
    - Dependencies in requirements.txt
    - Anthropic API key set as ANTHROPIC_API_KEY environment variable
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

# Initialize logging before other imports
from src.logger import get_logger, setup_logging

setup_logging()
logger = get_logger("main")


# Check for required dependencies
def check_dependencies():
    """Check if required packages are installed."""
    missing = []

    try:
        import customtkinter
    except ImportError:
        missing.append("customtkinter")

    try:
        import fitz
    except ImportError:
        missing.append("pymupdf")

    try:
        import anthropic
    except ImportError:
        missing.append("anthropic")

    try:
        from fpdf import FPDF
    except ImportError:
        missing.append("fpdf2")

    if missing:
        print("Missing required packages:")
        print(f"  pip install {' '.join(missing)}")
        print("\nOr install all requirements:")
        print("  pip install -r requirements.txt")
        sys.exit(1)


def check_api_key():
    """Check if Anthropic API key is set, with graceful degradation."""
    from src import config

    if not config.AI_ENABLED:
        logger.warning(
            "AI features disabled: ANTHROPIC_API_KEY not set or AI disabled via environment"
        )
        print("\n" + "=" * 50)
        print("⚠️  AI Features Disabled")
        print("=" * 50)
        print("ANTHROPIC_API_KEY environment variable not set.")
        print("The application will work without AI categorization.")
        print("\nTo enable AI features, set the API key:")
        print("  export ANTHROPIC_API_KEY='your-api-key-here'")
        print("=" * 50 + "\n")
    else:
        logger.info("AI features enabled")
        print("✓ AI categorization enabled")


def check_library_path():
    """Check if library path is configured and valid."""
    from src.config import LIBRARY_PATH, ensure_library_path

    print(f"Library path: {LIBRARY_PATH}")
    if not LIBRARY_PATH.exists():
        print("Library path not found. Opening folder picker...")
        ensure_library_path()
        from src.config import LIBRARY_PATH as updated_path

        print(f"Library path set to: {updated_path}")


def migrate_category_system():
    """Migrate to hierarchical category system (one-time)."""
    from src import config
    from src.cache.database import Database

    # Check if migration marker exists
    migration_marker = config.DATA_DIR / ".category_migration_v2"
    if migration_marker.exists():
        return  # Already migrated

    print("Migrating to hierarchical category system...")
    db = Database(config.DATABASE_PATH)
    db.clear_categorization_cache()
    print("Categorization cache cleared. Results will use new taxonomy.")

    # Create marker file
    migration_marker.touch()


def main():
    """Main entry point."""
    logger.info("Neurosurgery Reference Library Research System starting")
    print("Neurosurgery Reference Library Research System")
    print("=" * 50)

    # Check dependencies
    check_dependencies()

    # Check and configure library path (may show folder picker)
    check_library_path()

    # Run migration to new category system
    migrate_category_system()

    # Check API key
    check_api_key()

    # Import and run the app
    from src.ui.app import run_app

    logger.info("Application startup complete, launching UI")
    print("Starting application...")
    run_app()


if __name__ == "__main__":
    main()
