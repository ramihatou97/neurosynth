"""Query intent classification for neurosurgical searches.

This module determines whether a user's search query is looking for:
- Surgical/procedural content (operative techniques, approaches)
- Clinical/theoretical content (disease knowledge, diagnosis, management)
- Mixed content (both types)
"""

import json
from typing import Optional, Literal
from dataclasses import dataclass
import anthropic

from src import config


IntentType = Literal["SURGICAL_TECHNIQUE", "CLINICAL_KNOWLEDGE", "MIXED"]


@dataclass
class QueryIntent:
    """Result of query intent classification."""
    intent: IntentType
    confidence: float
    reasoning: str
    cached: bool = False


QUERY_INTENT_PROMPT = """You are a neurosurgical search intent analyzer. Determine what type of content the user is seeking.

Query: "{query}"

INTENT TYPES:

1. SURGICAL_TECHNIQUE - User wants operative steps, approaches, technical details
   Indicators:
   - Action verbs: "how to", "technique for", "approach to"
   - Procedural terms: "resection", "clipping", "fusion", "decompression"
   - Anatomical approach terms: "retrosigmoid", "pterional", "transforaminal"
   - Surgical context: "operative", "intraoperative", "surgical steps"
   
   Examples:
   - "retrosigmoid approach vestibular schwannoma"
   - "how to clip anterior communicating artery aneurysm"
   - "microvascular decompression technique"
   - "endoscopic third ventriculostomy procedure"

2. CLINICAL_KNOWLEDGE - User wants disease info, diagnosis, management, outcomes
   Indicators:
   - Disease/condition names alone: "glioblastoma", "chiari malformation"
   - Diagnostic terms: "presentation", "symptoms", "diagnosis", "imaging"
   - Management terms: "treatment", "prognosis", "outcomes", "complications"
   - Epidemiological terms: "incidence", "prevalence", "risk factors"
   
   Examples:
   - "vestibular schwannoma presentation"
   - "glioblastoma prognosis"
   - "chiari malformation types"
   - "spinal cord injury management"

3. MIXED - Query is ambiguous or could apply to both
   Indicators:
   - Bare condition/procedure names without context
   - Could reasonably want both surgical and clinical information
   
   Examples:
   - "acoustic neuroma" (could want surgery OR clinical info)
   - "spinal fusion" (could want technique OR indications)
   - "craniotomy" (could want procedure OR complications)

DECISION RULES:
1. If query contains explicit procedural language → SURGICAL_TECHNIQUE
2. If query contains explicit clinical/diagnostic language → CLINICAL_KNOWLEDGE
3. If query is just a condition/procedure name → MIXED
4. When in doubt, prefer MIXED to avoid over-filtering

Respond with JSON only:
{{"intent": "<SURGICAL_TECHNIQUE|CLINICAL_KNOWLEDGE|MIXED>", "confidence": <0.0-1.0>, "reasoning": "<1 sentence>"}}

Examples:
Query: "pterional craniotomy technique"
{{"intent": "SURGICAL_TECHNIQUE", "confidence": 0.95, "reasoning": "Explicit request for surgical technique with specific approach name"}}

Query: "glioblastoma survival rates"
{{"intent": "CLINICAL_KNOWLEDGE", "confidence": 0.9, "reasoning": "Asking for outcome data, which is theoretical/clinical content"}}

Query: "vestibular schwannoma"
{{"intent": "MIXED", "confidence": 0.8, "reasoning": "Bare condition name without context - user may want surgical or clinical information"}}
"""


class QueryIntentClassifier:
    """Classify search query intent using Claude API."""

    def __init__(self, api_key: str, database=None):
        """
        Initialize the classifier.
        
        Args:
            api_key: Anthropic API key
            database: Optional database for caching
        """
        self.api_key = api_key
        self.database = database
        self.client = None
        self._init_client()

    def _init_client(self):
        """Initialize Anthropic client."""
        if self.api_key:
            try:
                self.client = anthropic.Anthropic(api_key=self.api_key)
            except Exception as e:
                print(f"Warning: Failed to initialize Anthropic client: {e}")
                self.client = None

    def classify(self, query: str) -> QueryIntent:
        """
        Classify the intent of a search query.
        
        Args:
            query: The search query string
            
        Returns:
            QueryIntent with classification result
        """
        if not query or not query.strip():
            return QueryIntent(
                intent="MIXED",
                confidence=0.0,
                reasoning="Empty query",
                cached=False
            )

        # Check cache first
        if self.database:
            cached = self.database.get_cached_query_intent(query)
            if cached:
                return QueryIntent(
                    intent=cached["intent"],
                    confidence=cached["confidence"],
                    reasoning=cached["reasoning"],
                    cached=True
                )

        # Call Claude API
        if not self.client:
            return QueryIntent(
                intent="MIXED",
                confidence=0.5,
                reasoning="API not configured - defaulting to mixed",
                cached=False
            )

        try:
            prompt = QUERY_INTENT_PROMPT.format(query=query)
            
            response = self.client.messages.create(
                model=config.CLAUDE_MODEL,
                max_tokens=200,
                temperature=0.0,  # Deterministic for caching
                messages=[{"role": "user", "content": prompt}]
            )

            response_text = response.content[0].text.strip()
            
            # Parse JSON response
            data = json.loads(response_text)
            intent = data.get("intent", "MIXED")
            confidence = float(data.get("confidence", 0.5))
            reasoning = data.get("reasoning", "")

            # Validate intent type
            if intent not in ["SURGICAL_TECHNIQUE", "CLINICAL_KNOWLEDGE", "MIXED"]:
                intent = "MIXED"

            result = QueryIntent(
                intent=intent,
                confidence=confidence,
                reasoning=reasoning,
                cached=False
            )

            # Cache the result
            if self.database:
                self.database.cache_query_intent(query, intent, confidence, reasoning)

            return result

        except json.JSONDecodeError:
            print(f"Warning: Failed to parse intent classification response")
            return QueryIntent(
                intent="MIXED",
                confidence=0.5,
                reasoning="Parse error - defaulting to mixed",
                cached=False
            )
        except Exception as e:
            print(f"Warning: Intent classification failed: {type(e).__name__}")
            return QueryIntent(
                intent="MIXED",
                confidence=0.5,
                reasoning="Classification error - defaulting to mixed",
                cached=False
            )

