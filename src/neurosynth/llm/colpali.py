"""ColPali vision-language model client for visual embeddings.

ColPali is a vision-language model that creates semantic embeddings
for document images, enabling similarity search across visual content
like surgical diagrams, anatomical illustrations, and imaging studies.
"""

import asyncio
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np
from PIL import Image
from rich.console import Console

from neurosynth.config import get_settings

if TYPE_CHECKING:
    from neurosynth.models.visual import VisualElement

console = Console()


class ColPaliClient:
    """Client for ColPali visual embeddings.

    Uses singleton pattern since the model is expensive to load.
    Supports CPU, CUDA, and MPS (Apple Silicon) devices.
    """

    _instance: "ColPaliClient | None" = None
    _model = None
    _processor = None
    _initialized: bool = False

    def __new__(cls) -> "ColPaliClient":
        """Singleton pattern - ColPali model is expensive to load."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        """Initialize the ColPali client (lazy loading)."""
        if ColPaliClient._initialized:
            return

        self.settings = get_settings()
        self.model_name = self.settings.colpali_model
        self.batch_size = self.settings.colpali_batch_size

        # Determine best available device
        self.device = self._get_device()
        ColPaliClient._initialized = True

    def _get_device(self) -> str:
        """Determine the best available compute device."""
        try:
            import torch

            if torch.cuda.is_available():
                return "cuda"
            elif torch.backends.mps.is_available():
                return "mps"
            else:
                return "cpu"
        except ImportError:
            return "cpu"

    def _ensure_model_loaded(self) -> None:
        """Load the model if not already loaded (lazy loading)."""
        if ColPaliClient._model is not None:
            return

        console.print(f"[blue]Loading ColPali model: {self.model_name}[/blue]")
        console.print(f"[dim]Device: {self.device}[/dim]")

        try:
            import torch
            from colpali_engine.models import ColPali, ColPaliProcessor

            # Determine dtype based on device
            dtype = torch.float32 if self.device == "cpu" else torch.float16

            # Load model
            ColPaliClient._model = (
                ColPali.from_pretrained(
                    self.model_name,
                    torch_dtype=dtype,
                )
                .to(self.device)
                .eval()
            )

            # Load processor
            ColPaliClient._processor = ColPaliProcessor.from_pretrained(self.model_name)

            console.print("[green]ColPali model loaded successfully[/green]")

        except ImportError as e:
            raise RuntimeError(
                f"ColPali dependencies not installed. "
                f"Install with: pip install colpali-engine torch transformers\n"
                f"Error: {e}"
            )
        except Exception as e:
            raise RuntimeError(f"Failed to load ColPali model: {e}")

    @property
    def model(self):
        """Get the loaded model, loading if necessary."""
        self._ensure_model_loaded()
        return ColPaliClient._model

    @property
    def processor(self):
        """Get the loaded processor, loading if necessary."""
        self._ensure_model_loaded()
        return ColPaliClient._processor

    @property
    def embedding_dim(self) -> int:
        """Return embedding dimension.

        ColPali uses multi-vector embeddings, but we average them
        to get a single vector for storage efficiency.
        """
        return 128

    @property
    def is_loaded(self) -> bool:
        """Whether the model is currently loaded."""
        return ColPaliClient._model is not None

    async def embed_image(self, image: Image.Image | Path) -> np.ndarray:
        """Generate embedding for a single image.

        Args:
            image: PIL Image or path to image file

        Returns:
            Numpy array of shape (embedding_dim,)
        """
        embeddings = await self.embed_images([image])
        return embeddings[0]

    async def embed_images(
        self,
        images: list[Image.Image | Path],
    ) -> list[np.ndarray]:
        """Generate embeddings for multiple images.

        Args:
            images: List of PIL Images or paths to image files

        Returns:
            List of numpy arrays, each of shape (embedding_dim,)
        """
        if not images:
            return []

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, lambda: self._embed_images_sync(images))

    def _embed_images_sync(
        self,
        images: list[Image.Image | Path],
    ) -> list[np.ndarray]:
        """Synchronous image embedding implementation."""
        import torch

        all_embeddings: list[np.ndarray] = []

        # Convert paths to PIL images
        pil_images: list[Image.Image] = []
        for img in images:
            if isinstance(img, Path):
                try:
                    pil_images.append(Image.open(img).convert("RGB"))
                except Exception as e:
                    console.print(
                        f"[yellow]Warning: Could not load image {img}: {e}[/yellow]"
                    )
                    continue
            elif isinstance(img, Image.Image):
                pil_images.append(img.convert("RGB"))
            else:
                raise ValueError(f"Invalid image type: {type(img)}")

        if not pil_images:
            return []

        # Process in batches
        for i in range(0, len(pil_images), self.batch_size):
            batch = pil_images[i : i + self.batch_size]

            with torch.no_grad():
                # Process images through ColPali processor
                batch_inputs = self.processor.process_images(batch)

                # Move to device
                batch_inputs = {k: v.to(self.device) for k, v in batch_inputs.items()}

                # Get embeddings
                embeddings = self.model(**batch_inputs)

                # ColPali returns multi-vector embeddings (sequence_length, dim)
                # We take the mean across the sequence dimension for storage
                for emb in embeddings:
                    # emb shape: (sequence_length, dim)
                    mean_emb = emb.mean(dim=0).cpu().numpy()
                    all_embeddings.append(mean_emb)

            if len(pil_images) > self.batch_size:
                console.print(
                    f"  [dim]Embedded {min(i + self.batch_size, len(pil_images))}"
                    f"/{len(pil_images)} images[/dim]"
                )

        return all_embeddings

    async def embed_visual_elements(
        self,
        elements: list["VisualElement"],
    ) -> list["VisualElement"]:
        """Generate embeddings for VisualElement objects.

        Only processes elements that:
        - Don't already have embeddings
        - Have valid image paths

        Args:
            elements: List of VisualElement objects

        Returns:
            Same list with embeddings assigned
        """
        # Filter elements that need embedding
        to_embed = [
            e
            for e in elements
            if e.visual_embedding is None and e.image_path and e.image_path.exists()
        ]

        if not to_embed:
            return elements

        console.print(
            f"[blue]Generating ColPali embeddings for {len(to_embed)} images...[/blue]"
        )

        # Get image paths (filter None to satisfy mypy)
        image_paths = [e.image_path for e in to_embed if e.image_path is not None]

        # Generate embeddings
        embeddings = await self.embed_images(image_paths)

        # Assign embeddings to elements
        for element, embedding in zip(to_embed, embeddings, strict=False):
            element.visual_embedding = embedding
            element.embedding_model = self.model_name

        console.print(f"[green]Generated {len(embeddings)} visual embeddings[/green]")

        return elements

    async def compute_similarity(
        self,
        embedding1: np.ndarray,
        embedding2: np.ndarray,
    ) -> float:
        """Compute cosine similarity between two embeddings.

        Args:
            embedding1: First embedding vector
            embedding2: Second embedding vector

        Returns:
            Cosine similarity score in range [-1, 1]
        """
        norm1 = np.linalg.norm(embedding1)
        norm2 = np.linalg.norm(embedding2)

        if norm1 == 0 or norm2 == 0:
            return 0.0

        return float(np.dot(embedding1, embedding2) / (norm1 * norm2))

    async def find_similar(
        self,
        query_embedding: np.ndarray,
        corpus_embeddings: list[np.ndarray],
        top_k: int = 5,
    ) -> list[tuple[int, float]]:
        """Find most similar images in a corpus.

        Args:
            query_embedding: Query image embedding
            corpus_embeddings: List of corpus embeddings to search
            top_k: Number of top results to return

        Returns:
            List of (index, similarity_score) tuples, sorted by score descending
        """
        if not corpus_embeddings:
            return []

        corpus_matrix = np.vstack(corpus_embeddings)

        # Normalize
        query_norm = query_embedding / (np.linalg.norm(query_embedding) + 1e-8)
        corpus_norms = np.linalg.norm(corpus_matrix, axis=1, keepdims=True) + 1e-8
        corpus_normalized = corpus_matrix / corpus_norms

        # Compute similarities
        similarities = np.dot(corpus_normalized, query_norm)

        # Get top-k indices
        if top_k >= len(similarities):
            indices = np.argsort(similarities)[::-1]
        else:
            indices = np.argpartition(similarities, -top_k)[-top_k:]
            indices = indices[np.argsort(similarities[indices])[::-1]]

        results = [(int(idx), float(similarities[idx])) for idx in indices]
        return results

    async def build_similarity_matrix(
        self,
        embeddings: list[np.ndarray],
    ) -> np.ndarray:
        """Build pairwise similarity matrix for a set of embeddings.

        Args:
            embeddings: List of embedding vectors

        Returns:
            NxN similarity matrix
        """
        if not embeddings:
            return np.array([])

        matrix = np.vstack(embeddings)

        # Normalize
        norms = np.linalg.norm(matrix, axis=1, keepdims=True) + 1e-8
        normalized = matrix / norms

        # Compute pairwise similarities
        similarity_matrix = np.dot(normalized, normalized.T)

        return similarity_matrix

    def unload_model(self) -> None:
        """Unload the model to free memory."""
        import gc

        ColPaliClient._model = None
        ColPaliClient._processor = None
        ColPaliClient._initialized = False

        # Force garbage collection
        gc.collect()

        try:
            import torch

            if torch.cuda.is_available():
                torch.cuda.empty_cache()
        except ImportError:
            pass

        console.print("[dim]ColPali model unloaded[/dim]")


def get_colpali_client() -> ColPaliClient:
    """Get the global ColPali client instance.

    Returns:
        ColPaliClient singleton instance
    """
    return ColPaliClient()
