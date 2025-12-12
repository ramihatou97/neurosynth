#!/usr/bin/env python3
"""
Script to run the integrated workflow: Reference Library Search -> NeuroSynth Synthesis.
"""
import os
import shutil
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Optional

# Add reference-library to path
repo_root = Path(__file__).parent.parent
sys.path.insert(0, str(repo_root / "reference-library"))

from src.cache.database import Database
from src.export.page_extractor import extract_relevant_pages, generate_manifest
from src.integration.neurosynth_bridge import NeuroSynthBridge, SynthesisResult
from src.search.pdf_searcher import PDFSearcher

import config

# Ensure src is in PYTHONPATH for the subprocess
if "PYTHONPATH" not in os.environ:
    os.environ["PYTHONPATH"] = str(repo_root / "src")
else:
    os.environ["PYTHONPATH"] = (
        str(repo_root / "src") + os.pathsep + os.environ["PYTHONPATH"]
    )


class DockerBridge(NeuroSynthBridge):
    """Bridge that runs NeuroSynth in Docker with explicit volume mounts."""

    def __init__(self, workspace_dir: Path, **kwargs):
        super().__init__(**kwargs)
        self.workspace_dir = workspace_dir
        self.workspace_dir.mkdir(parents=True, exist_ok=True)

    def _get_neurosynth_command(self) -> list[str]:
        return [str(repo_root / "neurosynth")]

    def synthesize(
        self,
        topic: str,
        results: list,
        output_dir: Path | None = None,
        on_progress: Callable[[str], None] | None = None,
        context_pages: int = 1,
        search_query: str = "",
        search_mode: str = "keyword",
        template_type: str = None,
    ) -> SynthesisResult:
        """Override synthesize to use explicit workspace directory."""

        # Setup workspace for this run
        # Sanitize topic for directory name
        run_id = "".join(
            c for c in topic.lower() if c.isalnum() or c in (" ", "_", "-")
        ).replace(" ", "_")[:50]
        run_dir = self.workspace_dir / run_id

        # Clean previous run if exists
        if run_dir.exists():
            shutil.rmtree(run_dir)
        run_dir.mkdir()

        sources_dir = run_dir / "sources"
        sources_dir.mkdir()

        # Extract pages
        if on_progress:
            on_progress("Extracting relevant pages...")

        extracted = extract_relevant_pages(
            results=results,
            output_dir=sources_dir,
            context_pages=context_pages,
            database=self.database,
        )

        if not extracted:
            return SynthesisResult(success=False, error="No pages extracted")

        # Generate manifest
        manifest_path = run_dir / "manifest.json"
        generate_manifest(
            topic=topic,
            sources=extracted,
            output_path=manifest_path,
            search_query=search_query,
            search_mode=search_mode,
            template_type=template_type,
        )

        # Determine output path
        if output_dir is None:
            output_dir = Path.home() / "Documents" / "NeuroSynth"
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / f"{run_id}.pdf"

        # Run NeuroSynth via Docker
        return self._run_neurosynth(
            topic=topic,
            sources_dir=sources_dir,
            output_path=output_path,
            manifest_path=manifest_path,
            on_progress=on_progress,
        )

    def _run_neurosynth(
        self, topic, sources_dir, output_path, manifest_path, on_progress=None
    ):
        # Translate paths to /host mount
        # We assume repo_root is mounted as /host in the container

        container_sources = str(sources_dir).replace(str(repo_root), "/host")
        container_manifest = str(manifest_path).replace(str(repo_root), "/host")

        # Output needs to be in a place writable by Docker and accessible by host
        # We'll write to the run_dir (which is in repo_root) and then copy
        local_output_filename = output_path.name
        local_output_path = sources_dir.parent / local_output_filename
        container_output = str(local_output_path).replace(str(repo_root), "/host")

        cmd = self._get_neurosynth_command()
        cmd.extend(
            [
                "run",
                topic,
                "--sources",
                container_sources,
                "--output",
                container_output,
                "--manifest",
                container_manifest,
            ]
        )

        if on_progress:
            on_progress(f"Running Docker command: {' '.join(cmd)}")

        # Run subprocess
        try:
            # Use a longer timeout or make it configurable
            timeout = 7200  # 2 hours

            process = subprocess.run(
                cmd, capture_output=True, text=True, timeout=timeout
            )

            log = process.stdout + process.stderr

            # Save log
            (sources_dir.parent / "run.log").write_text(log)

            if process.returncode == 0:
                # Copy result
                if local_output_path.exists():
                    shutil.copy2(local_output_path, output_path)
                    return SynthesisResult(
                        success=True, output_path=output_path, log=log
                    )

                # Check for tex
                local_tex = local_output_path.with_suffix(".tex")
                if local_tex.exists():
                    final_tex = output_path.with_suffix(".tex")
                    shutil.copy2(local_tex, final_tex)
                    return SynthesisResult(success=True, output_path=final_tex, log=log)

                return SynthesisResult(
                    success=False, error="Output file missing", log=log
                )
            else:
                return SynthesisResult(
                    success=False, error=f"Exit code {process.returncode}", log=log
                )

        except subprocess.TimeoutExpired:
            return SynthesisResult(success=False, error="Synthesis timed out")
        except Exception as e:
            return SynthesisResult(success=False, error=f"Error: {e}")


def main():
    topic = "Lumbar Discectomy"
    query = "lumbar discectomy"

    print(f"Running integrated workflow for: {topic}")

    # 1. Setup
    # Ensure library path exists
    # Try to use Digital Editions if default doesn't exist
    library_path = config.LIBRARY_PATH
    if not library_path.exists():
        digital_editions = Path.home() / "Documents" / "Digital Editions"
        if digital_editions.exists():
            library_path = digital_editions
            # Monkey patch config
            config.LIBRARY_PATH = library_path

    if not library_path.exists():
        print(f"Error: Library path not found: {library_path}")
        print("Please set NEUROSURGERY_LIBRARY_PATH or configure user_config.json")
        sys.exit(1)

    print(f"Using library at: {library_path}")

    # Initialize Database
    db = Database(config.DATABASE_PATH)

    # Initialize Searcher
    searcher = PDFSearcher(library_path, db)

    # 2. Search
    print(f"Searching for '{query}'...")
    results = []
    try:
        # Use keyword search for reliability if semantic index isn't built
        for result in searcher.search_library(query, mode="keyword"):
            results.append(result)
            # Limit to top 5 results for this demo/test
            if len(results) >= 5:
                break
    except Exception as e:
        print(f"Search failed: {e}")
        sys.exit(1)

    if not results:
        print("No results found.")
        sys.exit(1)

    print(f"Found {len(results)} results.")
    for r in results:
        print(f" - {r.display_name} (p.{r.page_number})")

    # 3. Synthesize
    print("\nStarting synthesis...")

    # Initialize Bridge with explicit workspace
    workspace = repo_root / "data" / "bridge_workspace"
    bridge = DockerBridge(workspace_dir=workspace, database=db)

    # Run synthesis
    result = bridge.synthesize(
        topic=topic,
        results=results,
        search_query=query,
        search_mode="keyword",
        on_progress=lambda msg: print(f"[Progress] {msg}"),
    )

    if result.success:
        print(f"\nSUCCESS! Output saved to: {result.output_path}")
    else:
        print(f"\nFAILURE: {result.error}")
        if result.log:
            print("Log output:")
            print(result.log)


if __name__ == "__main__":
    main()
