"""Thumbnail caching system for figure images."""
import hashlib
from pathlib import Path
from typing import Optional
from PIL import Image

from src import config

# Thumbnail sizes
THUMB_SIZE_SMALL = (80, 80)
THUMB_SIZE_MEDIUM = (160, 160)
THUMB_SIZE_LARGE = (320, 320)


class ThumbnailCache:
    """Manages cached thumbnails for figure images."""

    def __init__(self, cache_dir: Optional[Path] = None):
        """Initialize thumbnail cache.

        Args:
            cache_dir: Directory to store thumbnails. Defaults to config.THUMBS_DIR.
        """
        self.cache_dir = cache_dir or config.THUMBS_DIR
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def get_thumbnail_path(
        self,
        image_path: str,
        size: tuple[int, int] = THUMB_SIZE_SMALL
    ) -> Path:
        """Get the cached thumbnail path for an image.

        Args:
            image_path: Path to the original image.
            size: Thumbnail size tuple (width, height).

        Returns:
            Path to the thumbnail file.
        """
        # Create unique filename from image path and size
        path_hash = hashlib.md5(image_path.encode()).hexdigest()[:12]
        size_suffix = f"{size[0]}x{size[1]}"
        thumb_name = f"{path_hash}_{size_suffix}.png"
        return self.cache_dir / thumb_name

    def get_or_create_thumbnail(
        self,
        image_path: str,
        size: tuple[int, int] = THUMB_SIZE_SMALL
    ) -> Optional[Path]:
        """Get cached thumbnail or create if not exists.

        Args:
            image_path: Path to the original image.
            size: Thumbnail size tuple (width, height).

        Returns:
            Path to the thumbnail file, or None if creation failed.
        """
        thumb_path = self.get_thumbnail_path(image_path, size)

        # Return cached if exists
        if thumb_path.exists():
            return thumb_path

        # Create thumbnail
        return self.create_thumbnail(image_path, size)

    def create_thumbnail(
        self,
        image_path: str,
        size: tuple[int, int] = THUMB_SIZE_SMALL
    ) -> Optional[Path]:
        """Create and cache a thumbnail.

        Args:
            image_path: Path to the original image.
            size: Thumbnail size tuple (width, height).

        Returns:
            Path to the thumbnail file, or None if creation failed.
        """
        source_path = Path(image_path)
        if not source_path.exists():
            return None

        thumb_path = self.get_thumbnail_path(image_path, size)

        try:
            with Image.open(source_path) as img:
                # Convert to RGB if necessary (handles CMYK, RGBA, P, L, LA, etc.)
                if img.mode not in ('RGB',):
                    img = img.convert('RGB')

                # Create thumbnail maintaining aspect ratio
                img.thumbnail(size, Image.LANCZOS)

                # Save as PNG for quality
                img.save(thumb_path, 'PNG', optimize=True)

            return thumb_path
        except Exception as e:
            print(f"Error creating thumbnail for {image_path}: {e}")
            return None

    def create_thumbnails_batch(
        self,
        image_paths: list[str],
        size: tuple[int, int] = THUMB_SIZE_SMALL,
        progress_callback: Optional[callable] = None
    ) -> dict[str, Optional[Path]]:
        """Create thumbnails for multiple images.

        Args:
            image_paths: List of image paths.
            size: Thumbnail size tuple.
            progress_callback: Optional callback(current, total).

        Returns:
            Dict mapping image_path to thumbnail_path (or None if failed).
        """
        results = {}
        total = len(image_paths)

        for i, image_path in enumerate(image_paths):
            results[image_path] = self.get_or_create_thumbnail(image_path, size)

            if progress_callback:
                progress_callback(i + 1, total)

        return results

    def has_thumbnail(
        self,
        image_path: str,
        size: tuple[int, int] = THUMB_SIZE_SMALL
    ) -> bool:
        """Check if a thumbnail exists.

        Args:
            image_path: Path to the original image.
            size: Thumbnail size tuple.

        Returns:
            True if thumbnail exists.
        """
        thumb_path = self.get_thumbnail_path(image_path, size)
        return thumb_path.exists()

    def invalidate(self, image_path: str) -> int:
        """Remove all cached thumbnails for an image.

        Args:
            image_path: Path to the original image.

        Returns:
            Number of thumbnails removed.
        """
        path_hash = hashlib.md5(image_path.encode()).hexdigest()[:12]
        removed = 0

        for thumb_file in self.cache_dir.glob(f"{path_hash}_*.png"):
            thumb_file.unlink()
            removed += 1

        return removed

    def clear_cache(self) -> int:
        """Remove all cached thumbnails.

        Returns:
            Number of thumbnails removed.
        """
        removed = 0
        for thumb_file in self.cache_dir.glob("*.png"):
            thumb_file.unlink()
            removed += 1
        return removed

    def get_cache_stats(self) -> dict:
        """Get cache statistics.

        Returns:
            Dict with count and total_size_mb.
        """
        thumbs = list(self.cache_dir.glob("*.png"))
        total_size = sum(t.stat().st_size for t in thumbs)

        return {
            "count": len(thumbs),
            "total_size_mb": total_size / (1024 * 1024)
        }


# Global instance for convenience
_thumbnail_cache: Optional[ThumbnailCache] = None


def get_thumbnail_cache() -> ThumbnailCache:
    """Get the global thumbnail cache instance."""
    global _thumbnail_cache
    if _thumbnail_cache is None:
        _thumbnail_cache = ThumbnailCache()
    return _thumbnail_cache
