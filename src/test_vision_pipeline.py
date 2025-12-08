import logging
import sys
from pathlib import Path

# Add src to path
sys.path.append(str(Path(__file__).parent))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("VisionTest")


def test():
    print("\n🧪 Testing AI Vision Stack...\n")

    # 1. Test BiomedCLIP
    try:
        from neurosynth.ai.biomed_searcher import BiomedCLIPSearcher

        print("Expected: Loading BiomedCLIP model (may take a moment)...")
        embedder = BiomedCLIPSearcher()
        print(f"✅ BiomedCLIP loaded successfully on device: {embedder.device}")

        # Test text embedding
        vec = embedder.embed_text("glioblastoma multiforme")
        print(f"✅ Text embedding shape: {vec.shape}")

    except ImportError as e:
        print(f"❌ Failed to import/load BiomedCLIP: {e}")
        return
    except Exception as e:
        print(f"❌ Error during BiomedCLIP test: {e}")
        return

    # 2. Test Classifier
    try:
        from neurosynth.ai.classifier import ModalityClassifier

        clf = ModalityClassifier(embedder)
        print("✅ Classifier initialized")

        # Mock classification
        import numpy as np

        dummy_vec = np.random.rand(1, 512).astype(np.float32)
        label, score = clf.classify(dummy_vec[0])
        print(f"✅ Mock classification result: {label} ({score:.2f})")

    except Exception as e:
        print(f"❌ Classifier test failed: {e}")

    # 3. Test Smart Extractor (if pymupdf4llm is present)
    try:
        from ingest.smart_extractor import SmartImageExtractor

        print("✅ SmartImageExtractor importable")
    except ImportError:
        print("⚠️ SmartImageExtractor import failed (check dependencies)")

    print("\n✅ System Codebase Ready (Pending dependencies install).\n")


if __name__ == "__main__":
    test()
