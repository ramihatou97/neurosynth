"""Synthesis verification using Gemini.

This module provides post-synthesis verification to ensure:
1. All source claims are accurately represented
2. No hallucinated content has been introduced
3. Conflicts are properly preserved (not silently resolved)
4. Medical accuracy is maintained

The verifier uses Gemini (different from Claude used for synthesis)
as a cross-check to catch potential issues.
"""

import json
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, cast

from rich.console import Console

from neurosynth import get_logger
from neurosynth.config import get_settings

console = Console()
logger = get_logger("synthesis.verifier")


class VerificationStatus(str, Enum):
    """Status of verification check."""

    PASSED = "passed"
    WARNING = "warning"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class VerificationIssue:
    """A single verification issue found."""

    category: str  # "hallucination", "misrepresentation", "conflict_resolved", "missing_claim"
    severity: str  # "high", "medium", "low"
    description: str
    source_text: str | None = None
    synthesized_text: str | None = None
    suggestion: str | None = None


@dataclass
class VerificationResult:
    """Result of synthesis verification."""

    status: VerificationStatus
    score: float  # 0.0 to 1.0
    issues: list[VerificationIssue] = field(default_factory=list)
    checks_passed: list[str] = field(default_factory=list)
    checks_failed: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


class SynthesisVerifier:
    """Verify synthesized content against source material using Gemini.

    Uses a different model (Gemini) than synthesis (Claude) to provide
    independent verification and catch potential issues.
    """

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        strict_mode: bool = True,
    ):
        """Initialize the verifier.

        Args:
            api_key: Google API key (uses settings if not provided)
            model: Gemini model to use (uses settings if not provided)
            strict_mode: If True, fail on any high-severity issues
        """
        settings = get_settings()
        self.api_key = api_key or settings.google_api_key
        self.model_name = model or settings.gemini_model
        self.strict_mode = strict_mode

        # Import Gemini client
        try:
            import google.generativeai as genai

            genai.configure(api_key=self.api_key)
            self.model = genai.GenerativeModel(self.model_name)
            self.available = True
            logger.info(f"Initialized SynthesisVerifier with model: {self.model_name}")
        except ImportError:
            logger.warning("google-generativeai not installed. Verification disabled.")
            self.model = None
            self.available = False

    async def verify(
        self,
        synthesized_text: str,
        source_chunks: list[dict[str, Any]],
        section_title: str | None = None,
    ) -> VerificationResult:
        """Verify synthesized content against source material.

        Args:
            synthesized_text: The synthesized section text
            source_chunks: Original source chunks used for synthesis
            section_title: Optional section title for context

        Returns:
            VerificationResult with status, score, and any issues
        """
        if not self.available:
            return VerificationResult(
                status=VerificationStatus.SKIPPED,
                score=0.0,
                metadata={"reason": "Gemini not available"},
            )

        issues = []

        # Run verification checks
        check_results = await self._run_verification_checks(
            synthesized_text, source_chunks, section_title
        )

        issues.extend(check_results.get("issues", []))

        # Calculate score and status
        high_severity = sum(1 for i in issues if i.severity == "high")
        medium_severity = sum(1 for i in issues if i.severity == "medium")
        low_severity = sum(1 for i in issues if i.severity == "low")

        # Scoring: high = -0.3, medium = -0.1, low = -0.02
        score = max(
            0.0,
            1.0
            - (high_severity * 0.3)
            - (medium_severity * 0.1)
            - (low_severity * 0.02),
        )

        # Determine status
        if high_severity > 0:
            status = (
                VerificationStatus.FAILED
                if self.strict_mode
                else VerificationStatus.WARNING
            )
        elif medium_severity > 2:
            status = VerificationStatus.WARNING
        else:
            status = VerificationStatus.PASSED

        return VerificationResult(
            status=status,
            score=score,
            issues=issues,
            checks_passed=check_results.get("passed", []),
            checks_failed=check_results.get("failed", []),
            metadata={
                "section_title": section_title,
                "source_count": len(source_chunks),
                "synthesis_length": len(synthesized_text),
            },
        )

    async def _run_verification_checks(
        self,
        synthesized_text: str,
        source_chunks: list[dict[str, Any]],
        section_title: str | None,
    ) -> dict[str, Any]:
        """Run all verification checks."""
        # Build source context
        source_text = "\n\n---\n\n".join(
            f"[SOURCE {i+1}: {c.get('source', 'Unknown')}]\n{c.get('content', '')}"
            for i, c in enumerate(source_chunks)
        )

        prompt = f"""You are a medical content verifier. Compare synthesized content against original sources.

SYNTHESIZED TEXT:
{synthesized_text}

ORIGINAL SOURCE MATERIAL:
{source_text}

Analyze the synthesized text and identify any issues:

1. HALLUCINATIONS: Claims in synthesis not supported by any source
2. MISREPRESENTATIONS: Claims that distort or misrepresent source material
3. SILENT CONFLICT RESOLUTION: Where sources disagreed but synthesis presents only one view
4. MISSING KEY CLAIMS: Important claims from sources not included in synthesis

Return a JSON object with:
{{
    "issues": [
        {{
            "category": "hallucination|misrepresentation|conflict_resolved|missing_claim",
            "severity": "high|medium|low",
            "description": "Description of the issue",
            "source_text": "Relevant source text (if applicable)",
            "synthesized_text": "Problematic synthesized text (if applicable)",
            "suggestion": "How to fix (optional)"
        }}
    ],
    "passed": ["List of verification aspects that passed"],
    "failed": ["List of verification aspects that failed"],
    "overall_assessment": "Brief overall assessment"
}}

Be thorough but fair. Minor wording differences are acceptable. Focus on:
- Factual accuracy (especially numbers, percentages, measurements)
- Proper attribution of conflicting claims
- Completeness of key medical information

Return ONLY valid JSON."""

        try:
            import asyncio

            # Run in executor since genai is sync
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: self.model.generate_content(prompt).text,
            )

            # Parse JSON response
            result = self._parse_verification_response(response)
            return result

        except Exception as e:
            logger.error(f"Verification failed: {e}")
            return {
                "issues": [
                    VerificationIssue(
                        category="error",
                        severity="low",
                        description=f"Verification error: {e}",
                    )
                ],
                "passed": [],
                "failed": ["verification_execution"],
            }

    def _parse_verification_response(self, response: str) -> dict[str, Any]:
        """Parse the JSON response from Gemini."""
        try:
            # Find JSON in response
            start = response.find("{")
            end = response.rfind("}") + 1
            if start >= 0 and end > start:
                data = json.loads(response[start:end])

                # Convert issue dicts to VerificationIssue objects
                issues = []
                for issue_data in data.get("issues", []):
                    issues.append(
                        VerificationIssue(
                            category=issue_data.get("category", "unknown"),
                            severity=issue_data.get("severity", "low"),
                            description=issue_data.get("description", ""),
                            source_text=issue_data.get("source_text"),
                            synthesized_text=issue_data.get("synthesized_text"),
                            suggestion=issue_data.get("suggestion"),
                        )
                    )

                return {
                    "issues": issues,
                    "passed": data.get("passed", []),
                    "failed": data.get("failed", []),
                }
        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse verification response: {e}")

        return {"issues": [], "passed": [], "failed": []}

    async def verify_citations(
        self,
        synthesized_text: str,
        source_chunks: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Verify that citations in synthesized text match source claims.

        Args:
            synthesized_text: Text with citation tags
            source_chunks: Original source material

        Returns:
            Dict with citation verification results
        """
        # Extract citations from synthesized text
        claim_pattern = re.compile(
            r'<claim\s+source_id=["\']([^"\']+)["\']>(.*?)</claim>',
            re.DOTALL,
        )
        claims = claim_pattern.findall(synthesized_text)

        results: dict[str, int | list[dict]] = {
            "total_citations": len(claims),
            "verified": 0,
            "unverified": 0,
            "issues": [],
        }

        # Build source index
        source_index = {}
        for chunk in source_chunks:
            source_id = chunk.get("source_id", "")
            if source_id:
                source_index[source_id] = chunk.get("content", "")

        for source_id, claim_text in claims:
            if source_id in source_index:
                # Check if claim is supported by source
                source_content = source_index[source_id].lower()
                claim_lower = claim_text.lower().strip()

                # Simple keyword overlap check (could be made more sophisticated)
                claim_words = set(claim_lower.split())
                source_words = set(source_content.split())
                overlap = (
                    len(claim_words & source_words) / len(claim_words)
                    if claim_words
                    else 0
                )

                if overlap > 0.3:  # At least 30% word overlap
                    results["verified"] = cast(int, results["verified"]) + 1
                else:
                    results["unverified"] = cast(int, results["unverified"]) + 1
                    cast(list, results["issues"]).append(
                        {
                            "source_id": source_id,
                            "claim": claim_text[:100],
                            "issue": "Low overlap with source content",
                        }
                    )
            else:
                results["unverified"] = cast(int, results["unverified"]) + 1
                cast(list, results["issues"]).append(
                    {
                        "source_id": source_id,
                        "claim": claim_text[:100],
                        "issue": "Source ID not found in provided chunks",
                    }
                )

        return results


def get_verifier() -> SynthesisVerifier:
    """Get a configured SynthesisVerifier instance."""
    settings = get_settings()
    return SynthesisVerifier(strict_mode=settings.enable_verification)


async def verify_synthesis(
    synthesized_text: str,
    source_chunks: list[dict[str, Any]],
    section_title: str | None = None,
) -> VerificationResult:
    """Convenience function to verify synthesized content.

    Args:
        synthesized_text: The synthesized text to verify
        source_chunks: Original source material
        section_title: Optional section title

    Returns:
        VerificationResult
    """
    verifier = get_verifier()
    return await verifier.verify(synthesized_text, source_chunks, section_title)
