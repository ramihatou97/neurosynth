"""JSON serialization utilities with numpy array support.

This module provides JSON encoding/decoding that handles numpy arrays
by converting them to/from Python lists, as well as Path objects and Enums.
"""

import json
import pickle
from enum import Enum
from pathlib import Path
from typing import Any

import numpy as np


class NumpyEncoder(json.JSONEncoder):
    """JSON encoder that handles numpy arrays and other special types.

    Converts:
    - numpy arrays to lists (via .tolist())
    - numpy scalar types to Python scalars
    - Path objects to strings
    - Enums to their values
    """

    def default(self, obj: Any) -> Any:
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        elif isinstance(obj, np.generic):
            return obj.item()
        elif isinstance(obj, Path):
            return str(obj)
        elif isinstance(obj, Enum):
            return obj.value
        elif isinstance(obj, bytes):
            # Rare case - encode bytes as base64 if encountered
            import base64

            return {"_bytes_": base64.b64encode(obj).decode("utf-8")}
        return super().default(obj)


def numpy_decoder_hook(dct: dict) -> Any:
    """JSON decoder hook to reconstruct special types.

    Note: Numpy arrays must be explicitly reconstructed by the caller
    since we don't mark which lists were originally arrays.
    This hook primarily handles bytes objects.
    """
    if "_bytes_" in dct:
        import base64

        return base64.b64decode(dct["_bytes_"])
    return dct


def save_json_with_numpy(data: Any, path: Path, indent: int = 2) -> None:
    """Save data to JSON file, handling numpy arrays.

    Args:
        data: Data to serialize (can contain numpy arrays)
        path: Output file path
        indent: JSON indentation level
    """
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, cls=NumpyEncoder, indent=indent)


def load_json_with_numpy(path: Path) -> Any:
    """Load data from JSON file.

    Note: Arrays are loaded as Python lists. Use np.array() to convert
    back to numpy arrays where needed.

    Args:
        path: Input file path

    Returns:
        Loaded data with bytes objects reconstructed
    """
    with open(path, encoding="utf-8") as f:
        return json.load(f, object_hook=numpy_decoder_hook)


def load_clusters_auto(path: Path) -> Any:
    """Load clusters with automatic format detection.

    Supports both legacy .pkl files and new .json files.

    Args:
        path: Path to clusters file (.pkl or .json)

    Returns:
        Loaded clusters data

    Raises:
        ValueError: If file format is not supported
    """
    if path.suffix == ".pkl":
        with open(path, "rb") as f:
            return pickle.load(f)
    elif path.suffix == ".json":
        return load_json_with_numpy(path)
    else:
        # Try to auto-detect by reading first bytes
        with open(path, "rb") as f:
            header = f.read(1)

        if header == b"{" or header == b"[":
            # Likely JSON
            return load_json_with_numpy(path)
        else:
            # Likely pickle
            with open(path, "rb") as f:
                return pickle.load(f)
