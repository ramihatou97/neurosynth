"""Google Gemini client for fast extraction tasks."""

import asyncio
from typing import Any

import google.generativeai as genai
from google.api_core import exceptions as google_exceptions
from rich.console import Console
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from neurosynth import get_logger
from neurosynth.config import get_settings

console = Console()
logger = get_logger("llm.gemini")


class GeminiClient:
    """Client for Google Gemini API - used for fast extraction tasks."""

    def __init__(self, api_key: str | None = None, model: str | None = None):
        settings = get_settings()
        self.api_key = api_key or settings.google_api_key
        self.model_name = model or settings.gemini_model
        self.timeout = settings.llm_timeout
        self.max_retries = settings.llm_max_retries

        genai.configure(api_key=self.api_key)
        self.model = genai.GenerativeModel(self.model_name)
        logger.info(f"Initialized GeminiClient with model: {self.model_name}")

    @retry(
        stop=stop_after_attempt(5),  # Will be updated in __init__ if possible
        wait=wait_exponential(multiplier=1, min=2, max=60),
        retry=retry_if_exception_type(
            (
                google_exceptions.ResourceExhausted,
                google_exceptions.ServiceUnavailable,
                google_exceptions.DeadlineExceeded,
            )
        ),
        before_sleep=lambda retry_state: logger.warning(
            f"Gemini API error, retrying in {retry_state.next_action.sleep if retry_state.next_action else 0} seconds..."
        ),
    )
    async def generate(
        self,
        prompt: str,
        temperature: float = 0.1,
        max_tokens: int = 8192,
    ) -> str:
        """Generate text completion."""
        config = genai.GenerationConfig(
            temperature=temperature,
            max_output_tokens=max_tokens,
        )

        logger.debug(
            f"Generating response (prompt length: {len(prompt)}, max_tokens: {max_tokens})"
        )

        try:
            # Run in executor since genai is sync
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: self.model.generate_content(
                    prompt,
                    generation_config=config,
                    request_options={"timeout": self.timeout},
                ),
            )

            result = response.text
            logger.debug(f"Generated response (length: {len(result)})")
            return result

        except Exception as e:
            logger.error(f"Gemini API error: {e}")
            raise

    async def extract_structure(self, text: str) -> dict[str, Any]:
        """Extract document structure (sections, headings) from text."""
        prompt = f"""Analyze this neurosurgical text and extract its structure.
Return a JSON object with:
- "sections": list of section titles found
- "key_topics": list of main medical/surgical topics covered
- "has_references": boolean if references section exists
- "estimated_pages": rough page count

Text:
{text[:15000]}...

Return ONLY valid JSON, no explanation."""

        response = await self.generate(prompt, temperature=0.0)

        # Parse JSON from response
        import json

        try:
            # Find JSON in response
            start = response.find("{")
            end = response.rfind("}") + 1
            if start >= 0 and end > start:
                return json.loads(response[start:end])
        except json.JSONDecodeError:
            pass

        return {"sections": [], "key_topics": [], "has_references": False}

    async def identify_chunk_topic(self, chunk_text: str) -> dict[str, str]:
        """Identify the topic and subtopic of a content chunk."""
        prompt = f"""Analyze this neurosurgical content and identify its topic.

Content:
{chunk_text[:3000]}

Return a JSON object with:
- "topic": The main topic (e.g., "Surgical Technique", "Anatomy", "Complications")
- "subtopic": More specific subtopic
- "key_concepts": List of key medical concepts mentioned
- "section_suggestion": Which standard chapter section this belongs to

Standard sections: Introduction, Anatomy, Pathophysiology, Clinical Presentation,
Diagnostic Workup, Surgical Indications, Surgical Technique, Complications, Outcomes

Return ONLY valid JSON."""

        response = await self.generate(prompt, temperature=0.0)

        import json

        try:
            start = response.find("{")
            end = response.rfind("}") + 1
            if start >= 0 and end > start:
                return json.loads(response[start:end])
        except json.JSONDecodeError:
            pass

        return {
            "topic": "Unknown",
            "subtopic": "",
            "key_concepts": [],
            "section_suggestion": "Introduction",
        }

    async def segment_into_chunks(
        self,
        text: str,
        target_size: int = 1000,
    ) -> list[dict[str, Any]]:
        """Intelligently segment text into semantic chunks."""
        prompt = f"""Segment this neurosurgical text into logical chunks of approximately {target_size} words each.
Keep related content together. Split at natural boundaries (topic changes, new sections).

Text:
{text[:30000]}

Return a JSON array where each item has:
- "content": The chunk text
- "suggested_title": A brief title for this chunk
- "word_count": Approximate word count

Return ONLY valid JSON array."""

        response = await self.generate(prompt, temperature=0.1, max_tokens=16000)

        import json

        try:
            start = response.find("[")
            end = response.rfind("]") + 1
            if start >= 0 and end > start:
                return json.loads(response[start:end])
        except json.JSONDecodeError:
            pass

        # Fallback: simple chunking
        words = text.split()
        chunks = []
        for i in range(0, len(words), target_size):
            chunk_words = words[i : i + target_size]
            chunks.append(
                {
                    "content": " ".join(chunk_words),
                    "suggested_title": f"Chunk {i // target_size + 1}",
                    "word_count": len(chunk_words),
                }
            )
        return chunks

    async def extract_metadata(self, first_pages: str) -> dict[str, Any]:
        """Extract document metadata from first pages."""
        prompt = f"""Extract bibliographic metadata from this document's first pages.

Text:
{first_pages[:5000]}

Return a JSON object with:
- "title": Full document title
- "authors": List of author names
- "year": Publication year (integer or null)
- "edition": Edition if mentioned
- "publisher": Publisher name if found
- "chapter_number": Chapter number if this is a chapter

Return ONLY valid JSON."""

        response = await self.generate(prompt, temperature=0.0)

        import json

        try:
            start = response.find("{")
            end = response.rfind("}") + 1
            if start >= 0 and end > start:
                return json.loads(response[start:end])
        except json.JSONDecodeError:
            pass

    async def synthesize_section(
        self,
        section_title: str,
        clusters: list[dict[str, str]],
        word_target: int = 1500,
        use_xml_citations: bool = True,
    ) -> str:
        """Synthesize a chapter section from knowledge clusters (Gemini implementation)."""
        # Build cluster text with source IDs for traceability
        cluster_parts = []
        for i, c in enumerate(clusters):
            source_id = c.get("source_id", f"cluster_{i+1}")
            source_name = c.get("source", "Unknown")
            cluster_parts.append(
                f"[SOURCE_ID: {source_id}]\n"
                f"[SOURCE: {source_name}]\n"
                f"{c['content']}"
            )
        clusters_text = "\n\n---\n\n".join(cluster_parts)

        if use_xml_citations:
            system = """You are writing a section of a neurosurgical textbook chapter.
Write in formal academic medical prose. Be comprehensive but not redundant.

CRITICAL: Use XML citation anchoring for every factual claim. Format:
<claim source_id="SOURCE_ID">factual statement here</claim>

Example:
<claim source_id="Smith2020">The mortality rate for this procedure is approximately 2.3%</claim>

This allows verification of every claim back to its source. Never make unsourced claims."""

            prompt = f"""Write the "{section_title}" section for a neurosurgical chapter.

Knowledge to incorporate (each has a SOURCE_ID for citation):
{clusters_text}

Requirements:
- Target length: approximately {word_target} words
- Academic medical writing style
- WRAP EVERY FACTUAL CLAIM in <claim source_id="...">...</claim> tags
- Include ALL relevant information from the clusters
- Present conflicting viewpoints explicitly with both source_ids
- Use precise anatomical and medical terminology
- Flow logically from concept to concept

Write the section content now:"""
        else:
            system = """You are writing a section of a neurosurgical textbook chapter.
Write in formal academic medical prose. Be comprehensive but not redundant.
Include inline citations as (AuthorYear) format."""

            prompt = f"""Write the "{section_title}" section for a neurosurgical chapter.

Knowledge to incorporate:
{clusters_text}

Requirements:
- Target length: approximately {word_target} words
- Academic medical writing style
- Include ALL relevant information from the clusters
- Present conflicting viewpoints with attribution
- Use precise anatomical and medical terminology
- Flow logically from concept to concept
- Include citations inline

Write the section content now:"""

        # Gemini uses system instructions differently, but we can prepend it to the prompt
        full_prompt = f"{system}\n\n{prompt}"
        return await self.generate(full_prompt, temperature=0.3, max_tokens=8192)
