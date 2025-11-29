"""Configuration for the Neurosurgery Reference Library App."""
import json
import os
from pathlib import Path

# Paths
PROJECT_ROOT = Path(__file__).parent
DATA_DIR = PROJECT_ROOT / "data"
TEMPLATES_DIR = PROJECT_ROOT / "templates"
USER_CONFIG_FILE = DATA_DIR / "user_config.json"

# Ensure data directory exists
DATA_DIR.mkdir(parents=True, exist_ok=True)


def _load_user_config() -> dict:
    """Load user configuration from JSON file."""
    if USER_CONFIG_FILE.exists():
        try:
            config = json.loads(USER_CONFIG_FILE.read_text())
            if not isinstance(config, dict):
                print("Warning: Invalid config file format, using defaults")
                return {}
            return config
        except json.JSONDecodeError as e:
            print(f"Warning: Failed to parse config file: {e}")
            return {}
        except IOError as e:
            print(f"Warning: Failed to read config file: {e}")
            return {}
    return {}


def _save_user_config(config: dict) -> None:
    """Save user configuration to JSON file."""
    try:
        USER_CONFIG_FILE.write_text(json.dumps(config, indent=2))
    except IOError:
        pass


def _get_library_path() -> Path:
    """Get the library path from config or environment.

    Priority:
    1. User config file (user_config.json)
    2. Environment variable NEUROSURGERY_LIBRARY_PATH
    3. Default path (will prompt if doesn't exist)
    """
    config = _load_user_config()

    # Try user config first
    if "library_path" in config:
        # Strip whitespace to prevent path resolution issues
        path_str = str(config["library_path"]).strip()
        if path_str:
            path = Path(path_str).expanduser()
            if path.exists():
                return path

    # Try environment variable
    env_path = os.environ.get("NEUROSURGERY_LIBRARY_PATH")
    if env_path:
        path = Path(env_path).expanduser()
        if path.exists():
            return path

    # Default path (may not exist - will trigger folder picker)
    default_path = Path.home() / "Documents" / "NeurosurgeryLibrary"
    return default_path


def prompt_for_library_path() -> Path | None:
    """Show folder picker dialog for library path selection.

    Returns the selected path or None if cancelled.
    """
    try:
        import tkinter as tk
        from tkinter import filedialog, messagebox

        # Create hidden root window
        root = tk.Tk()
        root.withdraw()

        # Show info message
        messagebox.showinfo(
            "Neurosurgery Reference Library",
            "Please select the folder containing your neurosurgery reference PDFs.\n\n"
            "This is typically a folder with PDF textbooks and reference materials."
        )

        # Show folder picker
        selected_path = filedialog.askdirectory(
            title="Select Neurosurgery Reference Library Folder",
            initialdir=str(Path.home() / "Documents")
        )

        root.destroy()

        if selected_path:
            path = Path(selected_path)
            # Save to user config
            config = _load_user_config()
            config["library_path"] = str(path)
            _save_user_config(config)
            return path

        return None

    except ImportError:
        return None


def ensure_library_path() -> Path:
    """Ensure library path exists, prompting user if needed.

    Returns a valid Path or raises SystemExit if user cancels.
    """
    global LIBRARY_PATH

    path = _get_library_path()

    if not path.exists():
        # Prompt user to select folder
        selected = prompt_for_library_path()
        if selected and selected.exists():
            LIBRARY_PATH = selected
            return LIBRARY_PATH
        else:
            print("No valid library path selected. Exiting.")
            raise SystemExit(1)

    LIBRARY_PATH = path
    return LIBRARY_PATH


# Initialize library path (may be updated by ensure_library_path())
LIBRARY_PATH = _get_library_path()

# NeuroSynth Integration (parent directory since we're now inside neurosynth/)
NEUROSYNTH_PATH = PROJECT_ROOT.parent
NEUROSYNTH_VENV = NEUROSYNTH_PATH / "venv"

# Database
DATABASE_PATH = DATA_DIR / "library.db"

# API Configuration
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")

# AI Feature Flag - can be disabled via environment or if API key missing
AI_ENABLED = bool(ANTHROPIC_API_KEY) and os.environ.get("NEUROSYNTH_DISABLE_AI", "").lower() not in ("1", "true", "yes")

# Search Configuration
CONTEXT_WINDOW_SIZE = 500  # Characters before/after match for context
MAX_CONCURRENT_SEARCHES = 4  # Parallel PDF searches
MAX_CONCURRENT_API_CALLS = 3  # Parallel Claude API calls

# Semantic Search Configuration
SEMANTIC_SEARCH_ENABLED = True
EMBEDDING_MODEL = "all-MiniLM-L6-v2"  # Fast, 384-dim, good for medical text
CHROMA_DB_PATH = DATA_DIR / "chroma"

# AI Model Configuration
AI_MODEL = os.environ.get("NEUROSYNTH_AI_MODEL", "claude-sonnet-4-20250514")
AI_MAX_TOKENS = 200

# Hierarchical Category System (based on standard neurosurgical textbook structure)
CATEGORY_GROUPS = {
    "Surgical/Anatomical": {
        "color": "#e74c3c",  # Red family
        "description": "Step-by-step procedural content from positioning to closure",
        "subcategories": [
            "Preoperative Planning",
            "Anesthetic Considerations",
            "Patient Positioning",
            "Surgical Approach",
            "Anatomical Landmarks",
            "Surgical Technique",
            "Reconstruction",
            "Closure",
            "Intraoperative Monitoring",
            "Technical Pitfalls"
        ]
    },
    "Theoretical": {
        "color": "#3498db",  # Blue family
        "description": "Disease knowledge, diagnosis, and clinical management",
        "subcategories": [
            "Definition & Classification",
            "Epidemiology",
            "Pathophysiology",
            "Clinical Presentation",
            "Diagnostic Evaluation",
            "Differential Diagnosis",
            "Treatment Options",
            "Postoperative Management",
            "Complications",
            "Outcomes",
            "Future Directions"
        ]
    }
}

# Flattened list for backward compatibility
CATEGORIES = []
for group, data in CATEGORY_GROUPS.items():
    CATEGORIES.extend(data["subcategories"])
CATEGORIES.append("Other")

# Subcategory to group mapping
CATEGORY_TO_GROUP = {}
for group, data in CATEGORY_GROUPS.items():
    for subcat in data["subcategories"]:
        CATEGORY_TO_GROUP[subcat] = group
CATEGORY_TO_GROUP["Other"] = "Theoretical"

# Category colors for UI (hex) - distinct within each group
CATEGORY_COLORS = {
    # Surgical/Anatomical (Red/Orange spectrum)
    "Preoperative Planning": "#c0392b",
    "Anesthetic Considerations": "#e74c3c",
    "Patient Positioning": "#d35400",
    "Surgical Approach": "#e67e22",
    "Anatomical Landmarks": "#f39c12",
    "Surgical Technique": "#e74c3c",
    "Reconstruction": "#c0392b",
    "Closure": "#d35400",
    "Intraoperative Monitoring": "#e67e22",
    "Technical Pitfalls": "#c0392b",

    # Theoretical (Blue/Green/Purple spectrum)
    "Definition & Classification": "#2980b9",
    "Epidemiology": "#27ae60",
    "Pathophysiology": "#8e44ad",
    "Clinical Presentation": "#16a085",
    "Diagnostic Evaluation": "#1abc9c",
    "Differential Diagnosis": "#3498db",
    "Treatment Options": "#2ecc71",
    "Postoperative Management": "#9b59b6",
    "Complications": "#e74c3c",
    "Outcomes": "#27ae60",
    "Future Directions": "#3498db",

    "Other": "#95a5a6"
}

# Known book series for parsing
KNOWN_SERIES = {
    "Youmans and Winn": "Youmans & Winn Neurological Surgery 8th Ed",
    "Core Techniques": "Core Techniques in Operative Neurosurgery",
    "AOSpine": "AOSpine Master Series",
    "Rhoton": "Rhoton's Cranial Anatomy",
    "Rothman-Simeone": "Rothman-Simeone & Herkowitz's The Spine",
    "Practical Surgical Neuropathology": "Practical Surgical Neuropathology 2nd Ed",
    "Neurosurgical Operative Atlas": "Neurosurgical Operative Atlas",
    "AANS": "AANS Neurosurgical Operative Atlas",
    "Benzel": "Benzel's Spine Surgery"
}

# UI Configuration
WINDOW_WIDTH = 1400
WINDOW_HEIGHT = 900
APPEARANCE_MODE = "dark"  # "dark", "light", or "system"

# Visual Processing Configuration
VISUAL_EXTRACTION_ENABLED = True
VISUAL_SEARCH_ENABLED = True
COLPALI_ENABLED = True  # Set to False on low-memory systems
MIN_IMAGE_SIZE = 50  # Skip images smaller than this (likely icons)
MAX_IMAGE_SIZE = 2048  # Resize images larger than this

# Visual Storage
IMAGES_DIR = DATA_DIR / "images"
THUMBS_DIR = DATA_DIR / "thumbs"
QDRANT_PATH = DATA_DIR / "qdrant"
QDRANT_COLLECTION = "reference_library_visuals"

# Figure type display colors (for thumbnail borders)
IMAGE_TYPE_COLORS = {
    "surgical_step": "#e74c3c",
    "anatomical": "#3498db",
    "imaging": "#9b59b6",
    "illustration": "#27ae60",
    "photograph": "#f39c12",
    "table": "#1abc9c",
    "unknown": "#95a5a6",
}

# Ensure visual directories exist
IMAGES_DIR.mkdir(parents=True, exist_ok=True)
THUMBS_DIR.mkdir(parents=True, exist_ok=True)
