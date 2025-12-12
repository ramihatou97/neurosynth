import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path.cwd()))

try:
    from src.reference_library.config import LIBRARY_PATH, _get_library_path

    print(f"Resolved Library Path: {_get_library_path()}")
    print(f"Global LIBRARY_PATH: {LIBRARY_PATH}")

    if _get_library_path().exists():
        print("✅ Library path exists on disk.")
    else:
        print("❌ Library path does NOT exist.")

except ImportError as e:
    print(f"Import Error: {e}")
except Exception as e:
    import traceback

    traceback.print_exc()
