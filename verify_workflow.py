import asyncio
import json
import os
import shutil
import sys
from pathlib import Path

# Add src directories to path
project_root = Path(__file__).parent
sys.path.append(str(project_root / "src"))
sys.path.append(str(project_root / "reference-library"))

from src.export.page_extractor import ExtractedSource
from src.integration.neurosynth_bridge import NeuroSynthBridge

from neurosynth.config import get_settings
from neurosynth.parsers.image_extractor import ImageExtractor

# Setup paths
TEST_PDF = (
    project_root / "test_pipeline/sources/42 Minimally Invasive Lumbar Diskectomy.pdf"
)
OUTPUT_DIR = project_root / "verification_output"
IMAGES_DIR = OUTPUT_DIR / "images"
MANIFEST_PATH = OUTPUT_DIR / "manifest.json"


def setup():
    if OUTPUT_DIR.exists():
        shutil.rmtree(OUTPUT_DIR)
    OUTPUT_DIR.mkdir(parents=True)
    IMAGES_DIR.mkdir(parents=True)
    print(f"📂 Setup complete. Output dir: {OUTPUT_DIR}")


async def test_extraction():
    print("\n" + "=" * 50)
    print("TEST 1: Phase 4 Image Extraction")
    print("=" * 50)

    settings = get_settings()
    print(f"Config: Unified Pipeline Enabled: {settings.enable_unified_pipeline}")
    print(f"Config: Vector Extraction Enabled: {settings.enable_vector_extraction}")

    extractor = ImageExtractor()
    print(f"Extractor Mode: {extractor.extraction_mode}")
    print(f"Extracting from: {TEST_PDF.name}")

    visuals = await extractor.extract_images(TEST_PDF, IMAGES_DIR)

    print(f"\n✅ Extracted {len(visuals)} visual elements")

    procedural_count = sum(1 for v in visuals if v.is_procedural)
    vector_count = sum(1 for v in visuals if v.image_type.value == "flowchart")
    caption_count = sum(1 for v in visuals if v.caption)

    print(f"  - Procedural Images: {procedural_count}")
    print(f"  - Vector/Flowcharts: {vector_count}")
    print(f"  - Captioned Images: {caption_count}")

    if len(visuals) > 0:
        v = visuals[0]
        print(f"\nSample Image Metadata (ID: {v.id}):")
        print(f"  - Type: {v.image_type}")
        print(f"  - Caption: {v.caption[:50]}...")
        print(f"  - Keywords: {v.keywords_matched}")
        print(f"  - Sequence ID: {v.sequence_id}")

    return visuals


def test_bridge_integration(visuals):
    print("\n" + "=" * 50)
    print("TEST 2: Bridge Integration & Manifest Generation")
    print("=" * 50)

    bridge = NeuroSynthBridge()

    # Mock an ExtractedSource (as if it came from the GUI)
    # In a real run, extracted_path would be a mini-PDF, but we'll use the full one for this test
    source = ExtractedSource(
        extracted_path=TEST_PDF,
        original_path=TEST_PDF,
        original_source="Test Source",
        pages=[1, 2, 3, 4, 5],  # Mock pages
        full_text="""
        Minimally Invasive Lumbar Microdiskectomy: Surgical Technique

        Clinical Context:
        Lumbar microdiskectomy is indicated for patients with symptomatic lumbar disk herniation who have failed conservative management. The primary goal is nerve root decompression.

        Strategic Planning:
        Pre-operative MRI imaging is reviewed to plan the trajectory. Risk stratification is performed. Standard equipment includes a microscope and tubular retractors.

        Positioning and Exposure:
        The patient is positioned prone on a Wilson frame or Jackson table to reduce lumbar lordosis and open the interlaminar space. Fixation is checked. All pressure points are padded. Fluoroscopy is used to confirm the level.

        Surface Anatomy and Incision:
        The midline and iliac crest are identified as surface landmarks. A 2cm incision is made 1-2cm lateral to the midline. Danger zones are avoided.

        Dissection and Approach:
        Under microscopic visualization, the remaining muscle is cleared from the lamina. Layered dissection is performed to identify the plane. A high-speed drill or Kerrison rongeur is used to perform a laminotomy. The ligamentum flavum is identified and detached or resected to expose the epidural space.

        The Definitive Action:
        The nerve root is gently retracted medially. The disk herniation is identified ventral to the nerve root. An annulotomy is performed if not already present, and the herniated disk fragments are removed using pituitary rongeurs. The target is decompressed.

        Closure and Post-op:
        Hemostasis is achieved. The tubular retractor is removed slowly while checking for bleeding. The fascia and skin are closed in layers with sutures. A dressing is applied. No drain is typically needed.
        """,
        context_excerpts=[
            """
        Minimally Invasive Lumbar Microdiskectomy: Surgical Technique

        Clinical Context:
        Lumbar microdiskectomy is indicated for patients with symptomatic lumbar disk herniation who have failed conservative management. The primary goal is nerve root decompression.

        Strategic Planning:
        Pre-operative MRI imaging is reviewed to plan the trajectory. Risk stratification is performed. Standard equipment includes a microscope and tubular retractors.

        Positioning and Exposure:
        The patient is positioned prone on a Wilson frame or Jackson table to reduce lumbar lordosis and open the interlaminar space. Fixation is checked. All pressure points are padded. Fluoroscopy is used to confirm the level.

        Surface Anatomy and Incision:
        The midline and iliac crest are identified as surface landmarks. A 2cm incision is made 1-2cm lateral to the midline. Danger zones are avoided.

        Dissection and Approach:
        Under microscopic visualization, the remaining muscle is cleared from the lamina. Layered dissection is performed to identify the plane. A high-speed drill or Kerrison rongeur is used to perform a laminotomy. The ligamentum flavum is identified and detached or resected to expose the epidural space.

        The Definitive Action:
        The nerve root is gently retracted medially. The disk herniation is identified ventral to the nerve root. An annulotomy is performed if not already present, and the herniated disk fragments are removed using pituitary rongeurs. The target is decompressed.

        Closure and Post-op:
        Hemostasis is achieved. The tubular retractor is removed slowly while checking for bleeding. The fascia and skin are closed in layers with sutures. A dressing is applied. No drain is typically needed.
        """
        ],
        category="Surgical",
        category_group="Surgical/Anatomical",
        confidence=0.9,
    )

    # We manually populate figures here to simulate what the bridge's _extract_images_from_sources does
    # But wait, we want to TEST the bridge's method.
    # The bridge method runs extraction internally.

    print("Running Bridge._extract_images_from_sources...")
    # We need to mock the extracted_path to exist (it does)

    count = bridge._extract_images_from_sources([source], IMAGES_DIR)
    print(f"✅ Bridge extracted {count} images")

    # Verify source.figures was populated
    print(f"Source figures count: {len(source.figures)}")
    if len(source.figures) > 0:
        fig = source.figures[0]
        print("Sample Manifest Entry:")
        print(f"  - Keywords: {fig.get('keywords')}")
        print(f"  - Is Procedural: {fig.get('is_procedural')}")

    # Generate Manifest
    from src.export.page_extractor import generate_manifest

    print("Generating manifest.json...")
    generate_manifest(
        topic="Lumbar Microdiskectomy", sources=[source], output_path=MANIFEST_PATH
    )

    if MANIFEST_PATH.exists():
        print(f"✅ Manifest created at {MANIFEST_PATH}")
        with open(MANIFEST_PATH) as f:
            data = json.load(f)
            # Check for Phase 4 fields in JSON
            first_fig = data["sources"][0]["figures"][0]
            if "keywords" in first_fig:
                print("✅ Verified 'keywords' field present in manifest")
            else:
                print("❌ 'keywords' field MISSING in manifest")
    else:
        print("❌ Manifest creation failed")


async def test_synthesis():
    print("\n" + "=" * 50)
    print("TEST 3: Full Synthesis (CLI)")
    print("=" * 50)

    # We will simulate the CLI run command
    # neurosynth run --manifest ...

    sources_dir = TEST_PDF.parent
    cmd = f"neurosynth run 'Verification Test' --sources '{sources_dir}' --manifest '{MANIFEST_PATH}' --output '{OUTPUT_DIR}/synthesis'"
    print(f"Running command: {cmd}")

    # We'll use os.system for simplicity in this verification script,
    # ensuring we use the current venv python
    python_exe = sys.executable
    cli_script = project_root / "src/neurosynth/cli.py"

    # Construct command to run via python -m to ensure path correctness
    full_cmd = f"export PYTHONPATH=$PYTHONPATH:{project_root}/src:{project_root}/reference-library/src && {python_exe} -m neurosynth.cli run 'Verification Test' --sources '{sources_dir}' --manifest '{MANIFEST_PATH}' --output '{OUTPUT_DIR}/synthesis'"

    import subprocess

    process = await asyncio.create_subprocess_shell(
        full_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE
    )

    stdout, stderr = await process.communicate()

    if process.returncode == 0:
        print("✅ Synthesis completed successfully")
        print(stdout.decode()[:500] + "...")
    else:
        print("❌ Synthesis failed")
        print(stderr.decode())


if __name__ == "__main__":
    setup()

    # Run async extraction test
    visuals = asyncio.run(test_extraction())

    # Run sync bridge test (which creates its own event loop internally)
    test_bridge_integration(visuals)

    # Run async synthesis test
    asyncio.run(test_synthesis())

    print("\nVerification Complete.")
