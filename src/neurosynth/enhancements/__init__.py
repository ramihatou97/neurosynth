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
]
