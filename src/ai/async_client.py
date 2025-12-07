"""
Async AI Client - Production-ready with connection pooling and retry logic.

Non-blocking version of AIClient for use in GUI and async contexts.
Uses Voyage AI for embeddings and Claude for synthesis.
"""

import os
import logging
from pathlib import Path
from typing import List, Optional

import httpx
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)

# Try to load .env from neurosynth root if not already loaded
try:
    from dotenv import load_dotenv
    # Look for .env in the src parent directory (neurosynth root)
    env_path = Path(__file__).parent.parent.parent / ".env"
    if env_path.exists():
        load_dotenv(env_path)
except ImportError:
    pass  # dotenv not installed, rely on existing env vars

from config import settings

logger = logging.getLogger(__name__)


class AsyncAIClient:
    """
    Non-blocking AI client with connection pooling and resilience.

    Uses:
    - Voyage AI for embeddings (high quality, reasonable cost)
    - Claude for synthesis (best for long-form medical content)
    """

    VOYAGE_API_URL = "https://api.voyageai.com/v1/embeddings"
    ANTHROPIC_API_URL = "https://api.anthropic.com/v1/messages"

    def __init__(
        self,
        voyage_api_key: Optional[str] = None,
        anthropic_api_key: Optional[str] = None,
        timeout: float = 600.0,  # 10 minutes per attempt for complex synthesis
    ):
        self.voyage_key = (
            voyage_api_key or settings.voyage_api_key or os.getenv("VOYAGE_API_KEY")
        )
        self.anthropic_key = (
            anthropic_api_key
            or settings.anthropic_api_key
            or os.getenv("ANTHROPIC_API_KEY")
        )
        self._timeout = timeout
        self._validate_keys()

        # Lazy-initialized client to support multiple event loops (GUI threading)
        self._client: Optional[httpx.AsyncClient] = None
        self._client_loop_id: Optional[int] = None
        logger.info("AsyncAIClient initialized with connection pooling")

    def _validate_keys(self):
        """Validate that required API keys are present."""
        if not self.voyage_key:
            raise ValueError(
                "Voyage AI API key required. Set VOYAGE_API_KEY environment variable "
                "or pass voyage_api_key parameter."
            )
        if not self.anthropic_key:
            raise ValueError(
                "Anthropic API key required. Set ANTHROPIC_API_KEY environment variable "
                "or pass anthropic_api_key parameter."
            )

    # ========================================================================
    # Client Management (supports multiple event loops for GUI threading)
    # ========================================================================

    def _get_client(self) -> httpx.AsyncClient:
        """Get or create an httpx.AsyncClient for the current event loop.

        This handles the case where the GUI creates new event loops per search,
        which would otherwise break a pre-created client.
        """
        import asyncio

        try:
            current_loop = asyncio.get_running_loop()
            current_loop_id = id(current_loop)
        except RuntimeError:
            current_loop_id = None

        # Create new client if none exists or if loop changed
        if self._client is None or self._client_loop_id != current_loop_id:
            # Close old client if exists (best effort)
            if self._client is not None:
                try:
                    # Can't await here, so we mark for GC cleanup
                    self._client = None
                except Exception:
                    pass

            self._client = httpx.AsyncClient(
                timeout=self._timeout,
                limits=httpx.Limits(max_keepalive_connections=20, max_connections=100),
            )
            self._client_loop_id = current_loop_id
            logger.debug("Created new httpx.AsyncClient for event loop %s", current_loop_id)

        return self._client

    # ========================================================================
    # Embeddings
    # ========================================================================

    @retry(
        stop=stop_after_attempt(5),
        wait=wait_exponential(multiplier=2, min=4, max=120),
        retry=retry_if_exception_type((httpx.ConnectError, httpx.TimeoutException)),
    )
    async def get_embedding(self, text: str, model: str = None) -> List[float]:
        """Get embedding for a single text (non-blocking)."""
        embeddings = await self.get_embeddings([text], model=model)
        return embeddings[0]

    @retry(
        stop=stop_after_attempt(5),
        wait=wait_exponential(multiplier=2, min=4, max=120),
        retry=retry_if_exception_type((httpx.ConnectError, httpx.TimeoutException)),
    )
    async def get_embeddings(
        self, texts: List[str], model: str = None
    ) -> List[List[float]]:
        """Get embeddings for multiple texts (non-blocking)."""
        model = model or settings.embedding_model

        # Voyage has a limit of 128 texts per request
        all_embeddings = []
        batch_size = 128

        for i in range(0, len(texts), batch_size):
            batch = texts[i : i + batch_size]
            batch_embeddings = await self._get_embeddings_batch(batch, model)
            all_embeddings.extend(batch_embeddings)

        return all_embeddings

    async def _get_embeddings_batch(
        self, texts: List[str], model: str
    ) -> List[List[float]]:
        """Get embeddings for a batch of texts."""
        # Clean texts (Voyage has max length)
        cleaned = [self._truncate_text(t, max_chars=8000) for t in texts]

        headers = {
            "Authorization": f"Bearer {self.voyage_key}",
            "Content-Type": "application/json",
        }

        logger.debug(f"Requesting embeddings for {len(texts)} texts with model {model}")

        client = self._get_client()
        response = await client.post(
            self.VOYAGE_API_URL,
            headers=headers,
            json={"model": model, "input": cleaned, "input_type": "document"},
        )
        response.raise_for_status()
        data = response.json()

        # Extract embeddings in order
        embeddings = [None] * len(texts)
        for item in data["data"]:
            embeddings[item["index"]] = item["embedding"]

        logger.debug(f"Received {len(embeddings)} embeddings")
        return embeddings

    # ========================================================================
    # Synthesis
    # ========================================================================

    @retry(
        stop=stop_after_attempt(5),
        wait=wait_exponential(multiplier=2, min=4, max=120),
        retry=retry_if_exception_type((httpx.ConnectError, httpx.TimeoutException)),
    )
    async def synthesize(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        max_tokens: int = 4096,
        temperature: float = 0.3,
        model: str = None,
    ) -> str:
        """Generate synthesized content using Claude (non-blocking)."""
        model = model or settings.synthesis_model

        messages = [{"role": "user", "content": prompt}]

        default_system = """You are an expert neurosurgical knowledge synthesizer. 
Your task is to create comprehensive, accurate medical content by combining information from multiple sources.

Guidelines:
- Synthesize information coherently, don't just concatenate
- Maintain medical accuracy and precision
- Cite sources using [Author, page] format
- Note when sources conflict or provide different perspectives
- Use clear, professional medical prose
- Do not invent information not present in the sources"""

        system = system_prompt or default_system

        headers = {
            "x-api-key": self.anthropic_key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
        }

        payload = {
            "model": model,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "system": system,
            "messages": messages,
        }

        logger.info(f"Requesting synthesis with model {model}, max_tokens={max_tokens}")

        client = self._get_client()
        response = await client.post(
            self.ANTHROPIC_API_URL, headers=headers, json=payload
        )
        response.raise_for_status()
        data = response.json()

        text = data["content"][0]["text"]
        tokens_used = data.get("usage", {}).get("output_tokens", "unknown")
        logger.info(f"Synthesis complete, tokens used: {tokens_used}")

        return text

    # ========================================================================
    # Utilities
    # ========================================================================

    def _truncate_text(self, text: str, max_chars: int) -> str:
        """Truncate text to maximum characters."""
        if len(text) <= max_chars:
            return text
        return text[:max_chars]

    async def close(self):
        """Close the persistent HTTP client."""
        if self._client is not None:
            await self._client.aclose()
            self._client = None
            self._client_loop_id = None
        logger.info("AsyncAIClient closed")

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()

