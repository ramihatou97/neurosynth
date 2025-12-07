"""
AI Client (Async)

Production-ready async AI client for embeddings and synthesis.
Uses Voyage AI for embeddings and Claude for synthesis.

Features:
- Async/await with httpx.AsyncClient
- Connection pooling (20 keepalive, 100 max connections)
- Automatic retry with exponential backoff
- Structured logging with context
- Context manager support for lifecycle
"""

import os
from typing import List, Optional

import httpx
import structlog
from config import settings
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

logger = structlog.get_logger(__name__)


class AsyncAIClient:
    """
    Production-ready async AI client with connection pooling and resilience.

    Uses:
    - Voyage AI for embeddings (high quality, reasonable cost)
    - Claude for synthesis (best for long-form medical content)

    Features:
    - Connection pooling for efficiency
    - Automatic retry on transient failures
    - Structured logging for observability
    - Context manager for proper cleanup
    """

    VOYAGE_API_URL = "https://api.voyageai.com/v1/embeddings"
    ANTHROPIC_API_URL = "https://api.anthropic.com/v1/messages"

    def __init__(
        self,
        voyage_api_key: Optional[str] = None,
        anthropic_api_key: Optional[str] = None,
        timeout: float = 60.0,
    ):
        self.voyage_key = (
            voyage_api_key or settings.voyage_api_key or os.getenv("VOYAGE_API_KEY")
        )
        self.anthropic_key = (
            anthropic_api_key
            or settings.anthropic_api_key
            or os.getenv("ANTHROPIC_API_KEY")
        )
        self.timeout = timeout

        self._validate_keys()

        # Persistent AsyncClient for connection pooling
        self.client = httpx.AsyncClient(
            timeout=self.timeout,
            limits=httpx.Limits(max_keepalive_connections=20, max_connections=100),
        )

        logger.info(
            "ai_client_initialized",
            timeout=timeout,
            has_voyage_key=bool(self.voyage_key),
            has_anthropic_key=bool(self.anthropic_key),
        )

    def _validate_keys(self):
        """Validate that required API keys are present"""
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
    # Embeddings
    # ========================================================================

    async def get_embedding(
        self, text: str, model: Optional[str] = None
    ) -> list[float]:
        """
        Get embedding for a single text.

        Args:
            text: Text to embed
            model: Voyage model to use (default from settings)

        Returns:
            Embedding vector
        """
        embeddings = await self.get_embeddings([text], model=model)
        return embeddings[0]

    async def get_embeddings(
        self, texts: list[str], model: Optional[str] = None
    ) -> list[list[float]]:
        """
        Get embeddings for multiple texts.

        Args:
            texts: List of texts to embed
            model: Voyage model to use (default: from settings)

        Returns:
            List of embedding vectors
        """
        model = model or settings.embedding_model

        # Voyage has a limit of 128 texts per request
        all_embeddings = []
        batch_size = 128

        for i in range(0, len(texts), batch_size):
            batch = texts[i : i + batch_size]
            batch_embeddings = await self._get_embeddings_batch(batch, model)
            all_embeddings.extend(batch_embeddings)

        return all_embeddings

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type(
            (httpx.ConnectError, httpx.ReadTimeout, httpx.HTTPStatusError)
        ),
    )
    async def _get_embeddings_batch(
        self, texts: list[str], model: str
    ) -> list[list[float]]:
        """
        Get embeddings for a batch of texts (with retry).

        Includes automatic retry on transient failures.
        """
        # Clean texts (Voyage has max length)
        cleaned = [self._truncate_text(t, max_chars=8000) for t in texts]

        logger.info(
            "requesting_embeddings",
            provider="voyage",
            batch_size=len(texts),
            model=model,
        )

        response = await self.client.post(
            self.VOYAGE_API_URL,
            headers={
                "Authorization": f"Bearer {self.voyage_key}",
                "Content-Type": "application/json",
            },
            json={"model": model, "input": cleaned, "input_type": "document"},
        )
        response.raise_for_status()
        data = response.json()

        # Extract embeddings in order
        embeddings = [None] * len(texts)
        for item in data["data"]:
            embeddings[item["index"]] = item["embedding"]

        logger.info("embeddings_received", count=len(embeddings))
        return embeddings

    # ========================================================================
    # Synthesis
    # ========================================================================

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type(
            (httpx.ConnectError, httpx.ReadTimeout, httpx.HTTPStatusError)
        ),
    )
    async def synthesize(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        max_tokens: int = 4096,
        temperature: float = 0.3,
        model: Optional[str] = None,
    ) -> str:
        """
        Generate synthesized content using Claude (with retry).

        Args:
            prompt: The main prompt
            system_prompt: System instructions
            max_tokens: Maximum tokens in response
            temperature: Sampling temperature (lower = more focused)
            model: Claude model to use (default from settings)

        Returns:
            Generated text
        """
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

        logger.info(
            "requesting_synthesis",
            provider="anthropic",
            model=model,
            max_tokens=max_tokens,
            temperature=temperature,
        )

        response = await self.client.post(
            self.ANTHROPIC_API_URL,
            headers={
                "x-api-key": self.anthropic_key,
                "anthropic-version": "2023-06-01",
                "Content-Type": "application/json",
            },
            json={
                "model": model,
                "max_tokens": max_tokens,
                "temperature": temperature,
                "system": system,
                "messages": messages,
            },
            timeout=120.0,  # Longer timeout for synthesis
        )
        response.raise_for_status()
        data = response.json()

        text = data["content"][0]["text"]
        tokens_used = data.get("usage", {}).get("output_tokens", 0)

        logger.info("synthesis_complete", tokens_used=tokens_used)
        return text

    async def synthesize_section(
        self,
        topic: str,
        section_name: str,
        subsections: list[str],
        source_chunks: list[dict],
        format_type: str = "prose",
    ) -> str:
        """
        Synthesize a chapter section from source chunks.

        Args:
            topic: Chapter topic
            section_name: Name of the section
            subsections: List of subsection names to cover
            source_chunks: List of {content, source_title, page} dicts
            format_type: "prose" or "step_by_step"

        Returns:
            Synthesized section content
        """
        # Format source material
        source_text = "\n\n---\n\n".join(
            [
                f"[Source: {c['source_title']}, p.{c.get('page', 'N/A')}]\n{c['content']}"
                for c in source_chunks
            ]
        )

        if format_type == "step_by_step":
            prompt = f"""Synthesize a surgical technique section from the following sources.

Topic: {topic}
Section: {section_name}
Subsections to cover: {', '.join(subsections)}

SOURCE MATERIAL:
{source_text}

INSTRUCTIONS:
Write a clear, step-by-step surgical technique section. For each step:
1. Number the step clearly
2. Be specific and actionable
3. Include relevant anatomical landmarks
4. Note critical structures to preserve/avoid
5. Cite sources as [Author, page]

Include subsections for: {', '.join(subsections)}

Do not invent information not present in the sources. If sources provide different techniques, describe the variations."""
        else:
            prompt = f"""Synthesize a comprehensive chapter section from the following sources.

Topic: {topic}
Section: {section_name}
Subsections to cover: {', '.join(subsections)}

SOURCE MATERIAL:
{source_text}

INSTRUCTIONS:
Create a unified, coherent section that:
1. Covers all specified subsections
2. Synthesizes information from multiple sources (don't just concatenate)
3. Resolves redundancy (same information from multiple sources)
4. Uses clear, professional medical prose
5. Cites sources as [Author, page]
6. Notes any conflicts or different perspectives between sources

Do not invent information not present in the sources."""

        return await self.synthesize(prompt, max_tokens=4096)

    # ========================================================================
    # Lifecycle Management
    # ========================================================================

    async def close(self):
        """Close the persistent HTTP client."""
        await self.client.aclose()
        logger.info("ai_client_closed")

    async def __aenter__(self):
        """Context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        await self.close()

    # ========================================================================
    # Utilities
    # ========================================================================

    def _truncate_text(self, text: str, max_chars: int) -> str:
        """Truncate text to maximum characters"""
        if len(text) <= max_chars:
            return text
        return text[:max_chars]


# Backward compatibility alias
AIClient = AsyncAIClient
