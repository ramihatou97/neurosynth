import sys
from pathlib import Path

# Ensure src in path
root_dir = Path(__file__).parent.parent
sys.path.append(str(root_dir))

from src.index.database import Database


def main():
    print("🚀 Inspecting Images for 'Marino's ICU Book'...")

    db = Database()
    sources = db.get_all_sources()
    marino = next((s for s in sources if "Marino" in s.title), None)

    if not marino:
        print("❌ Marino's ICU Book not found in library.")
        return

    print(f"✅ Found Source: {marino.title} ({marino.id})")

    images = db.get_images_by_source(marino.id)
    print(f"📸 Total Images Extracted: {len(images)}")

    embedded_count = sum(1 for img in images if img.embedding is not None)
    print(f"🧠 Images with Embeddings: {embedded_count}")

    print("\n--- Sample Images ---")
    for i, img in enumerate(images[:5]):
        status = "✅ Embedded" if img.embedding else "❌ No Embedding"
        print(
            f"#{i+1}: {img.image_type.value} | Pg {img.page} | {status} | {img.caption[:50]}..."
        )


if __name__ == "__main__":
    main()
