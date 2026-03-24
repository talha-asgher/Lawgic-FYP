#!/usr/bin/env python3
"""
Extract text from a single PDF using LlamaParser and save to a JSON file.

Uses the same extraction logic as llamaparser_extractor.py. The PDF path is
passed as an argument; the PDF must be under data/raw_pdfs/<category>/ where
category is civil, criminal, or family. The output JSON is written to
data/extracted_text/<category>/ with the same base filename.
"""

import argparse
import json
import os
import sys
from pathlib import Path

# Add project root for imports
project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from extraction.llamaparser_extractor import extract_text_from_pdf

ALLOWED_CATEGORIES = ("civil", "criminal", "family")


def main():
    parser = argparse.ArgumentParser(
        description="Extract text from a single PDF using LlamaParser and save to JSON."
    )
    parser.add_argument(
        "pdf_path",
        type=str,
        help="Path to the PDF file (must be under data/raw_pdfs)",
    )
    args = parser.parse_args()

    pdf_path = Path(args.pdf_path)
    if not pdf_path.is_absolute():
        pdf_path = (project_root / pdf_path).resolve()

    if not pdf_path.exists():
        print(f"Error: PDF file not found: {pdf_path}", file=sys.stderr)
        sys.exit(1)

    raw_pdfs = (project_root / "data" / "raw_pdfs").resolve()
    try:
        rel = pdf_path.resolve().relative_to(raw_pdfs)
    except ValueError:
        print(
            f"Error: PDF must be under data/raw_pdfs. Got: {pdf_path}",
            file=sys.stderr,
        )
        sys.exit(1)

    # First path part under raw_pdfs is the category (civil, criminal, family)
    parts = rel.parts
    if not parts or parts[0].lower() not in ALLOWED_CATEGORIES:
        print(
            f"Error: PDF must be under data/raw_pdfs/<category>/ where category is one of {ALLOWED_CATEGORIES}. Got: {pdf_path}",
            file=sys.stderr,
        )
        sys.exit(1)
    category = parts[0].lower()

    out_dir = project_root / "data" / "extracted_text" / category
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / pdf_path.with_suffix(".json").name

    print(f"Extracting text from: {pdf_path}")
    try:
        extracted_text, footnotes, position_to_page = extract_text_from_pdf(
            str(pdf_path)
        )
    except Exception as e:
        print(f"Error during extraction: {e}", file=sys.stderr)
        sys.exit(1)

    # JSON requires string keys; position_to_page has int keys
    position_to_page_str = {str(k): v for k, v in position_to_page.items()}

    out_data = {
        "extracted_text": extracted_text,
        "footnotes": footnotes,
        "position_to_page": position_to_page_str,
    }

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(out_data, f, ensure_ascii=False, indent=2)

    print(f"Saved extraction to: {out_path}")
    print(f"  Characters: {len(extracted_text)}")
    print(f"  Footnotes: {len(footnotes)}")


if __name__ == "__main__":
    main()
