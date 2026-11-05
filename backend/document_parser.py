"""
document_parser.py
──────────────────
Extracts plain text from uploaded files.

Supported formats:
  • PDF  – text-layer extraction via PyPDF2; falls back to OCR (pytesseract)
            if the page has no text (scanned certificate).
  • DOCX – python-docx paragraph extraction.
  • XLSX / XLS / CSV – pandas table → string.
  • PNG / JPG / JPEG / TIFF – direct OCR via pytesseract / Pillow.
"""

import io
import logging
from pathlib import Path

import pandas as pd

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# PDF
# ─────────────────────────────────────────────────────────────────────────────

def _extract_pdf(file_bytes: bytes) -> str:
    """Try text-layer first; fall back to OCR page-by-page."""
    try:
        import PyPDF2
    except ImportError:
        raise ImportError("PyPDF2 is required for PDF parsing. Run: pip install pypdf2")

    reader = PyPDF2.PdfReader(io.BytesIO(file_bytes))
    pages_text = []

    for page in reader.pages:
        text = page.extract_text() or ""
        if text.strip():
            pages_text.append(text)
        else:
            # Scanned page – use OCR
            pages_text.append(_ocr_pdf_page(page))

    return "\n".join(pages_text)


def _ocr_pdf_page(page) -> str:
    """Convert a PDF page to an image and run OCR."""
    try:
        import pytesseract
        from PIL import Image
        import fitz  # PyMuPDF – lighter than pdf2image
    except ImportError:
        logger.warning("pytesseract / PyMuPDF not available; skipping OCR for scanned page.")
        return ""

    # Render page to RGB image using PyMuPDF
    mat = fitz.Matrix(2, 2)  # 2× zoom for better OCR accuracy
    clip = page.get_pixmap(matrix=mat)  # type: ignore[attr-defined]
    img = Image.frombytes("RGB", [clip.width, clip.height], clip.samples)
    return pytesseract.image_to_string(img)


# ─────────────────────────────────────────────────────────────────────────────
# DOCX
# ─────────────────────────────────────────────────────────────────────────────

def _extract_docx(file_bytes: bytes) -> str:
    """Extract all paragraph text from a Word document."""
    try:
        from docx import Document
    except ImportError:
        raise ImportError("python-docx is required. Run: pip install python-docx")

    doc = Document(io.BytesIO(file_bytes))
    paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
    # Also extract text from tables
    for table in doc.tables:
        for row in table.rows:
            for cell in row.cells:
                if cell.text.strip():
                    paragraphs.append(cell.text.strip())
    return "\n".join(paragraphs)


# ─────────────────────────────────────────────────────────────────────────────
# Excel / CSV
# ─────────────────────────────────────────────────────────────────────────────

def _extract_spreadsheet(file_bytes: bytes, suffix: str) -> str:
    """Convert a spreadsheet to a readable text block."""
    buf = io.BytesIO(file_bytes)
    if suffix in (".xlsx", ".xls"):
        # Read all sheets
        xl = pd.read_excel(buf, sheet_name=None)
        parts = []
        for sheet_name, df in xl.items():
            parts.append(f"[Sheet: {sheet_name}]\n{df.to_string(index=False)}")
        return "\n\n".join(parts)
    else:  # CSV
        df = pd.read_csv(buf)
        return df.to_string(index=False)


# ─────────────────────────────────────────────────────────────────────────────
# Image (certificate scans, etc.)
# ─────────────────────────────────────────────────────────────────────────────

def _extract_image(file_bytes: bytes) -> str:
    """OCR on a direct image file."""
    try:
        import pytesseract
        from PIL import Image
    except ImportError:
        raise ImportError("Pillow and pytesseract are required for image OCR.")

    img = Image.open(io.BytesIO(file_bytes))
    return pytesseract.image_to_string(img)


# ─────────────────────────────────────────────────────────────────────────────
# Public entry point
# ─────────────────────────────────────────────────────────────────────────────

def extract_text(file_bytes: bytes, filename: str) -> str:
    """
    Route `file_bytes` to the right extractor based on the file extension.

    Returns:
        str – the extracted plain text, stripped of leading/trailing whitespace.

    Raises:
        ValueError – if the file type is unsupported.
    """
    suffix = Path(filename).suffix.lower()

    if suffix == ".pdf":
        text = _extract_pdf(file_bytes)
    elif suffix in (".docx", ".doc"):
        text = _extract_docx(file_bytes)
    elif suffix in (".xlsx", ".xls", ".csv"):
        text = _extract_spreadsheet(file_bytes, suffix)
    elif suffix in (".png", ".jpg", ".jpeg", ".tiff", ".tif", ".bmp"):
        text = _extract_image(file_bytes)
    else:
        raise ValueError(f"Unsupported file type: {suffix!r}")

    cleaned = text.strip()
    logger.info("Extracted %d characters from '%s'", len(cleaned), filename)
    return cleaned
