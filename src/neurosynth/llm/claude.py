"""Anthropic Claude client for high-quality synthesis tasks."""

from typing import Any

import anthropic
from anthropic.types import TextBlock
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
logger = get_logger("llm.claude")


def _log_retry(retry_state):
    """Log retry attempts with detailed info."""
    attempt = retry_state.attempt_number
    exception = retry_state.outcome.exception()
    wait_time = retry_state.next_action.sleep if retry_state.next_action else 0
    logger.warning(
        f"Claude API retry {attempt}/5: {type(exception).__name__}: {exception}. "
        f"Waiting {wait_time:.1f}s before next attempt..."
    )
    console.print(
        f"  [yellow]Claude API retry {attempt}/5: {type(exception).__name__}. "
        f"Waiting {wait_time:.0f}s...[/yellow]"
    )


class ClaudeClient:
    """Client for Anthropic Claude API - used for synthesis and analysis."""

    def __init__(self, api_key: str | None = None, model: str | None = None):
        settings = get_settings()
        self.api_key = api_key or settings.anthropic_api_key
        self.model_name = model or settings.claude_model
        self.timeout = settings.llm_timeout
        self.max_retries = settings.llm_max_retries

        self.client = anthropic.Anthropic(api_key=self.api_key, timeout=self.timeout)
        self.async_client = anthropic.AsyncAnthropic(
            api_key=self.api_key, timeout=self.timeout
        )
        logger.info(f"Initialized ClaudeClient with model: {self.model_name}")

    @retry(
        stop=stop_after_attempt(
            5
        ),  # Will be updated in __init__ if possible, but decorator runs at import time.
        # We can use a custom retry strategy or just keep the hardcoded 5 for now as it matches the default in config.
        wait=wait_exponential(
            multiplier=2, min=4, max=120
        ),  # Longer waits: 4s, 8s, 16s, 32s, 64s (max 120s)
        retry=retry_if_exception_type(
            (
                anthropic.RateLimitError,
                anthropic.APIConnectionError,
                anthropic.APITimeoutError,  # Added timeout
                anthropic.InternalServerError,  # Added server errors (500s)
            )
        ),
        before_sleep=_log_retry,
    )
    async def generate(
        self,
        prompt: str,
        system: str | None = None,
        temperature: float = 0.3,
        max_tokens: int = 8192,
    ) -> str:
        """Generate text completion with robust retry handling."""
        messages = [{"role": "user", "content": prompt}]

        logger.debug(
            f"Generating response (prompt length: {len(prompt)}, max_tokens: {max_tokens})"
        )

        try:
            response = await self.async_client.messages.create(
                model=self.model_name,
                max_tokens=max_tokens,
                temperature=temperature,
                system=system or "You are an expert neurosurgeon and medical writer.",
                messages=messages,
            )

            first_block = response.content[0]
            if isinstance(first_block, TextBlock):
                result = first_block.text
            else:
                raise ValueError(
                    f"Expected TextBlock, got {type(first_block).__name__}"
                )
            logger.debug(f"Generated response (length: {len(result)})")
            return result

        except (
            anthropic.RateLimitError,
            anthropic.APIConnectionError,
            anthropic.APITimeoutError,
            anthropic.InternalServerError,
        ):
            # Let tenacity handle these retryable errors
            raise
        except anthropic.APIError as e:
            # Log non-retryable API errors
            logger.error(f"Claude API error (non-retryable): {type(e).__name__}: {e}")
            raise

    async def merge_chunks(
        self,
        chunks: list[dict[str, str]],
        preserve_all_details: bool = True,
        preserve_conflicts: bool = True,
    ) -> str:
        """Merge multiple semantically similar chunks into one comprehensive text.

        Args:
            chunks: List of dicts with 'content' and optionally 'source', 'source_id'
            preserve_all_details: If True, ensure no unique information is lost
            preserve_conflicts: If True, preserve conflicting claims with attribution

        Returns:
            Merged text with XML citation anchors
        """
        # Build chunks text with source IDs
        chunk_parts = []
        for i, c in enumerate(chunks):
            source_id = c.get("source_id", f"src_{i+1}")
            source_name = c.get("source", "Unknown")
            chunk_parts.append(
                f"[SOURCE_ID: {source_id}]\n"
                f"[SOURCE: {source_name}]\n"
                f"{c['content']}"
            )
        chunks_text = "\n\n---\n\n".join(chunk_parts)

        conflict_instruction = ""
        if preserve_conflicts:
            conflict_instruction = """
CONFLICT HANDLING (CRITICAL FOR MEDICAL ACCURACY):
- When sources provide DIFFERENT values for the same metric, preserve BOTH with attribution
- Example: If Source A says "5% mortality" and Source B says "8% mortality":
  <conflict type="quantitative">
    <perspective source_id="A">5% mortality rate</perspective>
    <perspective source_id="B">8% mortality rate</perspective>
  </conflict>
- NEVER average conflicting numbers
- NEVER silently choose one value over another"""

        system = f"""You are an expert neurosurgeon synthesizing knowledge from multiple authoritative sources.
Your task is to merge overlapping content while:
1. Preserving ALL unique details from each source
2. Eliminating true redundancy (identical information, not similar-but-different values)
3. Maintaining academic precision
4. Using XML citation anchoring: <claim source_id="...">fact</claim>
{conflict_instruction}"""

        prompt = f"""Merge these overlapping passages into a single comprehensive text.

CRITICAL REQUIREMENTS:
- Include ALL unique information from each source
- Remove only TRUE redundancy (identical claims from multiple sources)
- Preserve ALL specific numbers, measurements, percentages (even if they differ between sources)
- Wrap factual claims in <claim source_id="SOURCE_ID">...</claim>
- Mark disagreements with <conflict>...</conflict>
- Use precise medical terminology

Passages to merge:
{chunks_text}

Write the merged content as flowing academic prose with XML citation anchors."""

        return await self.generate(prompt, system=system, temperature=0.2)

    async def detect_conflicts(
        self,
        chunks: list[dict[str, str]],
    ) -> list[dict[str, Any]]:
        """Detect conflicts or contradictions between chunks."""
        chunks_text = "\n\n---\n\n".join(
            [f"SOURCE: {c.get('source', 'Unknown')}\n{c['content']}" for c in chunks]
        )

        system = """You are analyzing neurosurgical literature for conflicting information.
Identify disagreements in: numbers/percentages, treatment approaches, anatomical descriptions,
outcome data, surgical techniques, or recommendations."""

        prompt = f"""Analyze these passages from different sources for conflicts or contradictions.

Passages:
{chunks_text}

Return a JSON array of conflicts found. Each conflict should have:
- "type": One of "quantitative", "contradictory", "approach", "temporal", "terminology"
- "description": Brief description of the conflict
- "perspectives": Array of objects with "claim" and "source" fields
- "significance": "high", "medium", or "low"

If no conflicts found, return an empty array [].
Return ONLY valid JSON."""

        response = await self.generate(prompt, system=system, temperature=0.1)

        import json

        try:
            start = response.find("[")
            end = response.rfind("]") + 1
            if start >= 0 and end > start:
                return json.loads(response[start:end])
        except json.JSONDecodeError:
            pass

        return []

    async def generate_outline(
        self,
        topic: str,
        available_content: list[str],
    ) -> list[dict[str, Any]]:
        """Generate a comprehensive chapter outline based on available content."""
        content_summary = "\n".join([f"- {c[:200]}..." for c in available_content[:50]])

        system = """You are structuring a comprehensive neurosurgical chapter.
Follow standard neurosurgical textbook format while adapting to available content."""

        prompt = f"""Create a detailed outline for a chapter on: {topic}

Available content summaries (50 knowledge clusters):
{content_summary}

Standard chapter structure to follow:
1. Introduction
2. Historical Background (if relevant)
3. Epidemiology
4. Anatomy and Neuroanatomy
5. Pathophysiology
6. Clinical Presentation
7. Diagnostic Workup
8. Classification (if applicable)
9. Treatment Options (non-surgical)
10. Surgical Indications
11. Surgical Technique
12. Complications and Management
13. Outcomes and Prognosis
14. Controversies and Emerging Trends
15. Conclusions

Return a JSON array of sections. Each section should have:
- "title": Section title
- "level": 1 for main section, 2 for subsection
- "description": What content belongs here
- "expected_clusters": List of content types this section should include

Return ONLY valid JSON array."""

        response = await self.generate(prompt, system=system, temperature=0.2)

        import json

        try:
            start = response.find("[")
            end = response.rfind("]") + 1
            if start >= 0 and end > start:
                return json.loads(response[start:end])
        except json.JSONDecodeError:
            pass

        # Fallback to standard outline
        return [
            {"title": "Introduction", "level": 1, "description": "Overview"},
            {
                "title": "Anatomy",
                "level": 1,
                "description": "Anatomical considerations",
            },
            {
                "title": "Surgical Technique",
                "level": 1,
                "description": "Operative details",
            },
            {"title": "Outcomes", "level": 1, "description": "Results and prognosis"},
        ]

    async def synthesize_section(
        self,
        section_title: str,
        clusters: list[dict[str, str]],
        word_target: int = 1500,
        use_xml_citations: bool = True,
    ) -> str:
        """Synthesize a chapter section from knowledge clusters.

        Args:
            section_title: Title of the section being synthesized
            clusters: List of dicts with 'content', 'source', and optionally 'source_id'
            word_target: Target word count for the section
            use_xml_citations: If True, use XML citation anchoring for traceability

        Returns:
            Synthesized section text, with XML citation tags if enabled
        """
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

        return await self.generate(
            prompt, system=system, temperature=0.3, max_tokens=4096
        )

    async def synthesize_section_with_conflict_preservation(
        self,
        section_title: str,
        clusters: list[dict[str, str]],
        detected_conflicts: list[dict[str, Any]] | None = None,
        word_target: int = 1500,
    ) -> str:
        """Synthesize section with explicit conflict preservation.

        This method ensures conflicting viewpoints are preserved with clear
        attribution rather than being silently resolved or averaged.

        Args:
            section_title: Title of the section
            clusters: Knowledge clusters with content and source info
            detected_conflicts: Pre-detected conflicts from detect_conflicts()
            word_target: Target word count

        Returns:
            Synthesized text with explicit conflict markers
        """
        # Build cluster text
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

        # Format detected conflicts
        conflicts_text = ""
        if detected_conflicts:
            conflict_strs = []
            for c in detected_conflicts:
                perspectives: list[dict] = c.get("perspectives", [])
                persp_str = "; ".join(
                    f"{p.get('source', 'Unknown')}: {p.get('claim', '')}"
                    for p in perspectives
                )
                conflict_strs.append(
                    f"- {c.get('description', 'Conflict')}: {persp_str}"
                )
            conflicts_text = "\n".join(conflict_strs)

        system = """You are writing a section of a neurosurgical textbook chapter.
Write in formal academic medical prose.

CRITICAL REQUIREMENTS FOR MEDICAL INTEGRITY:
1. PRESERVE ALL CONFLICTING DATA - never average or silently resolve conflicts
2. Use XML citation anchoring: <claim source_id="...">statement</claim>
3. Mark conflicts explicitly: <conflict type="quantitative|approach|temporal">
   <perspective source_id="A">claim A</perspective>
   <perspective source_id="B">claim B</perspective>
</conflict>
4. State uncertainty when sources disagree
5. Include evidence levels where available"""

        prompt = f"""Write the "{section_title}" section for a neurosurgical chapter.

Knowledge to incorporate:
{clusters_text}

{"KNOWN CONFLICTS TO PRESERVE:" + conflicts_text if conflicts_text else ""}

Requirements:
- Target length: approximately {word_target} words
- Use <claim source_id="...">...</claim> for all factual statements
- Use <conflict>...</conflict> to explicitly present disagreements
- NEVER silently resolve conflicts - present both viewpoints
- Academic medical writing style
- Precise anatomical and medical terminology

Write the section content now:"""

        return await self.generate(
            prompt, system=system, temperature=0.3, max_tokens=4096
        )

    async def generate_abstract(
        self,
        chapter_content: str,
        topic: str,
    ) -> str:
        """Generate an abstract for the synthesized chapter."""
        system = "You write concise, informative medical abstracts."

        prompt = f"""Write a structured abstract for this neurosurgical chapter on {topic}.

Chapter content (first 10000 chars):
{chapter_content[:10000]}

The abstract should:
- Be 200-300 words
- Cover: Background, Key Points, Conclusions
- Highlight unique or conflicting findings
- Be suitable for a medical textbook

Write the abstract:"""

        return await self.generate(
            prompt, system=system, temperature=0.2, max_tokens=500
        )

    async def extract_keywords(self, chapter_content: str) -> list[str]:
        """Extract relevant medical keywords from the chapter."""
        prompt = f"""Extract 8-12 medical keywords/phrases from this neurosurgical chapter content.

Content:
{chapter_content[:5000]}

Return as a JSON array of strings. Include:
- Anatomical terms
- Pathological terms
- Surgical procedure names
- Key concepts

Return ONLY a JSON array."""

        response = await self.generate(prompt, temperature=0.0, max_tokens=200)

        import json

        try:
            start = response.find("[")
            end = response.rfind("]") + 1
            if start >= 0 and end > start:
                return json.loads(response[start:end])
        except json.JSONDecodeError:
            pass

        return []
