"""Production-safe checkpoint system for synthesis recovery.

This module provides a checkpoint manager that saves all artifacts to a persistent
recovery directory at each pipeline stage, ensuring that generated content is
never lost even on partial failures.
"""

import json
import logging
import pickle
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class SynthesisCheckpoint:
    """Persistent checkpoint manager for synthesis recovery.

    Saves all synthesis artifacts to ~/.neurosynth/recovery/{topic}_{timestamp}/
    so that content is never lost, even when synthesis fails partway through.

    Recovery directory structure:
        manifest.json          - Input manifest (if from Reference Library)
        clusters.pkl           - Processed clusters
        outline.json           - Generated outline
        sections/              - Individual section text files
            section_00.md
            section_01.md
            ...
        figures/               - All figures used
            fig_001.png
            ...
        chapter.tex            - LaTeX source
        chapter.pdf            - Final PDF (if successful)
        error.log              - Any errors encountered
        stage_status.json      - Current pipeline stage

    Usage:
        checkpoint = SynthesisCheckpoint(topic="Craniotomy Approaches")
        checkpoint.save_stage("parsed", parsed_data)
        checkpoint.save_section(0, "Introduction content...")
        checkpoint.save_latex(latex_string)
        checkpoint.copy_figures([Path("fig1.png"), Path("fig2.png")])
        checkpoint.log_error("PDF compilation failed: missing font")
    """

    # Maximum number of recovery directories to keep
    MAX_RECOVERY_DIRS = 10

    def __init__(self, topic: str, base_dir: Path | None = None):
        """Initialize checkpoint manager.

        Args:
            topic: The synthesis topic (used in directory name)
            base_dir: Override base recovery directory (default: ~/.neurosynth/recovery)
        """
        self.topic = topic
        self.timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        # Sanitize topic for directory name
        safe_topic = self._sanitize_name(topic)

        # Set up recovery directory
        self.base_dir = base_dir or (Path.home() / ".neurosynth" / "recovery")
        self.recovery_dir = self.base_dir / f"{safe_topic}_{self.timestamp}"
        self.recovery_dir.mkdir(parents=True, exist_ok=True)

        # Create subdirectories
        self.sections_dir = self.recovery_dir / "sections"
        self.figures_dir = self.recovery_dir / "figures"
        self.sections_dir.mkdir(exist_ok=True)
        self.figures_dir.mkdir(exist_ok=True)

        # Initialize error log
        self.error_log_path = self.recovery_dir / "error.log"

        # Initialize stage status
        self.stage_status: dict[str, str] = {}
        self._update_stage_status("initialized", "completed")

        # Clean up old checkpoints
        self._cleanup_old_checkpoints()

        logger.info(f"Checkpoint initialized: {self.recovery_dir}")

    def _sanitize_name(self, name: str) -> str:
        """Sanitize name for use in filesystem paths."""
        # Remove/replace unsafe characters
        unsafe = '<>:"/\\|?*'
        result = name.lower().replace(" ", "_")
        for char in unsafe:
            result = result.replace(char, "_")
        # Limit length
        return result[:50]

    def _update_stage_status(self, stage: str, status: str) -> None:
        """Update and persist stage status."""
        self.stage_status[stage] = status
        self.stage_status["last_updated"] = datetime.now().isoformat()

        status_path = self.recovery_dir / "stage_status.json"
        with open(status_path, "w", encoding="utf-8") as f:
            json.dump(self.stage_status, f, indent=2)

    def save_stage(self, stage: str, data: Any) -> Path:
        """Save data at a pipeline stage.

        Args:
            stage: Stage name (e.g., "parsed", "embeddings", "clusters", "outline")
            data: Data to save (must be JSON-serializable or pickleable)

        Returns:
            Path to saved file
        """
        self._update_stage_status(stage, "in_progress")

        # Try JSON first (more portable)
        json_path = self.recovery_dir / f"{stage}.json"
        try:
            with open(json_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, default=str)
            self._update_stage_status(stage, "completed")
            logger.debug(f"Saved stage {stage} as JSON: {json_path}")
            return json_path
        except (TypeError, ValueError):
            # Fall back to pickle for non-JSON-serializable data
            pkl_path = self.recovery_dir / f"{stage}.pkl"
            with open(pkl_path, "wb") as f:
                pickle.dump(data, f)
            self._update_stage_status(stage, "completed")
            logger.debug(f"Saved stage {stage} as pickle: {pkl_path}")
            return pkl_path

    def save_section(self, index: int, content: str, title: str | None = None) -> Path:
        """Immediately save a synthesized section.

        This is called after EACH section is synthesized, not after all are done.
        This ensures partial progress is preserved on failure.

        Args:
            index: Section index (0-based)
            content: Section content (markdown/text)
            title: Optional section title for metadata

        Returns:
            Path to saved section file
        """
        # Save content
        path = self.sections_dir / f"section_{index:02d}.md"

        # Add metadata header
        header = f"# Section {index}"
        if title:
            header = f"# {title}"

        full_content = f"{header}\n\n{content}"
        path.write_text(full_content, encoding="utf-8")

        # Update index file
        self._update_sections_index()

        logger.debug(f"Saved section {index}: {path}")
        return path

    def _update_sections_index(self) -> None:
        """Update sections index file."""
        index_path = self.sections_dir / "_index.json"

        sections = []
        for section_file in sorted(self.sections_dir.glob("section_*.md")):
            # Read first line for title
            with open(section_file, encoding="utf-8") as f:
                first_line = f.readline().strip()
                title = (
                    first_line.lstrip("# ")
                    if first_line.startswith("#")
                    else section_file.stem
                )

            sections.append(
                {
                    "file": section_file.name,
                    "title": title,
                    "saved_at": datetime.now().isoformat(),
                }
            )

        with open(index_path, "w", encoding="utf-8") as f:
            json.dump({"sections": sections, "count": len(sections)}, f, indent=2)

    def save_latex(self, latex: str) -> Path:
        """Save LaTeX source BEFORE attempting PDF compilation.

        Args:
            latex: Complete LaTeX document string

        Returns:
            Path to saved .tex file
        """
        self._update_stage_status("latex", "in_progress")

        path = self.recovery_dir / "chapter.tex"
        path.write_text(latex, encoding="utf-8")

        self._update_stage_status("latex", "completed")
        logger.info(f"LaTeX saved to recovery: {path}")
        return path

    def save_manifest(self, manifest: dict) -> Path:
        """Save the input manifest from Reference Library.

        Args:
            manifest: Manifest dictionary

        Returns:
            Path to saved manifest file
        """
        path = self.recovery_dir / "manifest.json"
        with open(path, "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2, ensure_ascii=False)

        logger.debug(f"Manifest saved: {path}")
        return path

    def copy_figures(self, figures: list[Path]) -> int:
        """Copy all figures to recovery directory.

        Args:
            figures: List of figure paths to copy

        Returns:
            Number of figures successfully copied
        """
        self._update_stage_status("figures", "in_progress")

        copied = 0
        failed = []

        for fig in figures:
            if not isinstance(fig, Path):
                fig = Path(fig)

            if not fig.exists():
                self.log_error(f"Figure not found: {fig}")
                failed.append(str(fig))
                continue

            try:
                dest = self.figures_dir / fig.name
                # Handle name collisions
                counter = 1
                while dest.exists():
                    dest = self.figures_dir / f"{fig.stem}_{counter}{fig.suffix}"
                    counter += 1

                shutil.copy2(fig, dest)
                copied += 1
            except Exception as e:
                self.log_error(f"Failed to copy figure {fig}: {e}")
                failed.append(str(fig))

        # Update figures index
        figures_list = list(self.figures_dir.glob("*"))
        figures_list = [
            f for f in figures_list if f.is_file() and not f.name.startswith("_")
        ]

        index_path = self.figures_dir / "_index.json"
        with open(index_path, "w", encoding="utf-8") as f:
            json.dump(
                {
                    "total_copied": copied,
                    "total_failed": len(failed),
                    "failed_files": failed,
                    "figures": [fig.name for fig in figures_list],
                },
                f,
                indent=2,
            )

        self._update_stage_status("figures", "completed" if not failed else "partial")
        logger.info(f"Copied {copied}/{len(figures)} figures to recovery")
        return copied

    def copy_pdf(self, pdf_path: Path) -> Path | None:
        """Copy the final PDF to recovery directory.

        Args:
            pdf_path: Path to compiled PDF

        Returns:
            Path to copied PDF, or None if copy failed
        """
        if not pdf_path.exists():
            self.log_error(f"PDF not found for copy: {pdf_path}")
            return None

        try:
            dest = self.recovery_dir / "chapter.pdf"
            shutil.copy2(pdf_path, dest)
            self._update_stage_status("pdf", "completed")
            logger.info(f"PDF saved to recovery: {dest}")
            return dest
        except Exception as e:
            self.log_error(f"Failed to copy PDF: {e}")
            return None

    def log_error(self, message: str) -> None:
        """Log an error to the error log file.

        Args:
            message: Error message to log
        """
        timestamp = datetime.now().isoformat()
        log_line = f"[{timestamp}] {message}\n"

        with open(self.error_log_path, "a", encoding="utf-8") as f:
            f.write(log_line)

        logger.error(f"Checkpoint error: {message}")

    def mark_complete(self) -> None:
        """Mark synthesis as successfully completed."""
        self._update_stage_status("synthesis", "completed")

        # Write completion marker
        complete_path = self.recovery_dir / "_COMPLETE"
        complete_path.write_text(f"Completed at {datetime.now().isoformat()}")

        logger.info(f"Synthesis marked complete: {self.recovery_dir}")

    def get_recovery_summary(self) -> dict:
        """Get summary of what's in the recovery directory.

        Returns:
            Dictionary with recovery status and available files
        """
        summary = {
            "recovery_dir": str(self.recovery_dir),
            "topic": self.topic,
            "timestamp": self.timestamp,
            "stage_status": self.stage_status.copy(),
            "has_manifest": (self.recovery_dir / "manifest.json").exists(),
            "has_latex": (self.recovery_dir / "chapter.tex").exists(),
            "has_pdf": (self.recovery_dir / "chapter.pdf").exists(),
            "section_count": len(list(self.sections_dir.glob("section_*.md"))),
            "figure_count": len(
                [
                    f
                    for f in self.figures_dir.iterdir()
                    if f.is_file() and not f.name.startswith("_")
                ]
            ),
            "has_errors": self.error_log_path.exists()
            and self.error_log_path.stat().st_size > 0,
        }

        # Read errors if any
        if summary["has_errors"]:
            summary["errors"] = (
                self.error_log_path.read_text(encoding="utf-8").strip().split("\n")
            )

        return summary

    def _cleanup_old_checkpoints(self) -> None:
        """Remove old checkpoint directories, keeping only the most recent ones."""
        if not self.base_dir.exists():
            return

        # Get all recovery directories
        recovery_dirs = []
        for d in self.base_dir.iterdir():
            if d.is_dir() and d != self.recovery_dir:
                try:
                    # Extract timestamp from directory name
                    recovery_dirs.append((d, d.stat().st_mtime))
                except Exception:
                    continue

        # Sort by modification time (newest first)
        recovery_dirs.sort(key=lambda x: x[1], reverse=True)

        # Remove directories beyond the limit
        for old_dir, _ in recovery_dirs[self.MAX_RECOVERY_DIRS - 1 :]:
            try:
                shutil.rmtree(old_dir)
                logger.debug(f"Cleaned up old checkpoint: {old_dir}")
            except Exception as e:
                logger.warning(f"Failed to cleanup {old_dir}: {e}")

    def cleanup_on_success(self) -> None:
        """Optional cleanup after successful synthesis.

        Call this only if you want to remove the recovery directory after
        a fully successful synthesis (all outputs copied to final destination).
        """
        try:
            shutil.rmtree(self.recovery_dir)
            logger.info(
                f"Cleaned up recovery directory after success: {self.recovery_dir}"
            )
        except Exception as e:
            logger.warning(f"Failed to cleanup recovery dir: {e}")


def get_latest_recovery(
    topic: str | None = None, base_dir: Path | None = None
) -> Path | None:
    """Get the most recent recovery directory, optionally filtered by topic.

    Args:
        topic: Filter by topic name (optional)
        base_dir: Base recovery directory (default: ~/.neurosynth/recovery)

    Returns:
        Path to most recent recovery directory, or None if not found
    """
    base = base_dir or (Path.home() / ".neurosynth" / "recovery")
    if not base.exists():
        return None

    # Get all recovery directories
    recovery_dirs = []
    for d in base.iterdir():
        if not d.is_dir():
            continue

        # Filter by topic if specified
        if topic:
            safe_topic = topic.lower().replace(" ", "_")
            if not d.name.startswith(safe_topic):
                continue

        try:
            recovery_dirs.append((d, d.stat().st_mtime))
        except Exception:
            continue

    if not recovery_dirs:
        return None

    # Return most recent
    recovery_dirs.sort(key=lambda x: x[1], reverse=True)
    return recovery_dirs[0][0]


def list_recoveries(base_dir: Path | None = None) -> list[dict]:
    """List all available recovery directories.

    Args:
        base_dir: Base recovery directory (default: ~/.neurosynth/recovery)

    Returns:
        List of recovery info dictionaries
    """
    base = base_dir or (Path.home() / ".neurosynth" / "recovery")
    if not base.exists():
        return []

    recoveries = []
    for d in base.iterdir():
        if not d.is_dir():
            continue

        try:
            # Parse directory name
            parts = d.name.rsplit("_", 2)
            if len(parts) >= 3:
                topic = "_".join(parts[:-2])
                timestamp = f"{parts[-2]}_{parts[-1]}"
            else:
                topic = d.name
                timestamp = "unknown"

            # Check status
            status_path = d / "stage_status.json"
            if status_path.exists():
                with open(status_path) as f:
                    status = json.load(f)
            else:
                status = {}

            recoveries.append(
                {
                    "path": str(d),
                    "topic": topic,
                    "timestamp": timestamp,
                    "has_latex": (d / "chapter.tex").exists(),
                    "has_pdf": (d / "chapter.pdf").exists(),
                    "section_count": (
                        len(list((d / "sections").glob("section_*.md")))
                        if (d / "sections").exists()
                        else 0
                    ),
                    "is_complete": (d / "_COMPLETE").exists(),
                    "last_stage": status.get("last_updated", "unknown"),
                }
            )
        except Exception:
            continue

    # Sort by most recent first
    recoveries.sort(key=lambda x: x["timestamp"], reverse=True)
    return recoveries
