import os
import shutil
from pathlib import Path

# Config
SOURCE_LIST = Path("/Users/ramihatoum/neurosynth/my_sources.txt")
DEST_DIR = Path("/Users/ramihatoum/neurosynth/data/sources")


def main():
    if not SOURCE_LIST.exists():
        print(f"❌ Source list not found: {SOURCE_LIST}")
        return

    # Create dest dir
    DEST_DIR.mkdir(parents=True, exist_ok=True)
    print(f"📂 Destination: {DEST_DIR}")

    # Read sources
    with open(SOURCE_LIST) as f:
        lines = [
            l.strip() for l in f.readlines() if l.strip() and not l.startswith("#")
        ]

    print(f"🔍 Found {len(lines)} files to copy")

    success_count = 0
    for file_path in lines:
        src = Path(file_path)
        if not src.exists():
            print(f"  ⚠️  Missing: {src.name}")
            continue

        try:
            shutil.copy2(src, DEST_DIR / src.name)
            # print(f"  ✓ Copied: {src.name}")
            success_count += 1
        except Exception as e:
            print(f"  ❌ Failed {src.name}: {e}")

    print(f"\n✅ Successfully copied {success_count}/{len(lines)} files")


if __name__ == "__main__":
    main()
