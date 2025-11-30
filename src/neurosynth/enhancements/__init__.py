"""
NeuroSynth Enhancement Modules v3.1 (Phase 3 Core)
===================================================

Core enhancement modules for Phase 3 integration:
- Resilient 3-tier fallback filtering
- Multi-directional caption detection
- Neurosurgical keyword scoring (340+ terms)
- Procedural sequence detection

ALL WEIGHTS ARE CENTRALIZED IN config.py

Version: 3.1 (Phase 3 Core)
"""

__version__ = "3.1.0-phase3"
__author__ = "NeuroSynth Team"

# Core configuration
from .config import (
    NeuroSynthEnhancedConfig,
    KeywordWeightConfig,
    AssociationWeightConfig,
    CaptionConfidenceConfig,
    NeurosurgicalKeywords,
    ImageFilterConfig,
    CaptionDetectionConfig,
    LaTeXConfig,
    PerformanceConfig,
    ImageCategory,
    CaptionPosition,
    FilterFallbackLevel,
)

# Image filtering (3-tier fallback)
from .resilient_filter import (
    ResilientImageFilter,
    EnhancedMedicalClassifier,
    BasicImageFilter,
    PermissiveFilter,
    FilterResult,
    ColorAnalyzer,
    EntropyCalculator,
    SurgicalColorDetector,
)

# Caption detection (multi-directional)
from .enhanced_caption_detector import (
    EnhancedCaptionDetector,
    CaptionPatternMatcher,
    DetectedCaption,
    BatchCaptionProcessor,
    CrossReferenceTracker,
)

# Visual association (neurosurgical keywords)
from .visual_cluster_associator import (
    EnhancedVisualClusterAssociator,
    NeurosurgicalKeywordScorer,
    SpatialProximityCalculator,
    ContextAnalyzer,
    ClusterBuilder,
    TextBlock,
    ImageBlock,
    Association,
    AssociationScore,
)

# Procedural sequences (Step 1→2→3)
from .procedural_detector import (
    ProceduralSequenceDetector,
    ProceduralSequence,
    SequenceElement,
    SequenceType,
    SequenceValidator,
    SequenceExporter,
)

# Phase 4: Unified Pipeline (conditional import)
try:
    from .unified_pipeline import (
        UnifiedExtractionPipeline,
        ExtractionResult,
        ExtractedImage,
    )
    HAS_UNIFIED_PIPELINE = True
except ImportError:
    HAS_UNIFIED_PIPELINE = False

# Phase 4.1: Dependencies
from .vector_extractor import VectorGraphicsExtractor, VectorGraphic
from .batch_processor import BatchPageProcessor, BatchProcessingResult
from .async_wrappers import (
    async_wrap,
    process_batch,
    AsyncPDFDocument,
    get_executor_pool,
    ExecutorPool,
    shutdown_executor_pool,
)
from .latex_validator import (
    LaTeXValidator,
    ValidationResult,
    escape_latex,
    sanitize_label,
    unescape_latex,
    validate_figure_environment,
)

__all__ = [
    # Version
    "__version__",

    # Config
    "NeuroSynthEnhancedConfig",
    "KeywordWeightConfig",
    "AssociationWeightConfig",
    "CaptionConfidenceConfig",
    "NeurosurgicalKeywords",
    "ImageFilterConfig",
    "CaptionDetectionConfig",
    "LaTeXConfig",
    "PerformanceConfig",

    # Enums
    "ImageCategory",
    "CaptionPosition",
    "FilterFallbackLevel",
    "SequenceType",

    # Filtering
    "ResilientImageFilter",
    "EnhancedMedicalClassifier",
    "BasicImageFilter",
    "PermissiveFilter",
    "FilterResult",
    "ColorAnalyzer",
    "EntropyCalculator",
    "SurgicalColorDetector",

    # Caption Detection
    "EnhancedCaptionDetector",
    "CaptionPatternMatcher",
    "DetectedCaption",
    "BatchCaptionProcessor",
    "CrossReferenceTracker",

    # Visual Association
    "EnhancedVisualClusterAssociator",
    "NeurosurgicalKeywordScorer",
    "SpatialProximityCalculator",
    "ContextAnalyzer",
    "ClusterBuilder",
    "TextBlock",
    "ImageBlock",
    "Association",
    "AssociationScore",

    # Procedural Sequences
    "ProceduralSequenceDetector",
    "ProceduralSequence",
    "SequenceElement",
    "SequenceValidator",
    "SequenceExporter",

    # Phase 4: Unified Pipeline
    "HAS_UNIFIED_PIPELINE",  # Flag to check if unified pipeline available

    # Phase 4.1: Dependencies
    "VectorGraphicsExtractor",
    "VectorGraphic",
    "BatchPageProcessor",
    "BatchProcessingResult",
    "async_wrap",
    "process_batch",
    "AsyncPDFDocument",
    "get_executor_pool",
    "ExecutorPool",
    "shutdown_executor_pool",
    "LaTeXValidator",
    "ValidationResult",
    "escape_latex",
    "sanitize_label",
    "unescape_latex",
    "validate_figure_environment",
]

# Add conditional Phase 4 exports
if HAS_UNIFIED_PIPELINE:
    __all__.extend([
        "UnifiedExtractionPipeline",
        "ExtractionResult",
        "ExtractedImage",
    ])

