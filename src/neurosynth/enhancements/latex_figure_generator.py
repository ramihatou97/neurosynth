"""
Enhanced LaTeX Figure Generator
================================
Generate publication-quality LaTeX figure code:
- Single figures with captions
- Subfigure groups
- Procedural step sequences
- Comparison figures (side-by-side)
- Auto-pagination for long sequences

Version: 3.0
"""

import re
import logging
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Tuple, Any
from enum import Enum

from .config import LaTeXConfig, NeuroSynthEnhancedConfig
from .latex_validator import LaTeXValidator, escape_latex, sanitize_label

logger = logging.getLogger(__name__)


# =============================================================================
# DATA STRUCTURES
# =============================================================================

class FigureLayout(Enum):
    """Figure layout types."""
    SINGLE = "single"
    SUBFIGURES = "subfigures"
    PROCEDURAL = "procedural"
    COMPARISON = "comparison"
    GRID = "grid"


@dataclass
class FigureImage:
    """A single image in a figure."""
    path: str
    caption: str = ""
    label: str = ""
    width: float = 1.0  # Fraction of available width
    
    # Optional metadata
    subfigure_id: Optional[str] = None  # (a), (b), etc.
    step_number: Optional[int] = None


@dataclass
class FigureSpec:
    """Specification for a complete figure."""
    images: List[FigureImage]
    main_caption: str
    main_label: str
    layout: FigureLayout = FigureLayout.SINGLE
    
    # Layout options
    columns: int = 2
    placement: str = "htbp"
    
    # Metadata
    figure_number: Optional[str] = None
    chapter: Optional[str] = None
    
    def to_dict(self) -> dict:
        return {
            'images': len(self.images),
            'caption': self.main_caption[:50],
            'label': self.main_label,
            'layout': self.layout.value,
            'columns': self.columns,
        }


@dataclass
class GeneratedFigure:
    """Result of figure generation."""
    latex_code: str
    spec: FigureSpec
    is_valid: bool = True
    validation_errors: List[str] = field(default_factory=list)
    page_breaks: int = 0  # For multi-page sequences


# =============================================================================
# LATEX CODE BUILDERS
# =============================================================================

class SingleFigureBuilder:
    """Build single figure LaTeX code."""
    
    def __init__(self, config: LaTeXConfig):
        self.config = config
    
    def build(self, spec: FigureSpec) -> str:
        """Generate LaTeX for a single figure."""
        if not spec.images:
            return ""
        
        image = spec.images[0]
        
        # Calculate width
        width = f"{image.width}\\textwidth"
        
        lines = [
            f"\\begin{{figure}}[{spec.placement}]",
            "    \\centering",
            f"    \\includegraphics[width={width}]{{{self._format_path(image.path)}}}",
            f"    \\caption{{{escape_latex(spec.main_caption)}}}",
            f"    \\label{{{spec.main_label}}}",
            "\\end{figure}",
        ]
        
        return '\n'.join(lines)
    
    def _format_path(self, path: str) -> str:
        """Format image path for LaTeX."""
        # Ensure forward slashes
        path = path.replace('\\', '/')
        
        # Add base path if not absolute
        if not path.startswith('/') and not path.startswith(self.config.image_base_path):
            path = self.config.image_base_path + path
        
        return path


class SubfigureBuilder:
    """Build subfigure LaTeX code."""
    
    def __init__(self, config: LaTeXConfig):
        self.config = config
    
    def build(self, spec: FigureSpec) -> str:
        """Generate LaTeX for subfigures."""
        if not spec.images:
            return ""
        
        lines = [
            f"\\begin{{figure}}[{spec.placement}]",
            "    \\centering",
        ]
        
        # Calculate subfigure width based on columns
        subfig_width = 0.95 / spec.columns
        
        for i, image in enumerate(spec.images):
            # Start subfigure
            lines.append(f"    \\begin{{subfigure}}[b]{{{subfig_width:.2f}\\textwidth}}")
            lines.append("        \\centering")
            
            # Image
            img_path = self._format_path(image.path)
            lines.append(f"        \\includegraphics[width=\\textwidth]{{{img_path}}}")
            
            # Subfigure caption
            subcaption = image.caption or f"({chr(ord('a') + i)})"
            lines.append(f"        \\caption{{{escape_latex(subcaption)}}}")
            
            # Subfigure label
            if image.label:
                lines.append(f"        \\label{{{image.label}}}")
            
            lines.append("    \\end{subfigure}")
            
            # Add spacing
            if (i + 1) % spec.columns == 0 and i < len(spec.images) - 1:
                lines.append(self.config.row_spacing)
            elif i < len(spec.images) - 1:
                lines.append(f"    {self.config.subfigure_spacing}")
        
        # Main caption and label
        lines.append(f"    \\caption{{{escape_latex(spec.main_caption)}}}")
        lines.append(f"    \\label{{{spec.main_label}}}")
        lines.append("\\end{figure}")
        
        return '\n'.join(lines)
    
    def _format_path(self, path: str) -> str:
        path = path.replace('\\', '/')
        if not path.startswith('/') and not path.startswith(self.config.image_base_path):
            path = self.config.image_base_path + path
        return path


class ProceduralSequenceBuilder:
    """Build procedural sequence LaTeX code with pagination."""
    
    def __init__(self, config: LaTeXConfig):
        self.config = config
    
    def build(self, spec: FigureSpec) -> Tuple[str, int]:
        """
        Generate LaTeX for procedural sequence.
        
        Returns:
            (latex_code, page_break_count)
        """
        if not spec.images:
            return "", 0
        
        # Split into pages if needed
        max_per_page = self.config.max_steps_per_page
        pages = []
        
        for i in range(0, len(spec.images), max_per_page):
            page_images = spec.images[i:i + max_per_page]
            pages.append(page_images)
        
        all_latex = []
        
        for page_idx, page_images in enumerate(pages):
            is_continuation = page_idx > 0
            is_final = page_idx == len(pages) - 1
            
            latex = self._build_page(
                page_images, spec, page_idx, 
                is_continuation, is_final
            )
            all_latex.append(latex)
        
        # Join pages with pagebreak
        page_breaks = len(pages) - 1
        full_latex = '\n\n\\clearpage\n\n'.join(all_latex)
        
        return full_latex, page_breaks
    
    def _build_page(
        self,
        images: List[FigureImage],
        spec: FigureSpec,
        page_idx: int,
        is_continuation: bool,
        is_final: bool
    ) -> str:
        """Build a single page of the sequence."""
        # Use 'p' placement for procedural figures
        placement = self.config.procedure_placement
        
        lines = [
            f"\\begin{{figure}}[{placement}]",
            "    \\centering",
        ]
        
        # Calculate layout (typically 2 columns)
        columns = min(spec.columns, 3)
        subfig_width = 0.95 / columns
        
        for i, image in enumerate(images):
            lines.append(f"    \\begin{{subfigure}}[b]{{{subfig_width:.2f}\\textwidth}}")
            lines.append("        \\centering")
            
            # Image
            img_path = self._format_path(image.path)
            lines.append(f"        \\includegraphics[width=\\textwidth]{{{img_path}}}")
            
            # Step label
            step_num = image.step_number or (page_idx * self.config.max_steps_per_page + i + 1)
            step_label = self.config.step_label_format.format(num=step_num)
            
            if image.caption:
                subcaption = f"{step_label}: {escape_latex(image.caption)}"
            else:
                subcaption = step_label
            
            lines.append(f"        \\caption{{{subcaption}}}")
            
            if image.label:
                lines.append(f"        \\label{{{image.label}}}")
            
            lines.append("    \\end{subfigure}")
            
            # Row break
            if (i + 1) % columns == 0 and i < len(images) - 1:
                lines.append(self.config.row_spacing)
            elif i < len(images) - 1:
                lines.append(f"    {self.config.subfigure_spacing}")
        
        # Caption
        caption = spec.main_caption
        if is_continuation:
            caption += " (continued)"
        
        lines.append(f"    \\caption{{{escape_latex(caption)}}}")
        
        # Label only on first page
        if page_idx == 0:
            lines.append(f"    \\label{{{spec.main_label}}}")
        
        lines.append("\\end{figure}")
        
        return '\n'.join(lines)
    
    def _format_path(self, path: str) -> str:
        path = path.replace('\\', '/')
        if not path.startswith('/') and not path.startswith(self.config.image_base_path):
            path = self.config.image_base_path + path
        return path


class ComparisonFigureBuilder:
    """Build side-by-side comparison figures."""
    
    def __init__(self, config: LaTeXConfig):
        self.config = config
    
    def build(self, spec: FigureSpec) -> str:
        """Generate LaTeX for comparison figure."""
        if len(spec.images) < 2:
            # Fall back to single figure
            return SingleFigureBuilder(self.config).build(spec)
        
        lines = [
            f"\\begin{{figure}}[{spec.placement}]",
            "    \\centering",
        ]
        
        # Two images side by side
        for i, image in enumerate(spec.images[:2]):
            lines.append("    \\begin{subfigure}[b]{0.48\\textwidth}")
            lines.append("        \\centering")
            
            img_path = self._format_path(image.path)
            lines.append(f"        \\includegraphics[width=\\textwidth]{{{img_path}}}")
            
            # Labels like "Pre-operative" / "Post-operative" or "Before" / "After"
            default_labels = ["(a)", "(b)"]
            subcaption = image.caption or default_labels[i]
            lines.append(f"        \\caption{{{escape_latex(subcaption)}}}")
            
            if image.label:
                lines.append(f"        \\label{{{image.label}}}")
            
            lines.append("    \\end{subfigure}")
            
            if i == 0:
                lines.append("    \\hfill")
        
        lines.append(f"    \\caption{{{escape_latex(spec.main_caption)}}}")
        lines.append(f"    \\label{{{spec.main_label}}}")
        lines.append("\\end{figure}")
        
        return '\n'.join(lines)
    
    def _format_path(self, path: str) -> str:
        path = path.replace('\\', '/')
        if not path.startswith('/') and not path.startswith(self.config.image_base_path):
            path = self.config.image_base_path + path
        return path


# =============================================================================
# MAIN GENERATOR
# =============================================================================

class EnhancedLaTeXFigureGenerator:
    """
    Generate publication-quality LaTeX figure code.
    """
    
    def __init__(self, config: NeuroSynthEnhancedConfig = None):
        cfg = config or NeuroSynthEnhancedConfig()
        self.config = cfg.latex
        self.validator = LaTeXValidator(cfg)
        
        # Initialize builders
        self._builders = {
            FigureLayout.SINGLE: SingleFigureBuilder(self.config),
            FigureLayout.SUBFIGURES: SubfigureBuilder(self.config),
            FigureLayout.PROCEDURAL: ProceduralSequenceBuilder(self.config),
            FigureLayout.COMPARISON: ComparisonFigureBuilder(self.config),
            FigureLayout.GRID: SubfigureBuilder(self.config),  # Same as subfigures
        }
    
    def generate(
        self,
        spec: FigureSpec,
        validate: bool = True
    ) -> GeneratedFigure:
        """
        Generate LaTeX code from figure specification.
        
        Args:
            spec: Figure specification
            validate: Whether to validate generated code
            
        Returns:
            GeneratedFigure with code and validation results
        """
        builder = self._builders.get(spec.layout)
        if not builder:
            builder = self._builders[FigureLayout.SINGLE]
        
        # Generate code
        page_breaks = 0
        if spec.layout == FigureLayout.PROCEDURAL:
            latex_code, page_breaks = builder.build(spec)
        else:
            latex_code = builder.build(spec)
        
        # Validate if requested
        is_valid = True
        errors = []
        
        if validate and latex_code:
            result = self.validator.validate_figure(latex_code)
            is_valid = result.is_valid
            errors = [issue.message for issue in result.errors]
        
        return GeneratedFigure(
            latex_code=latex_code,
            spec=spec,
            is_valid=is_valid,
            validation_errors=errors,
            page_breaks=page_breaks
        )
    
    def generate_single(
        self,
        image_path: str,
        caption: str,
        label: str = None,
        width: float = 0.8
    ) -> GeneratedFigure:
        """Convenience method for single figure."""
        if not label:
            label = "fig:" + sanitize_label(caption[:30])
        
        spec = FigureSpec(
            images=[FigureImage(path=image_path, width=width)],
            main_caption=caption,
            main_label=label,
            layout=FigureLayout.SINGLE
        )
        
        return self.generate(spec)
    
    def generate_subfigures(
        self,
        images: List[Dict[str, Any]],
        main_caption: str,
        main_label: str = None,
        columns: int = 2
    ) -> GeneratedFigure:
        """
        Generate subfigure group.
        
        Args:
            images: List of dicts with 'path', 'caption' keys
            main_caption: Overall figure caption
            main_label: Figure label
            columns: Number of columns
        """
        if not main_label:
            main_label = "fig:" + sanitize_label(main_caption[:30])
        
        fig_images = []
        for i, img in enumerate(images):
            subfig_label = f"{main_label}_{chr(ord('a') + i)}"
            fig_images.append(FigureImage(
                path=img.get('path', ''),
                caption=img.get('caption', ''),
                label=subfig_label,
                subfigure_id=chr(ord('a') + i)
            ))
        
        spec = FigureSpec(
            images=fig_images,
            main_caption=main_caption,
            main_label=main_label,
            layout=FigureLayout.SUBFIGURES,
            columns=columns
        )
        
        return self.generate(spec)
    
    def generate_procedural_sequence(
        self,
        steps: List[Dict[str, Any]],
        procedure_title: str,
        label: str = None
    ) -> GeneratedFigure:
        """
        Generate procedural sequence.
        
        Args:
            steps: List of dicts with 'path', 'caption', 'step_number' keys
            procedure_title: Procedure name/caption
            label: Figure label
        """
        if not label:
            label = "fig:" + sanitize_label(procedure_title[:30])
        
        fig_images = []
        for i, step in enumerate(steps):
            step_num = step.get('step_number', i + 1)
            fig_images.append(FigureImage(
                path=step.get('path', ''),
                caption=step.get('caption', ''),
                label=f"{label}_step{step_num}",
                step_number=step_num
            ))
        
        spec = FigureSpec(
            images=fig_images,
            main_caption=procedure_title,
            main_label=label,
            layout=FigureLayout.PROCEDURAL,
            columns=2,
            placement=self.config.procedure_placement
        )
        
        return self.generate(spec)
    
    def generate_comparison(
        self,
        image_a: Dict[str, Any],
        image_b: Dict[str, Any],
        main_caption: str,
        label: str = None
    ) -> GeneratedFigure:
        """
        Generate comparison figure.
        
        Args:
            image_a: First image dict with 'path', 'caption'
            image_b: Second image dict
            main_caption: Overall caption
            label: Figure label
        """
        if not label:
            label = "fig:" + sanitize_label(main_caption[:30])
        
        fig_images = [
            FigureImage(
                path=image_a.get('path', ''),
                caption=image_a.get('caption', 'Before'),
                label=f"{label}_a"
            ),
            FigureImage(
                path=image_b.get('path', ''),
                caption=image_b.get('caption', 'After'),
                label=f"{label}_b"
            )
        ]
        
        spec = FigureSpec(
            images=fig_images,
            main_caption=main_caption,
            main_label=label,
            layout=FigureLayout.COMPARISON,
            columns=2
        )
        
        return self.generate(spec)
    
    def get_required_packages(self) -> List[str]:
        """Get LaTeX packages required for generated figures."""
        return [
            r"\usepackage{graphicx}",
            r"\usepackage{subcaption}",
            r"\usepackage{float}",
        ]
    
    def generate_preamble(self) -> str:
        """Generate LaTeX preamble for figure support."""
        packages = self.get_required_packages()
        return '\n'.join(packages)


# =============================================================================
# BATCH GENERATOR
# =============================================================================

class BatchFigureGenerator:
    """Generate LaTeX for multiple figures."""
    
    def __init__(self, config: NeuroSynthEnhancedConfig = None):
        self.generator = EnhancedLaTeXFigureGenerator(config)
    
    def generate_all(
        self,
        specs: List[FigureSpec]
    ) -> List[GeneratedFigure]:
        """Generate LaTeX for all specifications."""
        return [self.generator.generate(spec) for spec in specs]
    
    def generate_chapter(
        self,
        specs: List[FigureSpec],
        chapter_title: str
    ) -> str:
        """Generate complete chapter with figures."""
        lines = [
            f"% Figures for: {chapter_title}",
            "",
            self.generator.generate_preamble(),
            "",
        ]
        
        for i, spec in enumerate(specs):
            result = self.generator.generate(spec)
            
            if result.is_valid:
                lines.append(f"% Figure {i + 1}")
                lines.append(result.latex_code)
                lines.append("")
            else:
                lines.append(f"% Figure {i + 1} - VALIDATION ERRORS:")
                for error in result.validation_errors:
                    lines.append(f"%   {error}")
                lines.append("")
        
        return '\n'.join(lines)
    
    def export_to_file(
        self,
        specs: List[FigureSpec],
        output_path: str
    ):
        """Export all figures to a LaTeX file."""
        content = self.generate_chapter(specs, "Exported Figures")
        
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(content)
