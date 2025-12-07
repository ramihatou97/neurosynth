
import sys
from pathlib import Path

# Ensure src is in path
src_path = Path.cwd() / "src"
sys.path.append(str(src_path))

from deep_dx.retrieval.indexer import DeepDxIndexer

def main():
    print("🚀 Starting Deep-Dx Phase 1 Indexing (Dense Retrieval)...")
    
    # Define paths
    root_dir = Path.cwd()
    source_dir = root_dir / "data" / "sources"
    
    # Validate source dir
    if not source_dir.exists():
        print(f"❌ Source directory not found: {source_dir}")
        sys.exit(1)
        
    # Initialize and run
    try:
        indexer = DeepDxIndexer()
        indexer.build_index(source_dir=source_dir)
        print("\n✨ Indexing Pipeline Complete!")
    except Exception as e:
        print(f"\n❌ FATAL ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
