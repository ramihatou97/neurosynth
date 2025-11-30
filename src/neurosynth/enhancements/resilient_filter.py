"""
Resilient Image Filter with Fallback Chain
===========================================
Provides robust image filtering with graceful degradation:
- Enhanced classifier (color/entropy analysis)
- Basic filter (simple heuristics)
- Permissive fallback (size-only)

Includes PIL-free fallback using pure PyMuPDF.

Version: 3.0
"""

import math
import hashlib
import logging
from dataclasses import dataclass
from typing import Tuple, Optional, Dict, List, Any
from io import BytesIO
from enum import Enum

from .config import (
    ImageFilterConfig,
    FilterFallbackLevel,
    ImageCategory,
    NeuroSynthEnhancedConfig
)

logger = logging.getLogger(__name__)

# Try to import PIL
try:
    from PIL import Image
    HAS_PIL = True
except ImportError:
    HAS_PIL = False
    logger.warning("PIL not available - using PyMuPDF fallback for image analysis")

# Import PyMuPDF
try:
    import fitz
    HAS_FITZ = True
except ImportError:
    HAS_FITZ = False
    logger.error("PyMuPDF not available - image analysis will be limited")


# =============================================================================
# RESULT STRUCTURES
# =============================================================================

@dataclass
class FilterResult:
    """Result of image filtering operation."""
    should_extract: bool
    confidence: float
    image_type: str
    fallback_level: FilterFallbackLevel
    features: Dict[str, Any]
    rejection_reason: Optional[str] = None
    
    def to_dict(self) -> dict:
        return {
            'should_extract': self.should_extract,
            'confidence': self.confidence,
            'image_type': self.image_type,
            'fallback_level': self.fallback_level.value,
            'features': self.features,
            'rejection_reason': self.rejection_reason,
        }


@dataclass
class ColorAnalysisResult:
    """Result of color distribution analysis."""
    grayscale_ratio: float
    dynamic_range: int
    unique_colors: int
    dominant_colors: List[Tuple[int, int, int]]
    analysis_method: str  # 'pil', 'pymupdf', 'bytes'


# =============================================================================
# COLOR ANALYSIS (PIL-FREE FALLBACK)
# =============================================================================

class ColorAnalyzer:
    """
    Analyze image color distribution with multiple fallback methods.
    Works with or without PIL installed.
    """
    
    def __init__(self, config: ImageFilterConfig = None):
        self.config = config or ImageFilterConfig()
    
    def analyze(
        self, 
        image_bytes: bytes,
        width: int = 0,
        height: int = 0,
        doc: 'fitz.Document' = None,
        xref: int = 0
    ) -> ColorAnalysisResult:
        """
        Analyze color distribution using best available method.
        
        Args:
            image_bytes: Raw image bytes
            width: Image width (if known)
            height: Image height (if known)
            doc: PyMuPDF document (for pixmap fallback)
            xref: Image xref (for pixmap fallback)
            
        Returns:
            ColorAnalysisResult
        """
        # Try PIL first
        if HAS_PIL:
            try:
                result = self._analyze_with_pil(image_bytes)
                if result:
                    return result
            except Exception as e:
                logger.debug(f"PIL analysis failed: {e}")
        
        # Try PyMuPDF pixmap
        if HAS_FITZ and doc and xref:
            try:
                result = self._analyze_with_pymupdf(doc, xref)
                if result:
                    return result
            except Exception as e:
                logger.debug(f"PyMuPDF analysis failed: {e}")
        
        # Fallback to raw bytes analysis
        return self._analyze_bytes_fallback(image_bytes)
    
    def _analyze_with_pil(self, image_bytes: bytes) -> Optional[ColorAnalysisResult]:
        """Analyze using PIL (most accurate)."""
        img = Image.open(BytesIO(image_bytes))
        img_rgb = img.convert('RGB')
        pixels = list(img_rgb.getdata())
        
        if not pixels:
            return None
        
        # Sample for performance
        sample_size = min(len(pixels), 10000)
        step = max(1, len(pixels) // sample_size)
        sampled = pixels[::step]
        
        # Grayscale ratio
        grayscale_count = sum(
            1 for r, g, b in sampled
            if abs(r - g) < 15 and abs(g - b) < 15 and abs(r - b) < 15
        )
        grayscale_ratio = grayscale_count / len(sampled)
        
        # Dynamic range
        intensities = [sum(p) // 3 for p in sampled]
        dynamic_range = max(intensities) - min(intensities) if intensities else 0
        
        # Unique colors (quantized)
        unique = set((r // 16, g // 16, b // 16) for r, g, b in sampled)
        unique_colors = len(unique) * 16
        
        # Dominant colors (simple histogram)
        from collections import Counter
        quantized = [(r // 32 * 32, g // 32 * 32, b // 32 * 32) for r, g, b in sampled]
        dominant = [c for c, _ in Counter(quantized).most_common(5)]
        
        return ColorAnalysisResult(
            grayscale_ratio=grayscale_ratio,
            dynamic_range=dynamic_range,
            unique_colors=unique_colors,
            dominant_colors=dominant,
            analysis_method='pil'
        )
    
    def _analyze_with_pymupdf(
        self, 
        doc: 'fitz.Document', 
        xref: int
    ) -> Optional[ColorAnalysisResult]:
        """Analyze using PyMuPDF pixmap (no PIL required)."""
        pix = fitz.Pixmap(doc, xref)
        
        try:
            samples = pix.samples
            n = pix.n  # Components per pixel
            
            if n < 3:
                # Grayscale image
                return ColorAnalysisResult(
                    grayscale_ratio=1.0,
                    dynamic_range=max(samples) - min(samples) if samples else 0,
                    unique_colors=len(set(samples)),
                    dominant_colors=[],
                    analysis_method='pymupdf_grayscale'
                )
            
            # RGB or RGBA
            pixel_count = len(samples) // n
            step = max(1, pixel_count // 5000)  # Sample ~5000 pixels
            
            grayscale_count = 0
            intensities = []
            colors = []
            
            for i in range(0, pixel_count, step):
                offset = i * n
                r, g, b = samples[offset], samples[offset + 1], samples[offset + 2]
                
                # Check grayscale
                if abs(r - g) < 15 and abs(g - b) < 15:
                    grayscale_count += 1
                
                intensities.append((r + g + b) // 3)
                colors.append((r // 32 * 32, g // 32 * 32, b // 32 * 32))
            
            sampled_count = pixel_count // step
            grayscale_ratio = grayscale_count / sampled_count if sampled_count else 0
            dynamic_range = max(intensities) - min(intensities) if intensities else 0
            
            # Count unique quantized colors
            from collections import Counter
            color_counts = Counter(colors)
            unique_colors = len(color_counts) * 32
            dominant = [c for c, _ in color_counts.most_common(5)]
            
            return ColorAnalysisResult(
                grayscale_ratio=grayscale_ratio,
                dynamic_range=dynamic_range,
                unique_colors=unique_colors,
                dominant_colors=dominant,
                analysis_method='pymupdf'
            )
            
        finally:
            pix = None  # Release pixmap
    
    def _analyze_bytes_fallback(self, image_bytes: bytes) -> ColorAnalysisResult:
        """
        Fallback analysis using raw bytes.
        Less accurate but always works.
        """
        # Sample bytes
        sample = image_bytes[:min(5000, len(image_bytes))]
        
        # Byte histogram
        histogram = [0] * 256
        for b in sample:
            histogram[b] += 1
        
        # Estimate dynamic range from histogram
        non_zero_indices = [i for i, h in enumerate(histogram) if h > 0]
        if non_zero_indices:
            dynamic_range = max(non_zero_indices) - min(non_zero_indices)
        else:
            dynamic_range = 0
        
        # Estimate unique "colors" from histogram spread
        unique_colors = len(non_zero_indices)
        
        return ColorAnalysisResult(
            grayscale_ratio=0.5,  # Unknown - assume mixed
            dynamic_range=dynamic_range,
            unique_colors=unique_colors,
            dominant_colors=[],
            analysis_method='bytes_fallback'
        )


# =============================================================================
# ENTROPY CALCULATOR
# =============================================================================

class EntropyCalculator:
    """Calculate Shannon entropy of image data."""
    
    @staticmethod
    def calculate(data: bytes) -> float:
        """
        Calculate Shannon entropy.
        
        Higher entropy = more information/detail
        Lower entropy = more uniform/simple
        
        Typical values:
        - Icons/simple graphics: 2-4
        - Diagrams: 4-6
        - Photographs/medical images: 6-8
        """
        if not data:
            return 0.0
        
        # Byte frequency
        freq = [0] * 256
        for byte in data:
            freq[byte] += 1
        
        # Entropy calculation
        total = len(data)
        entropy = 0.0
        for f in freq:
            if f > 0:
                p = f / total
                entropy -= p * math.log2(p)
        
        return entropy


# =============================================================================
# SURGICAL COLOR DETECTOR
# =============================================================================

class SurgicalColorDetector:
    """Detect surgical field colors in images."""
    
    def __init__(self, config: ImageFilterConfig = None):
        self.config = config or ImageFilterConfig()
        self.color_ranges = self.config.surgical_colors
    
    def detect(
        self, 
        image_bytes: bytes,
        doc: 'fitz.Document' = None,
        xref: int = 0
    ) -> float:
        """
        Calculate surgical color score.
        
        Returns:
            Score 0-1 indicating presence of surgical colors
        """
        if HAS_PIL:
            try:
                return self._detect_with_pil(image_bytes)
            except Exception:
                pass
        
        if HAS_FITZ and doc and xref:
            try:
                return self._detect_with_pymupdf(doc, xref)
            except Exception:
                pass
        
        return 0.0  # Cannot detect without image processing
    
    def _detect_with_pil(self, image_bytes: bytes) -> float:
        """Detect using PIL."""
        img = Image.open(BytesIO(image_bytes)).convert('RGB')
        pixels = list(img.getdata())
        
        sample_size = min(len(pixels), 5000)
        step = max(1, len(pixels) // sample_size)
        sampled = pixels[::step]
        
        return self._score_pixels(sampled)
    
    def _detect_with_pymupdf(self, doc: 'fitz.Document', xref: int) -> float:
        """Detect using PyMuPDF pixmap."""
        pix = fitz.Pixmap(doc, xref)
        
        try:
            if pix.n < 3:
                return 0.0  # Grayscale, no surgical colors
            
            samples = pix.samples
            n = pix.n
            pixel_count = len(samples) // n
            step = max(1, pixel_count // 5000)
            
            pixels = []
            for i in range(0, pixel_count, step):
                offset = i * n
                pixels.append((
                    samples[offset],
                    samples[offset + 1],
                    samples[offset + 2]
                ))
            
            return self._score_pixels(pixels)
            
        finally:
            pix = None
    
    def _score_pixels(self, pixels: List[Tuple[int, int, int]]) -> float:
        """Score pixels for surgical colors."""
        if not pixels:
            return 0.0
        
        surgical_matches = 0
        
        for r, g, b in pixels:
            # Blood/tissue colors (red spectrum)
            if 100 < r and g < 150 and b < 150:
                if r > g + 30 and r > b + 30:  # Distinctly red
                    surgical_matches += 1
            
            # Surgical drape (green)
            elif g > r and g > b and 50 < g < 180:
                if g > r + 20 and g > b + 20:  # Distinctly green
                    surgical_matches += 0.5
            
            # Steel instruments (gray)
            elif 150 < r < 230 and 150 < g < 230 and 150 < b < 230:
                if abs(r - g) < 20 and abs(g - b) < 20:  # Uniform gray
                    surgical_matches += 0.3
        
        return min(surgical_matches / len(pixels), 1.0)


# =============================================================================
# EDGE DENSITY ANALYZER
# =============================================================================

class EdgeDensityAnalyzer:
    """Analyze edge density to distinguish diagrams from photos."""
    
    def analyze(
        self, 
        image_bytes: bytes,
        doc: 'fitz.Document' = None,
        xref: int = 0
    ) -> float:
        """
        Calculate edge density.
        
        Returns:
            Score 0-1, higher = more edges/detail
        """
        if HAS_PIL:
            try:
                return self._analyze_with_pil(image_bytes)
            except Exception:
                pass
        
        if HAS_FITZ and doc and xref:
            try:
                return self._analyze_with_pymupdf(doc, xref)
            except Exception:
                pass
        
        return 0.5  # Unknown
    
    def _analyze_with_pil(self, image_bytes: bytes) -> float:
        """Analyze using PIL."""
        img = Image.open(BytesIO(image_bytes)).convert('L')
        pixels = list(img.getdata())
        width = img.width
        
        if width < 3 or len(pixels) < width * 3:
            return 0.0
        
        # Simple horizontal gradient detection
        edge_count = 0
        sample_rows = min(100, len(pixels) // width)
        
        for row in range(sample_rows):
            start = row * width
            for i in range(start, start + width - 1):
                if abs(pixels[i] - pixels[i + 1]) > 30:
                    edge_count += 1
        
        total_checked = sample_rows * (width - 1)
        return edge_count / total_checked if total_checked > 0 else 0.0
    
    def _analyze_with_pymupdf(self, doc: 'fitz.Document', xref: int) -> float:
        """Analyze using PyMuPDF pixmap."""
        pix = fitz.Pixmap(doc, xref)
        
        try:
            # Convert to grayscale if needed
            if pix.n > 1:
                pix = fitz.Pixmap(fitz.csGRAY, pix)
            
            samples = pix.samples
            width = pix.width
            height = pix.height
            
            if width < 3 or height < 3:
                return 0.0
            
            edge_count = 0
            sample_rows = min(100, height)
            row_step = max(1, height // sample_rows)
            
            for row_idx in range(0, height, row_step):
                row_start = row_idx * width
                for col in range(width - 1):
                    if abs(samples[row_start + col] - samples[row_start + col + 1]) > 30:
                        edge_count += 1
            
            rows_sampled = height // row_step
            total_checked = rows_sampled * (width - 1)
            return edge_count / total_checked if total_checked > 0 else 0.0
            
        finally:
            pix = None


# =============================================================================
# ENHANCED MEDICAL IMAGE CLASSIFIER
# =============================================================================

class EnhancedMedicalClassifier:
    """
    Advanced medical image classifier using multiple analysis methods.
    """
    
    def __init__(self, config: ImageFilterConfig = None):
        self.config = config or ImageFilterConfig()
        self.color_analyzer = ColorAnalyzer(config)
        self.entropy_calc = EntropyCalculator()
        self.surgical_detector = SurgicalColorDetector(config)
        self.edge_analyzer = EdgeDensityAnalyzer()
    
    def classify(
        self,
        image_bytes: bytes,
        width: int,
        height: int,
        doc: 'fitz.Document' = None,
        xref: int = 0,
        context_text: str = ""
    ) -> FilterResult:
        """
        Classify an image with full analysis.
        
        Args:
            image_bytes: Raw image bytes
            width: Image width
            height: Image height
            doc: PyMuPDF document (optional, for pixmap fallback)
            xref: Image xref (optional, for pixmap fallback)
            context_text: Surrounding text context
            
        Returns:
            FilterResult with classification
        """
        features = {}
        
        # Quick rejection checks
        rejection = self._quick_rejection_check(image_bytes, width, height)
        if rejection:
            return FilterResult(
                should_extract=False,
                confidence=0.0,
                image_type='rejected',
                fallback_level=FilterFallbackLevel.ENHANCED,
                features=features,
                rejection_reason=rejection
            )
        
        # Color analysis
        color_result = self.color_analyzer.analyze(image_bytes, width, height, doc, xref)
        features['color'] = {
            'grayscale_ratio': color_result.grayscale_ratio,
            'dynamic_range': color_result.dynamic_range,
            'unique_colors': color_result.unique_colors,
            'analysis_method': color_result.analysis_method,
        }
        
        is_grayscale = color_result.grayscale_ratio > self.config.radiological_grayscale_ratio
        features['is_grayscale'] = is_grayscale
        
        # Entropy analysis
        entropy = self.entropy_calc.calculate(image_bytes)
        features['entropy'] = entropy
        
        # Surgical color detection (only for non-grayscale)
        surgical_score = 0.0
        if not is_grayscale:
            surgical_score = self.surgical_detector.detect(image_bytes, doc, xref)
            features['surgical_color_score'] = surgical_score
        
        # Edge density
        edge_density = self.edge_analyzer.analyze(image_bytes, doc, xref)
        features['edge_density'] = edge_density
        
        # Classification scoring
        score = 0.0
        image_type = 'unknown'
        
        # Radiological indicators
        if is_grayscale:
            if entropy > 6.0:
                score += 0.3
                image_type = 'radiological'
            if color_result.dynamic_range > 150:
                score += 0.2
        
        # Surgical photo indicators
        if surgical_score > self.config.surgical_color_threshold:
            score += 0.4
            image_type = 'intraoperative'
        
        # Diagram indicators
        if not is_grayscale and entropy < self.config.diagram_max_entropy:
            if edge_density > self.config.diagram_min_edge_density:
                score += 0.3
                image_type = 'anatomical_diagram'
        
        # Size bonus
        area = width * height
        if area > 100000:
            score += 0.1
        if area > 250000:
            score += 0.1
        
        # Icon rejection
        if (entropy < self.config.icon_max_entropy and 
            area < self.config.icon_max_area and 
            color_result.unique_colors < self.config.icon_max_colors):
            return FilterResult(
                should_extract=False,
                confidence=0.0,
                image_type='icon',
                fallback_level=FilterFallbackLevel.ENHANCED,
                features=features,
                rejection_reason='likely_icon'
            )
        
        # Context boost
        if context_text:
            context_boost = self._calculate_context_boost(context_text)
            score += context_boost
            features['context_boost'] = context_boost
        
        return FilterResult(
            should_extract=score >= self.config.min_confidence,
            confidence=min(score, 1.0),
            image_type=image_type,
            fallback_level=FilterFallbackLevel.ENHANCED,
            features=features,
            rejection_reason=None if score >= self.config.min_confidence else 'low_confidence'
        )
    
    def _quick_rejection_check(
        self, 
        image_bytes: bytes, 
        width: int, 
        height: int
    ) -> Optional[str]:
        """Quick rejection checks before full analysis."""
        cfg = self.config
        
        if len(image_bytes) < cfg.min_bytes:
            return 'too_small_bytes'
        
        if width < cfg.min_dimension and height < cfg.min_dimension:
            return 'too_small_dimensions'
        
        if width * height < cfg.min_area:
            return 'too_small_area'
        
        aspect = width / height if height > 0 else 0
        if aspect > cfg.max_aspect_ratio or aspect < cfg.min_aspect_ratio:
            return 'extreme_aspect_ratio'
        
        return None
    
    def _calculate_context_boost(self, context_text: str) -> float:
        """Calculate confidence boost from context."""
        cfg = self.config
        text_lower = context_text.lower()
        boost = 0.0
        
        keywords = [
            'figure', 'image', 'scan', 'mri', 'ct', 'radiograph',
            'intraoperative', 'surgical', 'anatomy', 'histology',
            'microscopy', 'dissection', 'exposure', 'approach'
        ]
        
        for kw in keywords:
            if kw in text_lower:
                boost += cfg.context_keyword_boost
        
        return min(boost, cfg.context_max_boost)


# =============================================================================
# BASIC FILTER (FALLBACK)
# =============================================================================

class BasicImageFilter:
    """
    Basic image filter using simple heuristics.
    Fallback when enhanced classifier fails.
    """
    
    def __init__(self, config: ImageFilterConfig = None):
        self.config = config or ImageFilterConfig()
    
    def filter(
        self,
        image_bytes: bytes,
        width: int,
        height: int
    ) -> FilterResult:
        """Apply basic filtering."""
        cfg = self.config
        features = {}
        
        # Size checks
        if len(image_bytes) < cfg.min_bytes:
            return FilterResult(
                should_extract=False,
                confidence=0.0,
                image_type='unknown',
                fallback_level=FilterFallbackLevel.BASIC,
                features=features,
                rejection_reason='too_small_bytes'
            )
        
        if width < cfg.min_dimension and height < cfg.min_dimension:
            return FilterResult(
                should_extract=False,
                confidence=0.0,
                image_type='unknown',
                fallback_level=FilterFallbackLevel.BASIC,
                features=features,
                rejection_reason='too_small_dimensions'
            )
        
        # Aspect ratio
        aspect = width / height if height > 0 else 0
        if aspect > cfg.max_aspect_ratio or aspect < cfg.min_aspect_ratio:
            return FilterResult(
                should_extract=False,
                confidence=0.0,
                image_type='unknown',
                fallback_level=FilterFallbackLevel.BASIC,
                features=features,
                rejection_reason='extreme_aspect_ratio'
            )
        
        # Passed basic checks
        area = width * height
        confidence = 0.3
        if area > 50000:
            confidence += 0.1
        if area > 100000:
            confidence += 0.1
        if len(image_bytes) > 10000:
            confidence += 0.1
        
        features['area'] = area
        features['size_bytes'] = len(image_bytes)
        
        return FilterResult(
            should_extract=True,
            confidence=confidence,
            image_type='unknown',
            fallback_level=FilterFallbackLevel.BASIC,
            features=features,
            rejection_reason=None
        )


# =============================================================================
# PERMISSIVE FILTER (LAST RESORT)
# =============================================================================

class PermissiveFilter:
    """
    Permissive filter that only checks minimum size.
    Last resort fallback.
    """
    
    def filter(
        self,
        image_bytes: bytes,
        width: int,
        height: int
    ) -> FilterResult:
        """Apply permissive filtering."""
        # Only reject truly tiny images
        if width < 50 or height < 50:
            return FilterResult(
                should_extract=False,
                confidence=0.0,
                image_type='unknown',
                fallback_level=FilterFallbackLevel.PERMISSIVE,
                features={},
                rejection_reason='too_small'
            )
        
        return FilterResult(
            should_extract=True,
            confidence=0.2,  # Low confidence
            image_type='unknown',
            fallback_level=FilterFallbackLevel.PERMISSIVE,
            features={'permissive_pass': True},
            rejection_reason=None
        )


# =============================================================================
# RESILIENT FILTER (MAIN INTERFACE)
# =============================================================================

class ResilientImageFilter:
    """
    Resilient image filter with fallback chain.
    
    Tries in order:
    1. Enhanced classifier (full analysis)
    2. Basic filter (simple heuristics)
    3. Permissive filter (size-only)
    
    Gracefully handles failures at each level.
    """
    
    def __init__(self, config: NeuroSynthEnhancedConfig = None):
        self.config = config or NeuroSynthEnhancedConfig()
        
        # Initialize filter chain
        self.enhanced = EnhancedMedicalClassifier(self.config.image_filter)
        self.basic = BasicImageFilter(self.config.image_filter)
        self.permissive = PermissiveFilter()
        
        # Statistics
        self.stats = {
            'enhanced_success': 0,
            'enhanced_fail': 0,
            'basic_success': 0,
            'basic_fail': 0,
            'permissive_success': 0,
            'total_processed': 0,
        }
    
    def should_extract(
        self,
        image_bytes: bytes,
        width: int,
        height: int,
        doc: 'fitz.Document' = None,
        xref: int = 0,
        context_text: str = ""
    ) -> Tuple[bool, FilterResult]:
        """
        Determine if image should be extracted.
        
        Uses fallback chain for resilience.
        
        Args:
            image_bytes: Raw image bytes
            width: Image width
            height: Image height
            doc: PyMuPDF document (optional)
            xref: Image xref (optional)
            context_text: Surrounding text context
            
        Returns:
            Tuple of (should_extract, FilterResult)
        """
        self.stats['total_processed'] += 1
        
        # Try enhanced classifier
        if self.config.use_fallback_chain:
            try:
                result = self.enhanced.classify(
                    image_bytes, width, height, doc, xref, context_text
                )
                self.stats['enhanced_success'] += 1
                return result.should_extract, result
            except Exception as e:
                self.stats['enhanced_fail'] += 1
                if self.config.log_fallbacks:
                    logger.warning(f"Enhanced classifier failed: {e}")
            
            # Try basic filter
            try:
                result = self.basic.filter(image_bytes, width, height)
                self.stats['basic_success'] += 1
                return result.should_extract, result
            except Exception as e:
                self.stats['basic_fail'] += 1
                if self.config.log_fallbacks:
                    logger.warning(f"Basic filter failed: {e}")
            
            # Permissive fallback
            result = self.permissive.filter(image_bytes, width, height)
            self.stats['permissive_success'] += 1
            return result.should_extract, result
        
        else:
            # No fallback - enhanced only
            result = self.enhanced.classify(
                image_bytes, width, height, doc, xref, context_text
            )
            return result.should_extract, result
    
    def get_stats(self) -> dict:
        """Get filter statistics."""
        return dict(self.stats)
    
    def reset_stats(self):
        """Reset statistics."""
        for key in self.stats:
            self.stats[key] = 0
