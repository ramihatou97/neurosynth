"""AI-powered content categorization using Claude API."""
import json
import asyncio
from typing import Optional, Callable
from concurrent.futures import ThreadPoolExecutor
import anthropic

from .prompts import CATEGORIZATION_PROMPT
from .category_model import CategoryResult
from ..search.result_model import SearchResult
from ..cache.database import Database
from src import config


class ContentCategorizer:
    """Categorize search results using Claude API."""

    def __init__(self, api_key: str, database: Database):
        self.api_key = api_key
        self.database = database
        self.client = None
        self._init_client()

    def _init_client(self):
        """Initialize Anthropic client."""
        if self.api_key:
            self.client = anthropic.Anthropic(api_key=self.api_key)

    def categorize_result(self, result: SearchResult, search_term: str) -> CategoryResult:
        """Categorize a single search result, using cache if available."""
        # Check cache first
        context_hash = self.database.compute_context_hash(search_term, result.context)
        cached = self.database.get_cached_categorization(context_hash)

        if cached:
            return CategoryResult(
                group=cached["group"],
                category=cached["category"],
                confidence=cached["confidence"],
                reasoning=cached["reasoning"],
                cached=True
            )

        # Call Claude API
        if not self.client:
            return CategoryResult(
                group="Theoretical",
                category="Other",
                confidence=0.0,
                reasoning="API key not configured",
                cached=False
            )

        try:
            prompt = CATEGORIZATION_PROMPT.format(
                search_term=search_term,
                book_title=result.book_title,
                chapter_title=result.chapter_title,
                page_number=result.page_number,
                context=result.context
            )

            response = self.client.messages.create(
                model=config.AI_MODEL,
                max_tokens=config.AI_MAX_TOKENS,
                messages=[{"role": "user", "content": prompt}]
            )

            # Parse JSON response
            response_text = response.content[0].text.strip()

            # Handle potential JSON wrapped in code blocks
            if response_text.startswith("```"):
                response_text = response_text.split("```")[1]
                if response_text.startswith("json"):
                    response_text = response_text[4:]

            data = json.loads(response_text)

            # Parse hierarchical response
            group = data.get("group", "Theoretical")
            category = data.get("category", "Other")
            confidence = float(data.get("confidence", 0.5))
            reasoning = data.get("reasoning", "")

            # Validate group
            if group not in config.CATEGORY_GROUPS:
                group = "Theoretical"

            # Validate category against group's subcategories
            if category not in config.CATEGORIES:
                category = "Other"

            # Ensure group matches category (derive from CATEGORY_TO_GROUP if mismatch)
            expected_group = config.CATEGORY_TO_GROUP.get(category, "Theoretical")
            if category != "Other" and group != expected_group:
                group = expected_group

            # Cache the result
            self.database.cache_categorization(
                context_hash, search_term, group, category, confidence, reasoning
            )

            return CategoryResult(
                group=group,
                category=category,
                confidence=confidence,
                reasoning=reasoning,
                cached=False
            )

        except json.JSONDecodeError:
            # Don't log the actual response content - may contain sensitive data
            print("Categorization failed: invalid JSON response")
            return CategoryResult(
                group="Theoretical",
                category="Other",
                confidence=0.0,
                reasoning="Failed to parse AI response",
                cached=False
            )
        except anthropic.RateLimitError:
            print("Categorization failed: rate limit exceeded")
            return CategoryResult(
                group="Theoretical",
                category="Other",
                confidence=0.0,
                reasoning="Service temporarily unavailable",
                cached=False
            )
        except anthropic.AuthenticationError:
            # Don't expose that it's an auth error - could reveal API key issues
            print("Categorization failed: authentication error")
            return CategoryResult(
                group="Theoretical",
                category="Other",
                confidence=0.0,
                reasoning="Service configuration error",
                cached=False
            )
        except anthropic.APIError:
            # Generic API error - don't expose error details
            print("Categorization failed: API error")
            return CategoryResult(
                group="Theoretical",
                category="Other",
                confidence=0.0,
                reasoning="AI service unavailable",
                cached=False
            )
        except Exception as e:
            # Log only the exception type, not the message which may contain sensitive data
            print(f"Categorization failed: {type(e).__name__}")
            return CategoryResult(
                group="Theoretical",
                category="Other",
                confidence=0.0,
                reasoning="Categorization service error",
                cached=False
            )

    def categorize_result_async(
        self,
        result: SearchResult,
        search_term: str,
        callback: Callable[[SearchResult, CategoryResult], None]
    ):
        """Categorize in background thread, call callback when done."""
        def _categorize():
            cat_result = self.categorize_result(result, search_term)
            callback(result, cat_result)

        executor = ThreadPoolExecutor(max_workers=1)
        executor.submit(_categorize)

    def categorize_batch(
        self,
        results: list[SearchResult],
        search_term: str,
        progress_callback: Optional[Callable[[int, int], None]] = None
    ) -> list[tuple[SearchResult, CategoryResult]]:
        """Categorize multiple results with progress tracking."""
        categorized = []
        total = len(results)

        for i, result in enumerate(results):
            cat_result = self.categorize_result(result, search_term)
            categorized.append((result, cat_result))

            if progress_callback:
                progress_callback(i + 1, total)

        return categorized


class AsyncCategorizer:
    """Async wrapper for categorization with rate limiting."""

    def __init__(self, categorizer: ContentCategorizer, max_concurrent: int = 3):
        self.categorizer = categorizer
        self.max_concurrent = max_concurrent
        self.semaphore = asyncio.Semaphore(max_concurrent)
        self._cancelled = False

    def cancel(self):
        """Cancel ongoing categorization."""
        self._cancelled = True

    def reset(self):
        """Reset cancellation flag."""
        self._cancelled = False

    async def categorize_result(self, result: SearchResult, search_term: str) -> CategoryResult:
        """Categorize with rate limiting."""
        async with self.semaphore:
            if self._cancelled:
                return CategoryResult("Other", 0.0, "Cancelled", False)

            # Run in thread pool to not block
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(
                None,
                self.categorizer.categorize_result,
                result,
                search_term
            )

    async def categorize_all(
        self,
        results: list[SearchResult],
        search_term: str,
        result_callback: Optional[Callable[[SearchResult, CategoryResult], None]] = None
    ) -> list[tuple[SearchResult, CategoryResult]]:
        """Categorize all results concurrently with rate limiting."""
        self.reset()

        async def _categorize_one(result: SearchResult):
            cat_result = await self.categorize_result(result, search_term)
            if result_callback:
                result_callback(result, cat_result)
            return (result, cat_result)

        tasks = [_categorize_one(r) for r in results]
        return await asyncio.gather(*tasks)
