import importlib
import sys

packages = [
    "networkx",
    "transformers",
    "torch",
    "torchvision",
    "ultralytics",
    "cv2",  # opencv-python-headless
    "qdrant_client",
    "rich",
    "pydantic_settings",
    "sklearn",
    "voyageai",
    "anthropic",
    "numpy",
    "PIL",
]

print("🔍 Verifying ML Dependencies...")
failed = []
for pkg in packages:
    try:
        importlib.import_module(pkg)
        print(f"✅ {pkg} installed")
    except ImportError as e:
        print(f"❌ {pkg} MISSING: {e}")
        failed.append(pkg)

if failed:
    print(f"\n⚠️  {len(failed)} packages failed to load.")
    sys.exit(1)
else:
    print("\n🚀 All ML dependencies are ready!")
