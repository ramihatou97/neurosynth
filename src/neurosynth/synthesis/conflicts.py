"""Conflict detection and presentation."""

from dataclasses import dataclass

from rich.console import Console
from rich.table import Table

from neurosynth.models.knowledge import Conflict, ConflictType, KnowledgeCluster

console = Console()


@dataclass
class ConflictSummary:
    """Summary of conflicts in the knowledge base."""

    total_conflicts: int
    by_type: dict[ConflictType, int]
    high_priority: list[Conflict]
    clusters_with_conflicts: int


class ConflictHandler:
    """Handle detection and presentation of conflicts."""

    def __init__(self):
        self.academic_templates = {
            ConflictType.QUANTITATIVE: (
                "Reported values vary across the literature: {perspectives}."
            ),
            ConflictType.CONTRADICTORY: (
                "There is disagreement in the literature regarding this point. "
                "{perspectives}"
            ),
            ConflictType.APPROACH: (
                "Different surgical approaches have been advocated: {perspectives}."
            ),
            ConflictType.TEMPORAL: (
                "Understanding has evolved over time. {perspectives}"
            ),
            ConflictType.TERMINOLOGY: (
                "Terminology varies across sources: {perspectives}."
            ),
            ConflictType.EMPHASIS: (
                "Authors differ in their emphasis: {perspectives}."
            ),
        }

    def generate_conflict_text(
        self,
        clusters: list[KnowledgeCluster],
    ) -> str:
        """Generate academic text presenting all conflicts."""
        all_conflicts = []
        for cluster in clusters:
            all_conflicts.extend(cluster.conflicts)

        if not all_conflicts:
            return ""

        # Group by type
        by_type = self._group_by_type(all_conflicts)

        paragraphs = []

        # Generate text for each conflict type
        for _conflict_type, conflicts in by_type.items():
            for conflict in conflicts:
                text = self._format_conflict(conflict)
                if text:
                    paragraphs.append(text)

        if paragraphs:
            header = "**Points of Controversy**\n\n"
            return header + "\n\n".join(paragraphs)

        return ""

    def _format_conflict(self, conflict: Conflict) -> str:
        """Format a single conflict for presentation."""
        if not conflict.perspectives:
            return ""

        # Format perspectives
        perspective_texts = []
        for p in conflict.perspectives:
            source_ref = f"({p.source.citation_key})" if p.source else ""
            perspective_texts.append(f"{p.claim} {source_ref}")

        # Use appropriate template
        template = self.academic_templates.get(
            conflict.type,
            "{perspectives}",
        )

        if conflict.type == ConflictType.TEMPORAL:
            # Special handling for temporal conflicts
            if len(conflict.perspectives) >= 2:
                sorted_persp = sorted(
                    conflict.perspectives,
                    key=lambda p: p.source.year if p.source and p.source.year else 0,
                )
                older = sorted_persp[0]
                newer = sorted_persp[-1]

                older_ref = f"({older.source.citation_key})" if older.source else ""
                newer_ref = f"({newer.source.citation_key})" if newer.source else ""

                return (
                    f"Classic teaching suggests {older.claim} {older_ref}, "
                    f"though recent evidence indicates {newer.claim} {newer_ref}."
                )

        perspectives_str = "; ".join(perspective_texts)
        return template.format(perspectives=perspectives_str)

    def _group_by_type(
        self,
        conflicts: list[Conflict],
    ) -> dict[ConflictType, list[Conflict]]:
        """Group conflicts by type."""
        groups: dict[ConflictType, list[Conflict]] = {}
        for conflict in conflicts:
            if conflict.type not in groups:
                groups[conflict.type] = []
            groups[conflict.type].append(conflict)
        return groups

    def summarize_conflicts(
        self,
        clusters: list[KnowledgeCluster],
    ) -> ConflictSummary:
        """Generate summary of all conflicts."""
        all_conflicts = []
        clusters_with_conflicts = 0

        for cluster in clusters:
            if cluster.conflicts:
                clusters_with_conflicts += 1
                all_conflicts.extend(cluster.conflicts)

        by_type = {}
        for conflict in all_conflicts:
            if conflict.type not in by_type:
                by_type[conflict.type] = 0
            by_type[conflict.type] += 1

        # Identify high-priority conflicts
        high_priority = [
            c
            for c in all_conflicts
            if c.type in [ConflictType.CONTRADICTORY, ConflictType.QUANTITATIVE]
        ]

        return ConflictSummary(
            total_conflicts=len(all_conflicts),
            by_type=by_type,
            high_priority=high_priority,
            clusters_with_conflicts=clusters_with_conflicts,
        )

    def display_conflict_report(
        self,
        summary: ConflictSummary,
    ) -> None:
        """Display conflict summary in console."""
        console.print("\n[bold]Conflict Analysis Report[/bold]\n")

        # Summary table
        table = Table(title="Conflict Statistics")
        table.add_column("Metric", style="cyan")
        table.add_column("Value", style="green")

        table.add_row("Total Conflicts", str(summary.total_conflicts))
        table.add_row("Clusters with Conflicts", str(summary.clusters_with_conflicts))
        table.add_row("High Priority", str(len(summary.high_priority)))

        console.print(table)

        # Type breakdown
        if summary.by_type:
            type_table = Table(title="Conflicts by Type")
            type_table.add_column("Type", style="cyan")
            type_table.add_column("Count", style="yellow")

            for conflict_type, count in sorted(
                summary.by_type.items(),
                key=lambda x: -x[1],
            ):
                type_table.add_row(conflict_type.value, str(count))

            console.print(type_table)

        # High priority details
        if summary.high_priority:
            console.print("\n[bold red]High Priority Conflicts:[/bold red]")
            for i, conflict in enumerate(summary.high_priority[:5], 1):
                console.print(f"\n{i}. [{conflict.type.value}] {conflict.description}")
                for p in conflict.perspectives:
                    source_ref = p.source.citation_key if p.source else "Unknown"
                    console.print(f"   - {p.claim} ({source_ref})", style="dim")


class ConflictLaTeXFormatter:
    """Format conflicts for LaTeX output."""

    @staticmethod
    def format_conflict_box(conflict: Conflict) -> str:
        """Format conflict as a LaTeX box environment."""
        perspectives = []
        for p in conflict.perspectives:
            ref = f"\\cite{{{p.source.citation_key}}}" if p.source else ""
            perspectives.append(f"\\item {p.claim} {ref}")

        persp_text = "\n".join(perspectives)

        return f"""\\begin{{controversybox}}
\\textbf{{{conflict.type.value.title()} Conflict}}

{conflict.description}

\\begin{{itemize}}
{persp_text}
\\end{{itemize}}
\\end{{controversybox}}"""

    @staticmethod
    def format_inline_conflict(conflict: Conflict) -> str:
        """Format conflict for inline presentation."""
        if len(conflict.perspectives) < 2:
            return ""

        sorted_persp = sorted(
            conflict.perspectives,
            key=lambda p: p.source.year if p.source and p.source.year else 0,
        )

        refs = [
            f"\\cite{{{p.source.citation_key}}}" if p.source else ""
            for p in sorted_persp
        ]

        claims = [p.claim for p in sorted_persp]

        return f"{claims[0]} {refs[0]}, though others report {claims[-1]} {refs[-1]}"
