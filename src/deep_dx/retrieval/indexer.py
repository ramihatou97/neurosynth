"""
Deep-Dx Retrieval Module - Dense Indexer (SBERT + Faiss)
"""

import json
import pickle
from pathlib import Path
from typing import Dict, List, Tuple

import faiss
import numpy as np
import pymupdf
from sentence_transformers import SentenceTransformer

from deep_dx.config import get_deepdx_settings


class DeepDxIndexer:
    """Handles PDF ingestion and Dense Vector indexing."""

    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        self.settings = get_deepdx_settings()
        self.index_dir = self.settings.colbert_index_path

        print(f"🤖 Loading Embedding Model: {model_name}...")
        self.model = SentenceTransformer(model_name)
        self.dimension = self.model.get_sentence_embedding_dimension()

    def load_and_chunk_pdf(
        self, pdf_path: Path, chunk_size: int = 1000, overlap: int = 200
    ) -> list[dict]:
        """Extacts and chunks text from PDF."""
        doc = pymupdf.open(pdf_path)
        filename = pdf_path.name
        chunks = []
        full_text = ""
        page_map = []

        current_pos = 0
        for i, page in enumerate(doc):
            text = page.get_text()
            if not text.strip():
                continue
            full_text += text
            end_pos = current_pos + len(text)
            page_map.append((current_pos, end_pos, i + 1))
            current_pos = end_pos

        if not full_text:
            return []

        start = 0
        while start < len(full_text):
            end = start + chunk_size
            chunk_text = full_text[start:end]
            midpoint = start + (len(chunk_text) // 2)
            page_num = 0
            for p_start, p_end, p_num in page_map:
                if p_start <= midpoint < p_end:
                    page_num = p_num
                    break

            if len(chunk_text.strip()) > 50:
                chunks.append(
                    {
                        "text": chunk_text,
                        "metadata": {
                            "source": filename,
                            "page": page_num,
                            "char_start": start,
                            "char_end": len(chunk_text),
                        },
                    }
                )
            start += chunk_size - overlap
        return chunks

    def encode_chunks(self, chunks: list[dict]) -> np.ndarray:
        """Generates normalized embeddings for a list of chunks."""
        texts = [c["text"] for c in chunks]
        embeddings = self.model.encode(texts, show_progress_bar=True)
        faiss.normalize_L2(embeddings)
        return embeddings

    def save_index(self, embeddings: np.ndarray, chunks: list[dict], index_name: str):
        """Builds and saves FAISS index and metadata."""
        print(f"🏗️  Building Index '{index_name}'...")
        index = faiss.IndexFlatIP(self.dimension)
        index.add(embeddings)

        output_dir = self.index_dir / index_name
        output_dir.mkdir(parents=True, exist_ok=True)

        faiss.write_index(index, str(output_dir / "index.faiss"))
        with open(output_dir / "metadata.json", "w") as f:
            json.dump(chunks, f, indent=2)

        print(f"\n✅ Index saved to: {output_dir}")
        print(f"  - Vectors: {index.ntotal}")
        return str(output_dir)

    def build_index(self, source_dir: Path, index_name: str = "deep_dx_v1"):
        """Pipeline to load, encode, and save index."""
        print(f"📂 Loading PDFs from {source_dir}...")
        all_chunks = []
        pdf_files = list(source_dir.glob("*.pdf"))

        for pdf_file in pdf_files:
            try:
                file_chunks = self.load_and_chunk_pdf(pdf_file)
                all_chunks.extend(file_chunks)
                print(f"  ✓ Processed {pdf_file.name}: {len(file_chunks)} chunks")
            except Exception as e:
                print(f"  ❌ Failed to process {pdf_file.name}: {e}")

        if not all_chunks:
            return

        print(f"⚡ Generating Embeddings for {len(all_chunks)} chunks...")
        embeddings = self.encode_chunks(all_chunks)
        self.save_index(embeddings, all_chunks, index_name)
