"""Chapter synthesis engine."""

from neurosynth.synthesis.category_outline import (
    CategoryAwareOutlineGenerator,
    OutlineNode,
    OutlineTemplate,
    SectionBlueprint,
)
from neurosynth.synthesis.checkpoint import (
    SynthesisCheckpoint,
    get_latest_recovery,
    list_recoveries,
)
from neurosynth.synthesis.citation_resolver import (
    CitationStats,
    SourceMapping,
    XMLToLatexResolver,
    resolve_xml_to_latex,
)
from neurosynth.synthesis.conflicts import ConflictHandler
from neurosynth.synthesis.figure_integration import (
    ChapterFigureResolution,
    FigureIntegrationConfig,
    FigureIntegrationPipeline,
)
from neurosynth.synthesis.figure_resolver import FigurePlaceholderResolver
from neurosynth.synthesis.outline import OutlineGenerator
from neurosynth.synthesis.position_optimizer import (
    PositionOptimizer,
    PositionOptimizerConfig,
)
from neurosynth.synthesis.positioned_figure import (
    FigureLibrary,
    MatchMethod,
    PlaceholderMatch,
    PlacementType,
    PositionedFigure,
    ProceduralMatch,
    SectionFigureResolution,
    SemanticMatch,
)
from neurosynth.synthesis.procedural_correlator import ProceduralStepCorrelator
from neurosynth.synthesis.section import SectionSynthesizer
from neurosynth.synthesis.semantic_matcher import SemanticImageMatcher
from neurosynth.synthesis.verifier import (
    SynthesisVerifier,
    VerificationIssue,
    VerificationResult,
    VerificationStatus,
    get_verifier,
    verify_synthesis,
)

__all__ = [
    "OutlineGenerator",
    "SectionSynthesizer",
    "ConflictHandler",
    "CategoryAwareOutlineGenerator",
    "OutlineTemplate",
    "SectionBlueprint",
    "OutlineNode",
    "SynthesisCheckpoint",
    "get_latest_recovery",
    "list_recoveries",
    # Citation resolution
    "XMLToLatexResolver",
    "SourceMapping",
    "CitationStats",
    "resolve_xml_to_latex",
    # Verification
    "SynthesisVerifier",
    "VerificationResult",
    "VerificationStatus",
    "VerificationIssue",
    "verify_synthesis",
    "get_verifier",
    # Figure positioning
    "PlacementType",
    "MatchMethod",
    "PlaceholderMatch",
    "SemanticMatch",
    "ProceduralMatch",
    "PositionedFigure",
    "SectionFigureResolution",
    "FigureLibrary",
    # Figure integration pipeline
    "FigureIntegrationPipeline",
    "FigureIntegrationConfig",
    "ChapterFigureResolution",
    "FigurePlaceholderResolver",
    "SemanticImageMatcher",
    "ProceduralStepCorrelator",
    "PositionOptimizer",
    "PositionOptimizerConfig",
]
