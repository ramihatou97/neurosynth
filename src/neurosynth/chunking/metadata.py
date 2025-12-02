"""Metadata extraction for content chunks."""

import re
from dataclasses import dataclass

from neurosynth.models.document import ContentChunk


@dataclass
class ChunkMetadata:
    """Extracted metadata for a chunk."""

    topic: str = ""
    subtopic: str = ""
    key_concepts: list[str] = None
    medical_entities: list[str] = None
    section_type: str = ""
    confidence: float = 1.0

    def __post_init__(self):
        if self.key_concepts is None:
            self.key_concepts = []
        if self.medical_entities is None:
            self.medical_entities = []


class ChunkMetadataExtractor:
    """Extract metadata from content chunks."""

    # Common neurosurgical terminology patterns
    ANATOMY_PATTERNS = [
        r"\b(cerebr|cortex|cortical|ventricle|ventricul|hemisphere|lobe)\w*\b",
        r"\b(spinal|vertebr|cervical|thoracic|lumbar|sacral)\w*\b",
        r"\b(artery|arter|vein|venous|sinus|vessel)\w*\b",
        r"\b(nerve|neural|neuro|gangli|plexus)\w*\b",
        r"\b(skull|cranial|cranio|dura|arachnoid|pia)\w*\b",
    ]

    PATHOLOGY_PATTERNS = [
        r"\b(tumor|tumour|neoplasm|malignant|benign|metasta)\w*\b",
        r"\b(hemorrhage|haemorrhage|bleeding|hematoma)\w*\b",
        r"\b(aneurysm|AVM|arteriovenous|fistula)\w*\b",
        r"\b(stenosis|occlusion|thrombosis|embol)\w*\b",
        r"\b(glioma|meningioma|schwannoma|adenoma)\w*\b",
    ]

    PROCEDURE_PATTERNS = [
        r"\b(craniotomy|craniectomy|laminectomy|discectomy)\w*\b",
        r"\b(resection|excision|ablation|decompression)\w*\b",
        r"\b(microsurg|endoscop|stereotact|radiosurg)\w*\b",
        r"\b(fusion|fixation|instrumentation|implant)\w*\b",
        r"\b(biopsy|aspiration|drainage|shunt)\w*\b",
    ]

    SECTION_KEYWORDS = {
        "introduction": ["introduction", "overview", "background", "history"],
        "anatomy": ["anatomy", "anatomical", "neuroanatomy", "surgical anatomy"],
        "pathophysiology": ["pathophysiology", "pathology", "mechanism", "etiology"],
        "clinical": ["presentation", "symptoms", "signs", "clinical", "examination"],
        "diagnostic": ["diagnosis", "imaging", "MRI", "CT", "workup", "evaluation"],
        "surgical_technique": [
            "technique",
            "procedure",
            "approach",
            "positioning",
            "incision",
        ],
        "complications": ["complication", "risk", "adverse", "morbidity", "mortality"],
        "outcomes": ["outcome", "prognosis", "result", "follow-up", "survival"],
    }

    def __init__(self):
        self._compiled_anatomy = [re.compile(p, re.I) for p in self.ANATOMY_PATTERNS]
        self._compiled_pathology = [
            re.compile(p, re.I) for p in self.PATHOLOGY_PATTERNS
        ]
        self._compiled_procedure = [
            re.compile(p, re.I) for p in self.PROCEDURE_PATTERNS
        ]

    def extract(self, chunk: ContentChunk) -> ChunkMetadata:
        """Extract metadata from a chunk."""
        text = chunk.content.lower()

        metadata = ChunkMetadata()

        # Extract medical entities
        metadata.medical_entities = self._extract_entities(chunk.content)

        # Determine section type
        metadata.section_type = self._classify_section(text)

        # Extract key concepts
        metadata.key_concepts = self._extract_key_concepts(chunk.content)

        # Set topic from section title or infer
        if chunk.section_title:
            metadata.topic = chunk.section_title
        else:
            metadata.topic = metadata.section_type.replace("_", " ").title()

        return metadata

    async def extract_with_llm(self, chunk: ContentChunk) -> ChunkMetadata:
        """Extract metadata using LLM for better accuracy."""
        from neurosynth.llm.gemini import GeminiClient

        gemini = GeminiClient()
        result = await gemini.identify_chunk_topic(chunk.content)

        metadata = ChunkMetadata(
            topic=result.get("topic", ""),
            subtopic=result.get("subtopic", ""),
            key_concepts=result.get("key_concepts", []),
            section_type=result.get("section_suggestion", ""),
        )

        # Also add rule-based entities
        metadata.medical_entities = self._extract_entities(chunk.content)

        return metadata

    def _extract_entities(self, text: str) -> list[str]:
        """Extract medical entities from text."""
        entities = set()

        # Find anatomy terms
        for pattern in self._compiled_anatomy:
            matches = pattern.findall(text)
            entities.update(m.lower() for m in matches)

        # Find pathology terms
        for pattern in self._compiled_pathology:
            matches = pattern.findall(text)
            entities.update(m.lower() for m in matches)

        # Find procedure terms
        for pattern in self._compiled_procedure:
            matches = pattern.findall(text)
            entities.update(m.lower() for m in matches)

        return list(entities)

    def _classify_section(self, text: str) -> str:
        """Classify the section type based on content."""
        scores = {}

        for section_type, keywords in self.SECTION_KEYWORDS.items():
            score = 0
            for keyword in keywords:
                # Count occurrences
                count = text.count(keyword.lower())
                score += count

            scores[section_type] = score

        # Return highest scoring section type
        if scores:
            best = max(scores.items(), key=lambda x: x[1])
            if best[1] > 0:
                return best[0]

        return "general"

    def _extract_key_concepts(self, text: str) -> list[str]:
        """Extract key medical concepts from text."""
        concepts = []

        # Look for defined terms (term: definition pattern)
        definitions = re.findall(r"(\w+(?:\s+\w+)?)\s*[:]\s*[^.]+\.", text)
        concepts.extend(d.strip() for d in definitions[:5])

        # Look for emphasized terms (in quotes or italics)
        emphasized = re.findall(r'"([^"]+)"', text)
        concepts.extend(e.strip() for e in emphasized[:5])

        # Look for capitalized medical terms
        caps_terms = re.findall(r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)\b", text)
        concepts.extend(t for t in caps_terms[:5] if len(t) > 5)

        return list(set(concepts))[:10]


def batch_extract_metadata(
    chunks: list[ContentChunk],
    use_llm: bool = False,
) -> dict[str, ChunkMetadata]:
    """Extract metadata for multiple chunks."""
    import asyncio

    extractor = ChunkMetadataExtractor()
    results = {}

    if use_llm:

        async def extract_all():
            tasks = [extractor.extract_with_llm(c) for c in chunks]
            return await asyncio.gather(*tasks)

        metadata_list = asyncio.run(extract_all())
        for chunk, metadata in zip(chunks, metadata_list, strict=False):
            results[chunk.id] = metadata
    else:
        for chunk in chunks:
            results[chunk.id] = extractor.extract(chunk)

    return results
