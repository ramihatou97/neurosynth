"""UI styles and theming for CustomTkinter."""
from src import config

# Font configurations
FONTS = {
    "heading": ("Helvetica", 16, "bold"),
    "subheading": ("Helvetica", 14, "bold"),
    "body": ("Helvetica", 12),
    "body_bold": ("Helvetica", 12, "bold"),
    "small": ("Helvetica", 10),
    "mono": ("Courier", 11),
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

# Category badge styles
def get_category_style(category: str) -> dict:
    """Get styling for category badge."""
    color = config.CATEGORY_COLORS.get(category, config.CATEGORY_COLORS["Other"])
    return {
        "fg_color": color,
        "text_color": "white",
        "corner_radius": 4,
    }


# Status colors
STATUS_COLORS = {
    "success": "#27ae60",
    "warning": "#f39c12",
    "error": "#e74c3c",
    "info": "#3498db",
}
