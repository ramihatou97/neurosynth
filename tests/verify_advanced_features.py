import asyncio
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

# Add src to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Fix for nested neurosynth imports if they assume they are in a package
sys.path.insert(0, str(project_root / "src"))

from src.models import SynthesizedChapter, SynthesizedSection
from src.neurosynth.synthesis.checkpoint import SynthesisCheckpoint
from src.neurosynth.synthesis.outline import OutlineEntry

# Mock external dependencies that might be missing in this env
# with patch.dict('sys.modules', {'rich': MagicMock(), 'rich.console': MagicMock(), 'weasyprint': MagicMock()}):
from src.neurosynth.synthesis.section import SectionSynthesizer, SynthesisConfig


async def test_batch_synthesis_flow():
    print("🧪 Testing Batch Synthesis Flow...")

    # 1. Setup Mock Synthesizer
    synthesizer = SectionSynthesizer(SynthesisConfig())
    # Mock the internal generate method to avoid API calls
    synthesizer._generate_section_content = AsyncMock(
        return_value="Mocked content for section"
    )

    # 2. Create Outline
    outline = [
        OutlineEntry(title="Intro", level=1),
        OutlineEntry(title="Methods", level=1),
    ]

    # 3. Test Checkpoint Creation (Simulate Failure)
    print("   ...Simulating synthesis failure/checkpointing")
    # We can't easily force a crash inside the gather without modifying code,
    # but we can verify checkpoint saving/loading logic directly.

    checkpoint_path = Path("test_checkpoint.json")
    checkpoint = SynthesisCheckpoint(
        topic="Test Chapter",
    )
    # Simulate saving a section
    checkpoint.save_section(0, "Mock Content", title="Intro")

    # Verify file creation
    recovery_dir = checkpoint.recovery_dir
    print(f"   ...Recovery Dir: {recovery_dir}")

    if (recovery_dir / "sections" / "section_00.md").exists():
        print("✅ Checkpoint saved successfully (Section file exists)")
    else:
        print("❌ Checkpoint failed to save section")

    # 4. Test Resume Logic
    print("   ...Testing Resume Logic (Skipping)")

    # Create new synthesizer and use the checkpoint
    resume_checkpoint = SynthesisCheckpoint(
        topic="Test Chapter", existing_dir=recovery_dir
    )

    # We will reset the synthesizer mock to see if it gets called for section 0
    synthesizer._generate_section_content = AsyncMock(return_value="New Content")

    # Helper to spy on synthesize_section
    original_synthesize = synthesizer.synthesize_section
    synthesizer.synthesize_section = AsyncMock(side_effect=original_synthesize)

    # Run synthesis again with the checkpoint
    # Outline has 2 entries. Section 0 is in checkpoint. Section 1 is not.
    # We expect synthesize_section to be called ONLY for section 1.

    chapter = await synthesizer.synthesize_chapter(
        topic="Test Chapter", outline=outline, checkpoint=resume_checkpoint
    )

    # Assertions
    # Section 0 content should be "Mock Content" (from checkpoint)
    # Note: save_section adds a header, so we check for containment
    if "Mock Content" in chapter.sections[0].content:
        print("✅ Section 0 correctly loaded from checkpoint")
    else:
        print(
            f"❌ Section 0 content mismatch. Got: {chapter.sections[0].content[:20]}..."
        )

    # Verify synthesize_section was called once (for section 1), not twice.
    # Actually synthesize_section is called by synthesize_with_limit.
    # My patch in section.py returns EARLY if checkpoint has section.
    # So synthesizer.synthesize_section should NOT be called for index 0.

    # Check call args of the mock
    # It takes (entry). entry.title for 0 is "Intro", for 1 is "Methods".

    # Let's count calls.
    # Since it's parallel, order might vary, but count should be 1.
    call_count = synthesizer.synthesize_section.call_count
    if call_count == 1:
        print("✅ Resume logic skipped section 0 (1 call total)")
    else:
        print(f"❌ Resume logic failed. Expected 1 call, got {call_count}")

    # Clean up (optional, or rely on temp dir)
    import shutil

    if recovery_dir.exists():
        shutil.rmtree(recovery_dir)


async def test_ingestion_components():
    print("\n🧪 Testing Ingestion Components...")

    try:
        from src.ingest.processor import DocumentProcessor

        print("✅ DocumentProcessor imported successfully")

        # Verify Library Path
        lib_path = Path("data/library")
        if not lib_path.exists():
            lib_path.mkdir(parents=True, exist_ok=True)
            print("✅ Created data/library directory")
        else:
            print("✅ data/library directory exists")

    except ImportError as e:
        print(f"❌ Failed to import Ingestion components: {e}")


async def test_export_components():
    print("\n🧪 Testing Export Components...")
    try:
        # Mock WeasyPrint since it requires system dependencies (pango/cairo) that might not be on the environment
        # with patch.dict('sys.modules', {'weasyprint': MagicMock()}):
        from src.ui.advanced_features import render_latex_export_panel

        # Just check it exists
        if callable(render_latex_export_panel):
            print("✅ render_latex_export_panel is callable")

    except ImportError as e:
        print(f"❌ Failed to import Advanced Features: {e}")


if __name__ == "__main__":
    print("🚀 Starting Advanced Feature Verification\n")
    # Wrap main execution in the patch context too, just in case late imports happen
    # with patch.dict('sys.modules', {'rich': MagicMock(), 'rich.console': MagicMock(), 'weasyprint': MagicMock()}):
    asyncio.run(test_batch_synthesis_flow())
    asyncio.run(test_ingestion_components())
    asyncio.run(test_export_components())
    print("\n✅ Verification Complete")
