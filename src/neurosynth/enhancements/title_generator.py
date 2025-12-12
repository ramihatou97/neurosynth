"""
Title Generator Enhancement Service
Uses LLM (Claude) to generate precise, professional titles for neurosurgical documents
when metadata titles are generic or low-quality.
"""

from neurosynth import get_logger
from neurosynth.llm.claude import ClaudeClient

logger = get_logger("enhancements.title_generator")


class TitleGenerator:
    """Generates professional titles for documents using LLM analysis of first page."""

    def __init__(self):
        self.client = ClaudeClient()
        logger.info("TitleGenerator service initialized with ClaudeClient")

    async def generate_title(self, first_page_text: str) -> str:
        """
        Analyze the first page text and generate a precise neurosurgical title.

        Args:
            first_page_text: The extracted text from the first page of the PDF.

        Returns:
            A clean, specific title string (max 20 words).
        """
        if not first_page_text or len(first_page_text.strip()) < 50:
            logger.warning("First page text insufficient for title generation")
            return "Unknown Document"

        system_prompt = (
            "You are an expert neurosurgical librarian and editor. "
            "Your task is to identify the precise clinical or matching title of a document based on its first page."
        )

        user_prompt = f"""Analyze the following first page content of a neurosurgical document.
Generate a concise, professional title that accurately reflects the specific clinical topic, procedure, or anatomical region described.

CRITICAL RULES FOR "METICULOUS" PRECISION:
1. Be specific (e.g., "Retrosigmoid Approach to Acoustic Neuroma" NOT just "Skull Base Surgery").
2. Ignore generic headers/footers like "Presentation", "Slide 1", "Chapter 4", "Volume X", "Downloaded from...".
3. If it looks like a book chapter, format as: "Topic Name" (ignore "Chapter N").
4. If it looks like a slide deck, extract the main presentation topic.
5. Return ONLY the title string. No quotes. No "The title is...".
6. Maximum 20 words.

First Page Content:
-------------------
{first_page_text[:3000]}
-------------------

Title:"""

        try:
            # high temperature 0.0 for deterministic extraction
            title = await self.client.generate(
                prompt=user_prompt,
                system=system_prompt,
                temperature=0.0,
                max_tokens=60,
            )
            title = title.strip().strip('"').strip("'")
            # Fallback if LLM returns something weirdly long or empty
            if len(title) > 200:
                logger.warning(
                    f"Generated title too long ({len(title)} chars), truncating"
                )
                title = title[:200]

            logger.info(f"Generated title: '{title}'")
            return title

        except Exception as e:
            logger.error(f"Failed to generate title: {e}")
            return "Unknown Title"
