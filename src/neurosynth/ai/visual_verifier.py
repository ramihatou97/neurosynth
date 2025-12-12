"""
Visual Verifier (VP)
====================
Provides VLM-based verification for image captions.
Uses a Vision-Language Model (e.g., Gemini Flash, Moondream) to check congruence
between an image and its caption.
"""

from dataclasses import dataclass
from typing import List


@dataclass
class VerificationResult:
    image_id: str
    is_congruent: bool
    confidence: float
    reason: str


class VisualVerifier:
    """
    Facade for VLM-based image verification.
    """

    def __init__(self, model_name: str = "gemini-1.5-flash"):
        self.model_name = model_name
        self._client = None  # Lazy init

    async def verify_caption_batch(
        self, image_paths: list[str], captions: list[str]
    ) -> list[VerificationResult]:
        """
        Verify a batch of image-caption pairs asynchronously.

        Args:
            image_paths: List of absolute file paths to images.
            captions: List of corresponding captions.

        Returns:
            List of VerificationResult objects.
        """
        import asyncio

        from src.config import settings

        if not settings.enable_vlm_verification:
            return [
                VerificationResult(
                    image_id=str(p),
                    is_congruent=True,
                    confidence=1.0,
                    reason="Verification disabled",
                )
                for p in image_paths
            ]

        tasks = [self._verify_single(p, c) for p, c in zip(image_paths, captions)]
        return await asyncio.gather(*tasks)

    async def _verify_single(self, image_path: str, caption: str) -> VerificationResult:
        """Verify a single image-caption pair with VLM."""
        import base64
        import json
        from pathlib import Path

        try:
            from anthropic import AsyncAnthropic
        except ImportError:
            # Fallback mock if dependency missing
            return VerificationResult(
                str(image_path), True, 0.5, "Anthropic SDK missing"
            )

        from src.config import settings

        # Check file
        path = Path(image_path)
        if not path.exists():
            return VerificationResult(
                str(image_path), False, 0.0, "Image file not found"
            )

        # Init client (lazy)
        client = AsyncAnthropic(api_key=settings.anthropic_api_key)

        # Encode image
        try:
            with open(path, "rb") as f:
                image_data = base64.standard_b64encode(f.read()).decode("utf-8")
        except Exception as e:
            return VerificationResult(
                str(image_path), False, 0.0, f"Image read error: {e}"
            )

        # Iterative Refinement Loop (max 3 attempts)
        max_retries = 3

        system_prompt = "You are a medical image analyst. Verify if the image matches the provided caption/context. Be strict about anatomical correctness."

        current_prompt = f"Does this image match the following caption? Caption: {caption}\n\nRespond with JSON: {{'is_congruent': bool, 'confidence': float (0.0-1.0), 'reason': str}}"

        for i in range(max_retries):
            try:
                messages = [
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "image",
                                "source": {
                                    "type": "base64",
                                    "media_type": "image/png",
                                    "data": image_data,
                                },
                            },
                            {"type": "text", "text": current_prompt},
                        ],
                    }
                ]

                # If refining, maybe include history?
                # For now, simple retry logic is sufficient or stateless refinement.

                response = await client.messages.create(
                    model=settings.claude_model,
                    max_tokens=300,
                    messages=messages,
                    system=system_prompt,
                )

                content = response.content[0].text

                # Parse JSON
                # Robust extraction needed as LLM might output text before JSON
                start = content.find("{")
                end = content.rfind("}") + 1
                if start >= 0 and end > start:
                    json_str = content[start:end]
                    data = json.loads(json_str)

                    confidence = float(data.get("confidence", 0.0))
                    is_congruent = bool(data.get("is_congruent", False))
                    reason = data.get("reason", "No reason provided")

                    # Refinement check
                    if (
                        confidence < settings.vlm_confidence_threshold
                        and i < max_retries - 1
                    ):
                        # Low confidence, ask to re-evaluate with more detail
                        current_prompt = f"Previous analysis was low confidence ({confidence}). Please re-evaluate carefully. Caption: {caption}. Focus on specific features. Respond with JSON."
                        continue

                    return VerificationResult(
                        str(image_path), is_congruent, confidence, reason
                    )
                else:
                    return VerificationResult(
                        str(image_path), False, 0.0, "Failed to parse VLM response"
                    )

            except Exception as e:
                if i == max_retries - 1:
                    return VerificationResult(
                        str(image_path), False, 0.0, f"VLM error: {e}"
                    )
                continue

        return VerificationResult(str(image_path), False, 0.0, "Max retries exceeded")

    async def verify_single(self, image_path: str, caption: str) -> VerificationResult:
        """Verify a single image (sync wrapper or alias)."""
        # This method signature in original was sync, but calling code likely expects sync?
        # The gap analysis created verify_caption_batch as async.
        # This wrapper should likely be async too.
        return await self._verify_single(image_path, caption)
