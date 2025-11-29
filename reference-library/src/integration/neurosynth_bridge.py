"""Bridge to NeuroSynth for document synthesis."""
import re
import subprocess
import sys
import shutil
import json
from datetime import datetime
from pathlib import Path
from typing import Optional, Callable, TYPE_CHECKING
from dataclasses import dataclass, field


@dataclass
class ProjectDirectory:
    """Represents a persistent NeuroSynth project directory structure.

    Structure:
        ~/Documents/NeuroSynth/projects/{topic_name}/
        ├── sources/          # Extracted source PDFs (mini-PDFs with relevant pages)
        ├── images/           # Filtered medical images extracted from sources
        ├── output/           # Generated chapters (PDF, LaTeX, Markdown)
        ├── manifest.json     # Metadata linking sources to synthesis
        └── project.json      # Project metadata (creation date, settings, etc.)
    """
    root: Path
    sources_dir: Path = field(init=False)
    images_dir: Path = field(init=False)
    output_dir: Path = field(init=False)
    manifest_path: Path = field(init=False)
    project_meta_path: Path = field(init=False)

    def __post_init__(self):
        self.sources_dir = self.root / "sources"
        self.images_dir = self.root / "images"
        self.output_dir = self.root / "output"
        self.manifest_path = self.root / "manifest.json"
        self.project_meta_path = self.root / "project.json"

    def create(self) -> "ProjectDirectory":
        """Create the directory structure."""
        self.sources_dir.mkdir(parents=True, exist_ok=True)
        self.images_dir.mkdir(parents=True, exist_ok=True)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        return self

    def save_project_meta(
        self,
        topic: str,
        search_query: str = "",
        search_mode: str = "keyword",
        template_type: str = None
    ):
        """Save project metadata."""
        meta = {
            "topic": topic,
            "created_at": datetime.now().isoformat(),
            "search_query": search_query,
            "search_mode": search_mode,
            "template_type": template_type,
            "version": "1.0"
        }
        with open(self.project_meta_path, 'w', encoding='utf-8') as f:
            json.dump(meta, f, indent=2, ensure_ascii=False)


def _create_project_directory(topic: str, base_dir: Optional[Path] = None) -> ProjectDirectory:
    """Create a persistent project directory for the given topic.

    Args:
        topic: The synthesis topic (will be sanitized for filesystem)
        base_dir: Base directory for projects (default: ~/Documents/NeuroSynth/projects)

    Returns:
        ProjectDirectory with all subdirectories created
    """
    if base_dir is None:
        base_dir = Path.home() / "Documents" / "NeuroSynth" / "projects"

    # Create safe directory name from topic
    safe_topic = re.sub(r'[^\w\s\-]', '', topic)  # Remove special chars
    safe_topic = safe_topic.lower().replace(' ', '_')[:50]  # Limit length

    # Add timestamp suffix if directory exists to avoid overwriting
    project_dir = base_dir / safe_topic
    if project_dir.exists():
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        project_dir = base_dir / f"{safe_topic}_{timestamp}"

    return ProjectDirectory(root=project_dir).create()


def _get_subprocess_kwargs() -> dict:
    """Get platform-specific subprocess kwargs to prevent terminal windows."""
    kwargs = {"stdin": subprocess.DEVNULL}
    if sys.platform == "win32":
        # Prevent console window on Windows
        kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
    return kwargs


def _sanitize_topic(topic: str) -> str:
    """
    Validate and sanitize topic name for subprocess safety.

    Prevents command injection by only allowing alphanumeric characters,
    spaces, hyphens, periods, underscores, and common punctuation.

    Args:
        topic: Raw topic string from user input

    Returns:
        Sanitized topic string

    Raises:
        ValueError: If topic contains unsafe characters
    """
    if not topic or not topic.strip():
        raise ValueError("Topic cannot be empty")

    # Allow alphanumeric, spaces, common punctuation for medical terms
    # e.g., "Chiari Malformation Type I" or "C1-C2 Fusion"
    if not re.match(r'^[\w\s\-\.\,\:\;\(\)\'\"]+$', topic, re.UNICODE):
        raise ValueError(
            f"Invalid topic name: contains unsafe characters. "
            f"Allowed: letters, numbers, spaces, and - . , : ; ( ) ' \""
        )

    # Limit length to prevent issues
    return topic.strip()[:200]

from ..export.page_extractor import extract_relevant_pages, generate_manifest, ExtractedSource

if TYPE_CHECKING:
    from ..cache.database import Database


@dataclass
class SynthesisResult:
    """Result of a synthesis operation."""
    success: bool
    output_path: Optional[Path] = None
    error: Optional[str] = None
    log: str = ""


class NeuroSynthBridge:
    """Bridge between Reference Library App and NeuroSynth CLI."""

    def __init__(
        self,
        neurosynth_path: Optional[Path] = None,
        neurosynth_venv: Optional[Path] = None,
        database: Optional["Database"] = None
    ):
        """
        Initialize the bridge.

        Args:
            neurosynth_path: Path to neurosynth installation (optional, uses PATH if not set)
            neurosynth_venv: Path to neurosynth virtualenv (optional)
            database: Database instance for logging synthesis history (optional)
        """
        self.neurosynth_path = neurosynth_path
        self.neurosynth_venv = neurosynth_venv
        self.database = database

    def synthesize(
        self,
        topic: str,
        results: list,  # list[SearchResult]
        output_dir: Optional[Path] = None,
        on_progress: Optional[Callable[[str], None]] = None,
        context_pages: int = 1,
        search_query: str = "",
        search_mode: str = "keyword",
        template_type: str = None
    ) -> SynthesisResult:
        """
        Synthesize a chapter from selected search results.

        Args:
            topic: The chapter topic/title
            results: List of SearchResult objects to synthesize
            output_dir: Where to save output (default: ~/Documents/NeuroSynth)
            on_progress: Callback for progress updates
            context_pages: Number of pages before/after match to include
            search_query: Original search query from Reference Library
            search_mode: Search mode used (keyword/semantic/hybrid)
            template_type: Type of chapter template (procedural/theoretical)

        Returns:
            SynthesisResult with output path or error
        """
        if not results:
            return SynthesisResult(
                success=False,
                error="No results selected for synthesis"
            )

        # Sanitize topic to prevent command injection
        try:
            topic = _sanitize_topic(topic)
        except ValueError as e:
            return SynthesisResult(
                success=False,
                error=str(e)
            )

        # Create persistent project directory structure
        # ~/Documents/NeuroSynth/projects/{topic}/
        project = _create_project_directory(topic, output_dir)

        if on_progress:
            on_progress(f"Created project: {project.root.name}")

        # Save project metadata
        project.save_project_meta(
            topic=topic,
            search_query=search_query,
            search_mode=search_mode,
            template_type=template_type
        )

        # Extract relevant pages from selected PDFs into project sources
        if on_progress:
            on_progress("Extracting relevant pages...")

        try:
            extracted = extract_relevant_pages(
                results=results,
                output_dir=project.sources_dir,
                context_pages=context_pages,
                database=self.database
            )
        except Exception as e:
            return SynthesisResult(
                success=False,
                error=f"Failed to extract pages: {e}"
            )

        if not extracted:
            return SynthesisResult(
                success=False,
                error="No pages could be extracted from selected results"
            )

        # Copy medical images from extracted sources to project images directory
        if on_progress:
            on_progress("Collecting medical images...")

        image_count = self._collect_project_images(extracted, project.images_dir)
        if on_progress and image_count > 0:
            on_progress(f"Collected {image_count} medical images")

        # Generate enhanced manifest with search context
        generate_manifest(
            topic=topic,
            sources=extracted,
            output_path=project.manifest_path,
            search_query=search_query,
            search_mode=search_mode,
            template_type=template_type
        )

        if on_progress:
            on_progress(f"Extracted {len(extracted)} source documents")

        # Determine output file path in project output directory
        safe_topic = topic.lower().replace(" ", "_")
        output_pdf = project.output_dir / f"{safe_topic}.pdf"

        # Run NeuroSynth
        if on_progress:
            on_progress("Running NeuroSynth synthesis...")

        result = self._run_neurosynth(
            topic=topic,
            sources_dir=project.sources_dir,
            output_path=output_pdf,
            manifest_path=project.manifest_path,
            on_progress=on_progress
        )

        # Update result with project directory info
        if result.success:
            result.output_path = output_pdf
            # Also create a copy of output in the legacy location for backward compatibility
            legacy_output_dir = Path.home() / "Documents" / "NeuroSynth"
            legacy_output_dir.mkdir(parents=True, exist_ok=True)
            if output_pdf.exists():
                legacy_pdf = legacy_output_dir / output_pdf.name
                counter = 1
                while legacy_pdf.exists():
                    legacy_pdf = legacy_output_dir / f"{safe_topic}_{counter}.pdf"
                    counter += 1
                shutil.copy2(output_pdf, legacy_pdf)

        # Log synthesis to history
        self._log_synthesis(
            topic=topic,
            search_query=search_query,
            search_mode=search_mode,
            extracted=extracted,
            output_path=output_pdf if result.success else None,
            result=result,
            manifest_path=project.manifest_path
        )

        return result

    def _collect_project_images(
        self,
        extracted: list[ExtractedSource],
        images_dir: Path
    ) -> int:
        """Collect medical images from extracted sources into project images directory.

        Args:
            extracted: List of ExtractedSource objects with figure info
            images_dir: Directory to copy images to

        Returns:
            Number of images collected
        """
        collected = 0

        for source in extracted:
            for fig in source.figures:
                image_path = fig.get("image_path")
                if not image_path:
                    continue

                src_path = Path(image_path)
                if not src_path.exists():
                    continue

                # Create destination path with source context
                # e.g., "youmans_ch26_p15_fig1.png"
                dest_name = src_path.name
                dest_path = images_dir / dest_name

                # Handle collisions
                counter = 1
                while dest_path.exists():
                    stem = src_path.stem
                    suffix = src_path.suffix
                    dest_path = images_dir / f"{stem}_{counter}{suffix}"
                    counter += 1

                try:
                    shutil.copy2(src_path, dest_path)
                    collected += 1
                except Exception as e:
                    print(f"Warning: Failed to copy image {src_path}: {e}")

        return collected

    def _run_neurosynth(
        self,
        topic: str,
        sources_dir: Path,
        output_path: Path,
        manifest_path: Optional[Path] = None,
        on_progress: Optional[Callable[[str], None]] = None
    ) -> SynthesisResult:
        """Run the NeuroSynth CLI."""
        # Build command
        cmd = self._get_neurosynth_command()
        cmd.extend([
            "run",
            topic,
            "--sources", str(sources_dir),
            "--output", str(output_path)
        ])

        if manifest_path:
            cmd.extend(["--manifest", str(manifest_path)])

        # Set up environment
        env = None
        if self.neurosynth_venv:
            import os
            env = os.environ.copy()
            env["PATH"] = str(self.neurosynth_venv / "bin") + ":" + env["PATH"]
            env["VIRTUAL_ENV"] = str(self.neurosynth_venv)

        try:
            if on_progress:
                on_progress("Starting synthesis pipeline...")

            # Use Popen for streaming output (shows progress in real-time)
            import os as _os
            if env is None:
                env = _os.environ.copy()

            # Force unbuffered Python output for real-time streaming
            env["PYTHONUNBUFFERED"] = "1"

            # Set working directory to neurosynth root for .env discovery
            cwd = self.neurosynth_path if self.neurosynth_path else None

            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,  # Merge stderr into stdout
                text=True,
                env=env,
                cwd=cwd,
                bufsize=1,  # Line buffered
                **_get_subprocess_kwargs()
            )

            log_lines = []

            # Stream output line by line
            try:
                for line in iter(process.stdout.readline, ''):
                    line = line.rstrip()
                    if line:
                        log_lines.append(line)
                        # Send progress update for each line
                        if on_progress:
                            # Filter out ANSI codes and extract meaningful progress
                            clean_line = self._clean_progress_line(line)
                            if clean_line:
                                on_progress(clean_line)
            finally:
                # Always close stdout to prevent file descriptor leak
                if process.stdout:
                    process.stdout.close()

            process.wait()
            log = "\n".join(log_lines)

            if process.returncode == 0:
                # Check if output was created
                if output_path.exists():
                    if on_progress:
                        on_progress(f"Synthesis complete: {output_path.name}")
                    return SynthesisResult(
                        success=True,
                        output_path=output_path,
                        log=log
                    )
                else:
                    # Check for .tex fallback
                    tex_path = output_path.with_suffix(".tex")
                    if tex_path.exists():
                        if on_progress:
                            on_progress(f"Synthesis complete: {tex_path.name}")
                        return SynthesisResult(
                            success=True,
                            output_path=tex_path,
                            log=log
                        )
                    return SynthesisResult(
                        success=False,
                        error="Synthesis completed but no output file found",
                        log=log
                    )
            else:
                return SynthesisResult(
                    success=False,
                    error=f"NeuroSynth exited with code {process.returncode}",
                    log=log
                )

        except FileNotFoundError:
            return SynthesisResult(
                success=False,
                error="NeuroSynth not found. Ensure it's installed and in PATH."
            )
        except Exception as e:
            return SynthesisResult(
                success=False,
                error=f"Unexpected error: {e}"
            )

    def _clean_progress_line(self, line: str) -> str:
        """Clean and extract meaningful progress from a line."""
        import re
        # Remove ANSI escape codes
        ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
        clean = ansi_escape.sub('', line)

        # Skip empty lines and spinner frames
        if not clean.strip():
            return ""
        if clean.strip() in ['⠋', '⠙', '⠹', '⠸', '⠼', '⠴', '⠦', '⠧', '⠇', '⠏']:
            return ""

        # Check for structured [PROGRESS] messages (preferred)
        if clean.strip().startswith("[PROGRESS]"):
            # Extract the message after [PROGRESS]
            msg = clean.strip()[10:].strip()
            return msg[:80] if msg else ""

        # Extract key progress indicators (fallback for rich output)
        if any(keyword in clean.lower() for keyword in [
            'processing', 'parsing', 'extracted', 'embedding', 'cluster',
            'synthesiz', 'generat', 'compil', 'step', 'complete', 'error',
            'copying', 'deduplicat', 'outline', 'section', 'pdf', 'chunk'
        ]):
            return clean.strip()[:80]  # Truncate long lines

        return ""

    def _get_neurosynth_command(self) -> list[str]:
        """Get the command to run neurosynth."""
        if self.neurosynth_venv:
            # Use venv's neurosynth directly
            neurosynth_bin = self.neurosynth_venv / "bin" / "neurosynth"
            if neurosynth_bin.exists():
                return [str(neurosynth_bin)]
        if self.neurosynth_path:
            # Use specific installation with python -m
            python_bin = self.neurosynth_venv / "bin" / "python" if self.neurosynth_venv else "python"
            return [str(python_bin), "-m", "neurosynth"]
        # Use system neurosynth
        return ["neurosynth"]

    def _log_synthesis(
        self,
        topic: str,
        search_query: str,
        search_mode: str,
        extracted: list[ExtractedSource],
        output_path: Optional[Path],
        result: SynthesisResult,
        manifest_path: Optional[Path] = None
    ):
        """Log synthesis to the database history."""
        if not self.database:
            return

        try:
            # Read manifest JSON if available
            manifest_json = None
            if manifest_path and manifest_path.exists():
                with open(manifest_path, 'r', encoding='utf-8') as f:
                    manifest_json = f.read()

            # Convert extracted sources to dict format
            sources = [
                {
                    "original_source": s.original_source,
                    "original_path": str(s.original_path),
                    "category_group": s.category_group,
                    "category": s.category,
                    "pages": s.pages,
                    "confidence": s.confidence,
                }
                for s in extracted
            ]

            self.database.log_synthesis(
                topic=topic,
                search_query=search_query,
                search_mode=search_mode,
                sources=sources,
                template_used=None,  # Will be set by CategoryAwareOutlineGenerator later
                output_path=output_path,
                success=result.success,
                error_message=result.error,
                manifest_json=manifest_json
            )
        except Exception as e:
            # Don't fail synthesis because of logging error
            print(f"Warning: Failed to log synthesis history: {e}")

    def check_available(self) -> tuple[bool, str]:
        """
        Check if NeuroSynth is available.

        Returns:
            Tuple of (available, version_or_error)
        """
        cmd = self._get_neurosynth_command()
        cmd.append("version")

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=10,
                **_get_subprocess_kwargs()
            )
            if result.returncode == 0:
                version = result.stdout.strip()
                return True, version
            return False, result.stderr.strip()
        except FileNotFoundError:
            return False, "NeuroSynth not found in PATH"
        except Exception as e:
            return False, str(e)
