"""
Deep-Dx Critic Module
Responsible for validating retrieval relevance and ensuring answer safety.

Supports both sync and async modes for GUI integration.
"""

import json
import logging
from typing import Any, Optional

import httpx
from anthropic import Anthropic

from deep_dx.config import get_deepdx_settings
from neurosynth.config import get_settings as get_neurosynth_settings

logger = logging.getLogger(__name__)

# Anthropic API endpoint
ANTHROPIC_API_URL = "https://api.anthropic.com/v1/messages"


class DeepDxCritic:
    """
    The Critic uses LLM-based verification to ensure:
    1. Retrieval Relevance: Are the chunks actually related to the query?
    2. Safety: Is the generated answer medically safe?

    Supports both sync (using Anthropic SDK) and async (using httpx) modes.
    """

    def __init__(self, async_client: Optional[httpx.AsyncClient] = None):
        self.settings = get_deepdx_settings()
        self.ns_settings = get_neurosynth_settings()

        if not self.ns_settings.anthropic_api_key:
            raise ValueError(
                "Anthropic API Key incorrectly configured (check valid .env or NeuroSynth config)."
            )

        self._api_key = self.ns_settings.anthropic_api_key
        self.client = Anthropic(api_key=self._api_key)
        # We use a fast model for the Critic to keep latency low
        self.model = "claude-3-haiku-20240307"

        # Async client for non-blocking operations
        self._async_client = async_client
        self._owns_client = False

    async def _get_async_client(self) -> httpx.AsyncClient:
        """Get or create async HTTP client."""
        if self._async_client is None:
            self._async_client = httpx.AsyncClient(timeout=60.0)
            self._owns_client = True
        return self._async_client

    async def close(self):
        """Close async client if we own it."""
        if self._owns_client and self._async_client:
            await self._async_client.aclose()
            self._async_client = None

    def evaluate_relevance(
        self, query: str, chunks: list[dict], threshold: int = 7
    ) -> list[dict]:
        """
        Scoring each chunk 0-10 on relevance to the query.
        Returns only chunks meeting the threshold.
        """
        if not chunks:
            return []

        # We can batch this for efficiency or do one-by-one.
        # For granular control, we'll do a focused prompt for the batch.

        candidates_text = ""
        for i, c in enumerate(chunks):
            candidates_text += (
                f"<chunk_id={i}>\n{c.get('text', '')[:500]}...\n</chunk_id={i}>\n\n"
            )

        prompt = f"""You are a strict relevance filter for a neurosurgery RAG system.
QUERY: {query}

CANDIDATE CHUNKS:
{candidates_text}

TASK:
Score each chunk from 0-10 based on how helpful it is for answering the query.
0 = Irrelevant / Noise
5 = Tangentially related / General context
10 = Perfectly specific exact answer

OUTPUT FORMAT (JSON List):
[
    {{"id": 0, "score": 8, "reason": "Specific mention of procedure"}},
    ...
]
"""

        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=1000,
                messages=[{"role": "user", "content": prompt}],
            )

            content = response.content[0].text
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0]
            elif "```" in content:  # Handle generic code block
                content = content.split("```")[1].split("```")[0]

            scores = json.loads(content)

            # Filter and map back to original chunks
            relevant_chunks = []
            for s in scores:
                try:
                    idx = int(s["id"])
                    score = int(s["score"])
                    if score >= threshold and idx < len(chunks):
                        chunk = chunks[idx]
                        chunk["relevance_score"] = score
                        chunk["relevance_reason"] = s.get("reason", "")
                        relevant_chunks.append(chunk)
                except (ValueError, IndexError):
                    continue

            # Sort by score desc
            relevant_chunks.sort(key=lambda x: x["relevance_score"], reverse=True)
            return relevant_chunks

        except Exception as e:
            logger.warning(f"⚠️ Critic Relevance Error: {e}")
            # Fallback: return top 3 chunks without filtering if critic fails
            return chunks[:3]

    def check_safety(self, query: str, answer: str) -> dict[str, Any]:
        """
        Evaluates the generated answer for medical safety issues.
        Returns a dict with 'safe' (bool) and 'issues' (list).
        """
        prompt = f"""You are a Senior Neurosurgical Safety Officer.
Validate the following answer for SAFETY ERRORS.

QUERY: {query}
PROPOSED ANSWER: {answer}

SAFETY RULES:
1. No fatal dosage errors.
2. No recommendation of contraindicated procedures.
3. No confusion of laterality (left vs right).
4. No hallucination of non-existent anatomy.

TASK:
Determine if the answer is SAFE or UNSAFE.
If UNSAFE, explain why.
If SAFE, just confirm.

OUTPUT FORMAT (JSON):
{{
    "safe": boolean,
    "issues": ["List of specific safety violations if any"],
    "risk_level": "low"|"medium"|"high"|"critical"
}}
"""

        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=500,
                messages=[{"role": "user", "content": prompt}],
            )

            content = response.content[0].text.strip()

            # Helper to extract JSON
            if "```json" in content:
                json_str = content.split("```json")[1].split("```")[0]
            elif "```" in content:
                json_str = content.split("```")[1].split("```")[0]
            else:
                json_str = content

            try:
                result = json.loads(json_str)
                return result
            except json.JSONDecodeError:
                # Last ditch effort: find { and }
                if "{" in content and "}" in content:
                    json_str = content[content.find("{") : content.rfind("}") + 1]
                    return json.loads(json_str)
                raise

        except Exception as e:
            logger.warning(f"⚠️ Critic Safety Error: {e}")
            # Fail closed (assume unsafe if we can't verify)?
            # Or fail open but warn? For Phase 2, we return a warning.
            return {
                "safe": False,
                "issues": [f"Critic failed to validate: {e}"],
                "risk_level": "unknown",
            }

    async def check_safety_async(self, query: str, answer: str) -> dict[str, Any]:
        """
        Async version: Evaluates the generated answer for medical safety issues.
        Returns a dict with 'safe' (bool) and 'issues' (list).
        """
        prompt = f"""You are a Senior Neurosurgical Safety Officer.
Validate the following answer for SAFETY ERRORS.

QUERY: {query}
PROPOSED ANSWER: {answer}

SAFETY RULES:
1. No fatal dosage errors.
2. No recommendation of contraindicated procedures.
3. No confusion of laterality (left vs right).
4. No hallucination of non-existent anatomy.

TASK:
Determine if the answer is SAFE or UNSAFE.
If UNSAFE, explain why.
If SAFE, just confirm.

OUTPUT FORMAT (JSON):
{{
    "safe": boolean,
    "issues": ["List of specific safety violations if any"],
    "risk_level": "low"|"medium"|"high"|"critical"
}}
"""

        try:
            client = await self._get_async_client()

            headers = {
                "x-api-key": self._api_key,
                "anthropic-version": "2023-06-01",
                "Content-Type": "application/json",
            }

            payload = {
                "model": self.model,
                "max_tokens": 500,
                "messages": [{"role": "user", "content": prompt}],
            }

            logger.debug(f"Critic checking safety for query: {query[:50]}...")
            response = await client.post(
                ANTHROPIC_API_URL, headers=headers, json=payload
            )
            response.raise_for_status()
            data = response.json()

            content = data["content"][0]["text"].strip()

            # Helper to extract JSON
            if "```json" in content:
                json_str = content.split("```json")[1].split("```")[0]
            elif "```" in content:
                json_str = content.split("```")[1].split("```")[0]
            else:
                json_str = content

            try:
                result = json.loads(json_str)
                logger.debug(f"Critic result: safe={result.get('safe')}")
                return result
            except json.JSONDecodeError:
                # Last ditch effort: find { and }
                if "{" in content and "}" in content:
                    json_str = content[content.find("{") : content.rfind("}") + 1]
                    return json.loads(json_str)
                raise

        except Exception as e:
            logger.warning(f"⚠️ Critic Safety Error: {e}")
            return {
                "safe": False,
                "issues": [f"Critic failed to validate: {e}"],
                "risk_level": "unknown",
            }

    async def evaluate_relevance_async(
        self, query: str, chunks: list[dict], threshold: int = 7
    ) -> list[dict]:
        """
        Async version: Scoring each chunk 0-10 on relevance to the query.
        Returns only chunks meeting the threshold.
        """
        if not chunks:
            return []

        candidates_text = ""
        for i, c in enumerate(chunks):
            candidates_text += (
                f"<chunk_id={i}>\n{c.get('text', '')[:500]}...\n</chunk_id={i}>\n\n"
            )

        prompt = f"""You are a strict relevance filter for a neurosurgery RAG system.
QUERY: {query}

CANDIDATE CHUNKS:
{candidates_text}

TASK:
Score each chunk from 0-10 based on how helpful it is for answering the query.
0 = Irrelevant / Noise
5 = Tangentially related / General context
10 = Perfectly specific exact answer

OUTPUT FORMAT (JSON List):
[
    {{"id": 0, "score": 8, "reason": "Specific mention of procedure"}},
    ...
]
"""

        try:
            client = await self._get_async_client()

            headers = {
                "x-api-key": self._api_key,
                "anthropic-version": "2023-06-01",
                "Content-Type": "application/json",
            }

            payload = {
                "model": self.model,
                "max_tokens": 1000,
                "messages": [{"role": "user", "content": prompt}],
            }

            response = await client.post(
                ANTHROPIC_API_URL, headers=headers, json=payload
            )
            response.raise_for_status()
            data = response.json()

            content = data["content"][0]["text"]
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0]
            elif "```" in content:
                content = content.split("```")[1].split("```")[0]

            scores = json.loads(content)

            # Filter and map back to original chunks
            relevant_chunks = []
            for s in scores:
                try:
                    idx = int(s["id"])
                    score = int(s["score"])
                    if score >= threshold and idx < len(chunks):
                        chunk = chunks[idx]
                        chunk["relevance_score"] = score
                        chunk["relevance_reason"] = s.get("reason", "")
                        relevant_chunks.append(chunk)
                except (ValueError, IndexError):
                    continue

            # Sort by score desc
            relevant_chunks.sort(key=lambda x: x["relevance_score"], reverse=True)
            return relevant_chunks

        except Exception as e:
            logger.warning(f"⚠️ Critic Relevance Error: {e}")
            # Fallback: return top 3 chunks without filtering if critic fails
            return chunks[:3]
