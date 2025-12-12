import os
import sys
from pathlib import Path

# Emulate app.py sys.path modification
current_dir = os.getcwd()
sys.path.append(current_dir)
print(f"Added {current_dir} to sys.path")

try:
    print("Testing config import...")
    from src import config

    print("SUCCESS: config imported")

    print("Testing models import...")
    from src import models

    print("SUCCESS: models imported")

    print("Testing library import...")
    from src.ui import library

    print("SUCCESS: library imported")

    print("Testing synthesis engine import...")
    from src.synthesize import engine

    print("SUCCESS: synthesis engine imported")

except ImportError as e:
    print(f"FAIL: ImportError: {e}")
except Exception as e:
    print(f"FAIL: Exception: {e}")
