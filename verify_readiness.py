
import sys
import importlib
from pathlib import Path

def check_import(name):
    try:
        importlib.import_module(name)
        print(f"✅ Import successful: {name}")
        return True
    except ImportError as e:
        print(f"❌ Import failed: {name} ({e})")
        return False

def main():
    print("🔍 Verifying Deep-Dx Phase 1 Readiness...")
    
    # 1. Check Python version
    print(f"ℹ️  Python: {sys.version.split()[0]}")
    
    # 2. Check dependencies
    deps = ['anthropic', 'pymupdf', 'numpy']
    # Note: colbert/ragatouille might not be installed yet for Phase 1, 
    # but we should check if we can import the local package
    
    all_ok = True
    for dep in deps:
        if not check_import(dep):
            all_ok = False
            
    # 3. Check deep_dx package
    # Ensure src is in path
    sys.path.append(str(Path.cwd() / "src"))
    
    if check_import("deep_dx"):
        try:
            from deep_dx import config
            print(f"✅ Loaded deep_dx.config")
        except Exception as e:
            print(f"❌ Failed to load config: {e}")
            all_ok = False
    else:
        all_ok = False

    if all_ok:
        print("\n✅ SYSTEM READY FOR PHASE 1")
        sys.exit(0)
    else:
        print("\n❌ VERIFICATION FAILED")
        sys.exit(1)

if __name__ == "__main__":
    main()
