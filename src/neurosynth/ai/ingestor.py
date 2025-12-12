import logging
from pathlib import Path
from typing import List, Optional
from uuid import uuid4

from tqdm import tqdm

# Adjust import based on where QdrantClient comes from in this env
try:
    from qdrant_client import QdrantClient
    from qdrant_client.models import Distance, PointStruct, VectorParams

    QDRANT_AVAILABLE = True
except ImportError:
    QDRANT_AVAILABLE = False

from neurosynth.ai.biomed_searcher import BiomedCLIPSearcher
from neurosynth.ai.classifier import ModalityClassifier
from neurosynth.config import get_settings

# We need a forward reference to the new ExtractedFigure class
# But python 3.11 supports this cleanly, or we accept Duck typing for now
# from ingest.smart_extractor import ExtractedFigure

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("BiomedIngestor")


class BiomedIngestor:
    COLLECTION_NAME = "neurosurgical_figures_hybrid"

    def __init__(self):
        if not QDRANT_AVAILABLE:
            logger.error("qdrant-client not installed. Ingestion disabled.")
            return

        settings = get_settings()
        # Initialize Qdrant Client (local or remote based on settings)
        if settings.qdrant_path:
            self.client = QdrantClient(path=str(settings.qdrant_path))
        else:
            self.client = QdrantClient(host="localhost", port=6333)

        self._ensure_collection_exists()

        logger.info("Initializing AI Stack for Ingestion...")
        self.embedder = BiomedCLIPSearcher()
        self.classifier = ModalityClassifier(self.embedder)

    def _ensure_collection_exists(self):
        try:
            collections = self.client.get_collections().collections
            exists = any(c.name == self.COLLECTION_NAME for c in collections)

            if not exists:
                self.client.create_collection(
                    collection_name=self.COLLECTION_NAME,
                    vectors_config={
                        "biomed": VectorParams(size=512, distance=Distance.COSINE),
                    },
                )
                logger.info(f"Created Qdrant Collection: {self.COLLECTION_NAME}")
        except Exception as e:
            logger.error(f"CRITICAL: Could not check/create Qdrant collection: {e}")
            self.client = None
            raise RuntimeError(f"Qdrant initialization failed: {e}") from e

    def ingest_figures(self, figures: list[object], batch_size: int = 32):
        """
        Ingest a list of ExtractedFigure objects (from smart_extractor).
        """
        if not QDRANT_AVAILABLE or not figures:
            return

        logger.info(f"Ingesting {len(figures)} figures...")

        for i in tqdm(range(0, len(figures), batch_size)):
            batch = figures[i : i + batch_size]
            self._process_batch(batch)

    def _process_batch(self, figures: list[object]):
        try:
            image_paths = [str(f.local_path) for f in figures]

            # Generate Embeddings
            vectors = self.embedder.embed_image(image_paths)
            if len(vectors) == 0:
                logger.warning("No vectors generated for batch.")
                return

            # Classify
            classifications = self.classifier.classify_batch(vectors)

            points = []
            for i, (fig, vector) in enumerate(zip(figures, vectors)):
                # Safely get attributes, handling potential different object types
                filename = getattr(fig, "image_filename", "unknown")
                source_pdf = getattr(fig, "source_pdf", "unknown")
                caption = getattr(fig, "caption", "")
                context = getattr(fig, "context", "")
                path_str = str(getattr(fig, "local_path", ""))

                # Determine classification
                modality = "unknown"
                if i < len(classifications):
                    modality = classifications[i]["label"]

                # Get enhancement fields (from SmartImageExtractor)
                detected_regions = getattr(fig, "detected_regions", [])
                region_confidence = getattr(fig, "region_confidence", 0.0)
                ocr_caption = getattr(fig, "ocr_caption", "")
                caption_source = getattr(fig, "caption_source", "proximity")
                figure_number = getattr(fig, "figure_number", "")
                parsed_caption = getattr(fig, "parsed_caption", "")
                page_num = getattr(fig, "page_num", 0)

                payload = {
                    "filename": filename,
                    "source_pdf": source_pdf,
                    "caption": caption,
                    "context": context,
                    "modality": modality,
                    "path": path_str,
                    # Enhancement fields
                    "detected_regions": detected_regions,
                    "region_confidence": region_confidence,
                    "ocr_caption": ocr_caption,
                    "caption_source": caption_source,
                    "figure_number": figure_number,
                    "parsed_caption": parsed_caption,
                    "page_num": page_num,
                }

                points.append(
                    PointStruct(
                        id=str(uuid4()),
                        vector={"biomed": vector.tolist()},
                        payload=payload,
                    )
                )

            if points:
                self.client.upsert(self.COLLECTION_NAME, points=points)

        except Exception as e:
            logger.error(f"Batch ingestion failed: {e}")
