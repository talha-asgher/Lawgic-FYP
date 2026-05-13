"""OCR using Tesseract (pytesseract) + Pillow; PDF pages rendered with PyMuPDF."""

from __future__ import annotations

import io
import logging
import os
from typing import TYPE_CHECKING

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from PIL import Image


def _tesseract_cmd() -> str | None:
    return os.environ.get("TESSERACT_CMD", "").strip() or None


def _ocr_lang() -> str:
    return os.environ.get("OCR_LANG", "eng").strip() or "eng"


def _max_pdf_pages_ocr() -> int:
    return max(1, int(os.environ.get("OCR_MAX_PDF_PAGES", "40")))


def _configure_tesseract() -> None:
    import pytesseract

    cmd = _tesseract_cmd()
    if cmd:
        pytesseract.pytesseract.tesseract_cmd = cmd


def ocr_image_bytes(data: bytes) -> str:
    """Run Tesseract on a single image (PNG, JPEG, WebP, etc.)."""
    import pytesseract
    from PIL import Image

    _configure_tesseract()
    try:
        img = Image.open(io.BytesIO(data))
    except Exception as e:
        raise ValueError("Could not open image for OCR.") from e

    if img.mode not in ("RGB", "L", "1"):
        img = img.convert("RGB")
    try:
        text = pytesseract.image_to_string(img, lang=_ocr_lang())
    except pytesseract.TesseractNotFoundError as e:
        raise ValueError(
            "Tesseract is not installed or not on PATH. "
            "Install Tesseract OCR (https://github.com/tesseract-ocr/tesseract) "
            "and optionally set TESSERACT_CMD to the tesseract executable."
        ) from e
    except Exception as e:
        raise ValueError(f"OCR failed: {e}") from e
    return (text or "").strip()


def ocr_pdf_bytes(data: bytes) -> str:
    """Rasterize each PDF page with PyMuPDF and OCR. Limited page count for runtime."""
    import fitz  # PyMuPDF
    import pytesseract
    from PIL import Image

    _configure_tesseract()
    doc = fitz.open(stream=data, filetype="pdf")
    max_pages = min(len(doc), _max_pdf_pages_ocr())
    dpi = float(os.environ.get("OCR_PDF_DPI", "150"))
    scale = dpi / 72.0
    mat = fitz.Matrix(scale, scale)
    parts: list[str] = []

    for i in range(max_pages):
        page = doc[i]
        try:
            pix = page.get_pixmap(matrix=mat, alpha=False)
        except Exception as e:
            logger.warning("PDF page %s render failed: %s", i, e)
            continue
        try:
            img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
        except Exception as e:
            logger.warning("PDF page %s to image failed: %s", i, e)
            continue
        try:
            t = pytesseract.image_to_string(img, lang=_ocr_lang())
        except pytesseract.TesseractNotFoundError as e:
            doc.close()
            raise ValueError(
                "Tesseract is not installed or not on PATH. "
                "Install Tesseract OCR and optionally set TESSERACT_CMD."
            ) from e
        except Exception as e:
            logger.warning("OCR page %s failed: %s", i, e)
            continue
        if t and t.strip():
            parts.append(t.strip())

    doc.close()
    return "\n\n".join(parts)


def extract_pdf_text_pymupdf(data: bytes) -> str:
    """Often recovers more text than pypdf from complex layouts (still not scanned pages)."""
    import fitz

    doc = fitz.open(stream=data, filetype="pdf")
    parts: list[str] = []
    for i in range(len(doc)):
        t = (doc[i].get_text("text") or "").strip()
        if t:
            parts.append(t)
    doc.close()
    return "\n\n".join(parts)
