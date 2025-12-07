"""UI styles and theming for CustomTkinter."""

# Font configurations
FONTS = {
    "heading": ("Helvetica", 16, "bold"),
    "subheading": ("Helvetica", 14, "bold"),
    "body": ("Helvetica", 12),
    "body_bold": ("Helvetica", 12, "bold"),
    "small": ("Helvetica", 10),
    "small_bold": ("Helvetica", 10, "bold"),
    "mono": ("Courier", 11),
    "context_preview": ("Courier", 10),  # For inline context display
}

# Padding values
PADDING = {
    "small": 5,
    "medium": 10,
    "large": 20,
}

# Widget dimensions
DIMENSIONS = {
    "search_entry_width": 400,
    "button_width": 100,
    "tree_width": 500,
    "preview_width": 400,
}

# Rich Preview Mode Settings
RICH_PREVIEW = {
    # Inline thumbnail settings
    "thumb_size_small": (32, 32),  # Mini thumbnails in tree rows
    "thumb_size_medium": (48, 48),  # Medium thumbnails for expanded view
    "max_inline_thumbs": 4,  # Max thumbnails shown inline per result
    # Row heights for different modes
    "compact_row_height": 25,  # Standard mode row height
    "rich_row_height": 60,  # Rich mode with thumbnails
    "expanded_row_height": 120,  # Expanded context view
    # Context text settings
    "context_preview_chars": 80,  # Characters shown in compact mode
    "context_expanded_chars": 500,  # Characters shown when expanded
    "context_max_lines": 8,  # Max lines when fully expanded
    # Animation/transition (future)
    "transition_ms": 150,  # Milliseconds for expand/collapse
}

# Status colors
STATUS_COLORS = {
    "success": "#27ae60",
    "warning": "#f39c12",
    "error": "#e74c3c",
    "info": "#3498db",
}

# Rich Preview colors
RICH_PREVIEW_COLORS = {
    "expanded_bg": "#1a1a1a",  # Background for expanded rows
    "context_bg": "#242424",  # Background for context text
    "highlight": "#3498db",  # Highlighted search terms
    "thumb_border": "#444444",  # Default thumbnail border
}
