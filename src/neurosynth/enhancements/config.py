"""
NeuroSynth Enhancement Configuration v3.1
==========================================
Centralized configuration for all enhancement modules.
Single source of truth for ALL weights, thresholds, and settings.

CRITICAL: All scoring weights are defined HERE and ONLY here.
Do not hardcode weights in other modules.

Version: 3.1 (weight consolidation)
"""

from dataclasses import dataclass, field
from typing import Dict, List, Tuple, Optional
from enum import Enum
import os


# =============================================================================
# ENUMS
# =============================================================================

class ImageCategory(Enum):
    """Classification taxonomy for neurosurgical images."""
    ANATOMICAL_DIAGRAM = "anatomical_diagram"
    INTRAOPERATIVE = "intraoperative"
    RADIOLOGICAL = "radiological"
    PROCEDURAL_STEP = "procedural_step"
    THREE_D_RECONSTRUCTION = "3d_reconstruction"
    FLOWCHART = "flowchart"
    INSTRUMENT = "instrument"
    CADAVERIC = "cadaveric"
    HISTOLOGICAL = "histological"
    COMPARISON = "comparison"
    UNKNOWN = "unknown"


class CaptionPosition(Enum):
    """Position of caption relative to image."""
    BELOW = "below"
    ABOVE = "above"
    RIGHT = "right"
    LEFT = "left"
    INLINE = "inline"
    UNKNOWN = "unknown"


class FilterFallbackLevel(Enum):
    """Fallback levels for resilient filtering."""
    ENHANCED = "enhanced"      # Full MedicalImageClassifier
    BASIC = "basic"            # Simple heuristics
    PERMISSIVE = "permissive"  # Size-only check
    FAILED = "failed"          # All filters failed


# =============================================================================
# KEYWORD WEIGHTS CONFIGURATION
# =============================================================================

@dataclass
class KeywordWeightConfig:
    """
    Centralized keyword weights for semantic scoring.
    
    WEIGHTS MUST SUM TO 1.0 (±0.05 tolerance)
    
    Rationale for weights:
    - procedure (0.30): Highest - surgical actions are most relevant
    - anatomy (0.25): Critical for identifying anatomical structures
    - pathology (0.25): Important for disease/condition context
    - imaging (0.15): Useful but secondary to anatomy/procedure
    - instruments (0.05): Least discriminative, often in all surgical images
    """
    
    # Category weights — MUST SUM TO 1.0
    anatomy: float = 0.25
    pathology: float = 0.25
    procedure: float = 0.30      # Highest — most relevant for surgical content
    imaging: float = 0.15
    instruments: float = 0.05    # Lowest — least discriminative
    
    # Context multipliers (applied after category scoring)
    caption_context_boost: float = 1.5    # Keywords in captions worth 50% more
    heading_context_boost: float = 1.3    # Keywords in headings worth 30% more
    body_context_boost: float = 1.0       # Standard body text (no boost)
    figure_id_boost: float = 1.2          # Keywords in figure IDs
    
    # Minimum thresholds for relevance
    min_keyword_matches: int = 1          # Minimum keywords for any relevance
    min_category_diversity: int = 1       # Minimum different categories
    
    def __post_init__(self):
        """Validate weights on creation."""
        self.validate()
    
    def validate(self) -> bool:
        """Validate that weights sum to approximately 1.0."""
        total = (
            self.anatomy + self.pathology + self.procedure + 
            self.imaging + self.instruments
        )
        if not (0.95 <= total <= 1.05):
            raise ValueError(
                f"Keyword weights must sum to ~1.0, got {total:.2f}. "
                f"Current: anatomy={self.anatomy}, pathology={self.pathology}, "
                f"procedure={self.procedure}, imaging={self.imaging}, "
                f"instruments={self.instruments}"
            )
        return True
    
    def get_weight(self, category: str) -> float:
        """Get weight for a category name."""
        weights = {
            'anatomy': self.anatomy,
            'pathology': self.pathology,
            'procedure': self.procedure,
            'imaging': self.imaging,
            'instruments': self.instruments,
        }
        return weights.get(category.lower(), 0.0)
    
    def to_dict(self) -> dict:
        """Export weights as dictionary."""
        return {
            'anatomy': self.anatomy,
            'pathology': self.pathology,
            'procedure': self.procedure,
            'imaging': self.imaging,
            'instruments': self.instruments,
            'total': self.anatomy + self.pathology + self.procedure + self.imaging + self.instruments,
        }


# =============================================================================
# ASSOCIATION WEIGHTS CONFIGURATION (NEW)
# =============================================================================

@dataclass
class AssociationWeightConfig:
    """
    Weights for image-text association scoring.
    
    Association formula:
    total = (spatial × spatial_weight) + 
            (keyword × keyword_weight) + 
            (context × context_weight) + 
            caption_boost
            
    COMPONENT WEIGHTS MUST SUM TO 1.0
    """
    
    # Component weights — MUST SUM TO 1.0
    spatial_weight: float = 0.50    # Proximity to image
    keyword_weight: float = 0.30    # Neurosurgical keyword relevance
    context_weight: float = 0.20    # Contextual cues (references, demonstratives)
    
    # Boost values (added after weighted sum)
    caption_boost: float = 0.15     # Boost if text is a caption
    direct_ref_boost: float = 0.20  # Boost if text directly references figure
    
    # Thresholds
    min_association_score: float = 0.10   # Minimum score to consider
    high_confidence_threshold: float = 0.70  # High confidence association
    
    def __post_init__(self):
        """Validate weights on creation."""
        self.validate()
    
    def validate(self) -> bool:
        """Validate that component weights sum to 1.0."""
        total = self.spatial_weight + self.keyword_weight + self.context_weight
        if not (0.95 <= total <= 1.05):
            raise ValueError(
                f"Association weights must sum to ~1.0, got {total:.2f}. "
                f"Current: spatial={self.spatial_weight}, keyword={self.keyword_weight}, "
                f"context={self.context_weight}"
            )
        return True


# =============================================================================
# CAPTION CONFIDENCE WEIGHTS (NEW)
# =============================================================================

@dataclass
class CaptionConfidenceConfig:
    """
    Weights for caption detection confidence scoring.
    
    Confidence formula:
    confidence = pattern_score × pattern_weight +
                 proximity_score × proximity_weight +
                 formatting_score × formatting_weight +
                 length_score × length_weight
    """
    
    # Component weights — MUST SUM TO 1.0
    pattern_weight: float = 0.40     # Pattern match quality
    proximity_weight: float = 0.30   # Distance from image
    formatting_weight: float = 0.20  # Italic/bold formatting
    length_weight: float = 0.10      # Caption length
    
    # Scoring bonuses
    standard_figure_id_bonus: float = 0.10    # "Figure X" format
    italic_bonus: float = 0.10
    bold_bonus: float = 0.05
    close_proximity_bonus: float = 0.20       # Within 50px
    adequate_length_bonus: float = 0.10       # >30 chars
    
    # Thresholds
    min_confidence: float = 0.40
    high_confidence: float = 0.70
    close_proximity_px: float = 50.0
    adequate_length_chars: int = 30
    
    def __post_init__(self):
        self.validate()
    
    def validate(self) -> bool:
        total = (self.pattern_weight + self.proximity_weight + 
                 self.formatting_weight + self.length_weight)
        if not (0.95 <= total <= 1.05):
            raise ValueError(f"Caption confidence weights must sum to ~1.0, got {total:.2f}")
        return True


# =============================================================================
# KEYWORD DICTIONARIES
# =============================================================================

@dataclass
class NeurosurgicalKeywords:
    """
    Comprehensive neurosurgical keyword dictionaries.
    Organized by category for weighted scoring.
    """
    
    anatomy: List[str] = field(default_factory=lambda: [
        # Cerebral structures
        'cortex', 'gyrus', 'sulcus', 'lobe', 'hemisphere',
        'frontal', 'parietal', 'temporal', 'occipital', 'insular',
        # Deep structures
        'ventricle', 'thalamus', 'hypothalamus', 'basal ganglia',
        'caudate', 'putamen', 'globus pallidus', 'internal capsule',
        'corpus callosum', 'fornix', 'hippocampus', 'amygdala',
        # Posterior fossa
        'cerebellum', 'brainstem', 'pons', 'medulla', 'midbrain',
        'vermis', 'peduncle', 'fourth ventricle',
        # Cisterns and spaces
        'cistern', 'subarachnoid', 'epidural', 'subdural',
        'sylvian fissure', 'interhemispheric', 'ambient cistern',
        # Skull base
        'skull base', 'clivus', 'petrous', 'sella', 'cavernous sinus',
        'foramen magnum', 'jugular foramen', 'cribriform plate',
        # Vascular
        'carotid', 'vertebral', 'basilar', 'circle of willis',
        'MCA', 'ACA', 'PCA', 'PICA', 'AICA', 'SCA',
        'superior sagittal sinus', 'transverse sinus', 'sigmoid sinus',
        # Cranial nerves
        'cranial nerve', 'olfactory', 'optic', 'oculomotor',
        'trochlear', 'trigeminal', 'abducens', 'facial',
        'vestibulocochlear', 'glossopharyngeal', 'vagus',
        'accessory', 'hypoglossal',
        # Meninges
        'dura', 'dura mater', 'arachnoid', 'pia mater', 'falx', 'tentorium',
    ])
    
    pathology: List[str] = field(default_factory=lambda: [
        # Tumors
        'tumor', 'neoplasm', 'mass', 'lesion',
        'glioma', 'glioblastoma', 'astrocytoma', 'oligodendroglioma',
        'meningioma', 'schwannoma', 'neurofibroma', 'acoustic neuroma',
        'pituitary adenoma', 'craniopharyngioma', 'chordoma',
        'metastasis', 'metastatic', 'carcinoma',
        'ependymoma', 'medulloblastoma', 'hemangioblastoma',
        # Vascular
        'aneurysm', 'AVM', 'arteriovenous malformation', 'cavernoma',
        'hemorrhage', 'hematoma', 'subdural hematoma', 'epidural hematoma',
        'intracerebral hemorrhage', 'subarachnoid hemorrhage', 'SAH',
        'infarct', 'stroke', 'ischemia', 'thrombosis',
        # Degenerative/Other
        'hydrocephalus', 'herniation', 'edema', 'mass effect',
        'midline shift', 'compression', 'stenosis',
        'cyst', 'arachnoid cyst', 'colloid cyst',
        'abscess', 'empyema', 'infection', 'encephalitis',
        'demyelination', 'multiple sclerosis',
    ])
    
    procedure: List[str] = field(default_factory=lambda: [
        # Approaches
        'approach', 'craniotomy', 'craniectomy', 'cranioplasty',
        'pterional', 'frontal', 'temporal', 'parietal', 'occipital',
        'subfrontal', 'subtemporal', 'retrosigmoid', 'translabyrinthine',
        'transcallosal', 'interhemispheric', 'transcortical',
        'transsphenoidal', 'endonasal', 'endoscopic',
        'far lateral', 'extreme lateral', 'presigmoid',
        # Surgical actions
        'incision', 'exposure', 'dissection', 'retraction',
        'resection', 'excision', 'debulking', 'gross total resection',
        'coagulation', 'hemostasis', 'cauterization',
        'clipping', 'coiling', 'embolization', 'occlusion',
        'decompression', 'fenestration', 'marsupialization',
        'anastomosis', 'bypass', 'revascularization',
        'duraplasty', 'dural closure', 'watertight closure',
        # Techniques
        'microsurgical', 'keyhole', 'minimally invasive',
        'stereotactic', 'frameless', 'neuronavigation',
        'awake craniotomy', 'cortical mapping', 'stimulation',
        'intraoperative monitoring', 'IONM', 'MEP', 'SSEP',
        # Steps
        'step', 'first', 'then', 'next', 'finally', 'subsequently',
        'position', 'mark', 'identify', 'expose', 'elevate',
        'retract', 'coagulate', 'clip', 'remove', 'close',
    ])
    
    imaging: List[str] = field(default_factory=lambda: [
        # Modalities
        'MRI', 'CT', 'computed tomography', 'magnetic resonance',
        'angiogram', 'angiography', 'DSA', 'CTA', 'MRA',
        'PET', 'SPECT', 'functional MRI', 'fMRI',
        'ultrasound', 'intraoperative ultrasound',
        'X-ray', 'radiograph', 'fluoroscopy',
        # Sequences/Protocols
        'T1', 'T1-weighted', 'T2', 'T2-weighted',
        'FLAIR', 'DWI', 'diffusion', 'ADC',
        'contrast', 'gadolinium', 'enhancement', 'enhancing',
        'non-contrast', 'pre-contrast', 'post-contrast',
        'DTI', 'tractography', 'fiber tracking',
        # Views/Planes
        'axial', 'sagittal', 'coronal', 'oblique',
        '3D reconstruction', 'volume rendering', 'MIP',
        # Findings
        'hyperintense', 'hypointense', 'isointense',
        'hyperdense', 'hypodense', 'isodense',
        'bright', 'dark', 'signal abnormality',
    ])
    
    instruments: List[str] = field(default_factory=lambda: [
        # Visualization
        'microscope', 'endoscope', 'exoscope', 'loupe',
        # Retraction
        'retractor', 'self-retaining', 'handheld', 'brain spatula',
        'leyla', 'greenberg', 'yasargil',
        # Cutting/Dissection
        'scalpel', 'blade', 'scissors', 'dissector',
        'curette', 'rongeur', 'kerrison', 'bone cutter',
        # Coagulation
        'bipolar', 'monopolar', 'electrocautery', 'bovie',
        # Suction
        'suction', 'frazier', 'yankauer', 'irrigator',
        # Drilling
        'drill', 'craniotome', 'perforator', 'burr',
        'high-speed drill', 'matchstick', 'diamond burr',
        # Clips/Ligatures
        'clip', 'aneurysm clip', 'temporary clip', 'permanent clip',
        'sugita', 'yasargil clip', 'ligature',
        # Other
        'forceps', 'bayonet', 'needle holder', 'suture',
        'cottonoid', 'patty', 'gelfoam', 'surgicel',
        'navigation probe', 'ultrasonic aspirator', 'CUSA',
    ])
    
    def get_all_keywords(self) -> Dict[str, List[str]]:
        """Return all keywords organized by category."""
        return {
            'anatomy': self.anatomy,
            'pathology': self.pathology,
            'procedure': self.procedure,
            'imaging': self.imaging,
            'instruments': self.instruments,
        }
    
    def get_flat_keywords(self) -> List[str]:
        """Return all keywords as a flat list."""
        all_kw = []
        for category_list in self.get_all_keywords().values():
            all_kw.extend(category_list)
        return list(set(all_kw))


# =============================================================================
# IMAGE FILTER CONFIGURATION
# =============================================================================

@dataclass
class ImageFilterConfig:
    """Configuration for image filtering and classification."""
    
    # Size thresholds
    min_bytes: int = 1024               # 1KB minimum
    min_dimension: int = 100            # Minimum width OR height in pixels
    min_area: int = 15000               # Minimum width * height
    max_aspect_ratio: float = 6.0       # Reject if > this
    min_aspect_ratio: float = 0.167     # Reject if < this (1/6)
    
    # Quality thresholds
    min_confidence: float = 0.25        # Minimum classification confidence
    optimal_dpi_threshold: int = 150    # For surgical detail
    high_quality_threshold: float = 0.6 # For "high quality" label
    
    # Classification thresholds
    radiological_grayscale_ratio: float = 0.85
    surgical_color_threshold: float = 0.30
    icon_max_entropy: float = 3.0
    icon_max_area: int = 10000
    icon_max_colors: int = 32
    diagram_max_entropy: float = 5.0
    diagram_min_edge_density: float = 0.15
    
    # Surgical color ranges (RGB)
    surgical_colors: Dict[str, Tuple[Tuple[int, int, int], Tuple[int, int, int]]] = field(
        default_factory=lambda: {
            'blood': ((150, 0, 0), (255, 100, 100)),
            'tissue': ((200, 150, 150), (255, 220, 200)),
            'drape': ((0, 80, 0), (100, 180, 100)),
            'instrument': ((180, 180, 180), (220, 220, 220)),
        }
    )
    
    # Context boost
    context_keyword_boost: float = 0.05  # Per keyword found
    context_max_boost: float = 0.20      # Maximum context boost


# =============================================================================
# CAPTION DETECTION CONFIGURATION
# =============================================================================

@dataclass
class CaptionDetectionConfig:
    """Configuration for caption detection and association."""
    
    # Search parameters (pixels)
    search_radius_below: int = 100      # Below image
    search_radius_above: int = 80       # Above image
    search_radius_side: int = 150       # Left/right of image
    horizontal_tolerance: int = 50      # Horizontal alignment tolerance
    
    # Direction priorities by image position on page
    direction_priorities: Dict[str, List[CaptionPosition]] = field(
        default_factory=lambda: {
            'top': [CaptionPosition.BELOW, CaptionPosition.RIGHT, CaptionPosition.ABOVE],
            'middle': [CaptionPosition.BELOW, CaptionPosition.ABOVE, CaptionPosition.RIGHT],
            'bottom': [CaptionPosition.ABOVE, CaptionPosition.BELOW, CaptionPosition.RIGHT],
        }
    )
    
    # Confidence scoring (uses CaptionConfidenceConfig for weights)
    min_confidence: float = 0.4
    high_confidence: float = 0.7
    
    # Patterns
    figure_patterns: List[str] = field(default_factory=lambda: [
        r'(?P<type>fig(?:ure)?|plate|image|photo(?:graph)?|scheme|illustration)\.?\s*'
        r'(?P<num>\d+(?:[.\-]\d+)?(?:[a-z])?)',
        r'\((?P<sub>[A-Za-z]|\d+)\)',
        r'(?P<type>step)\s*(?P<num>\d+)',
        r'(?P<type>panel)\s*(?P<sub>[A-Za-z])',
    ])
    
    table_patterns: List[str] = field(default_factory=lambda: [
        r'(?P<type>table)\.?\s*(?P<num>\d+(?:[.\-]\d+)?)',
    ])
    
    cross_reference_patterns: List[str] = field(default_factory=lambda: [
        r'(?:see|cf\.?|compare)\s+(?:fig(?:ure)?\.?\s*)?(\d+(?:[.\-]\d+)?)',
        r'(?:as shown in|illustrated in)\s+(?:fig(?:ure)?\.?\s*)?(\d+(?:[.\-]\d+)?)',
        r'\((?:fig(?:ure)?\.?\s*)?(\d+(?:[.\-]\d+)?)\)',
    ])


# =============================================================================
# VECTOR GRAPHICS CONFIGURATION
# =============================================================================

@dataclass
class VectorGraphicsConfig:
    """Configuration for vector graphics extraction."""
    
    # Rendering
    render_dpi: int = 200
    high_res_dpi: int = 300
    
    # Detection thresholds
    min_vector_paths: int = 10
    min_path_complexity: int = 50
    min_area_ratio: float = 0.1         # Min % of page area
    max_area_ratio: float = 0.9         # Max % of page area
    
    # Clustering
    grid_size: int = 50                 # Pixels for grid-based clustering
    merge_distance: int = 50            # Distance for cluster merging
    
    # Classification keywords
    flowchart_keywords: List[str] = field(default_factory=lambda: [
        'algorithm', 'flowchart', 'decision', 'pathway', 'workflow',
        'protocol', 'management', 'if', 'then', 'yes', 'no',
    ])
    
    diagram_keywords: List[str] = field(default_factory=lambda: [
        'anatomy', 'schematic', 'illustration', 'drawing',
        'cross-section', 'dissection', 'view',
    ])


# =============================================================================
# LATEX OUTPUT CONFIGURATION
# =============================================================================

@dataclass
class LaTeXConfig:
    """Configuration for LaTeX figure generation."""
    
    # Paths
    image_base_path: str = "figures/"
    
    # Float placement
    default_placement: str = "htbp"
    procedure_placement: str = "p"      # Own page for procedures
    comparison_placement: str = "htbp"
    
    # Size presets (fraction of textwidth)
    size_presets: Dict[str, float] = field(default_factory=lambda: {
        'full': 1.0,
        'large': 0.8,
        'medium': 0.6,
        'small': 0.45,
        'thumbnail': 0.3,
    })
    
    # Subfigures
    max_subfigures_per_row: int = 3
    max_subfigures_per_figure: int = 6
    subfigure_spacing: str = "\\hfill"
    row_spacing: str = "\\\\[1ex]"
    
    # Procedural sequences
    max_steps_per_page: int = 6
    step_label_format: str = "Step {num}"
    
    # Validation
    enable_compilation_check: bool = False  # Requires pdflatex
    compilation_timeout: int = 30


# =============================================================================
# ASYNC/PERFORMANCE CONFIGURATION
# =============================================================================

@dataclass
class PerformanceConfig:
    """Configuration for async processing and performance."""
    
    # Thread pool
    max_workers: int = 4
    
    # Batch processing
    batch_size: int = 20                # Pages per batch
    enable_xref_dedup: bool = True      # Deduplicate by xref before extraction
    
    # Caching
    enable_hash_cache: bool = True
    enable_position_cache: bool = True
    enable_caption_cache: bool = True
    cache_max_size: int = 10000
    
    # Timeouts
    extraction_timeout: float = 30.0    # Per page
    total_timeout: float = 600.0        # Per document


# =============================================================================
# MASTER CONFIGURATION
# =============================================================================

@dataclass
class NeuroSynthEnhancedConfig:
    """
    Master configuration combining all enhancement settings.
    Single source of truth for the entire pipeline.
    
    Usage:
        config = NeuroSynthEnhancedConfig()
        
        # Access keyword weights
        proc_weight = config.keyword_weights.procedure  # 0.30
        
        # Access association weights
        spatial = config.association_weights.spatial_weight  # 0.50
        
        # Access caption confidence weights
        pattern_wt = config.caption_confidence.pattern_weight  # 0.40
    """
    
    # Output paths
    output_base_dir: str = "./neurosynth_output"
    images_subdir: str = "images"
    metadata_subdir: str = "metadata"
    latex_subdir: str = "latex"
    sequences_subdir: str = "sequences"
    vectors_subdir: str = "vectors"
    
    # Sub-configurations
    keywords: NeurosurgicalKeywords = field(default_factory=NeurosurgicalKeywords)
    keyword_weights: KeywordWeightConfig = field(default_factory=KeywordWeightConfig)
    association_weights: AssociationWeightConfig = field(default_factory=AssociationWeightConfig)
    caption_confidence: CaptionConfidenceConfig = field(default_factory=CaptionConfidenceConfig)
    image_filter: ImageFilterConfig = field(default_factory=ImageFilterConfig)
    caption_detection: CaptionDetectionConfig = field(default_factory=CaptionDetectionConfig)
    vector_graphics: VectorGraphicsConfig = field(default_factory=VectorGraphicsConfig)
    latex: LaTeXConfig = field(default_factory=LaTeXConfig)
    performance: PerformanceConfig = field(default_factory=PerformanceConfig)
    
    # Feature flags
    enable_enhanced_filtering: bool = True
    enable_caption_detection: bool = True
    enable_cluster_association: bool = True
    enable_vector_extraction: bool = True
    enable_procedural_detection: bool = True
    enable_cross_references: bool = True
    enable_slideshows: bool = True
    enable_latex_validation: bool = False
    
    # Fallback behavior
    use_fallback_chain: bool = True
    log_fallbacks: bool = True
    
    def __post_init__(self):
        """Create output directories and validate configuration."""
        self._create_directories()
        self._validate()
    
    def _create_directories(self):
        """Create all required output directories."""
        dirs = [
            self.output_base_dir,
            os.path.join(self.output_base_dir, self.images_subdir),
            os.path.join(self.output_base_dir, self.metadata_subdir),
            os.path.join(self.output_base_dir, self.latex_subdir),
            os.path.join(self.output_base_dir, self.sequences_subdir),
            os.path.join(self.output_base_dir, self.vectors_subdir),
        ]
        for d in dirs:
            os.makedirs(d, exist_ok=True)
    
    def _validate(self):
        """Validate all weight configurations."""
        # Each sub-config validates itself in __post_init__
        pass
    
    def get_path(self, subdir: str) -> str:
        """Get full path for a subdirectory."""
        return os.path.join(self.output_base_dir, subdir)
    
    def print_weights_summary(self):
        """Print a summary of all weights for debugging."""
        print("=" * 60)
        print("NEUROSYNTH WEIGHT CONFIGURATION SUMMARY")
        print("=" * 60)
        
        print("\n[Keyword Category Weights] (must sum to 1.0)")
        kw = self.keyword_weights
        total_kw = kw.anatomy + kw.pathology + kw.procedure + kw.imaging + kw.instruments
        print(f"  anatomy:     {kw.anatomy:.2f}")
        print(f"  pathology:   {kw.pathology:.2f}")
        print(f"  procedure:   {kw.procedure:.2f}  ← highest")
        print(f"  imaging:     {kw.imaging:.2f}")
        print(f"  instruments: {kw.instruments:.2f}  ← lowest")
        print(f"  TOTAL:       {total_kw:.2f}")
        
        print("\n[Association Weights] (must sum to 1.0)")
        aw = self.association_weights
        total_aw = aw.spatial_weight + aw.keyword_weight + aw.context_weight
        print(f"  spatial:  {aw.spatial_weight:.2f}")
        print(f"  keyword:  {aw.keyword_weight:.2f}")
        print(f"  context:  {aw.context_weight:.2f}")
        print(f"  TOTAL:    {total_aw:.2f}")
        
        print("\n[Caption Confidence Weights] (must sum to 1.0)")
        cc = self.caption_confidence
        total_cc = cc.pattern_weight + cc.proximity_weight + cc.formatting_weight + cc.length_weight
        print(f"  pattern:    {cc.pattern_weight:.2f}")
        print(f"  proximity:  {cc.proximity_weight:.2f}")
        print(f"  formatting: {cc.formatting_weight:.2f}")
        print(f"  length:     {cc.length_weight:.2f}")
        print(f"  TOTAL:      {total_cc:.2f}")
        
        print("=" * 60)
    
    @classmethod
    def from_dict(cls, data: dict) -> 'NeuroSynthEnhancedConfig':
        """Create configuration from dictionary."""
        return cls(**data)
    
    def to_dict(self) -> dict:
        """Export configuration to dictionary."""
        from dataclasses import asdict
        return asdict(self)


# =============================================================================
# DEFAULT INSTANCE
# =============================================================================

DEFAULT_CONFIG = NeuroSynthEnhancedConfig()


# =============================================================================
# QUICK VALIDATION TEST
# =============================================================================

if __name__ == "__main__":
    config = NeuroSynthEnhancedConfig()
    config.print_weights_summary()
    print("\n✅ All weights validated successfully")
