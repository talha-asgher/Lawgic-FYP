#!/usr/bin/env python3
"""
Process PDF files and create parent/child chunks, saving them to JSON files.

Text is read from data/extracted_text/{category}/{stem}.json (created by a prior
extraction step, e.g. LlamaParser batch extraction). The script matches the PDF path
to category and stem to find the JSON file.

Usage:
    python scripts/process_pdf_to_chunks.py [pdf_path]
    
    Single file:  python scripts/process_pdf_to_chunks.py "data/raw_pdfs/civil/Your_Act.pdf"
    All PDFs:     python scripts/process_pdf_to_chunks.py
    
    If pdf_path is provided, processes only that file.
    If not provided, processes all PDFs in data/raw_pdfs/.
    To use the Level-1/2/3 section extraction (CHAPTER, PART, SCHEDULE, etc.), change the
    import to: from scripts.process_legal_text1 import process_legal_text, determine_category
"""

import sys
import json
import io
import re
from pathlib import Path
from typing import Optional

# Fix Windows console encoding issues
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

PROJECT_ROOT = Path(__file__).parent.parent
EXTRACTED_TEXT_DIR = PROJECT_ROOT / "RAG""/data" / "extracted_text"

# Lazy import: process_legal_text1 pulls in langchain → nltk → scipy/numpy, which can take 15–30s on first run.
# Import is done inside process_single_pdf so we can print "Processing..." before the slow load.
_process_legal_text = None
_determine_category = None


def _get_process_legal_text():
    global _process_legal_text
    if _process_legal_text is None:
        print("Loading chunking pipeline (first run may take 15–30 seconds)...")
        from scripts.process_legal_text1 import process_legal_text, determine_category
        _process_legal_text = process_legal_text
        global _determine_category
        _determine_category = determine_category
    return _process_legal_text, _determine_category


def load_extracted_text_from_file(pdf_path: Path, category: str) -> tuple:
    """
    Load extracted text, footnotes, and position_to_page from data/extracted_text/{category}/{stem}.json.
    JSON keys: extracted_text, footnotes, position_to_page (position_to_page has string keys; converted to int).
    Returns:
        (extracted_text: str, footnotes: list, position_to_page: dict with int keys)
    Raises:
        FileNotFoundError if the JSON file does not exist.
    """
    stem = pdf_path.stem  # e.g. "ISLAMABAD CONSUMERS PROTECTION ACT, 1995"
    json_path = EXTRACTED_TEXT_DIR / category / f"{stem}.json"
    if not json_path.exists():
        raise FileNotFoundError(
            f"Extracted text file not found: {json_path}\n"
            f"Run extraction first to create it (e.g. batch extraction that saves to data/extracted_text)."
        )
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    extracted_text = data.get("extracted_text", "")
    footnotes = data.get("footnotes", [])
    position_to_page_raw = data.get("position_to_page", {})
    position_to_page = {int(k): v for k, v in position_to_page_raw.items()}
    return extracted_text, footnotes, position_to_page


def extract_rgn_date(text: str) -> str:
    """
    Extract RGN date from text.
    
    Looks for patterns like:
    - "RGN Date: 05-09-2024"
    - "RGN 123/2024"
    
    Args:
        text: Text to search for RGN date
        
    Returns:
        RGN date string if found, empty string otherwise
    """
    # Pattern 1: RGN Date: DD-MM-YYYY
    pattern1 = re.search(r'\bRGN\s+Date:\s*(\d{2}-\d{2}-\d{4})\b', text, re.IGNORECASE)
    if pattern1:
        return f"RGN Date: {pattern1.group(1)}"
    
    # Pattern 2: RGN NUMBER/YEAR
    pattern2 = re.search(r'\bRGN\s+(\d+/\d+)\b', text, re.IGNORECASE)
    if pattern2:
        return f"RGN {pattern2.group(1)}"
    
    return ""


def process_single_pdf(pdf_path: Path, base_output_dir: Path, update_progress: bool = True):
    """
    Process a single PDF file and save chunks organized by category.
    
    Args:
        pdf_path: Path to the PDF file
        base_output_dir: Base output directory (data/chunking)
        update_progress: Whether to update batch resume progress file
    """
    pdf_path = Path(pdf_path)
    filename = pdf_path.name
    print(f"\n{'='*80}")
    print(f"Processing: {filename}")
    print(f"{'='*80}")
    
    _, determine_category_fn = _get_process_legal_text()
    category = determine_category_fn(str(pdf_path))
    print(f"Category: {category}")
    
    # Create category-specific output directories
    category_dir = base_output_dir / category
    parent_chunks_dir = category_dir / "parent_chunks"
    child_chunks_dir = category_dir / "child_chunks"
    summary_dir = category_dir / "summary"
    
    # Create directories if they don't exist
    parent_chunks_dir.mkdir(parents=True, exist_ok=True)
    child_chunks_dir.mkdir(parents=True, exist_ok=True)
    summary_dir.mkdir(parents=True, exist_ok=True)
    
    # Step 1: Load extracted text from data/extracted_text/{category}/{stem}.json
    try:
        print("Loading extracted text from data/extracted_text...")
        extracted_text, footnotes, position_to_page = load_extracted_text_from_file(pdf_path, category)
        print(f"Loaded {len(extracted_text)} characters")
        
        if not extracted_text or len(extracted_text.strip()) < 100:
            print(f"[ERROR] Extracted text is too short or empty in the JSON for {filename}")
            return False
    except FileNotFoundError as e:
        print(f"[ERROR] {e}")
        return False
    except Exception as e:
        print(f"[ERROR] Error loading extracted text for {filename}: {e}")
        return False
    
    # Extract RGN date from raw text (before processing)
    rgn_date = extract_rgn_date(extracted_text)
    
    # Step 2: Process text into chunks
    try:
        print("Processing text into chunks...")
        process_legal_text_fn, _ = _get_process_legal_text()
        parent_chunks, child_chunks, table_chunks, form_chunks = process_legal_text_fn(
            extracted_text, 
            filename, 
            position_to_page,
            str(pdf_path),  # Pass pdf_path for category extraction
            all_footnotes=footnotes  # Pass footnotes from extractor
        )
        #print(f"Created {len(parent_chunks)} parent chunks, {len(child_chunks)} child chunks, {len(table_chunks)} table chunks, and {len(form_chunks)} form chunks")
    except Exception as e:
        error_msg = str(e)
        # Check if it's an API credit limit error
        if "exceeded the maximum number of credits" in error_msg.lower() or "credits" in error_msg.lower():
            print(f"[ERROR] API Credit Limit Exceeded for {filename}")
            print(f"[ERROR] You've exceeded the maximum number of credits for your LlamaParser plan.")
            print(f"[ERROR] Exiting script. Please upgrade your plan or wait for credits to reset.")
            sys.exit(1)
        else:
            print(f"[ERROR] Error processing text for {filename}: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    # Validate that we have non-empty chunks - if not, don't save and return
    if not parent_chunks or len(parent_chunks) == 0:
        print(f"[ERROR] No parent chunks generated for {filename}")
        print(f"[ERROR] This may indicate an API limit issue or processing error.")
        print(f"[ERROR] Skipping this file and exiting.")
        sys.exit(1)
    
    if not child_chunks or len(child_chunks) == 0:
        print(f"[ERROR] No child chunks generated for {filename}")
        print(f"[ERROR] This may indicate an API limit issue or processing error.")
        print(f"[ERROR] Skipping this file and exiting.")
        sys.exit(1)
    
    # Step 3: Save chunks to JSON files
    # Create base filename from PDF name
    base_name = pdf_path.stem.replace(' ', '_').replace('(', '').replace(')', '')
    
    # Save parent chunks (only if not empty - already validated above)
    parent_file = parent_chunks_dir / f"{base_name}_parent_chunks.json"
    with open(parent_file, 'w', encoding='utf-8') as f:
        json.dump([p.to_dict() for p in parent_chunks], f, indent=2, ensure_ascii=False)
    print(f"Saved parent chunks: {parent_file}")
    
    # Save child chunks (only if not empty - already validated above)
    child_file = child_chunks_dir / f"{base_name}_child_chunks.json"
    with open(child_file, 'w', encoding='utf-8') as f:
        json.dump([c.to_dict() for c in child_chunks], f, indent=2, ensure_ascii=False)
    print(f"Saved child chunks: {child_file}")
    
    # Save table chunks (only if not empty)
    tables_file = None
    if table_chunks:
        tables_dir = category_dir / "table_chunks"
        tables_dir.mkdir(parents=True, exist_ok=True)
        tables_file = tables_dir / f"{base_name}_table_chunks.json"
        with open(tables_file, 'w', encoding='utf-8') as f:
            json.dump([t.to_dict() for t in table_chunks], f, indent=2, ensure_ascii=False)
        print(f"Saved table chunks: {tables_file}")
    
    # Save form chunks (only if not empty)
    forms_file = None
    if form_chunks:
        forms_dir = category_dir / "form_chunks"
        forms_dir.mkdir(parents=True, exist_ok=True)
        forms_file = forms_dir / f"{base_name}_form_chunks.json"
        with open(forms_file, 'w', encoding='utf-8') as f:
            json.dump([f.to_dict() for f in form_chunks], f, indent=2, ensure_ascii=False)
        print(f"Saved form chunks: {forms_file}")
    
    # Save summary
    summary_file = summary_dir / f"{base_name}_summary.json"
    summary = {
        "source_file": filename,
        "pdf_path": str(pdf_path),
        "category": category,
        "rgn_date": rgn_date,
        "total_parent_chunks": len(parent_chunks),
        "total_child_chunks": len(child_chunks),
        "total_table_chunks": len(table_chunks),
        "total_form_chunks": len(form_chunks),
        "parent_chunks_file": str(parent_file),
        "child_chunks_file": str(child_file),
        "table_chunks_file": str(tables_file) if tables_file else None,
        "form_chunks_file": str(forms_file) if forms_file else None,
        "sections": [
            {
                "section_number": p.metadata['section_number'],
                "section_title": p.metadata['section_title'],
                "parent_id": p.metadata['parent_id'],
                "page_numbers": p.metadata['page_numbers'],
                "num_children": len([c for c in child_chunks if c.metadata['parent_id'] == p.metadata['parent_id']])
            }
            for p in parent_chunks
        ]
    }
    with open(summary_file, 'w', encoding='utf-8') as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)
    print(f"Saved summary: {summary_file}")
    
    # Save progress only for batch mode (single-file runs should not affect resume state)
    if update_progress:
        save_last_processed_pdf(pdf_path, base_output_dir)
    
    return True


def find_all_pdfs(raw_pdfs_dir: Path):
    """
    Find all PDF files in the raw_pdfs directory and its subdirectories.
    
    Args:
        raw_pdfs_dir: Path to data/raw_pdfs directory
        
    Returns:
        List of Path objects for all PDF files
    """
    pdf_files = []
    if raw_pdfs_dir.exists():
        # Find all PDF files recursively (case-insensitive)
        pdf_files = list(raw_pdfs_dir.rglob("*.pdf"))
        pdf_files.extend(list(raw_pdfs_dir.rglob("*.PDF")))
        # Remove duplicates (in case same file appears with different case)
        pdf_files = list(set(pdf_files))
    return sorted(pdf_files)


def get_progress_file_path(base_output_dir: Path) -> Path:
    """
    Get the path to the progress tracking file.
    
    Args:
        base_output_dir: Base output directory
        
    Returns:
        Path to the progress file
    """
    return base_output_dir / ".last_processed_pdf.json"


def save_last_processed_pdf(pdf_path: Path, base_output_dir: Path):
    """
    Save the last successfully processed PDF path to a progress file.
    
    Args:
        pdf_path: Path to the PDF that was just processed
        base_output_dir: Base output directory
    """
    progress_file = get_progress_file_path(base_output_dir)
    progress_data = {
        "last_processed_pdf": str(pdf_path),
        "last_processed_time": str(Path(pdf_path).stat().st_mtime) if pdf_path.exists() else None
    }
    progress_file.parent.mkdir(parents=True, exist_ok=True)
    with open(progress_file, 'w', encoding='utf-8') as f:
        json.dump(progress_data, f, indent=2)


def get_last_processed_pdf(base_output_dir: Path) -> Optional[Path]:
    """
    Get the path to the last processed PDF from the progress file.
    
    Args:
        base_output_dir: Base output directory
        
    Returns:
        Path to the last processed PDF, or None if not found
    """
    progress_file = get_progress_file_path(base_output_dir)
    if not progress_file.exists():
        return None
    
    try:
        with open(progress_file, 'r', encoding='utf-8') as f:
            progress_data = json.load(f)
            last_pdf_path = progress_data.get("last_processed_pdf")
            if last_pdf_path:
                pdf_path = Path(last_pdf_path)
                # Verify the file still exists
                if pdf_path.exists():
                    return pdf_path
    except (json.JSONDecodeError, KeyError, Exception):
        # If there's any error reading the progress file, return None
        pass
    
    return None


def find_resume_index(pdf_files: list[Path], last_processed_pdf: Optional[Path]) -> int:
    """
    Find the index in pdf_files where processing should resume.
    
    Args:
        pdf_files: List of all PDF files to process
        last_processed_pdf: Path to the last processed PDF, or None
        
    Returns:
        Index to start processing from (0 if no last processed PDF found)
    """
    if last_processed_pdf is None:
        return 0
    
    # Find the index of the last processed PDF
    try:
        last_index = pdf_files.index(last_processed_pdf)
        # Resume from the next PDF after the last processed one
        return last_index + 1
    except ValueError:
        # Last processed PDF not found in current list, start from beginning
        return 0


def main():
    # Base directories — chunk JSON under data/chunking/<category>/...
    project_root = Path(__file__).parent.parent
    raw_pdfs_dir = project_root / "data" / "raw_pdfs"
    base_output_dir = project_root / "data" / "chunking"
    
    # Check if a specific PDF path was provided
    if len(sys.argv) > 1:
        # Process single PDF
        pdf_path = Path(sys.argv[1])
        if not pdf_path.exists():
            print(f"[ERROR] PDF file not found: {pdf_path}")
            sys.exit(1)
        
        success = process_single_pdf(pdf_path, base_output_dir, update_progress=False)
        sys.exit(0 if success else 1)
    else:
        # Process all PDFs in data/raw_pdfs
        print("="*80)
        print("Processing all PDFs from data/raw_pdfs/")
        print("="*80)
        
        if not raw_pdfs_dir.exists():
            print(f"[ERROR] Directory not found: {raw_pdfs_dir}")
            sys.exit(1)
        
        # Find all PDF files
        pdf_files = find_all_pdfs(raw_pdfs_dir)
        
        if not pdf_files:
            print(f"[WARNING] No PDF files found in {raw_pdfs_dir}")
            sys.exit(0)
        
        # Check for last processed PDF to resume from
        last_processed_pdf = get_last_processed_pdf(base_output_dir)
        resume_index = find_resume_index(pdf_files, last_processed_pdf)
        
        if resume_index > 0:
            print(f"\n[INFO] Resuming from last processed PDF: {last_processed_pdf.name}")
            print(f"[INFO] Will continue from PDF #{resume_index + 1} of {len(pdf_files)}")
            pdf_files_to_process = pdf_files[resume_index:]
        else:
            print(f"\n[INFO] Starting fresh - no previous progress found")
            pdf_files_to_process = pdf_files
        
        print(f"\nFound {len(pdf_files)} PDF file(s) total")
        print(f"Processing {len(pdf_files_to_process)} PDF file(s) remaining\n")
        
        if not pdf_files_to_process:
            print("[INFO] All PDFs have already been processed!")
            sys.exit(0)
        
        # Process each PDF — stop entire batch on first failure
        for i, pdf_path in enumerate(pdf_files_to_process, resume_index + 1):
            print(f"\n[{i}/{len(pdf_files)}] Processing: {pdf_path.name}")
            if not process_single_pdf(pdf_path, base_output_dir):
                print(f"\n[ERROR] Batch terminated: failed processing {pdf_path.name}")
                sys.exit(1)

        print(f"\n[INFO] Batch complete: {len(pdf_files_to_process)} PDF(s) processed successfully.")


if __name__ == "__main__":
    main()

