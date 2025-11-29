"""LLM client interfaces for NeuroSynth."""

from neurosynth.llm.claude import ClaudeClient
from neurosynth.llm.gemini import GeminiClient
from neurosynth.llm.voyage import VoyageClient

# Check if visual processing dependencies are available
try:
    import torch
    from colpali_engine.models import ColPali
    VISUAL_AVAILABLE = True
except ImportError:
    VISUAL_AVAILABLE = False

# Conditionally import ColPali client
if VISUAL_AVAILABLE:
    from neurosynth.llm.colpali import ColPaliClient, get_colpali_client
else:
    ColPaliClient = None
    get_colpali_client = None

__all__ = [
    "ClaudeClient",
    "GeminiClient",
    "VoyageClient",
    "ColPaliClient",
    "get_colpali_client",
    "VISUAL_AVAILABLE",
]
