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
    AssociationWeightConfig,
    CaptionConfidenceConfig,
    CaptionDetectionConfig,
    CaptionPosition,
    FilterFallbackLevel,
    ImageCategory,
    ImageFilterConfig,
    KeywordWeightConfig,
    LaTeXConfig,
    NeurosurgicalKeywords,
    NeuroSynthEnhancedConfig,
    PerformanceConfig,
)

# Caption detection (multi-directional)
from .enhanced_caption_detector import (
    BatchCaptionProcessor,
    CaptionPatternMatcher,
    CrossReferenceTracker,
    DetectedCaption,
    EnhancedCaptionDetector,
)

# Procedural sequences (Step 1→2→3)
from .procedural_detector import (
    ProceduralSequence,
    ProceduralSequenceDetector,
    SequenceElement,
    SequenceExporter,
    SequenceType,
    SequenceValidator,
)

# Image filtering (3-tier fallback)
from .resilient_filter import (
    BasicImageFilter,
    ColorAnalyzer,
    EnhancedMedicalClassifier,
    EntropyCalculator,
    FilterResult,
    PermissiveFilter,
    ResilientImageFilter,
    SurgicalColorDetector,
)

# Visual association (neurosurgical keywords)
from .visual_cluster_associator import (
    Association,
    AssociationScore,
    ClusterBuilder,
    ContextAnalyzer,
    EnhancedVisualClusterAssociator,
    ImageBlock,
    NeurosurgicalKeywordScorer,
    SpatialProximityCalculator,
    TextBlock,
)

# Phase 4: Unified Pipeline (conditional import)
try:
    from .unified_pipeline import (
        ExtractedImage,
        ExtractionResult,
        UnifiedExtractionPipeline,
    )

    HAS_UNIFIED_PIPELINE = True
except ImportError:
    HAS_UNIFIED_PIPELINE = False

from .async_wrappers import (
    AsyncPDFDocument,
    ExecutorPool,
    async_wrap,
    get_executor_pool,
    process_batch,
    shutdown_executor_pool,
)
from .batch_processor import BatchPageProcessor, BatchProcessingResult
from .latex_validator import (
    LaTeXValidator,
    ValidationResult,
    escape_latex,
    sanitize_label,
    unescape_latex,
    validate_figure_environment,
)

# Phase 4.1: Dependencies
from .vector_extractor import VectorGraphic, VectorGraphicsExtractor

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
    __all__.extend(
        [
            "UnifiedExtractionPipeline",
            "ExtractionResult",
            "ExtractedImage",
        ]
    )
