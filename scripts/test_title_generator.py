import asyncio
import logging
import sys
from pathlib import Path

# Setup path
root_dir = Path(__file__).parent.parent
sys.path.append(str(root_dir))

from src.neurosynth.enhancements.title_generator import TitleGenerator

# Setup logging
logging.basicConfig(level=logging.INFO)


async def test_generator():
    print("🧠 Testing Title Generator prompt effectiveness...")

    # Mock first page content of a neurosurgical paper
    # Simulating a file named "Slide 1.pdf" that is actually about Pterional Craniotomy
    mock_text = """
    Slide 1

    NEUROSURGICAL OPERATIVE ATLAS

    Pterional Craniotomy for Posterior Communicating Artery Aneurysm Clipping

    Department of Neurosurgery
    St. Joseph's Hospital and Medical Center
    Phoenix, Arizona

    Robert F. Spetzler, MD
    Peter Nakaji, MD

    Presentation 1

    Introduction
    The pterional craniotomy is the workhorse of neurosurgery...
    """

    generator = TitleGenerator()
    print("\n--- Input Text (Simulated Bad Metadata) ---")
    print(mock_text.strip()[:200] + "...")

    print("\n--- Generating Title ---")
    title = await generator.generate_title(mock_text)

    print(f"\n✅ Result: '{title}'")

    expected_keywords = ["Pterional", "Craniotomy", "Aneurysm"]
    if all(k in title for k in expected_keywords):
        print("✅ PASS: Title contains specific keywords.")
    else:
        print("❌ FAIL: Title lacks specificity.")


if __name__ == "__main__":
    asyncio.run(test_generator())
