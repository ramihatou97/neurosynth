#!/usr/bin/env python3
"""Clustering quality validation script.

This script validates the quality of semantic clustering by:
1. Measuring intra-cluster vs inter-cluster similarity (silhouette-like metric)
2. Checking for over-merging (clusters too large)
3. Checking for under-merging (singleton clusters)
4. Comparing FAISS vs sklearn clustering results

Usage:
    python scripts/validate_clustering.py --chunks 1000 --threshold 0.92
    python scripts/validate_clustering.py --input data/processed/chunks.json
"""

import argparse
import asyncio
import json
import sys
from pathlib import Path

import numpy as np
from rich.console import Console
from rich.table import Table

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

console = Console()


def generate_synthetic_chunks(n: int, n_topics: int = 10):
    """Generate synthetic chunks with known topic structure for validation."""
    from neurosynth.models.document import ContentChunk, SourceRef

    chunks = []
    topics = [
        "craniotomy surgical approach",
        "tumor resection techniques",
        "aneurysm clipping procedure",
        "spine fusion methods",
        "deep brain stimulation",
        "endoscopic approaches",
        "ventriculostomy drainage",
        "stereotactic biopsy",
        "microvascular decompression",
        "awake craniotomy mapping",
    ]

    for i in range(n):
        topic_idx = i % n_topics
        base_topic = topics[topic_idx % len(topics)]

        # Create variations of the same topic
        variations = [
            f"The {base_topic} involves careful patient positioning and precise incision planning. "
            f"Critical anatomical landmarks must be identified before proceeding. Variation {i}.",
            f"During {base_topic}, the surgeon must maintain awareness of surrounding structures. "
            f"Hemostasis is crucial throughout the procedure. Instance {i}.",
            f"Post-operative care following {base_topic} includes monitoring for complications. "
            f"Neurological assessment should be performed regularly. Sample {i}.",
        ]

        content = variations[i % len(variations)]

        chunk = ContentChunk(
            content=content,
            source=SourceRef(
                path=Path(f"source_{topic_idx}.pdf"), title=f"Source {topic_idx}"
            ),
            chunk_index=i,
        )
        # Store ground truth topic for validation
        chunk.metadata = {"ground_truth_topic": topic_idx}
        chunks.append(chunk)

    return chunks


async def run_clustering_comparison(chunks, threshold: float):
    """Run both FAISS and sklearn clustering and compare results."""
    from neurosynth.dedup import FAISS_AVAILABLE, SemanticClusterer
    from neurosynth.dedup.embeddings import EmbeddingGenerator

    results = {}

    # Generate embeddings first
    console.print("[blue]Generating embeddings...[/blue]")
    generator = EmbeddingGenerator()
    await generator.generate_embeddings(chunks)

    # sklearn clustering
    console.print("[blue]Running sklearn AgglomerativeClustering...[/blue]")
    sklearn_clusterer = SemanticClusterer(similarity_threshold=threshold)
    sklearn_result = await sklearn_clusterer.cluster_chunks(chunks)
    results["sklearn"] = {
        "num_clusters": sklearn_result.num_clusters,
        "clusters": sklearn_result.clusters,
        "dedup_ratio": sklearn_result.dedup_ratio,
    }

    # FAISS clustering
    if FAISS_AVAILABLE:
        console.print("[blue]Running FAISS IndexFlatIP clustering...[/blue]")
        from neurosynth.dedup import FAISSClusterer

        faiss_clusterer = FAISSClusterer(similarity_threshold=threshold)
        faiss_result = await faiss_clusterer.cluster_chunks(chunks)
        results["faiss"] = {
            "num_clusters": faiss_result.num_clusters,
            "clusters": faiss_result.clusters,
            "dedup_ratio": faiss_result.dedup_ratio,
            "search_time_ms": faiss_result.faiss_search_time_ms,
        }
    else:
        console.print("[yellow]FAISS not available, skipping FAISS comparison[/yellow]")

    return results


def compute_cluster_quality_metrics(clusters, chunks):
    """Compute clustering quality metrics."""
    if not clusters or not chunks:
        return {}

    # Build chunk index -> cluster mapping
    chunk_to_cluster = {}
    for cluster in clusters:
        for chunk in cluster.chunks:
            chunk_to_cluster[chunk.id] = cluster.id

    # Collect embeddings
    embeddings = np.vstack([c.embedding for c in chunks if c.embedding is not None])

    # Compute pairwise similarities for sampled pairs
    n = len(chunks)
    n_samples = min(5000, n * (n - 1) // 2)

    intra_sims = []
    inter_sims = []

    rng = np.random.default_rng(42)
    sampled_pairs = set()

    while len(sampled_pairs) < n_samples:
        i, j = rng.integers(0, n, size=2)
        if i != j and (i, j) not in sampled_pairs:
            sampled_pairs.add((i, j))
            sampled_pairs.add((j, i))

            sim = float(
                np.dot(embeddings[i], embeddings[j])
                / (np.linalg.norm(embeddings[i]) * np.linalg.norm(embeddings[j]))
            )

            chunk_i_cluster = chunk_to_cluster.get(chunks[i].id)
            chunk_j_cluster = chunk_to_cluster.get(chunks[j].id)

            if chunk_i_cluster and chunk_j_cluster:
                if chunk_i_cluster == chunk_j_cluster:
                    intra_sims.append(sim)
                else:
                    inter_sims.append(sim)

    # Compute cluster size distribution
    sizes = [len(c.chunks) for c in clusters]

    metrics = {
        "mean_intra_similarity": float(np.mean(intra_sims)) if intra_sims else 0.0,
        "std_intra_similarity": float(np.std(intra_sims)) if intra_sims else 0.0,
        "mean_inter_similarity": float(np.mean(inter_sims)) if inter_sims else 0.0,
        "std_inter_similarity": float(np.std(inter_sims)) if inter_sims else 0.0,
        "separation_gap": (
            float(np.mean(intra_sims) - np.mean(inter_sims))
            if intra_sims and inter_sims
            else 0.0
        ),
        "num_clusters": len(clusters),
        "num_singletons": sum(1 for s in sizes if s == 1),
        "largest_cluster": max(sizes) if sizes else 0,
        "mean_cluster_size": float(np.mean(sizes)) if sizes else 0.0,
        "median_cluster_size": float(np.median(sizes)) if sizes else 0.0,
    }

    return metrics


def evaluate_topic_purity(clusters, chunks):
    """Evaluate clustering purity against ground truth topics (for synthetic data)."""
    if not all(hasattr(c, "metadata") and c.metadata for c in chunks):
        return None

    total_correct = 0
    total = 0

    for cluster in clusters:
        # Get ground truth topics for chunks in this cluster
        topics = []
        for chunk in cluster.chunks:
            if hasattr(chunk, "metadata") and chunk.metadata:
                topic = chunk.metadata.get("ground_truth_topic")
                if topic is not None:
                    topics.append(topic)

        if topics:
            # Purity: fraction of chunks belonging to majority topic
            from collections import Counter

            counts = Counter(topics)
            majority_count = counts.most_common(1)[0][1]
            total_correct += majority_count
            total += len(topics)

    purity = total_correct / total if total > 0 else 0.0
    return purity


def print_results(results, chunks):
    """Print comparison results in a nice table."""
    table = Table(title="Clustering Comparison")
    table.add_column("Metric", style="cyan")

    backends = list(results.keys())
    for backend in backends:
        table.add_column(backend.upper(), style="green")

    # Basic metrics
    metrics_to_show = [
        ("num_clusters", "Number of Clusters"),
        ("dedup_ratio", "Dedup Ratio"),
    ]

    for key, label in metrics_to_show:
        row = [label]
        for backend in backends:
            val = results[backend].get(key, "N/A")
            if isinstance(val, float):
                row.append(f"{val:.2f}")
            else:
                row.append(str(val))
        table.add_row(*row)

    # Quality metrics
    for backend in backends:
        clusters = results[backend].get("clusters", [])
        metrics = compute_cluster_quality_metrics(clusters, chunks)
        results[backend]["quality_metrics"] = metrics

    quality_metrics = [
        ("mean_intra_similarity", "Mean Intra-Cluster Sim"),
        ("mean_inter_similarity", "Mean Inter-Cluster Sim"),
        ("separation_gap", "Separation Gap"),
        ("num_singletons", "Singleton Clusters"),
        ("largest_cluster", "Largest Cluster Size"),
        ("mean_cluster_size", "Mean Cluster Size"),
    ]

    for key, label in quality_metrics:
        row = [label]
        for backend in backends:
            qm = results[backend].get("quality_metrics", {})
            val = qm.get(key, "N/A")
            if isinstance(val, float):
                row.append(f"{val:.3f}")
            else:
                row.append(str(val))
        table.add_row(*row)

    # Topic purity (for synthetic data)
    purity_row = ["Topic Purity"]
    for backend in backends:
        clusters = results[backend].get("clusters", [])
        purity = evaluate_topic_purity(clusters, chunks)
        if purity is not None:
            purity_row.append(f"{purity:.3f}")
        else:
            purity_row.append("N/A")
    table.add_row(*purity_row)

    # FAISS-specific metrics
    if "faiss" in results and "search_time_ms" in results["faiss"]:
        table.add_row(
            "FAISS Search Time", "N/A", f"{results['faiss']['search_time_ms']:.1f}ms"
        )

    console.print(table)

    # Quality assessment
    console.print("\n[bold]Quality Assessment:[/bold]")

    for backend in backends:
        qm = results[backend].get("quality_metrics", {})
        sep_gap = qm.get("separation_gap", 0)
        singletons = qm.get("num_singletons", 0)
        largest = qm.get("largest_cluster", 0)
        num_chunks = len(chunks)

        issues = []

        if sep_gap < 0.1:
            issues.append("⚠️ Low separation gap - clusters may be poorly separated")
        if singletons > num_chunks * 0.3:
            issues.append("⚠️ Many singleton clusters - threshold may be too high")
        if largest > num_chunks * 0.3:
            issues.append("⚠️ Very large cluster - threshold may be too low")

        if issues:
            console.print(f"\n[yellow]{backend.upper()} issues:[/yellow]")
            for issue in issues:
                console.print(f"  {issue}")
        else:
            console.print(
                f"\n[green]{backend.upper()}: All quality checks passed ✓[/green]"
            )


async def main():
    parser = argparse.ArgumentParser(description="Validate clustering quality")
    parser.add_argument(
        "--chunks",
        type=int,
        default=500,
        help="Number of synthetic chunks to generate (default: 500)",
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=0.92,
        help="Similarity threshold for clustering (default: 0.92)",
    )
    parser.add_argument(
        "--topics",
        type=int,
        default=10,
        help="Number of topics for synthetic data (default: 10)",
    )
    parser.add_argument(
        "--input",
        type=str,
        help="Path to JSON file with real chunks (optional)",
    )

    args = parser.parse_args()

    # Generate or load chunks
    if args.input:
        console.print(f"[blue]Loading chunks from {args.input}...[/blue]")
        with open(args.input) as f:
            data = json.load(f)
        # Would need to deserialize chunks here
        console.print("[red]Loading real chunks not yet implemented[/red]")
        return
    else:
        console.print(
            f"[blue]Generating {args.chunks} synthetic chunks with {args.topics} topics...[/blue]"
        )
        chunks = generate_synthetic_chunks(args.chunks, args.topics)

    console.print(
        f"[blue]Running clustering with threshold={args.threshold}...[/blue]\n"
    )

    # Run clustering comparison
    results = await run_clustering_comparison(chunks, args.threshold)

    # Print results
    print_results(results, chunks)


if __name__ == "__main__":
    asyncio.run(main())
