import hashlib
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List

import fitz  # PyMuPDF

# Add src to path
sys.path.append(str(Path(__file__).parent.parent.parent.parent))

from ai.client import AIClient
from deep_dx.config import get_deepdx_settings
from index.database import Database
from models import Chunk, ChunkType, DocumentType, SourceMetadata, Specialty


class DeepDxIngestor:
    def __init__(self):
        self.settings = get_deepdx_settings()
        self.db = Database(db_path=Path("neurosynth.db"))
        self.ai_client = AIClient()
        self.chunk_size = 1000  # chars ~ 200-300 tokens
        self.overlap = 200

    def process_directory(self, source_dir: Path):
        print(f"📂 Scanning {source_dir}...")
        pdf_files = list(source_dir.glob("*.pdf"))
        print(f"Found {len(pdf_files)} PDFs.")

        for i, pdf_file in enumerate(pdf_files):
            print(f"[{i+1}/{len(pdf_files)}] Processing {pdf_file.name}...")
            try:
                self.ingest_pdf(pdf_file)
            except Exception as e:
                print(f"❌ Error processing {pdf_file.name}: {e}")

    def ingest_pdf(self, pdf_path: Path):
        # 1. Check if source exists
        source_id = hashlib.md5(pdf_path.name.encode()).hexdigest()
        if self.db.source_exists(source_id):
            print(f"  - Source {source_id} already exists. Skipping.")
            return

        # 2. Extract Text
        doc = fitz.open(pdf_path)
        full_text = ""
        total_pages = len(doc)

        # Simple Page Map: (start_char, end_char, page_num)
        page_map = []
        current_iter = 0

        for i, page in enumerate(doc):
            text = page.get_text()
            if not text:
                continue

            # Simple cleanup
            text = text.replace("\xa0", " ").strip()
            if not text:
                continue

            start = current_iter
            full_text += text + "\n\n"
            end = current_iter + len(text) + 2
            page_map.append((start, end, i + 1))
            current_iter = end

        # 3. Create Source Entry
        specialty = Specialty.GENERAL
        # Simple heuristic for specialty (could be improved)
        fname = pdf_path.name.lower()
        if "spine" in fname:
            specialty = Specialty.SPINE
        elif "tumor" in fname or "glioma" in fname:
            specialty = Specialty.TUMOR
        elif "anatomy" in fname:
            specialty = Specialty.ANATOMY

        source = SourceMetadata(
            id=source_id,
            title=pdf_path.stem.replace("_", " "),
            doc_type=DocumentType.PAPER if "paper" in fname else DocumentType.CHAPTER,
            file_path=pdf_path,
            authors="Unknown",  # Would need metadata extraction
            year=datetime.now().year,
            specialty=specialty,
            total_pages=total_pages,
            processed_at=datetime.now(),
        )
        self.db.insert_source(source)

        # 4. Chunking
        chunks = []
        texts_to_embed = []

        start = 0
        text_len = len(full_text)

        chunk_idx = 0
        while start < text_len:
            end = min(start + self.chunk_size, text_len)
            chunk_text = full_text[start:end]

            # Find page number (midpoint)
            midpoint = start + (len(chunk_text) // 2)
            page_num = 1
            for p_start, p_end, p_n in page_map:
                if p_start <= midpoint < p_end:
                    page_num = p_n
                    break

            if len(chunk_text.strip()) > 50:
                chunk_id = f"{source_id}_chunk_{chunk_idx}"
                chunk = Chunk(
                    id=chunk_id,
                    source_id=source.id,
                    source_title=source.title,
                    section_title="",  # Would need structure analysis
                    content=chunk_text,
                    chunk_type=ChunkType.NARRATIVE,
                    page_start=page_num,
                    page_end=page_num,
                    embedding=None,  # To be filled
                )
                chunks.append(chunk)
                texts_to_embed.append(chunk_text)
                chunk_idx += 1

            start += self.chunk_size - self.overlap

        print(f"  - Generated {len(chunks)} chunks. Embedding...")

        if not chunks:
            print("  ⚠️ No chunks generated.")
            return

        # 5. Embed (Batch)
        try:
            embeddings = self.ai_client.get_embeddings(
                texts_to_embed
            )  # Handles batching internally

            for c, emb in zip(chunks, embeddings):
                c.embedding = emb

            # 6. Insert Chunks
            self.db.insert_chunks(chunks)
            print(f"  ✅ Inserted {len(chunks)} chunks.")

        except Exception as e:
            print(f"  ❌ Embedding failed: {e}")
            # If embedding fails, maybe we still save chunks without vectors?
            # No, SynthesisEngine needs vectors.


def main():
    ingestor = DeepDxIngestor()
    sources_dir = Path("data/sources")
    if not sources_dir.exists():
        print(f"❌ Source directory {sources_dir} does not exist.")
        return
    ingestor.process_directory(sources_dir)


if __name__ == "__main__":
    main()
