import logging
import sys
from pathlib import Path

# Add src to path
sys.path.append(str(Path(__file__).parent / "src"))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("SingleBookTest")


def run_single_book(pdf_path: str):
    print(f"\n📚 Running Smart Extraction on: {Path(pdf_path).name}\n")

    try:
        from ingest.smart_extractor import SmartImageExtractor
        from neurosynth.ai.ingestor import BiomedIngestor

        # 1. Setup
        assets_dir = Path("assets/extracted_images")
        assets_dir.mkdir(parents=True, exist_ok=True)

        extractor = SmartImageExtractor(str(assets_dir))
        ingestor = BiomedIngestor()

        # 2. Extract
        print("   -> 🧠 Analyzing PDF layout and context (First 20 pages)...")
        figures = extractor.process_pdf(pdf_path, pages=list(range(20)))

        if not figures:
            print("   -> ⚠️ No figures found!")
            return

        print(f"   -> ✅ Found {len(figures)} relevant figures.")

        # 3. Ingest
        print("   -> 👁️  Generating AI Embeddings and Indexing...")
        ingestor.ingest_figures(figures)

        print("\n✅ Processing Complete! Figures are now index in Qdrant.")

    except ImportError:
        print("❌ Imports failed. Are dependencies installed?")
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    target_pdf = "/Users/ramihatoum/Desktop/NeuroLi/reference library/01_COMPLETE_TEXTBOOKS/Spine-Surgery-Tricks-of-the-Trade-Vaccaro.pdf"
    run_single_book(target_pdf)
