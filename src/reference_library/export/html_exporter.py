"""HTML export for generating interactive index pages."""

from collections import defaultdict
from datetime import datetime
from pathlib import Path

from src import config

from ..search.result_model import SearchResult


class HTMLExporter:
    """Export search results as interactive HTML index."""

    def export(self, results: list[SearchResult], search_term: str, output_path: Path):
        """Export results to HTML file."""
        html = self._generate_html(results, search_term)
        output_path.write_text(html, encoding="utf-8")

    def _generate_html(self, results: list[SearchResult], search_term: str) -> str:
        """Generate complete HTML document."""
        # Group results by series and chapter
        grouped = self._group_results(results)

        # Count by category
        category_counts = defaultdict(int)
        for r in results:
            category_counts[r.category or "Uncategorized"] += 1

        html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Index: {search_term} - Neurosurgery Reference Library</title>
    <style>
        :root {{
            --bg-primary: #1a1a2e;
            --bg-secondary: #16213e;
            --bg-card: #0f3460;
            --text-primary: #eee;
            --text-secondary: #aaa;
            --accent: #e94560;
        }}

        * {{
            box-sizing: border-box;
            margin: 0;
            padding: 0;
        }}

        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            background: var(--bg-primary);
            color: var(--text-primary);
            line-height: 1.6;
            padding: 20px;
        }}

        .container {{
            max-width: 1200px;
            margin: 0 auto;
        }}

        header {{
            text-align: center;
            padding: 40px 20px;
            background: var(--bg-secondary);
            border-radius: 10px;
            margin-bottom: 30px;
        }}

        h1 {{
            font-size: 2.5em;
            margin-bottom: 10px;
            color: var(--accent);
        }}

        .subtitle {{
            color: var(--text-secondary);
            font-size: 1.1em;
        }}

        .stats {{
            display: flex;
            justify-content: center;
            gap: 30px;
            margin-top: 20px;
            flex-wrap: wrap;
        }}

        .stat {{
            text-align: center;
        }}

        .stat-value {{
            font-size: 2em;
            font-weight: bold;
            color: var(--accent);
        }}

        .stat-label {{
            color: var(--text-secondary);
            font-size: 0.9em;
        }}

        .filters {{
            background: var(--bg-secondary);
            padding: 20px;
            border-radius: 10px;
            margin-bottom: 30px;
        }}

        .filter-title {{
            font-weight: bold;
            margin-bottom: 10px;
        }}

        .category-filters {{
            display: flex;
            gap: 10px;
            flex-wrap: wrap;
        }}

        .category-btn {{
            padding: 8px 16px;
            border: none;
            border-radius: 20px;
            cursor: pointer;
            font-size: 0.9em;
            transition: opacity 0.2s;
        }}

        .category-btn.inactive {{
            opacity: 0.4;
        }}

        .search-box {{
            margin-top: 15px;
        }}

        .search-box input {{
            width: 100%;
            padding: 10px 15px;
            border: none;
            border-radius: 5px;
            background: var(--bg-card);
            color: var(--text-primary);
            font-size: 1em;
        }}

        .series {{
            margin-bottom: 30px;
        }}

        .series-header {{
            background: var(--bg-secondary);
            padding: 15px 20px;
            border-radius: 10px 10px 0 0;
            cursor: pointer;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }}

        .series-header:hover {{
            background: var(--bg-card);
        }}

        .series-title {{
            font-size: 1.3em;
            font-weight: bold;
        }}

        .series-count {{
            background: var(--accent);
            padding: 4px 12px;
            border-radius: 15px;
            font-size: 0.9em;
        }}

        .chapters {{
            background: var(--bg-card);
            border-radius: 0 0 10px 10px;
            padding: 10px;
        }}

        .chapter {{
            margin: 10px 0;
            padding: 15px;
            background: var(--bg-secondary);
            border-radius: 8px;
        }}

        .chapter-title {{
            font-weight: bold;
            margin-bottom: 10px;
            color: var(--text-primary);
        }}

        .matches {{
            display: flex;
            flex-direction: column;
            gap: 8px;
        }}

        .match {{
            display: flex;
            align-items: flex-start;
            gap: 10px;
            padding: 10px;
            background: var(--bg-primary);
            border-radius: 5px;
            font-size: 0.95em;
        }}

        .match-page {{
            background: var(--bg-card);
            padding: 4px 10px;
            border-radius: 4px;
            font-weight: bold;
            white-space: nowrap;
        }}

        .match-category {{
            padding: 4px 10px;
            border-radius: 4px;
            font-size: 0.85em;
            font-weight: bold;
            white-space: nowrap;
        }}

        .match-context {{
            flex: 1;
            color: var(--text-secondary);
        }}

        .highlight {{
            background: var(--accent);
            color: white;
            padding: 0 2px;
            border-radius: 2px;
        }}

        footer {{
            text-align: center;
            padding: 30px;
            color: var(--text-secondary);
            font-size: 0.9em;
        }}

        /* Category colors */
        .cat-Anatomy {{ background: #3498db; color: white; }}
        .cat-Pathology {{ background: #9b59b6; color: white; }}
        .cat-Imaging {{ background: #1abc9c; color: white; }}
        .cat-Surgery {{ background: #e74c3c; color: white; }}
        .cat-Management {{ background: #f39c12; color: white; }}
        .cat-Epidemiology {{ background: #27ae60; color: white; }}
        .cat-Complications {{ background: #e67e22; color: white; }}
        .cat-Other {{ background: #95a5a6; color: white; }}
        .cat-Uncategorized {{ background: #7f8c8d; color: white; }}

        .collapsed .chapters {{
            display: none;
        }}

        @media (max-width: 768px) {{
            .stats {{
                gap: 15px;
            }}
            .stat-value {{
                font-size: 1.5em;
            }}
            .match {{
                flex-direction: column;
            }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>"{search_term}"</h1>
            <p class="subtitle">Neurosurgery Reference Library Index</p>
            <div class="stats">
                <div class="stat">
                    <div class="stat-value">{len(results)}</div>
                    <div class="stat-label">Total Matches</div>
                </div>
                <div class="stat">
                    <div class="stat-value">{len(grouped)}</div>
                    <div class="stat-label">Book Series</div>
                </div>
                <div class="stat">
                    <div class="stat-value">{sum(len(chapters) for chapters in grouped.values())}</div>
                    <div class="stat-label">Chapters</div>
                </div>
            </div>
        </header>

        <div class="filters">
            <div class="filter-title">Filter by Category:</div>
            <div class="category-filters">
                {self._generate_category_buttons(category_counts)}
            </div>
            <div class="search-box">
                <input type="text" id="searchFilter" placeholder="Filter results..." oninput="filterResults()">
            </div>
        </div>

        <div id="results">
            {self._generate_results_html(grouped, search_term)}
        </div>

        <footer>
            Generated on {datetime.now().strftime("%Y-%m-%d %H:%M")} |
            Neurosurgery Reference Library Research System
        </footer>
    </div>

    <script>
        // Category filter state
        const activeCategories = new Set({list(category_counts.keys())});

        function toggleCategory(category) {{
            const btn = event.target;
            if (activeCategories.has(category)) {{
                activeCategories.delete(category);
                btn.classList.add('inactive');
            }} else {{
                activeCategories.add(category);
                btn.classList.remove('inactive');
            }}
            filterResults();
        }}

        function filterResults() {{
            const searchText = document.getElementById('searchFilter').value.toLowerCase();
            const matches = document.querySelectorAll('.match');

            matches.forEach(match => {{
                const category = match.dataset.category;
                const text = match.textContent.toLowerCase();
                const categoryMatch = activeCategories.has(category);
                const textMatch = searchText === '' || text.includes(searchText);
                match.style.display = (categoryMatch && textMatch) ? 'flex' : 'none';
            }});

            // Hide empty chapters/series
            document.querySelectorAll('.chapter').forEach(chapter => {{
                const visibleMatches = chapter.querySelectorAll('.match[style="display: flex;"], .match:not([style])');
                chapter.style.display = visibleMatches.length > 0 ? 'block' : 'none';
            }});

            document.querySelectorAll('.series').forEach(series => {{
                const visibleChapters = series.querySelectorAll('.chapter[style="display: block;"], .chapter:not([style])');
                series.style.display = visibleChapters.length > 0 ? 'block' : 'none';
            }});
        }}

        function toggleSeries(element) {{
            element.closest('.series').classList.toggle('collapsed');
        }}
    </script>
</body>
</html>"""
        return html

    def _group_results(self, results: list[SearchResult]) -> dict:
        """Group results by series and chapter."""
        grouped = defaultdict(lambda: defaultdict(list))
        for r in results:
            series_name = config.KNOWN_SERIES.get(r.book_series, r.book_series)
            chapter_key = r.display_name
            grouped[series_name][chapter_key].append(r)
        return grouped

    def _generate_category_buttons(self, category_counts: dict) -> str:
        """Generate HTML for category filter buttons."""
        buttons = []
        for category, count in sorted(category_counts.items()):
            css_class = f"cat-{category.replace(' ', '')}"
            buttons.append(
                f'<button class="category-btn {css_class}" onclick="toggleCategory(\'{category}\')">'
                f"{category} ({count})</button>"
            )
        return "\n                ".join(buttons)

    def _generate_results_html(self, grouped: dict, search_term: str) -> str:
        """Generate HTML for grouped results."""
        html_parts = []

        for series_name, chapters in sorted(grouped.items()):
            total_matches = sum(len(matches) for matches in chapters.values())

            chapters_html = []
            for chapter_name, matches in sorted(chapters.items()):
                matches_html = []
                for m in sorted(matches, key=lambda x: x.page_number):
                    category = m.category or "Uncategorized"
                    css_class = f"cat-{category.replace(' ', '')}"

                    # Highlight search term in context
                    context = m.context
                    import re

                    highlighted = re.sub(
                        f"({re.escape(search_term)})",
                        r'<span class="highlight">\1</span>',
                        context,
                        flags=re.IGNORECASE,
                    )

                    matches_html.append(
                        f"""
                    <div class="match" data-category="{category}">
                        <span class="match-page">p.{m.page_number}</span>
                        <span class="match-category {css_class}">{category}</span>
                        <span class="match-context">{highlighted}</span>
                    </div>"""
                    )

                chapters_html.append(
                    f"""
                <div class="chapter">
                    <div class="chapter-title">{chapter_name}</div>
                    <div class="matches">
                        {''.join(matches_html)}
                    </div>
                </div>"""
                )

            html_parts.append(
                f"""
            <div class="series">
                <div class="series-header" onclick="toggleSeries(this)">
                    <span class="series-title">{series_name}</span>
                    <span class="series-count">{total_matches} matches</span>
                </div>
                <div class="chapters">
                    {''.join(chapters_html)}
                </div>
            </div>"""
            )

        return "\n".join(html_parts)
