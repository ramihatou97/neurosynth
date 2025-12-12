"""Bridge for importing NeuroSynth modules into Reference Library.

This module provides access to NeuroSynth's visual processing pipeline
(ColPali embeddings, Qdrant vector store) without code duplication.
"""

import sys
from pathlib import Path

# Ensure NeuroSynth source is in Python path
_neurosynth_root = Path(__file__).parent.parent.parent.parent
if str(_neurosynth_root) not in sys.path:
    sys.path.insert(0, str(_neurosynth_root))

# Import NeuroSynth modules
NEUROSYNTH_AVAILABLE = False
_import_error = None

try:
    from src.neurosynth.dedup.qdrant_store import QdrantVisualStore
    from src.neurosynth.llm.colpali import ColPaliClient, get_colpali_client

    NEUROSYNTH_AVAILABLE = True
except ImportError as e:
    _import_error = str(e)
    # Create placeholder for type hints
    ColPaliClient = None
    QdrantVisualStore = None


# Re-export for convenience
__all__ = [
    "NEUROSYNTH_AVAILABLE",
    "get_colpali_client",
    "get_qdrant_store",
    "ColPaliClient",
    "QdrantVisualStore",
]


# Lazy-loaded singleton instances
_colpali_client = None
_qdrant_store = None


def get_colpali_client():
    """Get the ColPali client for visual embeddings (lazy loaded).

    Returns:
        ColPaliClient singleton or None if not available
    """
    global _colpali_client

    if not NEUROSYNTH_AVAILABLE:
        return None

    if _colpali_client is None:
        try:
            from src.neurosynth.llm.colpali import get_colpali_client as _get_client

            _colpali_client = _get_client()
        except ImportError:
            return None
        except Exception as e:
            print(f"Warning: Failed to initialize ColPali client: {e}")
            return None

    return _colpali_client


def get_qdrant_store(collection_name: str = None):
    """Get a Qdrant visual store for similarity search.

    Args:
        collection_name: Name of the Qdrant collection (uses config default if None)

    Returns:
        QdrantVisualStore or None if not available
    """
    global _qdrant_store

    if not NEUROSYNTH_AVAILABLE:
        return None

    # Use cached instance if collection name matches
    if _qdrant_store is not None:
        return _qdrant_store

    try:
        from src.neurosynth.dedup.qdrant_store import QdrantVisualStore

        # Import config for default collection name
        try:
            from reference_library import config

            default_collection = getattr(
                config, "QDRANT_COLLECTION", "reference_library_visuals"
            )
        except ImportError:
            default_collection = "reference_library_visuals"

        collection = collection_name or default_collection

        # Create store instance
        _qdrant_store = QdrantVisualStore()
        return _qdrant_store

    except ImportError as e:
        print(f"Warning: Qdrant store not available: {e}")
        return None
    except Exception as e:
        print(f"Warning: Failed to initialize Qdrant store: {e}")
        return None
