"""Intelligent merging of clustered content."""

import asyncio
from dataclasses import dataclass

from rich.console import Console

from neurosynth.config import get_settings
from neurosynth.llm.claude import ClaudeClient
from neurosynth.models.knowledge import (
    Conflict,
    ConflictType,
    KnowledgeCluster,
    Perspective,
)
from neurosynth.models.document import ContentChunk

console = Console()


@dataclass
class MergeResult:
    """Result of merging operation."""

    merged_content: str
    conflicts: list[Conflict]
    sources_used: int
    unique_details_preserved: int


class ClusterMerger:
    """Merge content from semantically similar clusters."""

    def __init__(self):
        self.claude = ClaudeClient()

    async def merge_cluster(
        self,
        cluster: KnowledgeCluster,
        detect_conflicts: bool = True,
    ) -> MergeResult:
        """Merge all chunks in a cluster into unified content."""
        if not cluster.chunks:
            return MergeResult(
                merged_content="",
                conflicts=[],
                sources_used=0,
                unique_details_preserved=0,
            )

        # Single chunk - no merging needed
        if len(cluster.chunks) == 1:
            return MergeResult(
                merged_content=cluster.chunks[0].content,
                conflicts=[],
                sources_used=1,
                unique_details_preserved=0,
            )

        # Prepare chunks for merging
        chunk_data = [
            {
                "content": c.content,
                "source": c.source.citation_key,
                "location": c.location_str,
            }
            for c in cluster.chunks
        ]

        # Detect conflicts first (if enabled)
        conflicts = []
        if detect_conflicts:
            conflicts = await self._detect_conflicts(chunk_data, cluster.chunks)

        # Merge content
        merged_content = await self.claude.merge_chunks(
            chunk_data,
            preserve_all_details=True,
        )

        # Update cluster
        cluster.merged_content = merged_content
        cluster.conflicts = conflicts

        return MergeResult(
            merged_content=merged_content,
            conflicts=conflicts,
            sources_used=len(set(c.source.id for c in cluster.chunks)),
            unique_details_preserved=self._count_unique_details(chunk_data, merged_content),
        )

    async def merge_all_clusters(
        self,
        clusters: list[KnowledgeCluster],
        detect_conflicts: bool = True,
        max_concurrent: int | None = None,
    ) -> list[MergeResult]:
        """Merge all clusters in parallel with concurrency control.

        Args:
            clusters: List of knowledge clusters to merge
            detect_conflicts: Whether to detect conflicts during merging
            max_concurrent: Maximum concurrent Claude API calls (default from config)
        """
        settings = get_settings()
        max_concurrent = max_concurrent or settings.merge_concurrency
        console.print(f"[blue]Merging {len(clusters)} clusters (parallel, max {max_concurrent} concurrent)...[/blue]")

        # Semaphore to limit concurrent API calls
        semaphore = asyncio.Semaphore(max_concurrent)

        # Track progress
        completed = 0
        total_multi_chunk = sum(1 for c in clusters if len(c.chunks) > 1)

        async def merge_with_limit(cluster: KnowledgeCluster, index: int) -> MergeResult:
            nonlocal completed
            async with semaphore:
                if len(cluster.chunks) > 1:
                    console.print(
                        f"  Merging cluster {index+1}/{len(clusters)} "
                        f"({len(cluster.chunks)} chunks)",
                        style="dim",
                    )
                result = await self.merge_cluster(cluster, detect_conflicts)
                if len(cluster.chunks) > 1:
                    completed += 1
                    console.print(
                        f"  [dim]Completed {completed}/{total_multi_chunk} multi-chunk clusters[/dim]"
                    )
                return result

        # Create tasks for all clusters
        tasks = [
            merge_with_limit(cluster, i)
            for i, cluster in enumerate(clusters)
        ]

        # Execute all in parallel with semaphore limiting concurrency
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Handle any exceptions and filter results
        final_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                console.print(f"[red]Error merging cluster {i}: {result}[/red]")
                # Create empty result for failed cluster
                final_results.append(MergeResult(
                    merged_content="",
                    conflicts=[],
                    sources_used=0,
                    unique_details_preserved=0,
                ))
            else:
                final_results.append(result)

        total_conflicts = sum(len(r.conflicts) for r in final_results)
        console.print(
            f"[green]Merged {len(clusters)} clusters, "
            f"detected {total_conflicts} conflicts[/green]"
        )

        return final_results

    async def _detect_conflicts(
        self,
        chunk_data: list[dict[str, str]],
        original_chunks: list[ContentChunk],
    ) -> list[Conflict]:
        """Detect conflicts between chunks using Claude."""
        if len(chunk_data) < 2:
            return []

        raw_conflicts = await self.claude.detect_conflicts(chunk_data)

        conflicts = []
        for raw in raw_conflicts:
            conflict_type = self._parse_conflict_type(raw.get("type", ""))

            perspectives = []
            for p in raw.get("perspectives", []):
                # Find matching chunk for source attribution
                source_key = p.get("source", "")
                
                # Find index of matching chunk in chunk_data
                match_index = next(
                    (i for i, c in enumerate(chunk_data) if source_key in c.get("source", "")),
                    None,
                )

                if match_index is not None:
                    original_chunk = original_chunks[match_index]
                    perspectives.append(
                        Perspective(
                            claim=p.get("claim", ""),
                            source=original_chunk.source,
                            chunk=original_chunk,
                            confidence=1.0,
                        )
                    )

            if perspectives:
                conflict = Conflict(
                    type=conflict_type,
                    description=raw.get("description", ""),
                    perspectives=perspectives,
                )
                conflicts.append(conflict)

        return conflicts

    def _parse_conflict_type(self, type_str: str) -> ConflictType:
        """Parse conflict type string to enum."""
        type_map = {
            "quantitative": ConflictType.QUANTITATIVE,
            "contradictory": ConflictType.CONTRADICTORY,
            "approach": ConflictType.APPROACH,
            "temporal": ConflictType.TEMPORAL,
            "terminology": ConflictType.TERMINOLOGY,
            "emphasis": ConflictType.EMPHASIS,
        }
        return type_map.get(type_str.lower(), ConflictType.CONTRADICTORY)

    def _count_unique_details(
        self,
        original_chunks: list[dict[str, str]],
        merged_content: str,
    ) -> int:
        """Estimate number of unique details preserved."""
        # Simple heuristic: count unique sentences across originals
        # that appear (or are paraphrased) in merged content

        import re

        original_sentences = set()
        for chunk in original_chunks:
            sentences = re.split(r"[.!?]+", chunk["content"])
            for s in sentences:
                s = s.strip()
                if len(s) > 20:  # Skip very short fragments
                    original_sentences.add(s.lower())

        # Count how many original sentence concepts appear in merged
        merged_lower = merged_content.lower()
        preserved = 0

        for sentence in original_sentences:
            # Check for key phrases (first 50 chars)
            key_phrase = sentence[:50]
            if key_phrase in merged_lower:
                preserved += 1

        return preserved


class ConflictResolver:
    """Helper class for presenting and resolving conflicts."""

    @staticmethod
    def to_academic_text(conflicts: list[Conflict]) -> str:
        """Convert conflicts to academic presentation style."""
        if not conflicts:
            return ""

        paragraphs = []
        for conflict in conflicts:
            text = conflict.to_academic_text()
            if text:
                paragraphs.append(text)

        return "\n\n".join(paragraphs)

    @staticmethod
    def group_by_type(
        conflicts: list[Conflict],
    ) -> dict[ConflictType, list[Conflict]]:
        """Group conflicts by type."""
        groups: dict[ConflictType, list[Conflict]] = {}

        for conflict in conflicts:
            if conflict.type not in groups:
                groups[conflict.type] = []
            groups[conflict.type].append(conflict)

        return groups

    @staticmethod
    def prioritize(conflicts: list[Conflict]) -> list[Conflict]:
        """Prioritize conflicts by significance."""
        priority_order = [
            ConflictType.CONTRADICTORY,
            ConflictType.QUANTITATIVE,
            ConflictType.APPROACH,
            ConflictType.TEMPORAL,
            ConflictType.TERMINOLOGY,
            ConflictType.EMPHASIS,
        ]

        return sorted(
            conflicts,
            key=lambda c: priority_order.index(c.type) if c.type in priority_order else 99,
        )
