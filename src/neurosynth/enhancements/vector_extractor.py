"""
Vector Graphics Extractor for NeuroSynth
=========================================
Extracts vector graphics (flowcharts, diagrams, schematics) from PDF drawing commands.

Uses PyMuPDF's drawing API to identify complex vector paths, clusters them spatially,
classifies the type, and renders to PNG images.

Version: 1.0
"""

import logging
import uuid
import re
from dataclasses import dataclass, field
from typing import List, Tuple, Dict, Set, Optional
from collections import defaultdict

try:
    import fitz
    import numpy as np
    HAS_DEPENDENCIES = True
except ImportError:
    HAS_DEPENDENCIES = False

from .config import NeuroSynthEnhancedConfig

logger = logging.getLogger(__name__)


# =============================================================================
# DATA STRUCTURES
# =============================================================================

@dataclass
class VectorGraphic:
    """
    Represents a vector graphic extracted from a PDF page.

    Vector graphics include flowcharts, anatomical diagrams, and schematics
    that are defined by drawing commands rather than raster images.
    """
    graphic_id: str                                  # Unique identifier
    page_number: int                                 # Source page (0-indexed in PyMuPDF)
    bbox: Tuple[float, float, float, float]          # Bounding box (x0, y0, x1, y1)
    graphic_type: str                                # "flowchart", "diagram", "schematic", "unknown"
    confidence: float                                # Classification confidence (0-1)
    rendered_image: Optional[bytes] = None           # PNG render at configured DPI
    num_paths: int = 0                               # Number of drawing paths
    has_text: bool = False                           # Whether contains text elements
    contains_arrows: bool = False                    # Arrow detection (indicates flowchart)
    keywords_found: List[str] = field(default_factory=list)  # Matched keywords


# =============================================================================
# VECTOR GRAPHICS EXTRACTOR
# =============================================================================

class VectorGraphicsExtractor:
    """
    Extracts vector graphics from PDF pages using drawing command analysis.

    Algorithm:
    1. Extract drawing commands from page
    2. Filter by complexity (min paths threshold)
    3. Spatial clustering using grid-based grouping
    4. Type classification via keyword matching
    5. Arrow detection for flowchart identification
    6. Render clusters to PNG images

    Configuration comes from NeuroSynthEnhancedConfig.vector_graphics
    """

    def __init__(self, config: NeuroSynthEnhancedConfig):
        """
        Initialize extractor with configuration.

        Args:
            config: Master configuration object containing vector_graphics settings
        """
        if not HAS_DEPENDENCIES:
            raise ImportError("PyMuPDF (fitz) and numpy required for vector extraction")

        self.config = config
        self.vg_config = config.vector_graphics

        # Extract thresholds from config
        self.min_paths = self.vg_config.min_vector_paths
        self.min_complexity = self.vg_config.min_path_complexity
        self.grid_size = self.vg_config.grid_size
        self.merge_distance = self.vg_config.merge_distance
        self.render_dpi = self.vg_config.render_dpi

        # Keywords for classification
        self.flowchart_keywords = set(
            kw.lower() for kw in self.vg_config.flowchart_keywords
        )
        self.diagram_keywords = set(
            kw.lower() for kw in self.vg_config.diagram_keywords
        )

        logger.info(
            f"VectorGraphicsExtractor initialized: "
            f"min_paths={self.min_paths}, "
            f"min_complexity={self.min_complexity}, "
            f"grid_size={self.grid_size}px"
        )

    def extract_from_page(
        self,
        page: fitz.Page,
        page_num: int,
        context_text: str = ""
    ) -> List[VectorGraphic]:
        """
        Extract vector graphics from a single page.

        Args:
            page: PyMuPDF Page object
            page_num: Page number (0-indexed)
            context_text: Surrounding text for keyword classification

        Returns:
            List of VectorGraphic objects found on the page
        """
        try:
            # Step 1: Get drawing commands
            drawings = page.get_drawings()
            if not drawings:
                logger.debug(f"Page {page_num}: No drawings found")
                return []

            logger.debug(f"Page {page_num}: Found {len(drawings)} drawing commands")

            # Step 2: Filter by complexity
            complex_paths = self._filter_complex_paths(drawings)
            if not complex_paths:
                logger.debug(f"Page {page_num}: No complex paths after filtering")
                return []

            # Step 3: Spatial clustering
            clusters = self._cluster_nearby_paths(complex_paths, page.rect)
            if not clusters:
                logger.debug(f"Page {page_num}: No clusters formed")
                return []

            logger.debug(
                f"Page {page_num}: Formed {len(clusters)} clusters from "
                f"{len(complex_paths)} complex paths"
            )

            # Step 4: Convert clusters to VectorGraphic objects
            vector_graphics = []
            for cluster_idx, cluster in enumerate(clusters):
                # Create bounding box
                bbox = self._compute_cluster_bbox(cluster)

                # Detect arrows
                contains_arrows = self._detect_arrows(cluster)

                # Classify type
                graphic_type, confidence, matched_keywords = self._classify_graphic_type(
                    context_text, contains_arrows
                )

                # Generate unique ID
                graphic_id = f"vec_{page_num:03d}_{cluster_idx:02d}_{uuid.uuid4().hex[:8]}"

                # Render to image
                rendered_image = self._render_cluster_to_image(
                    page, cluster, bbox
                )

                # Create VectorGraphic object
                vector_graphic = VectorGraphic(
                    graphic_id=graphic_id,
                    page_number=page_num,
                    bbox=bbox,
                    graphic_type=graphic_type,
                    confidence=confidence,
                    rendered_image=rendered_image,
                    num_paths=len(cluster),
                    has_text=False,  # Would need text extraction to determine
                    contains_arrows=contains_arrows,
                    keywords_found=matched_keywords
                )

                vector_graphics.append(vector_graphic)

            logger.info(
                f"Page {page_num}: Extracted {len(vector_graphics)} vector graphics"
            )
            return vector_graphics

        except Exception as e:
            logger.error(f"Page {page_num}: Vector extraction failed: {e}", exc_info=True)
            return []

    def _filter_complex_paths(
        self,
        drawings: List[Dict]
    ) -> List[Dict]:
        """
        Filter drawing commands by complexity.

        Complexity is measured by number of drawing operations (lines, curves).
        Simple paths (few operations) are likely decorative and filtered out.

        Args:
            drawings: List of drawing dictionaries from page.get_drawings()

        Returns:
            List of complex drawing paths
        """
        complex_paths = []

        for drawing in drawings:
            # Count drawing operations
            num_operations = len(drawing.get('items', []))

            # Filter by complexity threshold
            if num_operations >= self.min_complexity:
                complex_paths.append(drawing)

        return complex_paths

    def _cluster_nearby_paths(
        self,
        paths: List[Dict],
        page_rect: fitz.Rect
    ) -> List[List[Dict]]:
        """
        Cluster paths that are spatially close using grid-based grouping.

        Algorithm:
        1. Divide page into grid cells
        2. Assign each path to grid cell based on centroid
        3. Merge adjacent cells containing paths
        4. Filter clusters by path count threshold

        Args:
            paths: List of drawing paths
            page_rect: Page bounding rectangle

        Returns:
            List of path clusters (each cluster is a list of paths)
        """
        if not paths:
            return []

        # Create grid
        page_width = page_rect.width
        page_height = page_rect.height
        grid_cols = int(np.ceil(page_width / self.grid_size))
        grid_rows = int(np.ceil(page_height / self.grid_size))

        # Assign paths to grid cells
        grid = defaultdict(list)

        for path in paths:
            # Get path bounding box
            path_rect = path.get('rect')
            if not path_rect:
                continue

            # Compute centroid
            centroid_x = (path_rect.x0 + path_rect.x1) / 2
            centroid_y = (path_rect.y0 + path_rect.y1) / 2

            # Map to grid cell
            col = int(centroid_x / self.grid_size)
            row = int(centroid_y / self.grid_size)

            # Clamp to grid bounds
            col = max(0, min(col, grid_cols - 1))
            row = max(0, min(row, grid_rows - 1))

            grid[(row, col)].append(path)

        # Merge adjacent cells (simple flood fill)
        visited = set()
        clusters = []

        def flood_fill(r, c):
            """Recursively collect connected cells."""
            if (r, c) in visited or (r, c) not in grid:
                return []

            visited.add((r, c))
            cluster_paths = list(grid[(r, c)])

            # Check 8 neighbors
            for dr in [-1, 0, 1]:
                for dc in [-1, 0, 1]:
                    if dr == 0 and dc == 0:
                        continue
                    nr, nc = r + dr, c + dc
                    if (nr, nc) in grid and (nr, nc) not in visited:
                        # Check if within merge distance
                        # (simplified: if adjacent in grid, merge)
                        cluster_paths.extend(flood_fill(nr, nc))

            return cluster_paths

        # Create clusters from connected grid cells
        for (row, col), cell_paths in grid.items():
            if (row, col) not in visited:
                cluster = flood_fill(row, col)
                if len(cluster) >= self.min_paths:
                    clusters.append(cluster)

        return clusters

    def _compute_cluster_bbox(
        self,
        cluster: List[Dict]
    ) -> Tuple[float, float, float, float]:
        """
        Compute bounding box for a cluster of paths.

        Args:
            cluster: List of path dictionaries

        Returns:
            Tuple (x0, y0, x1, y1) representing bounding box
        """
        if not cluster:
            return (0, 0, 0, 0)

        x0 = float('inf')
        y0 = float('inf')
        x1 = float('-inf')
        y1 = float('-inf')

        for path in cluster:
            rect = path.get('rect')
            if rect:
                x0 = min(x0, rect.x0)
                y0 = min(y0, rect.y0)
                x1 = max(x1, rect.x1)
                y1 = max(y1, rect.y1)

        # Handle edge case where no rects found
        if x0 == float('inf'):
            return (0, 0, 0, 0)

        return (x0, y0, x1, y1)

    def _detect_arrows(
        self,
        cluster: List[Dict]
    ) -> bool:
        """
        Detect if cluster contains arrow shapes (indicates flowchart).

        Arrows are identified by:
        1. Line segments with specific angular relationships
        2. Triangular fill shapes at line ends
        3. Multiple connected paths forming arrow shape

        This is a simplified heuristic; robust arrow detection would need
        deeper geometric analysis.

        Args:
            cluster: List of path dictionaries

        Returns:
            True if arrows detected, False otherwise
        """
        # Simplified heuristic: check for triangular fills
        # (arrow heads are often rendered as filled triangles)
        for path in cluster:
            items = path.get('items', [])
            for item in items:
                # Check if item is a filled path (potential arrow head)
                if item[0] == 'f':  # 'f' = fill operation in PyMuPDF
                    # If we find filled shapes, consider it potentially an arrow
                    # More sophisticated detection would analyze geometry
                    return True

        return False

    def _classify_graphic_type(
        self,
        context_text: str,
        contains_arrows: bool
    ) -> Tuple[str, float, List[str]]:
        """
        Classify graphic type using keyword matching and arrow detection.

        Classification hierarchy:
        1. If arrows detected + flowchart keywords → "flowchart" (high confidence)
        2. If flowchart keywords only → "flowchart" (medium confidence)
        3. If diagram keywords → "diagram" (medium confidence)
        4. Otherwise → "schematic" (low confidence)

        Args:
            context_text: Surrounding text for keyword matching
            contains_arrows: Whether arrows were detected in geometry

        Returns:
            Tuple of (graphic_type, confidence, matched_keywords)
        """
        context_lower = context_text.lower()

        # Check for keywords
        flowchart_matches = [
            kw for kw in self.flowchart_keywords
            if kw in context_lower
        ]
        diagram_matches = [
            kw for kw in self.diagram_keywords
            if kw in context_lower
        ]

        matched_keywords = flowchart_matches + diagram_matches

        # Classification logic
        if contains_arrows and flowchart_matches:
            return ("flowchart", 0.85, matched_keywords)
        elif flowchart_matches:
            return ("flowchart", 0.65, matched_keywords)
        elif diagram_matches:
            return ("diagram", 0.70, matched_keywords)
        elif contains_arrows:
            # Arrows without keywords suggest flowchart
            return ("flowchart", 0.50, [])
        else:
            return ("schematic", 0.40, [])

    def _render_cluster_to_image(
        self,
        page: fitz.Page,
        cluster: List[Dict],
        bbox: Tuple[float, float, float, float]
    ) -> Optional[bytes]:
        """
        Render a cluster region to PNG image.

        Uses PyMuPDF's pixmap rendering to capture the vector graphics
        as a raster image at the configured DPI.

        Args:
            page: PyMuPDF Page object
            cluster: List of paths in cluster (not directly used, kept for extensibility)
            bbox: Bounding box to render (x0, y0, x1, y1)

        Returns:
            PNG image bytes, or None if rendering failed
        """
        try:
            x0, y0, x1, y1 = bbox

            # Validate bbox
            if x1 <= x0 or y1 <= y0:
                logger.warning(f"Invalid bbox for rendering: {bbox}")
                return None

            # Create clip rect with small padding
            padding = 10
            clip_rect = fitz.Rect(
                max(0, x0 - padding),
                max(0, y0 - padding),
                x1 + padding,
                y1 + padding
            )

            # Compute zoom factor for desired DPI
            # Standard PDF DPI is 72, scale to render_dpi
            zoom = self.render_dpi / 72.0
            mat = fitz.Matrix(zoom, zoom)

            # Render page region to pixmap
            pix = page.get_pixmap(
                matrix=mat,
                clip=clip_rect,
                alpha=False  # No transparency
            )

            # Convert to PNG bytes
            png_bytes = pix.tobytes("png")

            logger.debug(
                f"Rendered vector graphic: {pix.width}x{pix.height}px, "
                f"{len(png_bytes)} bytes"
            )

            return png_bytes

        except Exception as e:
            logger.error(f"Failed to render cluster: {e}", exc_info=True)
            return None


# =============================================================================
# MODULE EXPORTS
# =============================================================================

__all__ = [
    'VectorGraphic',
    'VectorGraphicsExtractor',
]
