"""
Safety Kernel: Unified Guardrails for NeuroSynth
================================================

This module consolidates all safety, hallucination, and claim verification logic
into a single facade. It routes requests to the appropriate underlying engine
based on the type of check required.

Architecture:
    SafetyKernel (Facade)
        ├── routes 'check_safety' --> DeepDxCritic (Claude Haiku - Fast)
        └── routes 'verify_claims' --> SynthesisVerifier (Gemini - Deep)

Usage:
    kernel = get_safety_kernel()

    # 1. Pre-generation Safety Check (Example: Contraindications)
    is_safe = await kernel.check_safety(query, proposed_answer)

    # 2. Post-generation Hallucination Check
    audit = await kernel.verify_claims(generated_text, source_chunks)
"""

import logging
from typing import Any, Dict, List, Optional

from deep_dx.critic.critic import DeepDxCritic
from neurosynth.config import get_settings
from neurosynth.synthesis.verifier import SynthesisVerifier, VerificationResult

logger = logging.getLogger("ai.safety")


class SafetyKernel:
    """
    Unified Safety and Verification facade.

    Hides the complexity of having two separate validation engines (Claude vs Gemini).
    """

    def __init__(self):
        self.settings = get_settings()

        # Lazy initialization of sub-engines to save resources
        self._critic: DeepDxCritic | None = None
        self._verifier: SynthesisVerifier | None = None

    @property
    def critic(self) -> DeepDxCritic:
        """Get or initialize the DeepDxCritic (Claude-based)."""
        if not self._critic:
            try:
                self._critic = DeepDxCritic()
                logger.debug("SafetyKernel: Initialized DeepDxCritic")
            except Exception as e:
                logger.error(f"SafetyKernel: Failed to init DeepDxCritic: {e}")
                # We might want to raise here or return a dummy if completely critical
                raise e
        return self._critic

    @property
    def verifier(self) -> SynthesisVerifier:
        """Get or initialize the SynthesisVerifier (Gemini-based)."""
        if not self._verifier:
            try:
                self._verifier = SynthesisVerifier(strict_mode=True)
                logger.debug("SafetyKernel: Initialized SynthesisVerifier")
            except Exception as e:
                logger.error(f"SafetyKernel: Failed to init SynthesisVerifier: {e}")
                raise e
        return self._verifier

    async def check_safety(self, query: str, answer: str) -> dict[str, Any]:
        """
        FAST PATH: Check for medical safety violations (contraindications, dosage).
        Uses DeepDxCritic (Claude Haiku).

        Returns:
            {
                "safe": bool,
                "issues": list[str],
                "risk_level": "low"|"medium"|"high"|"critical"
            }
        """
        logger.info(f"🛡️ Safety Check: {query[:50]}...")
        # Use simple sync wrapper or async if available
        # DeepDxCritic has check_safety_async
        return await self.critic.check_safety_async(query, answer)

    async def verify_claims(
        self,
        synthesized_text: str,
        source_chunks: list[dict[str, Any]],
        section_title: str | None = None,
    ) -> VerificationResult:
        """
        DEEP PATH: Check for hallucinations and factual consistency.
        Uses SynthesisVerifier (Gemini).

        Args:
            synthesized_text: The AI-generated text.
            source_chunks: Validated chunks used as ground truth.
        """
        logger.info(f"🕵️ Claim Verification: {section_title or 'Text section'}")
        return await self.verifier.verify(
            synthesized_text, source_chunks, section_title
        )

    async def full_audit(
        self, query: str, answer: str, source_chunks: list[dict[str, Any]]
    ) -> dict[str, Any]:
        """
        Complete Safety Audit: Runs BOTH Safety Check and Claim Verification.
        """
        # Run in parallel for speed?
        # DeepDxCritic is usually fast, Verifier is slow.
        # For now, sequential is safer to reason about.

        # 1. Medical Safety
        safety_result = await self.check_safety(query, answer)
        if not safety_result.get("safe", False):
            return {"passed": False, "stage": "safety", "report": safety_result}

        # 2. Hallucination Check
        verification = await self.verify_claims(answer, source_chunks)

        return {
            "passed": verification.status == "passed",
            "stage": "verification",
            "safety_report": safety_result,
            "verification_report": verification,
            "score": verification.score,
        }


# Singleton instance
_safety_kernel = None


def get_safety_kernel() -> SafetyKernel:
    """Get global SafetyKernel instance."""
    global _safety_kernel
    if _safety_kernel is None:
        _safety_kernel = SafetyKernel()
    return _safety_kernel
