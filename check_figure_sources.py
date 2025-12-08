import json
from pathlib import Path

manifest_path = Path("/Users/ramihatoum/neurosynth/real_synthesis_output/manifest.json")

with open(manifest_path, "r") as f:
    data = json.load(f)

print(
    f"Total Figures in Summary: {data.get('figure_summary', {}).get('total_figures')}"
)

print("\nFigure Source Mapping:")
print(f"{'Figure ID':<15} | {'Source PDF':<40} | {'Page':<5} | {'Caption'}")
print("-" * 100)

found_figures = 0
for source in data.get("sources", []):
    pdf_name = source.get("pdf_path", "Unknown")
    figures = source.get("figures", [])

    for fig in figures:
        fig_id = fig.get("id", "N/A")
        page = fig.get("page_number", "N/A")
        caption = (
            fig.get("caption", "No caption")[:50] + "..."
            if len(fig.get("caption", "")) > 50
            else fig.get("caption", "")
        )

        print(f"{fig_id:<15} | {pdf_name:<40} | {page:<5} | {caption}")
        found_figures += 1

print(f"\nTotal Figures Found in Sources: {found_figures}")
