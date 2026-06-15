"""PDF text extraction (pypdf) with light whitespace normalization."""

from __future__ import annotations

import re
from pathlib import Path

from pypdf import PdfReader


def extract_text(pdf_path: str | Path) -> str:
    reader = PdfReader(str(pdf_path))
    pages = [page.extract_text() or "" for page in reader.pages]
    text = "\n".join(pages)
    # Normalize: collapse horizontal whitespace, squeeze blank lines. We deliberately
    # avoid aggressive de-spacing (risk of merging real words); the LLM tolerates noise.
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n[ \t]*\n+", "\n\n", text)
    return text.strip()
