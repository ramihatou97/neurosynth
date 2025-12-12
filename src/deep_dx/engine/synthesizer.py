import logging
from typing import List, Optional, Union

from ai.client import AIClient, AsyncAIClient
from deep_dx.config import get_deepdx_settings
from deep_dx.critic.critic import DeepDxCritic
from index.precision_search import PrecisionSearchEngine
from models import ChunkType

logger = logging.getLogger(__name__)


class DeepDxSynthesizer:
    """
    Synthesizer for answering specific clinical queries (QA mode).
    This complements the chapter-based SynthesisEngine.

    Supports both sync (AIClient) and async (AsyncAIClient) modes.
    """

    def __init__(
        self,
        search_engine: PrecisionSearchEngine,
        ai_client: AIClient | AsyncAIClient,
        critic: DeepDxCritic | None = None,
    ):
        self.search_engine = search_engine
        self.ai = ai_client
        self.critic = critic
        self._is_async = isinstance(ai_client, AsyncAIClient)

    async def generate_answer_async(self, query: str) -> dict:
        """
        Generate an answer for a specific query (async non-blocking version).

        Returns:
            Dict containing:
            - answer: str
            - sources: List[str]
            - confidence: float
            - context_used: List[str]
        """
        logger.info(f"🧠 Synthesizing answer for: {query[:50]}...")

        # 0. Query Expansion
        expanded_query = query
        try:
            expansion_prompt = f"""Identify 2-3 key medical synonyms or related terms for the core concepts in this query.
Query: {query}
Output ONLY the synonyms separated by spaces. Do not explain."""
            synonyms = await self.ai.synthesize(
                expansion_prompt,
                max_tokens=50,
                system_prompt="You are a medical terminologist.",
            )
            if synonyms and len(synonyms) < 100:
                expanded_query = f"{query} {synonyms}"
                logger.debug(f"  ✨ Expanded Query: {expanded_query}")
        except Exception as e:
            logger.warning(f"  ⚠️ Expansion failed: {e}")

        # 1. Embed Query (async)
        query_embedding = await self.ai.get_embedding(query)

        # 2. Retrieval (sync - search engine not yet async)
        settings = get_deepdx_settings()
        retrieval_result = self.search_engine.retrieve_for_topic(
            query_embedding=query_embedding,
            topic=expanded_query,
            top_k=settings.retrieval_top_k,
            include_images=True,
        )

        results = retrieval_result.results
        images = retrieval_result.images
        if not results:
            return {
                "answer": "I do not have enough information to answer this question.",
                "sources": [],
                "confidence": 0.0,
                "context_used": [],
            }

        # 3. Format Context
        context_texts = []
        sources_meta = []
        for res in results:
            chunk = res.chunk
            text = (
                f"[Source: {chunk.source_title}, p.{chunk.page_start}]: {chunk.content}"
            )
            context_texts.append(text)
            sources_meta.append(chunk.source_title)

        context_block = "\n\n".join(context_texts)

        # 4. Synthesize Answer (async)
        prompt = f"""You are a neurosurgical expert system. Answer the following query using ONLY the provided sources.

Query: {query}

SOURCES:
{context_block}

INSTRUCTIONS:
1. **Accuracy**: Answer clearly and concisely. Do not waffle.
2. **Safety**: Explicitly state any CONTRAINDICATIONS or "NEVER" events mentioned (e.g., "Do not X without Y").
3. **Anatomy**: If asked about landmarks, list specific structures (nerves, vessels, muscles, bones) and their relationships (medial/lateral/anterior).
4. **Citations**: Cite sources in [Source, p.X] format.
5. **Honesty**: If the sources do not contain the answer, state "I do not have enough information found in the sources."
6. **Conflict**: If sources contradict, note the conflict."""

        answer = await self.ai.synthesize(
            prompt=prompt,
            system_prompt="You are a precise neurosurgical assistant. Prioritize safety warnings and anatomical precision.",
            max_tokens=1024,
        )

        # 5. Critic Verification (async)
        confidence = 1.0
        if self.critic:
            logger.info("  🕵️‍♀️ Critic reviewing answer...")
            safety_result = await self.critic.check_safety_async(query, answer)

            if not safety_result.get("safe", True):
                issues = safety_result.get("issues", ["Unspecified safety concern"])
                warning_msg = f"\n\n🚨 **SAFETY WARNING**: The System Critic flagged this answer as potentially unsafe: {'; '.join(issues)}"
                answer += warning_msg
                confidence = 0.0
                logger.warning(f"  ⚠️ Answer flagged unsafe: {issues}")
            else:
                logger.info("  ✅ Critic approved safety.")

        return {
            "answer": answer,
            "sources": list(set(sources_meta)),
            "confidence": confidence,
            "context_used": context_texts,
            "images": images,
        }

    def generate_answer(self, query: str) -> dict:
        """
        Generate an answer for a specific query.

        Returns:
            Dict containing:
            - answer: str
            - sources: List[str]
            - confidence: float
            - context_used: List[str]
        """
        logger.info(f"🧠 Synthesizing answer for: {query[:50]}...")

        # 0. Query Expansion (Broad Domain Optimization)
        # We expand the query with synonyms to catch domain variations (e.g. VS vs Acoustic Neuroma)
        expanded_query = query
        try:
            # Fast synonym expansion
            expansion_prompt = f"""Identify 2-3 key medical synonyms or related terms for the core concepts in this query.
Query: {query}
Output ONLY the synonyms separated by spaces. Do not explain."""
            synonyms = self.ai.synthesize(
                expansion_prompt,
                max_tokens=50,
                system_prompt="You are a medical terminologist.",
            )
            if synonyms and len(synonyms) < 100:  # Sanity check
                expanded_query = f"{query} {synonyms}"
                logger.debug(f"  ✨ Expanded Query: {expanded_query}")
        except Exception as e:
            logger.warning(f"  ⚠️ Expansion failed: {e}")

        # 1. Embed Query
        query_embedding = self.ai.get_embedding(
            query
        )  # Use original query for embedding usually better, or expanded?
        # Actually for Dense, original is often better. For BM25, expanded is better.
        # Let's pass expanded_query to search engine if we want hybrid benefits.

        # 2. Retrieval (Precision Search)
        # We need chunks relevant to the query.

        # Get settings locally
        settings = get_deepdx_settings()

        retrieval_result = self.search_engine.retrieve_for_topic(
            query_embedding=query_embedding,
            topic=expanded_query,  # Use expanded for retrieval keywords
            top_k=settings.retrieval_top_k,
            include_images=True,
        )

        results = retrieval_result.results
        images = retrieval_result.images
        if not results:
            return {
                "answer": "I do not have enough information to answer this question.",
                "sources": [],
                "confidence": 0.0,
                "context_used": [],
            }

        # 3. Format Context
        context_texts = []
        sources_meta = []
        for res in results:
            # res is SearchResult(chunk=..., score=...)
            chunk = res.chunk
            text = (
                f"[Source: {chunk.source_title}, p.{chunk.page_start}]: {chunk.content}"
            )
            context_texts.append(text)
            sources_meta.append(chunk.source_title)

        context_block = "\n\n".join(context_texts)

        # 4. Synthesize Answer
        prompt = f"""You are a neurosurgical expert system. Answer the following query using ONLY the provided sources.

Query: {query}

SOURCES:
{context_block}

INSTRUCTIONS:
1. **Accuracy**: Answer clearly and concisely. Do not waffle.
2. **Safety**: Explicitly state any CONTRAINDICATIONS or "NEVER" events mentioned (e.g., "Do not X without Y").
3. **Anatomy**: If asked about landmarks, list specific structures (nerves, vessels, muscles, bones) and their relationships (medial/lateral/anterior).
4. **Citations**: Cite sources in [Source, p.X] format.
5. **Honesty**: If the sources do not contain the answer, state "I do not have enough information found in the sources."
6. **Conflict**: If sources contradict, note the conflict."""

        answer = self.ai.synthesize(
            prompt=prompt,
            system_prompt="You are a precise neurosurgical assistant. Prioritize safety warnings and anatomical precision.",
            max_tokens=1024,
        )

        # 5. Critic Verification
        confidence = 1.0  # Default
        if self.critic:
            logger.info("  🕵️‍♀️ Critic reviewing answer...")
            safety_result = self.critic.check_safety(query, answer)

            if not safety_result.get("safe", True):
                issues = safety_result.get("issues", ["Unspecified safety concern"])
                warning_msg = f"\n\n🚨 **SAFETY WARNING**: The System Critic flagged this answer as potentially unsafe: {'; '.join(issues)}"
                answer += warning_msg
                confidence = 0.0
                logger.warning(f"  ⚠️ Answer flagged unsafe: {issues}")
            else:
                logger.info("  ✅ Critic approved safety.")

        return {
            "answer": answer,
            "sources": list(set(sources_meta)),
            "confidence": confidence,
            "context_used": context_texts,
            "images": images,
        }
