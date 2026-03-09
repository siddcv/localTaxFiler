"""
OCR extraction module — Step 1 of the LocalTax pipeline.

Tries pdfplumber first (digital PDFs). Falls back to pytesseract+pdf2image
if extracted text is below the minimum character threshold (scanned PDFs).
"""

import json
import logging
from pathlib import Path
from typing import Optional

import pdfplumber

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Private extraction helpers
# ---------------------------------------------------------------------------

def _extract_with_pdfplumber(pdf_path: Path) -> tuple[str, int]:
    """Return (full_text, page_count). Raises on unreadable file."""
    pages = []
    with pdfplumber.open(pdf_path) as pdf:
        page_count = len(pdf.pages)
        for page in pdf.pages:
            pages.append(page.extract_text() or "")
    return "\n".join(pages).strip(), page_count


def _extract_with_tesseract(
    pdf_path: Path,
    tesseract_cmd: Optional[str] = None,
) -> tuple[str, int]:
    """Return (full_text, page_count). Requires poppler + tesseract in PATH."""
    import pytesseract
    from pdf2image import convert_from_path

    if tesseract_cmd:
        pytesseract.pytesseract.tesseract_cmd = tesseract_cmd

    images = convert_from_path(pdf_path)
    pages = [pytesseract.image_to_string(img) for img in images]
    return "\n".join(pages).strip(), len(images)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def extract_single_pdf(
    pdf_path: Path,
    min_chars: int = 50,
    tesseract_cmd: Optional[str] = None,
) -> dict:
    """
    Extract text from one PDF.

    Returns a result dict with keys:
        filename, method, page_count, char_count, text, warnings, error, output_file
    """
    result: dict = {
        "filename": pdf_path.name,
        "method": None,
        "page_count": 0,
        "char_count": 0,
        "text": "",
        "warnings": [],
        "error": None,
        "output_file": None,
    }

    # --- Attempt 1: pdfplumber ---
    try:
        text, page_count = _extract_with_pdfplumber(pdf_path)
        result["page_count"] = page_count
        if len(text) >= min_chars:
            result["method"] = "pdfplumber"
            result["text"] = text
            result["char_count"] = len(text)
            return result
        result["warnings"].append(
            f"pdfplumber extracted only {len(text)} chars "
            f"(threshold: {min_chars}) — falling back to pytesseract"
        )
    except Exception as exc:
        result["warnings"].append(f"pdfplumber failed: {exc} — falling back to pytesseract")

    # --- Attempt 2: pytesseract ---
    try:
        text, page_count = _extract_with_tesseract(pdf_path, tesseract_cmd)
        if result["page_count"] == 0:
            result["page_count"] = page_count
        result["method"] = "pytesseract"
        result["text"] = text
        result["char_count"] = len(text)
        if not text:
            result["warnings"].append(
                "pytesseract produced no output — manual field entry may be required"
            )
        return result
    except Exception as exc:
        result["error"] = str(exc)
        result["method"] = "failed"
        result["warnings"].append(f"pytesseract also failed: {exc}")
        return result


def run_extraction(
    input_dir: Path,
    output_dir: Path,
    min_chars: int = 50,
    tesseract_cmd: Optional[str] = None,
) -> list[dict]:
    """
    Process every PDF in input_dir.

    For each PDF:
      - Runs extract_single_pdf()
      - Writes <stem>.txt to output_dir (skipped on error)

    Writes extraction_summary.json to output_dir and returns the summary list.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    pdf_files = sorted(input_dir.glob("*.pdf"))

    summary = []
    for pdf_path in pdf_files:
        logger.info("Extracting: %s", pdf_path.name)
        result = extract_single_pdf(pdf_path, min_chars=min_chars, tesseract_cmd=tesseract_cmd)

        if result["error"] is None and result["text"]:
            out_name = pdf_path.stem.lower().replace(" ", "_") + ".txt"
            (output_dir / out_name).write_text(result["text"], encoding="utf-8")
            result["output_file"] = out_name
        elif result["error"]:
            logger.error("Extraction failed for %s: %s", pdf_path.name, result["error"])

        summary.append(result)

    summary_path = output_dir / "extraction_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2, default=str), encoding="utf-8")
    logger.info("extraction_summary.json written to %s", output_dir)

    return summary
