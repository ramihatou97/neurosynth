"""Integration modules for Reference Library and external services."""

from neurosynth.integration.doi_service import (
    BibliographicRecord,
    DOICache,
    DOIService,
    generate_bibliography,
    resolve_doi,
)
from neurosynth.integration.evidence import (
    EvidenceDetection,
    EvidenceDetector,
    EvidenceLevel,
    detect_evidence_level,
    get_evidence_summary,
)
from neurosynth.integration.promotion import (
    PromotedPaper,
    PromotionImporter,
    PromotionManifest,
    PromotionPipeline,
    import_from_cli,
    promote_from_cli,
)

__all__ = [
    # Promotion
    "PromotionPipeline",
    "PromotionImporter",
    "PromotedPaper",
    "PromotionManifest",
    "promote_from_cli",
    "import_from_cli",
    # DOI Service
    "DOIService",
    "BibliographicRecord",
    "DOICache",
    "resolve_doi",
    "generate_bibliography",
    # Evidence Detection
    "EvidenceDetector",
    "EvidenceDetection",
    "EvidenceLevel",
    "detect_evidence_level",
    "get_evidence_summary",
]
