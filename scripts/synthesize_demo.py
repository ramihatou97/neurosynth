import asyncio
import sys
from pathlib import Path

# Ensure src in path
root_dir = Path(__file__).parent.parent
sys.path.append(str(root_dir))

from src.ai import AIClient
from src.index import Database, SearchEngine
from src.neurosynth.models.document import ContentChunk, DocumentFormat, Source
from src.neurosynth.models.knowledge import KnowledgeCluster
from src.neurosynth.synthesis.outline import OutlineEntry
from src.neurosynth.synthesis.section import SectionSynthesizer, SynthesisConfig


async def main():
    print("🚀 Starting Synthesis Demo: Septic Shock (Marino Only)")

    # 1. Initialize
    db = Database()
    engine = SearchEngine(db)

    # 2. Find Marino Source
    sources = db.get_all_sources()
    marino = next((s for s in sources if "Marino" in s.title), None)

    if not marino:
        print("❌ Marino's ICU Book not found in library.")
        return

    print(f"✅ Found Source: {marino.title} ({marino.id})")

    # 3. Setup Synthesis
    topic = "Septic Shock"
    section_title = "Definition and Pathophysiology"

    print(f"🔎 Searching for '{topic} {section_title}' in source...")

    # Filter search to this source
    results = engine.search(
        f"{topic} {section_title}", top_k=15, filters={"source_ids": {marino.id}}
    )

    if not results.chunks:
        print("❌ No relevant chunks found.")
        return

    print(f"✅ Found {len(results.chunks)} chunks.")

    # 4. Prepare for Synthesizer
    chunks = []
    for res in results.chunks:
        # Create full objects locally
        dummy_source = Source(
            path=Path(res.chunk.source_title),
            format=DocumentFormat.PDF,
            title=res.chunk.source_title,
            id=res.chunk.source_id,
        )
        chunk = ContentChunk(
            id=str(res.chunk.id),
            content=res.chunk.content,
            source=dummy_source,
            page_number=res.chunk.page_start,
        )
        chunks.append(chunk)

    outline_entry = OutlineEntry(title=section_title)
    outline_entry.assigned_clusters = [
        KnowledgeCluster(topic=section_title, chunks=chunks)
    ]

    # 5. Synthesize
    print("✍️  Synthesizing section...")
    config = SynthesisConfig(academic_style=True)
    synthesizer = SectionSynthesizer(config)

    chapter = await synthesizer.synthesize_chapter(
        topic=topic, outline=[outline_entry], max_concurrent=1
    )

    section = chapter.sections[0]
    print("\n" + "=" * 50)
    print(f"📄 GENERATED CONTENT: {section.title}")
    print("=" * 50)
    print(section.content[:1000] + "...")  # Preview
    print("\n✅ Demo Complete.")


if __name__ == "__main__":
    asyncio.run(main())
