"""LaTeX document generator."""

import re
import shutil
import subprocess
from pathlib import Path
from typing import TYPE_CHECKING, Any

from jinja2 import Environment, PackageLoader, select_autoescape
from rich.console import Console

from neurosynth.models.document import Source
from neurosynth.models.output import Chapter, Section

if TYPE_CHECKING:
    from neurosynth.models.visual import FigurePlate, VisualElement

console = Console()


class LaTeXGenerator:
    """Generate LaTeX documents from synthesized chapters."""

    # Figure counter for unique labels
    _figure_counter: int = 0

    def __init__(self, template_dir: Path | None = None, images_dir: Path | None = None):
        """Initialize the LaTeX generator.

        Args:
            template_dir: Custom template directory (optional)
            images_dir: Directory to copy images for LaTeX compilation
        """
        # Initialize Jinja2 environment
        if template_dir and template_dir.exists():
            from jinja2 import FileSystemLoader

            self.env = Environment(
                loader=FileSystemLoader(str(template_dir)),
                autoescape=select_autoescape(["tex"]),
            )
        else:
            # Use built-in templates
            self.env = Environment(
                loader=PackageLoader("neurosynth", "latex/templates"),
                autoescape=False,  # Don't escape for LaTeX
            )

        # Directory for images during compilation
        self.images_dir = images_dir

        # Custom filters for LaTeX
        self.env.filters["latex_escape"] = self._latex_escape
        self.env.filters["citation"] = self._format_citation
        self.env.filters["figure"] = self._format_figure

    def generate_latex(self, chapter: Chapter, output_dir: Path | None = None) -> str:
        """Generate complete LaTeX document.

        Args:
            chapter: The chapter to generate LaTeX for
            output_dir: Output directory for copying images (optional)

        Returns:
            LaTeX document as string
        """
        template = self._get_chapter_template()

        # Reset figure counter
        LaTeXGenerator._figure_counter = 0

        # Collect visuals from all sections
        chapter.collect_all_visuals()

        # Debug: Log figure collection status
        console.print(f"[dim]Figure collection: {chapter.total_figures} total figures[/dim]")
        for section in chapter.sections:
            if section.inline_figures or section.figure_plate:
                inline_count = len(section.inline_figures) if section.inline_figures else 0
                plate_count = len(section.figure_plate.figures) if section.figure_plate else 0
                console.print(f"[dim]  {section.title}: {inline_count} inline, {plate_count} in plate[/dim]")

        # Prepare images directory for compilation
        if output_dir and self.images_dir is None:
            self.images_dir = output_dir / "figures"

        if self.images_dir:
            self.images_dir.mkdir(parents=True, exist_ok=True)

        # Prepare context
        context = {
            "title": self._latex_escape(chapter.title),
            "abstract": self._latex_escape(chapter.abstract),
            "keywords": [self._latex_escape(k) for k in chapter.keywords],
            "sections": [self._prepare_section(s) for s in chapter.sections],
            "bibliography": [self._prepare_source(s) for s in chapter.bibliography],
            "total_words": chapter.total_words,
            "total_sources": chapter.total_sources,
            "total_figures": chapter.total_figures,
            "has_figures": chapter.total_figures > 0,
        }

        return template.render(**context)

    def generate_to_file(
        self,
        chapter: Chapter,
        output_path: Path,
    ) -> Path:
        """Generate LaTeX and save to file."""
        # Set images directory relative to output
        self.images_dir = output_path.parent / "figures"

        latex_content = self.generate_latex(chapter, output_dir=output_path.parent)

        # Ensure .tex extension
        if output_path.suffix != ".tex":
            output_path = output_path.with_suffix(".tex")

        output_path.write_text(latex_content, encoding="utf-8")
        console.print(f"[green]LaTeX saved to: {output_path}[/green]")

        if self.images_dir.exists() and any(self.images_dir.iterdir()):
            console.print(f"[green]Figures saved to: {self.images_dir}[/green]")

        return output_path

    def compile_to_pdf(
        self,
        tex_path: Path,
        output_dir: Path | None = None,
        validate: bool = True,
    ) -> Path:
        """Compile LaTeX to PDF with validation.

        Args:
            tex_path: Path to .tex file
            output_dir: Output directory
            validate: Whether to validate PDF after compilation

        Returns:
            Path to compiled PDF

        Raises:
            LaTeXCompilationError: If compilation fails
            PDFValidationError: If validation fails
            FileNotFoundError: If pdflatex not found
        """
        import logging

        from neurosynth.latex.exceptions import (
            LaTeXCompilationError,
            PDFValidationError,
        )

        logger = logging.getLogger(__name__)
        output_dir = output_dir or tex_path.parent
        log_path = output_dir / tex_path.with_suffix(".log").name

        try:
            # Run pdflatex twice for references
            for pass_num in range(1, 3):
                result = subprocess.run(
                    [
                        "pdflatex",
                        "-interaction=nonstopmode",
                        "-output-directory",
                        str(output_dir),
                        str(tex_path),
                    ],
                    capture_output=True,
                    text=True,
                    timeout=120,
                )

                # CRITICAL: Check return code
                if result.returncode != 0:
                    logger.error(
                        f"pdflatex pass {pass_num} failed with code {result.returncode}"
                    )

                    # Parse log file for detailed errors
                    log_info = {}
                    error_details = ""
                    if log_path.exists():
                        log_info = self.parse_latex_log(log_path)
                        error_details = "\n".join(log_info.get("errors", []))
                    else:
                        error_details = "Log file not found"

                    raise LaTeXCompilationError(
                        f"LaTeX compilation failed on pass {pass_num}",
                        returncode=result.returncode,
                        stdout=result.stdout[-1000:] if result.stdout else None,
                        stderr=result.stderr[-1000:] if result.stderr else None,
                        log_path=log_path,
                        errors=error_details,
                    )

                logger.info(f"pdflatex pass {pass_num} completed successfully")

            # Check if PDF was generated
            pdf_path = output_dir / tex_path.with_suffix(".pdf").name
            if not pdf_path.exists():
                raise LaTeXCompilationError(
                    "PDF file was not generated despite successful compilation",
                    log_path=log_path,
                )

            # Validate PDF integrity
            if validate:
                is_valid, error_msg = self.validate_pdf(pdf_path)
                if not is_valid:
                    raise PDFValidationError(
                        f"Generated PDF failed validation: {error_msg}",
                        pdf_path=pdf_path,
                    )

            console.print(f"[green]PDF successfully generated: {pdf_path}[/green]")
            return pdf_path

        except FileNotFoundError:
            raise FileNotFoundError(
                "pdflatex not found. Install TeX distribution to compile PDFs."
            )
        except subprocess.TimeoutExpired:
            raise LaTeXCompilationError(
                "PDF compilation timed out after 120 seconds",
                log_path=log_path,
            )

    def validate_pdf(self, pdf_path: Path) -> tuple[bool, str]:
        """Validate PDF file integrity.

        Checks:
        1. File exists and is not empty
        2. Starts with PDF magic bytes (%PDF-)
        3. Contains %%EOF marker
        4. File size > minimum threshold

        Returns:
            (is_valid, error_message)
        """
        if not pdf_path.exists():
            return False, "File does not exist"

        file_size = pdf_path.stat().st_size
        if file_size == 0:
            return False, "File is empty (0 bytes)"
        if file_size < 1024:
            return False, f"File too small ({file_size} bytes, minimum 1024)"

        try:
            with open(pdf_path, "rb") as f:
                # Check PDF magic bytes
                header = f.read(5)
                if header != b"%PDF-":
                    return False, f"Invalid PDF header (expected %PDF-, found {header})"

                # Check for EOF marker in last 1KB
                f.seek(max(0, file_size - 1024))
                tail = f.read()
                if b"%%EOF" not in tail:
                    return False, "Missing PDF EOF marker"

        except Exception as e:
            return False, f"Error reading file: {e}"

        return True, ""

    def parse_latex_log(self, log_path: Path) -> dict[str, Any]:
        """Parse LaTeX .log file for errors and warnings.

        Returns dict with:
        - has_errors: bool
        - errors: list of error messages
        - missing_files: list of missing file paths
        - missing_packages: list of missing packages
        - page_count: int or None
        """
        import logging

        logger = logging.getLogger(__name__)

        result = {
            "has_errors": False,
            "errors": [],
            "missing_files": [],
            "missing_packages": [],
            "page_count": None,
        }

        if not log_path.exists():
            return result

        try:
            with open(log_path, "r", encoding="utf-8", errors="ignore") as f:
                log_content = f.read()

            # Parse for errors
            for line in log_content.split("\n"):
                if line.startswith("! "):
                    result["has_errors"] = True
                    result["errors"].append(line)

                # Missing files
                if "! File" in line and "not found" in line:
                    match = re.search(r"File `(.+?)' not found", line)
                    if match:
                        result["missing_files"].append(match.group(1))

                # Missing packages
                if "! LaTeX Error: File" in line and ".sty' not found" in line:
                    match = re.search(r"File `(.+?).sty' not found", line)
                    if match:
                        result["missing_packages"].append(match.group(1))

            # Extract page count
            page_match = re.search(r"Output written on .+ \((\d+) page", log_content)
            if page_match:
                result["page_count"] = int(page_match.group(1))

        except Exception as e:
            logger.warning(f"Could not parse log file: {e}")

        return result

    def _get_chapter_template(self) -> Any:
        """Get or create chapter template."""
        try:
            return self.env.get_template("chapter.tex.j2")
        except Exception:
            # Return default template as string
            return self.env.from_string(DEFAULT_CHAPTER_TEMPLATE)

    def _prepare_section(self, section: Section) -> dict[str, Any]:
        """Prepare section for template."""
        # Prepare inline figures
        inline_figures = []
        for visual in section.inline_figures:
            fig_data = self._prepare_figure(visual)
            if fig_data:
                inline_figures.append(fig_data)

        # Prepare figure plate
        figure_plate = None
        if section.figure_plate and section.figure_plate.figures:
            plate_figures = []
            for visual in section.figure_plate.figures:
                fig_data = self._prepare_figure(visual)
                if fig_data:
                    plate_figures.append(fig_data)
            if plate_figures:
                figure_plate = {
                    "title": self._latex_escape(section.figure_plate.section_title),
                    "figures": plate_figures,
                }

        return {
            "title": self._latex_escape(section.title),
            "level": section.level,
            "content": self._process_content(section.content),
            "has_conflicts": section.has_conflicts,
            "inline_figures": inline_figures,
            "figure_plate": figure_plate,
            "has_visuals": bool(inline_figures or figure_plate),
            "subsections": [self._prepare_section(s) for s in section.subsections],
        }

    def _prepare_figure(self, visual: "VisualElement") -> dict[str, Any] | None:
        """Prepare a visual element for LaTeX rendering.

        Copies the image file to the compilation directory and returns
        figure metadata for the template.
        """
        if not visual.image_path:
            console.print(f"[yellow]Warning: Visual has no image_path set[/yellow]")
            return None
        if not visual.image_path.exists():
            console.print(f"[yellow]Warning: Image file missing: {visual.image_path}[/yellow]")
            return None

        # Generate unique figure number
        LaTeXGenerator._figure_counter += 1
        fig_num = LaTeXGenerator._figure_counter

        # Generate label-safe filename
        safe_name = f"fig_{fig_num:03d}_{visual.image_path.stem}"
        safe_name = re.sub(r"[^a-zA-Z0-9_]", "_", safe_name)
        target_name = f"{safe_name}{visual.image_path.suffix}"

        # Copy image to figures directory
        if self.images_dir:
            from neurosynth.latex.exceptions import ImagePreparationError

            target_path = self.images_dir / target_name
            try:
                shutil.copy2(visual.image_path, target_path)
                # Use relative path for LaTeX
                latex_path = f"figures/{target_name}"
            except Exception as e:
                # CRITICAL CHANGE: Don't fall back to absolute paths
                # In Docker, absolute paths outside /data/jobs won't work
                console.print(
                    f"[red]Error: Could not copy image {visual.image_path}: {e}[/red]"
                )
                raise ImagePreparationError(
                    f"Failed to copy image to figures directory: {e}",
                    image_path=visual.image_path,
                    target_path=target_path,
                )
        else:
            # No images_dir set - likely testing scenario
            import logging

            logger = logging.getLogger(__name__)
            logger.warning(f"No images_dir set, using absolute path: {visual.image_path}")
            latex_path = str(visual.image_path)

        # Generate caption (preserve original only, per user requirement)
        caption = visual.caption if visual.caption else ""
        if not caption and visual.source_pdf:
            # Minimal source reference if no caption
            caption = f"From {visual.source_pdf.stem}, page {visual.page_number or '?'}"

        return {
            "number": fig_num,
            "path": latex_path,
            "caption": self._latex_escape(caption),
            "label": f"fig:{safe_name}",
            "width": self._calculate_figure_width(visual),
            "image_type": visual.image_type.value,
            "source_page": visual.page_number,
        }

    def _calculate_figure_width(self, visual: "VisualElement") -> str:
        """Calculate appropriate LaTeX width for figure.

        Returns width as fraction of textwidth.
        """
        if visual.width and visual.height:
            aspect = visual.width / visual.height
            if aspect > 1.5:  # Wide image
                return "0.9\\textwidth"
            elif aspect < 0.7:  # Tall image
                return "0.5\\textwidth"
        return "0.7\\textwidth"  # Default

    def _prepare_source(self, source: Source) -> dict[str, Any]:
        """Prepare source for bibliography."""
        return {
            "key": source.citation_key,
            "authors": ", ".join(source.authors) if source.authors else "Unknown",
            "title": self._latex_escape(source.title),
            "year": source.year or "n.d.",
            "publisher": self._latex_escape(source.publisher or ""),
        }

    def _process_content(self, content: str) -> str:
        """Process content for LaTeX."""
        # Escape special characters
        content = self._latex_escape(content)

        # Convert markdown-style bold to LaTeX
        content = re.sub(r"\*\*(.+?)\*\*", r"\\textbf{\1}", content)

        # Convert markdown-style italic to LaTeX
        content = re.sub(r"\*(.+?)\*", r"\\textit{\1}", content)

        # Convert inline citations (Author2020) to \cite{Author2020}
        content = re.sub(r"\(([A-Z][a-z]+\d{4})\)", r"\\cite{\1}", content)

        # Convert bullet points
        content = self._convert_lists(content)

        return content

    def _convert_lists(self, content: str) -> str:
        """Convert markdown lists to LaTeX itemize."""
        lines = content.split("\n")
        result = []
        in_list = False

        for line in lines:
            if line.strip().startswith("- "):
                if not in_list:
                    result.append("\\begin{itemize}")
                    in_list = True
                item_text = line.strip()[2:]
                result.append(f"\\item {item_text}")
            else:
                if in_list:
                    result.append("\\end{itemize}")
                    in_list = False
                result.append(line)

        if in_list:
            result.append("\\end{itemize}")

        return "\n".join(result)

    def _latex_escape(self, text: str) -> str:
        """Escape special LaTeX characters."""
        if not text:
            return ""

        replacements = [
            ("\\", "\\textbackslash{}"),
            ("&", "\\&"),
            ("%", "\\%"),
            ("$", "\\$"),
            ("#", "\\#"),
            ("_", "\\_"),
            ("{", "\\{"),
            ("}", "\\}"),
            ("~", "\\textasciitilde{}"),
            ("^", "\\textasciicircum{}"),
        ]

        for old, new in replacements:
            text = text.replace(old, new)

        return text

    def _format_citation(self, source: Source) -> str:
        """Format source as citation."""
        return f"\\cite{{{source.citation_key}}}"

    def _format_figure(self, fig_data: dict[str, Any]) -> str:
        """Format a figure dictionary as LaTeX figure environment."""
        return (
            f"\\begin{{figure}}[htbp]\n"
            f"\\centering\n"
            f"\\includegraphics[width={fig_data['width']}]{{{fig_data['path']}}}\n"
            f"\\caption{{{fig_data['caption']}}}\n"
            f"\\label{{{fig_data['label']}}}\n"
            f"\\end{{figure}}"
        )


# Default template when no external template is available
DEFAULT_CHAPTER_TEMPLATE = r"""
\documentclass[12pt,a4paper]{article}

% Packages
\usepackage[utf8]{inputenc}
\usepackage[T1]{fontenc}
\usepackage{amsmath,amssymb}
\usepackage{graphicx}
\usepackage{hyperref}
\usepackage{geometry}
\usepackage{setspace}
\usepackage{titlesec}
\usepackage{fancyhdr}
\usepackage{xcolor}

% Page geometry
\geometry{margin=1in}
\onehalfspacing

% Header/Footer
\pagestyle{fancy}
\fancyhf{}
\fancyhead[L]{\leftmark}
\fancyhead[R]{\thepage}
\renewcommand{\headrulewidth}{0.4pt}

% Custom environments
\newenvironment{controversybox}{
    \begin{center}
    \begin{minipage}{0.9\textwidth}
    \colorbox{gray!10}{
    \begin{minipage}{\dimexpr\textwidth-2\fboxsep}
    \small
}{
    \end{minipage}}
    \end{minipage}
    \end{center}
}

% Title
\title{ {{- title -}} }
\author{NeuroSynth - Automated Knowledge Synthesis}
\date{\today}

\begin{document}

\maketitle

% Abstract
{% if abstract %}
\begin{abstract}
{{ abstract }}
\end{abstract}
{% endif %}

% Keywords
{% if keywords %}
\noindent\textbf{Keywords:} {{ keywords | join(', ') }}
\vspace{1em}
{% endif %}

% Sections
{% for section in sections %}
{% if section.level == 1 %}
\section{ {{- section.title -}} }
{% elif section.level == 2 %}
\subsection{ {{- section.title -}} }
{% elif section.level == 3 %}
\subsubsection{ {{- section.title -}} }
{% else %}
\paragraph{ {{- section.title -}} }
{% endif %}

{% for fig in section.inline_figures %}
{{ fig | figure }}
{% endfor %}

{{ section.content }}

{% if section.figure_plate %}
\begin{figure}[htbp]
\centering
{% for fig in section.figure_plate.figures %}
\includegraphics[width=0.45\textwidth]{ {{- fig.path -}} }
{% endfor %}
\caption{ {{- section.figure_plate.title -}} }
\end{figure}
{% endif %}

{% for subsection in section.subsections %}
{% if subsection.level == 2 %}
\subsection{ {{- subsection.title -}} }
{% else %}
\subsubsection{ {{- subsection.title -}} }
{% endif %}

{% for fig in subsection.inline_figures %}
{{ fig | figure }}
{% endfor %}

{{ subsection.content }}

{% if subsection.figure_plate %}
\begin{figure}[htbp]
\centering
{% for fig in subsection.figure_plate.figures %}
\includegraphics[width=0.45\textwidth]{ {{- fig.path -}} }
{% endfor %}
\caption{ {{- subsection.figure_plate.title -}} }
\end{figure}
{% endif %}

{% endfor %}

{% endfor %}

% References
\section*{References}
\begin{enumerate}
{% for source in bibliography %}
\item {{ source.authors }} ({{ source.year }}). \textit{ {{- source.title -}} }. 
      {{ source.publisher }}
{% endfor %}
\end{enumerate}

% Footer
\vfill
\noindent\rule{\textwidth}{0.4pt}
\small
\noindent Generated by NeuroSynth - Neurosurgical Knowledge Synthesis System\\
\noindent Total words: {{ total_words }} | Sources: {{ total_sources }}

\end{document}
"""
