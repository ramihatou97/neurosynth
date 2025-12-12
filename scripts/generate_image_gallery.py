#!/usr/bin/env python
"""
Enhanced Image Quality Gallery Generator
=========================================
Generates an HTML gallery showing extracted images with:
- Anatomical region badges (colored tags)
- Caption source indicators (OCR/Proximity/Hybrid)
- Region detection confidence bars
- Entropy quality scores
- Deduplication status
"""

import base64
import json
import sys
from datetime import datetime
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

# Region category colors
REGION_COLORS = {
    "brain": "#4CAF50",  # Green
    "vascular": "#F44336",  # Red
    "spine": "#2196F3",  # Blue
    "cranial_nerve": "#9C27B0",  # Purple
    "surgical_corridor": "#FF9800",  # Orange
    "skull_base": "#795548",  # Brown
    "ventricular": "#00BCD4",  # Cyan
}

# Caption source colors
CAPTION_SOURCE_COLORS = {
    "ocr": "#4CAF50",  # Green
    "proximity": "#2196F3",  # Blue
    "hybrid": "#FF9800",  # Orange
}


def get_region_category(region_id: str) -> str:
    """Get category for a region ID."""
    try:
        from neurosynth.enhancements.anatomical_regions import REGION_BY_ID

        region = REGION_BY_ID.get(region_id)
        if region:
            return region.category.value
    except ImportError:
        pass
    return "brain"  # Default


def generate_region_badges(regions: list) -> str:
    """Generate HTML for region badges."""
    if not regions:
        return '<span class="badge badge-none">No regions</span>'

    badges = []
    for region_id in regions[:5]:  # Limit to 5
        category = get_region_category(region_id)
        color = REGION_COLORS.get(category, "#666")
        display_name = region_id.replace("_", " ").title()
        badges.append(
            f'<span class="badge" style="background:{color}">{display_name}</span>'
        )

    if len(regions) > 5:
        badges.append(f'<span class="badge badge-more">+{len(regions)-5} more</span>')

    return " ".join(badges)


def generate_caption_source_badge(source: str) -> str:
    """Generate HTML for caption source badge."""
    color = CAPTION_SOURCE_COLORS.get(source.lower(), "#666")
    icon = {"ocr": "📝", "proximity": "📍", "hybrid": "🔀"}.get(source.lower(), "❓")
    return f'<span class="caption-source" style="background:{color}">{icon} {source.upper()}</span>'


def generate_confidence_bar(confidence: float) -> str:
    """Generate HTML for confidence bar."""
    pct = int(confidence * 100)
    color = "#4CAF50" if pct >= 70 else "#FF9800" if pct >= 40 else "#F44336"
    return f"""
    <div class="confidence-bar">
        <div class="confidence-fill" style="width:{pct}%; background:{color}"></div>
        <span class="confidence-label">{pct}%</span>
    </div>
    """


def generate_entropy_bar(entropy: float) -> str:
    """Generate HTML for entropy quality bar."""
    # Entropy typically 0-8, good images >4.5
    pct = min(100, int((entropy / 8) * 100))
    color = "#4CAF50" if entropy >= 5.0 else "#FF9800" if entropy >= 4.0 else "#F44336"
    return f"""
    <div class="entropy-bar">
        <div class="entropy-fill" style="width:{pct}%; background:{color}"></div>
        <span class="entropy-label">{entropy:.2f}</span>
    </div>
    """


def encode_image_base64(image_path: Path) -> str:
    """Encode image to base64 for embedding in HTML."""
    if not image_path.exists():
        return ""
    try:
        with open(image_path, "rb") as f:
            data = base64.b64encode(f.read()).decode("utf-8")
        suffix = image_path.suffix.lower()
        mime = {
            "png": "image/png",
            "jpg": "image/jpeg",
            "jpeg": "image/jpeg",
            "gif": "image/gif",
        }.get(suffix[1:], "image/png")
        return f"data:{mime};base64,{data}"
    except Exception:
        return ""


def generate_image_card(fig: dict, idx: int) -> str:
    """Generate HTML card for a single image."""
    img_src = encode_image_base64(Path(fig.get("file_path", "")))
    if not img_src:
        img_src = "data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'><rect fill='%23333' width='100' height='100'/><text x='50' y='50' fill='%23666' text-anchor='middle'>No Image</text></svg>"

    regions = fig.get("detected_regions", [])
    confidence = fig.get("region_confidence", 0.0)
    caption_source = fig.get("caption_source", "proximity")
    entropy = fig.get("entropy", 0.0)
    caption = fig.get("caption", fig.get("filename", "Unknown"))
    figure_number = fig.get("figure_number", "")
    ocr_caption = fig.get("ocr_caption", "")
    is_duplicate = fig.get("is_duplicate", False)

    # Build card HTML
    return f"""
    <div class="image-card {'duplicate' if is_duplicate else ''}">
        <div class="image-wrapper">
            <img src="{img_src}" alt="Figure {idx+1}" loading="lazy">
            {f'<span class="fig-badge">{figure_number}</span>' if figure_number else ''}
            {'<span class="dup-badge">DUP</span>' if is_duplicate else ''}
        </div>
        <div class="card-body">
            <div class="region-badges">{generate_region_badges(regions)}</div>
            <div class="metrics-row">
                <div class="metric">
                    <label>Region Conf</label>
                    {generate_confidence_bar(confidence)}
                </div>
                <div class="metric">
                    <label>Entropy</label>
                    {generate_entropy_bar(entropy)}
                </div>
            </div>
            <div class="caption-row">
                {generate_caption_source_badge(caption_source)}
                <span class="caption-text">{caption[:100]}{'...' if len(caption) > 100 else ''}</span>
            </div>
            {'<div class="ocr-caption"><b>OCR:</b> ' + ocr_caption[:80] + '</div>' if ocr_caption else ''}
        </div>
    </div>
    """


def generate_html_gallery(figures_by_pdf: dict, stats: dict) -> str:
    """Generate complete HTML gallery document."""

    # Generate PDF sections
    pdf_sections = []
    for pdf_name, figures in figures_by_pdf.items():
        cards = "\n".join(
            generate_image_card(fig, i) for i, fig in enumerate(figures[:20])
        )

        # PDF-level stats
        total = len(figures)
        with_regions = sum(1 for f in figures if f.get("detected_regions"))
        with_ocr = sum(1 for f in figures if f.get("caption_source") == "ocr")
        avg_entropy = sum(f.get("entropy", 0) for f in figures) / max(1, total)

        pdf_sections.append(
            f"""
        <div class="pdf-section">
            <h2>📄 {pdf_name}</h2>
            <div class="pdf-stats">
                <span>📊 {total} images</span>
                <span>🏷️ {with_regions} with regions ({100*with_regions//max(1,total)}%)</span>
                <span>📝 {with_ocr} OCR captions</span>
                <span>📈 Avg entropy: {avg_entropy:.2f}</span>
            </div>
            <div class="image-grid">{cards}</div>
        </div>
        """
        )

    # Summary stats
    summary = f"""
    <div class="summary-section">
        <h2>📊 Extraction Summary</h2>
        <div class="summary-grid">
            <div class="stat-card">
                <div class="stat-value">{stats.get('total_images', 0)}</div>
                <div class="stat-label">Total Images</div>
            </div>
            <div class="stat-card">
                <div class="stat-value">{stats.get('with_regions', 0)}</div>
                <div class="stat-label">With Region Tags</div>
            </div>
            <div class="stat-card">
                <div class="stat-value">{stats.get('region_coverage_pct', 0):.1f}%</div>
                <div class="stat-label">Region Coverage</div>
            </div>
            <div class="stat-card">
                <div class="stat-value">{stats.get('unique_regions', 0)}</div>
                <div class="stat-label">Unique Regions</div>
            </div>
            <div class="stat-card">
                <div class="stat-value">{stats.get('duplicates_removed', 0)}</div>
                <div class="stat-label">Duplicates Removed</div>
            </div>
            <div class="stat-card">
                <div class="stat-value">{stats.get('avg_entropy', 0):.2f}</div>
                <div class="stat-label">Avg Entropy</div>
            </div>
        </div>
    </div>
    """

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>NeuroSynth Image Quality Gallery</title>
    <style>
        :root {{ --bg: #1a1a2e; --card: #16213e; --text: #eee; --muted: #888; }}
        * {{ box-sizing: border-box; margin: 0; padding: 0; }}
        body {{ font-family: system-ui, sans-serif; background: var(--bg); color: var(--text); padding: 20px; }}
        h1 {{ text-align: center; margin-bottom: 10px; }}
        .timestamp {{ text-align: center; color: var(--muted); margin-bottom: 30px; }}

        .summary-section {{ background: var(--card); padding: 20px; border-radius: 12px; margin-bottom: 30px; }}
        .summary-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 15px; margin-top: 15px; }}
        .stat-card {{ background: rgba(255,255,255,0.1); padding: 15px; border-radius: 8px; text-align: center; }}
        .stat-value {{ font-size: 28px; font-weight: bold; color: #4CAF50; }}
        .stat-label {{ color: var(--muted); font-size: 12px; margin-top: 5px; }}

        .pdf-section {{ margin-bottom: 40px; }}
        .pdf-section h2 {{ margin-bottom: 10px; padding-bottom: 10px; border-bottom: 1px solid #333; }}
        .pdf-stats {{ display: flex; gap: 20px; margin-bottom: 15px; color: var(--muted); font-size: 14px; }}

        .image-grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 15px; }}
        .image-card {{ background: var(--card); border-radius: 10px; overflow: hidden; }}
        .image-card.duplicate {{ opacity: 0.5; border: 2px solid #F44336; }}
        .image-wrapper {{ position: relative; height: 180px; background: #000; }}
        .image-wrapper img {{ width: 100%; height: 100%; object-fit: contain; }}
        .fig-badge {{ position: absolute; top: 8px; left: 8px; background: #4CAF50; color: #fff; padding: 2px 8px; border-radius: 4px; font-size: 11px; }}
        .dup-badge {{ position: absolute; top: 8px; right: 8px; background: #F44336; color: #fff; padding: 2px 8px; border-radius: 4px; font-size: 11px; }}

        .card-body {{ padding: 12px; }}
        .region-badges {{ display: flex; flex-wrap: wrap; gap: 4px; margin-bottom: 10px; }}
        .badge {{ padding: 2px 8px; border-radius: 12px; font-size: 11px; color: #fff; }}
        .badge-none {{ background: #444; color: #888; }}
        .badge-more {{ background: #555; }}

        .metrics-row {{ display: flex; gap: 15px; margin-bottom: 10px; }}
        .metric {{ flex: 1; }}
        .metric label {{ display: block; font-size: 10px; color: var(--muted); margin-bottom: 3px; }}
        .confidence-bar, .entropy-bar {{ height: 8px; background: #333; border-radius: 4px; position: relative; overflow: hidden; }}
        .confidence-fill, .entropy-fill {{ height: 100%; border-radius: 4px; }}
        .confidence-label, .entropy-label {{ position: absolute; right: 5px; top: -1px; font-size: 9px; color: #fff; }}

        .caption-row {{ display: flex; align-items: center; gap: 8px; }}
        .caption-source {{ padding: 2px 6px; border-radius: 4px; font-size: 10px; color: #fff; white-space: nowrap; }}
        .caption-text {{ font-size: 12px; color: var(--muted); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }}
        .ocr-caption {{ font-size: 11px; color: #666; margin-top: 8px; padding-top: 8px; border-top: 1px solid #333; }}
    </style>
</head>
<body>
    <h1>🧠 NeuroSynth Image Quality Gallery</h1>
    <p class="timestamp">Generated: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}</p>

    {summary}

    {"".join(pdf_sections)}
</body>
</html>
"""
    return html


def run_extraction_with_enhancements(
    pdf_paths: list[Path], output_dir: Path
) -> tuple[dict, dict]:
    """Run extraction pipeline with all enhancements enabled."""
    from ingest.smart_extractor import SmartImageExtractor

    extractor = SmartImageExtractor(str(output_dir), min_entropy=4.5)

    figures_by_pdf = {}
    all_regions = set()
    total_images = 0
    with_regions = 0
    duplicates = 0
    entropy_sum = 0

    for pdf_path in pdf_paths:
        print(f"Processing: {pdf_path.name}")

        figures = extractor.process_pdf(
            str(pdf_path),
            enable_caption_parsing=True,
            enable_deduplication=True,
            enable_region_detection=True,
            region_min_confidence=0.3,
            enable_ocr=False,  # Graceful fallback
        )

        # Convert to dicts for serialization
        fig_dicts = []
        for fig in figures:
            d = {
                "file_path": fig.file_path,
                "filename": fig.filename,
                "caption": fig.caption,
                "figure_number": fig.figure_number,
                "entropy": fig.entropy,
                "page": fig.page,
                "detected_regions": fig.detected_regions,
                "region_confidence": fig.region_confidence,
                "ocr_caption": fig.ocr_caption,
                "caption_source": fig.caption_source,
                "is_duplicate": fig.is_duplicate,
            }
            fig_dicts.append(d)

            total_images += 1
            if fig.detected_regions:
                with_regions += 1
                all_regions.update(fig.detected_regions)
            if fig.is_duplicate:
                duplicates += 1
            entropy_sum += fig.entropy

        figures_by_pdf[pdf_path.name] = fig_dicts

    stats = {
        "total_images": total_images,
        "with_regions": with_regions,
        "region_coverage_pct": (with_regions / max(1, total_images)) * 100,
        "unique_regions": len(all_regions),
        "duplicates_removed": duplicates,
        "avg_entropy": entropy_sum / max(1, total_images),
        "pdfs_processed": len(pdf_paths),
    }

    return figures_by_pdf, stats


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Generate enhanced image quality gallery"
    )
    parser.add_argument(
        "--sample", type=int, default=5, help="Number of PDFs to sample"
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path.home() / ".neurosynth" / "image_quality_gallery.html",
    )
    parser.add_argument(
        "--report",
        type=Path,
        default=Path.home() / ".neurosynth" / "enhanced_extraction_report.json",
    )
    args = parser.parse_args()

    # Find PDFs
    library_dir = Path.home() / ".neurosynth" / "library"
    if not library_dir.exists():
        print(f"Library not found at {library_dir}")
        sys.exit(1)

    pdf_files = list(library_dir.glob("**/*.pdf"))[: args.sample]
    if not pdf_files:
        print("No PDF files found")
        sys.exit(1)

    print(f"Found {len(pdf_files)} PDFs to process")

    # Output directory
    output_dir = Path.home() / ".neurosynth" / "extracted_images" / "gallery_sample"
    output_dir.mkdir(parents=True, exist_ok=True)

    # Run extraction
    figures_by_pdf, stats = run_extraction_with_enhancements(pdf_files, output_dir)

    # Generate HTML
    html = generate_html_gallery(figures_by_pdf, stats)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(html)
    print(f"\n✅ Gallery saved to: {args.output}")

    # Save JSON report
    report = {
        "generated_at": datetime.now().isoformat(),
        "stats": stats,
        "pdfs": list(figures_by_pdf.keys()),
        "sample_regions": list(
            set().union(
                *[
                    set(f.get("detected_regions", []))
                    for figs in figures_by_pdf.values()
                    for f in figs
                ]
            )
        )[:20],
    }
    args.report.write_text(json.dumps(report, indent=2))
    print(f"✅ Report saved to: {args.report}")

    # Print summary
    print(f"\n{'='*50}")
    print("EXTRACTION SUMMARY")
    print(f"{'='*50}")
    print(f"PDFs Processed:     {stats['pdfs_processed']}")
    print(f"Total Images:       {stats['total_images']}")
    print(
        f"With Region Tags:   {stats['with_regions']} ({stats['region_coverage_pct']:.1f}%)"
    )
    print(f"Unique Regions:     {stats['unique_regions']}")
    print(f"Duplicates Found:   {stats['duplicates_removed']}")
    print(f"Avg Entropy:        {stats['avg_entropy']:.2f}")
    print(f"{'='*50}")


if __name__ == "__main__":
    main()
