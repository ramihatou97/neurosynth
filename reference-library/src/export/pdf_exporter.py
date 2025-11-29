"""PDF export for generating printable index documents."""
from pathlib import Path
from datetime import datetime
from collections import defaultdict
from fpdf import FPDF

from src import config
from ..search.result_model import SearchResult


class PDFExporter:
    """Export search results as PDF index document."""

    def export(self, results: list[SearchResult], search_term: str, output_path: Path):
        """Export results to PDF file."""
        pdf = self._create_pdf(results, search_term)
        pdf.output(str(output_path))

    def _create_pdf(self, results: list[SearchResult], search_term: str) -> FPDF:
        """Create PDF document."""
        pdf = FPDF()
        pdf.set_auto_page_break(auto=True, margin=15)

        # Add fonts
        pdf.add_page()

        # Title page
        pdf.set_font("Helvetica", "B", 24)
        pdf.cell(0, 20, "", ln=True)  # Spacer
        pdf.cell(0, 15, f'Index: "{search_term}"', ln=True, align="C")

        pdf.set_font("Helvetica", "", 14)
        pdf.cell(0, 10, "Neurosurgery Reference Library", ln=True, align="C")

        pdf.set_font("Helvetica", "", 10)
        pdf.cell(0, 20, "", ln=True)  # Spacer
        pdf.cell(0, 8, f"Total Matches: {len(results)}", ln=True, align="C")
        pdf.cell(0, 8, f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}", ln=True, align="C")

        # Group results
        grouped = self._group_results(results)

        # Category summary
        pdf.add_page()
        pdf.set_font("Helvetica", "B", 16)
        pdf.cell(0, 12, "Summary by Category", ln=True)

        category_counts = defaultdict(int)
        for r in results:
            category_counts[r.category or "Uncategorized"] += 1

        pdf.set_font("Helvetica", "", 11)
        for category in config.CATEGORIES + ["Uncategorized"]:
            if category in category_counts:
                pdf.cell(0, 8, f"  {category}: {category_counts[category]} matches", ln=True)

        # Table of Contents
        pdf.add_page()
        pdf.set_font("Helvetica", "B", 16)
        pdf.cell(0, 12, "Table of Contents", ln=True)

        pdf.set_font("Helvetica", "", 10)
        page_num = 4  # Starting page for content

        for series_name in sorted(grouped.keys()):
            chapters = grouped[series_name]
            total = sum(len(m) for m in chapters.values())
            pdf.cell(0, 7, f"{series_name} ({total} matches)", ln=True)
            page_num += 1

        # Content pages - one per series
        for series_name, chapters in sorted(grouped.items()):
            pdf.add_page()

            # Series header
            pdf.set_font("Helvetica", "B", 14)
            pdf.set_fill_color(52, 152, 219)  # Blue
            pdf.set_text_color(255, 255, 255)
            pdf.cell(0, 10, series_name, ln=True, fill=True)
            pdf.set_text_color(0, 0, 0)

            for chapter_name, matches in sorted(chapters.items()):
                # Chapter header
                pdf.set_font("Helvetica", "B", 11)
                pdf.cell(0, 8, chapter_name, ln=True)

                # Matches table
                pdf.set_font("Helvetica", "", 9)

                for m in sorted(matches, key=lambda x: x.page_number):
                    category = m.category or "Uncategorized"

                    # Set category color
                    color = self._get_category_rgb(category)
                    pdf.set_fill_color(*color)
                    pdf.set_text_color(255, 255, 255)

                    # Page number
                    pdf.cell(15, 6, f"p.{m.page_number}", border=0)

                    # Category badge
                    pdf.cell(25, 6, category[:10], border=0, fill=True)

                    pdf.set_text_color(0, 0, 0)
                    pdf.set_fill_color(255, 255, 255)

                    # Context (truncated)
                    context = m.context[:100].replace('\n', ' ')
                    if len(m.context) > 100:
                        context += "..."

                    pdf.multi_cell(0, 6, f"  {context}", border=0)

                pdf.cell(0, 3, "", ln=True)  # Small spacer between chapters

        return pdf

    def _group_results(self, results: list[SearchResult]) -> dict:
        """Group results by series and chapter."""
        grouped = defaultdict(lambda: defaultdict(list))
        for r in results:
            series_name = config.KNOWN_SERIES.get(r.book_series, r.book_series)
            chapter_key = r.display_name
            grouped[series_name][chapter_key].append(r)
        return grouped

    def _get_category_rgb(self, category: str) -> tuple:
        """Get RGB tuple for category color."""
        hex_color = config.CATEGORY_COLORS.get(category, "#95a5a6")
        # Convert hex to RGB
        hex_color = hex_color.lstrip('#')
        return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
