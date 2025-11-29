"""Integration modules for Reference Library and external services."""

from neurosynth.integration.promotion import (
    PromotionPipeline,
    PromotionImporter,
    PromotedPaper,
    PromotionManifest,
    promote_from_cli,
    import_from_cli,
)
from neurosynth.integration.doi_service import (
    DOIService,
    BibliographicRecord,
    DOICache,
    resolve_doi,
    generate_bibliography,
)
from neurosynth.integration.evidence import (
    EvidenceDetector,
    EvidenceDetection,
    EvidenceLevel,
    detect_evidence_level,
    get_evidence_summary,
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
