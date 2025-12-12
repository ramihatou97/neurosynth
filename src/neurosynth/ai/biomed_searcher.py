import logging
from pathlib import Path
from typing import List, Optional, Union

import numpy as np
import torch
from PIL import Image

try:
    import open_clip
except ImportError:
    open_clip = None

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("BiomedCLIP")


class BiomedCLIPSearcher:
    """MPS-Optimized Wrapper for Microsoft's BiomedCLIP using open_clip."""

    # Using the HF Hub ID supported by open_clip
    MODEL_NAME = "hf-hub:microsoft/BiomedCLIP-PubMedBERT_256-vit_base_patch16_224"

    def __init__(self, device: str | None = None):
        if not open_clip:
            logger.error(
                "open_clip_torch not installed. Please pip install open_clip_torch"
            )
            raise ImportError("open_clip_torch not installed")

        if device:
            self.device = device
        else:
            if torch.backends.mps.is_available():
                self.device = "mps"
            elif torch.cuda.is_available():
                self.device = "cuda"
            else:
                self.device = "cpu"

        logger.info(f"Loading BiomedCLIP on: {self.device.upper()}")

        try:
            # open_clip loading mechanism
            self.model, _, self.preprocess = open_clip.create_model_and_transforms(
                self.MODEL_NAME, device=self.device
            )
            self.tokenizer = open_clip.get_tokenizer(self.MODEL_NAME)
            self.model.eval()
        except Exception as e:
            logger.error(f"Failed to load BiomedCLIP: {e}")
            raise

    def _normalize(self, vector: np.ndarray) -> np.ndarray:
        norm = np.linalg.norm(vector)
        return vector / norm if norm > 0 else vector

    def embed_text(self, text: str | list[str]) -> np.ndarray:
        if isinstance(text, str):
            text = [text]
        try:
            with torch.no_grad():
                # Tokenize
                text_tokens = self.tokenizer(text).to(self.device)
                # Encode
                features = self.model.encode_text(text_tokens)
                # Normalize and convert to numpy
                features /= features.norm(dim=-1, keepdim=True)
                return features.cpu().numpy()
        except Exception as e:
            logger.error(f"Text embedding failed: {e}")
            return np.array([])

    def embed_image(
        self, image_input: str | Path | list[str | Path | Image.Image]
    ) -> np.ndarray:
        images = []
        try:
            inputs = image_input if isinstance(image_input, list) else [image_input]

            for item in inputs:
                img_obj = None
                if isinstance(item, (str, Path)):
                    path = Path(item)
                    if path.exists():
                        img_obj = Image.open(str(path)).convert("RGB")
                    else:
                        logger.warning(f"Image not found: {path}")
                else:
                    img_obj = item  # Asume PIL Image

                if img_obj:
                    # Apply open_clip preprocessing
                    processed_img = self.preprocess(img_obj)
                    images.append(processed_img)

            if not images:
                return np.array([])

            # Stack images into a batch tensor
            if len(images) > 1:
                image_tensor = torch.stack(images).to(self.device)
            else:
                image_tensor = images[0].unsqueeze(0).to(self.device)

            with torch.no_grad():
                features = self.model.encode_image(image_tensor)
                features /= features.norm(dim=-1, keepdim=True)
                return features.cpu().numpy()

        except Exception as e:
            logger.error(f"Image embedding failed: {e}")
            return np.array([])
