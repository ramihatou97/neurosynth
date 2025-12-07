"""Top-level worker functions for ProcessPoolExecutor.

These functions must be at module level (not inside classes) for pickling.
They run in separate Python processes for true parallelism.
"""
import io
from pathlib import Path


def extract_text_worker(pdf_path: str) -> dict:
    """
    Worker that runs in a separate CPU process.
    Extracts all text from a PDF without database/UI interaction.

    Args:
        pdf_path: String path to PDF file

    Returns:
        Dict with keys: path, pages, page_count, error
    """
    result = {
        "path": pdf_path,
        "pages": {},
        "page_count": 0,
        "error": None
    }

    try:
        # Import inside function to avoid pickling issues
        import fitz

        doc = fitz.open(pdf_path)
        result["page_count"] = len(doc)

        for page_num in range(len(doc)):
            result["pages"][page_num] = doc[page_num].get_text()

        doc.close()
    except Exception as e:
        result["error"] = str(e)

    return result


def extract_figures_worker(
    pdf_path: str,
    output_dir: str,
    min_size: int = 50,
    max_size: int = 2048
) -> dict:
    """
    Worker that extracts figures from a PDF in a separate process.
    Returns figure metadata (not PIL images - can't pickle across processes).

    Args:
        pdf_path: String path to PDF file
        output_dir: String path to output directory for images
        min_size: Minimum image dimension to extract
        max_size: Maximum image dimension (larger images resized)

    Returns:
        Dict with keys: path, figures, error
    """
    result = {
        "path": pdf_path,
        "figures": [],
        "error": None
    }

    try:
        # Import inside function to avoid pickling issues
        import fitz
        from PIL import Image

        doc = fitz.open(pdf_path)
        out_path = Path(output_dir)
        out_path.mkdir(parents=True, exist_ok=True)

        pdf_stem = Path(pdf_path).stem

        for page_num in range(len(doc)):
            page = doc[page_num]

            for img_idx, img_info in enumerate(page.get_images(full=True)):
                xref = img_info[0]
                base_image = doc.extract_image(xref)

                if not base_image:
                    continue

                image_bytes = base_image.get("image")
                if not image_bytes:
                    continue

                # Load with PIL to check dimensions
                try:
                    pil_img = Image.open(io.BytesIO(image_bytes))
                except Exception:
                    continue

                w, h = pil_img.size

                # Skip images below minimum size
                if w < min_size or h < min_size:
                    continue

                # Convert non-RGB modes
                if pil_img.mode not in ('RGB', 'L'):
                    pil_img = pil_img.convert('RGB')

                # Resize if too large
                if w > max_size or h > max_size:
                    pil_img.thumbnail((max_size, max_size), Image.LANCZOS)
                    w, h = pil_img.size

                # Save to output directory
                fname = f"{pdf_stem}_p{page_num + 1}_i{img_idx + 1}.png"
                fpath = out_path / fname

                # Handle filename collisions
                counter = 1
                while fpath.exists():
                    fname = f"{pdf_stem}_p{page_num + 1}_i{img_idx + 1}_{counter}.png"
                    fpath = out_path / fname
                    counter += 1

                pil_img.save(fpath, "PNG")

                result["figures"].append({
                    "path": str(fpath),
                    "page": page_num + 1,
                    "width": w,
                    "height": h,
                    "xref": xref
                })

        doc.close()

    except Exception as e:
        result["error"] = str(e)

    return result


def extract_figures_snapshot_worker(
    pdf_path: str,
    output_dir: str,
    zoom: float = 3.0
) -> dict:
    """
    Worker that extracts figures using the "snapshot" approach.
    Renders figure regions at high resolution to capture labels/arrows.

    Args:
        pdf_path: String path to PDF file
        output_dir: String path to output directory
        zoom: Render zoom factor (3.0 = 216 DPI)

    Returns:
        Dict with keys: path, figures, error
    """
    import re

    result = {
        "path": pdf_path,
        "figures": [],
        "error": None
    }

    # Figure caption patterns
    figure_patterns = [
        re.compile(r"^(Figure|Fig\.?)\s*(\d+(?:\.\d+)?)[:\.\-]?\s*(.*)$", re.IGNORECASE | re.MULTILINE),
        re.compile(r"^(Plate|Image|Panel)\s*(\d+(?:\.\d+)?)[:\.\-]?\s*(.*)$", re.IGNORECASE | re.MULTILINE),
    ]

    try:
        import fitz
        from PIL import Image

        doc = fitz.open(pdf_path)
        out_path = Path(output_dir)
        out_path.mkdir(parents=True, exist_ok=True)

        pdf_stem = Path(pdf_path).stem
        mat = fitz.Matrix(zoom, zoom)

        for page_num in range(len(doc)):
            page = doc[page_num]
            page_text = page.get_text("text")
            page_rect = page.rect

            # Find figure captions on this page
            for pattern in figure_patterns:
                for match in pattern.finditer(page_text):
                    fig_num = match.group(2)
                    caption_text = match.group(3) if match.lastindex >= 3 else ""

                    # Try to find caption location via search
                    caption_instances = page.search_for(match.group(0)[:50])
                    if not caption_instances:
                        continue

                    cap_rect = caption_instances[0]

                    # Define clip area: from caption top, scan upward
                    clip_rect = fitz.Rect(
                        page_rect.x0,
                        max(0, cap_rect.y0 - 400),  # Up to 400pt above caption
                        page_rect.x1,
                        cap_rect.y0  # Stop at caption top
                    )

                    # Render to pixmap
                    pix = page.get_pixmap(matrix=mat, clip=clip_rect)

                    # Validate: skip if too small
                    if pix.width < 100 or pix.height < 50:
                        continue

                    # Save
                    fname = f"{pdf_stem}_fig{fig_num}_p{page_num + 1}.png"
                    fpath = out_path / fname

                    counter = 1
                    while fpath.exists():
                        fname = f"{pdf_stem}_fig{fig_num}_p{page_num + 1}_{counter}.png"
                        fpath = out_path / fname
                        counter += 1

                    pix.save(str(fpath))

                    result["figures"].append({
                        "path": str(fpath),
                        "page": page_num + 1,
                        "width": pix.width,
                        "height": pix.height,
                        "figure_number": fig_num,
                        "caption": caption_text[:500],
                        "method": "snapshot"
                    })

        doc.close()

    except Exception as e:
        result["error"] = str(e)

    return result
