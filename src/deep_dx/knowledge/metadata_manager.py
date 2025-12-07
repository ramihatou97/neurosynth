import logging
import re
from pathlib import Path
from typing import Any, Dict, Optional

# Configure logging
logger = logging.getLogger(__name__)


class MetadataManager:
    """
    Manages metadata lookup by scanning the structured NeuroLi library.
    Maps filenames to metadata (Subspecialty, Condition, Authority) based on folder path.
    """

    def __init__(self, library_root: str = "/Users/ramihatoum/Desktop/NeuroLi"):
        self.library_root = Path(library_root)
        self.file_map: dict[str, dict[str, Any]] = {}  # filename -> metadata
        self.is_loaded = False

        if self.library_root.exists():
            self._scan_library()
        else:
            logger.warning(
                f"⚠️ Library root not found at {self.library_root}. Metadata enrichment disabled."
            )

    def _scan_library(self):
        """Scans the library directory to build a fast filename->metadata map."""
        logger.info(f"📚 Scanning NeuroLi library at: {self.library_root}")
        count = 0

        # Walker
        for file_path in self.library_root.rglob("*.pdf"):
            filename = file_path.name
            meta = self.resolve_metadata_from_path(str(file_path))
            self.file_map[filename] = meta
            count += 1

        logger.info(f"✅ Metadata Index Built: {count} files mapped.")
        self.is_loaded = True

    def resolve_metadata_from_path(self, path_str: str) -> dict[str, Any]:
        """
        Parses a file path to extract metadata based on NeuroLi folder structure.
        """
        path = Path(path_str)
        parts = path.parts

        # Defaults
        meta = {
            "subspecialty": "General",
            "condition": None,
            "collection": "Unknown",
            "authority_score": 80,
        }

        # Heuristics based on NeuroLi Structure

        # 1. Detect Collection
        if "01_COMPLETE_TEXTBOOKS" in parts:
            meta["collection"] = "Textbooks"
            meta["authority_score"] = 95
        elif "04_EVIDENCE_BASE_STUDIES" in parts:
            meta["collection"] = "Evidence"
            meta["authority_score"] = 90
        elif "02_MULTI_CHAPTER_BOOKS" in parts:
            meta["collection"] = "Books"
        elif "06_CLINICAL_GUIDELINES" in parts:
            meta["collection"] = "Guidelines"
            meta["authority_score"] = 100

        # 2. Detect Subspecialty (look for "XX_Name")
        for part in parts:
            if "_" in part and part[0].isdigit():
                # e.g. "01_Vascular"
                match = re.match(r"\d+_([A-Za-z_\-]+)", part)
                if match:
                    potential_name = match.group(1).replace("_", " ")
                    # Filter out known collections to find subspecialties
                    if (
                        "TEXTBOOKS" not in potential_name
                        and "GUIDELINES" not in potential_name
                        and "CHAPTER" not in potential_name
                        and "EVIDENCE" not in potential_name
                    ):
                        meta["subspecialty"] = potential_name

        # 3. Detect Condition (Parent folder of file, often)
        parent = path.parent.name
        # Avoid generic parents
        if not parent.startswith("0") and parent != meta["subspecialty"]:
            meta["condition"] = parent

        return meta

    def get_metadata(self, filename: str) -> dict[str, Any]:
        """
        Returns metadata for a given filename.
        """
        return self.file_map.get(
            filename,
            {"authority_score": 80, "subspecialty": "General", "type": "Unknown"},
        )

    def get_all_subspecialties(self) -> list[str]:
        """Returns list of all unique subspecialties found."""
        return sorted(list(set(m["subspecialty"] for m in self.file_map.values())))
