#!/usr/bin/env python3
"""
PDF Text Extraction using LlamaParser

This module provides PDF text extraction functionality using LlamaParser.
It extracts text from PDF files with better formatting and footnote handling.

When run as main, it batch-processes all PDFs under data/raw_pdfs/{civil,criminal,family}/
and saves results to data/extracted_text/{civil,criminal,family}/. It stores the last
successfully processed file in data/.last_processed_extraction.json and resumes from
the next file on the next run. If the LlamaParser API limit is hit, it stops and
saves state so re-running continues from the next PDF.
"""

import json
import os
import sys
import re
from pathlib import Path
from typing import List, Dict, Tuple, Optional
from llama_parse import LlamaParse

# Paths for batch processing and resume state
PROJECT_ROOT = Path(__file__).resolve().parent.parent
RAW_PDFS_DIR = PROJECT_ROOT /"RAG" /"data" / "raw_pdfs"
EXTRACTED_TEXT_DIR = PROJECT_ROOT /"RAG" /"data" / "extracted_text"
LAST_PROCESSED_FILE = PROJECT_ROOT/"RAG" / "data" / ".last_processed_extraction.json"
CATEGORIES = ("civil", "criminal", "family")

# Load environment variables
try:
    from dotenv import load_dotenv
    # Try to load from .env file in project root
    env_path = Path(__file__).parent.parent.parent / ".env"
    if env_path.exists():
        load_dotenv(env_path)
    else:
        # Load from environment
        load_dotenv()
except ImportError:
    print("WARNING: python-dotenv not available, using system environment variables only")


# Mapping of superscript characters to regular digits
SUPERSCRIPT_TO_DIGIT = {
    '¹': '1', '²': '2', '³': '3', '⁴': '4', '⁵': '5',
    '⁶': '6', '⁷': '7', '⁸': '8', '⁹': '9', '⁰': '0'
}


def superscript_to_number(superscript_str: str) -> str:
    """
    Convert superscript string to regular number.
    
    Args:
        superscript_str: String containing superscript characters (e.g., "¹²", "³")
        
    Returns:
        Regular number string (e.g., "12", "3")
    """
    result = ""
    for char in superscript_str:
        if char in SUPERSCRIPT_TO_DIGIT:
            result += SUPERSCRIPT_TO_DIGIT[char]
        else:
            result += char
    return result


def remove_page_numbers_from_text(text: str) -> str:
    """
    Remove page number patterns from text.
    Patterns like "Page 11 of 12", "\n\nPage 11 of 12", etc.
    
    Args:
        text: Text that may contain page numbers
        
    Returns:
        Text with page numbers removed
    """
    if not text:
        return text
    
    # Pattern to match page numbers in various formats
    # Matches: "Page 11 of 12", "\n\nPage 11 of 12", "Page 11 of 12,", etc.
    page_number_pattern = re.compile(
        r'(?:\n\s*)*Page\s+\d+\s+of\s+\d+(?:\s*,\s*)?(?:\n\s*)*',
        re.IGNORECASE | re.MULTILINE
    )
    
    # Remove all page number patterns
    cleaned_text = page_number_pattern.sub('', text)
    
    # Clean up multiple consecutive newlines that might result
    cleaned_text = re.sub(r'\n{3,}', '\n\n', cleaned_text)
    
    return cleaned_text.strip()


def extract_footnotes_from_text_primary(text: str, page_number: int) -> List[Dict[str, str]]:
    """
    Primary function to extract footnotes by checking separators first.
    
    Strategy:
    1. Find all separators in the page (horizontal lines like ---, ___, ===, etc.)
    2. For each separator, check the content below it for footnotes
    3. Return footnotes found under separators
    4. Some separators may not have footnotes - only return those that do
    
    Args:
        text: Text content of a page
        page_number: Page number (1-indexed)
        
    Returns:
        List of dictionaries with keys: 'marker', 'marker_number', 'text', 'page_number'
        Empty list if no footnotes found under separators
    """
    footnotes = []
    
    # Pattern to match separator lines (horizontal lines with dashes, underscores, equals, etc.)
    # Separator should be at least 3 characters and contain only separator characters and spaces
    separator_pattern = re.compile(r'^[\s]*[-_=\.]{3,}[\s]*$')
    
    # Pattern to match superscript footnote markers
    superscript_pattern = re.compile(r'^([¹²³⁴⁵⁶⁷⁸⁹⁰]+)')
    
    lines = text.split('\n')
    
    # Find all separator positions
    separator_positions = []
    for i, line in enumerate(lines):
        if separator_pattern.match(line.strip()):
            separator_positions.append(i)
    
    if not separator_positions:
        # No separators found, return empty list (will fall back to secondary function)
        return []
    
    # Check content under each separator for footnotes
    for sep_idx in separator_positions:
        # Get lines after this separator (until next separator or end of page)
        next_sep_idx = None
        for next_sep in separator_positions:
            if next_sep > sep_idx:
                next_sep_idx = next_sep
                break
        
        # Lines to check: from separator + 1 to next separator (or end of page)
        start_line = sep_idx + 1
        end_line = next_sep_idx if next_sep_idx is not None else len(lines)
        
        # CRITICAL: If the first thing after separator is a footnote marker,
        # then ALL text under that separator until end of page is footnotes
        first_line_after_separator = None
        if start_line < len(lines):
            first_line_after_separator = lines[start_line].strip()
        
        # Check if first line after separator starts with a superscript marker
        first_line_has_marker = False
        if first_line_after_separator:
            match = superscript_pattern.match(first_line_after_separator)
            if match:
                first_line_has_marker = True
        
        # Extract potential footnote lines under this separator
        # When under a separator and a marker is found, ALL text after it until next marker is footnote text
        potential_footnote_lines = []
        found_footnotes_under_separator = False
        in_footnote = False  # Track if we're currently collecting a footnote
        current_footnote_marker = None  # Track the current footnote marker
        
        # If first line has a marker, we're definitely in footnote territory
        # All text from separator to end of page (or next separator) is footnotes
        if first_line_has_marker:
            found_footnotes_under_separator = True
        
        for line_idx in range(start_line, end_line):
            line = lines[line_idx]
            line_stripped = line.strip()
            
            # Check if line starts with superscript marker
            match = superscript_pattern.match(line_stripped)
            if match:
                # Found a superscript marker
                superscript_marker = match.group(1)
                remaining_text = line_stripped[len(superscript_marker):].strip()
                
                # If we're already collecting a footnote, this marker starts a new footnote
                # The previous footnote ends here
                if in_footnote:
                    # Previous footnote ends, start new one
                    in_footnote = False
                
                # If first line after separator has marker, ALL markers are footnotes
                # Otherwise, check if this looks like a footnote (has text or brackets)
                if first_line_has_marker or remaining_text or '[' in line_stripped or ']' in line_stripped:
                    found_footnotes_under_separator = True
                    in_footnote = True
                    current_footnote_marker = superscript_marker
                    potential_footnote_lines.append((line_idx, True, line, superscript_marker, remaining_text))
            elif in_footnote:
                # We're collecting a footnote - include ALL text until next marker
                # This includes empty lines, paragraphs, everything until the next superscript marker
                # CRITICAL: When a marker is found, include complete text (single line or multiple paragraphs) until next marker
                potential_footnote_lines.append((line_idx, False, line, None, line_stripped))
            elif first_line_has_marker:
                # First line after separator had a marker, so ALL text after separator is footnotes
                # We're in footnote territory - include this line as it's part of footnotes section
                # This handles text that appears before the first marker (shouldn't happen, but safety check)
                potential_footnote_lines.append((line_idx, False, line, None, line_stripped))
            # If not in footnote and no marker and first_line_has_marker is False, skip (not footnote territory)
        
        # If we found footnotes under this separator, process them
        if found_footnotes_under_separator and potential_footnote_lines:
            # Process the collected footnote lines
            # When under a separator and a marker is found, all text after it until next marker is footnote text
            current_footnote = None
            
            for line_info in potential_footnote_lines:
                line_index, is_footnote_start, line_content, superscript_marker, remaining_text = line_info
                
                if is_footnote_start:
                    # Save previous footnote if exists
                    if current_footnote:
                        # Clean page numbers from footnote text before appending
                        current_footnote['text'] = remove_page_numbers_from_text(current_footnote['text'])
                        footnotes.append(current_footnote)
                    
                    # Start new footnote
                    marker_number = superscript_to_number(superscript_marker)
                    current_footnote = {
                        'marker': superscript_marker,
                        'marker_number': marker_number,
                        'text': remaining_text,
                        'page_number': page_number
                    }
                else:
                    # This is a continuation line - include ALL text until next marker
                    # Even if it spans multiple paragraphs, it's all part of the current footnote
                    # CRITICAL: Preserve paragraph breaks and empty lines for multi-paragraph footnotes
                    if current_footnote:
                        # Append to current footnote text (preserve paragraph breaks and empty lines)
                        if current_footnote['text']:
                            # If current text doesn't end with newline, add one
                            if not current_footnote['text'].endswith('\n'):
                                current_footnote['text'] += '\n'
                            # Append the line content (preserve original line, including empty lines)
                            current_footnote['text'] += line_content
                        else:
                            # First line of footnote
                            current_footnote['text'] = line_content
            
            # Don't forget the last footnote
            if current_footnote:
                # Clean page numbers from footnote text before appending
                current_footnote['text'] = remove_page_numbers_from_text(current_footnote['text'])
                footnotes.append(current_footnote)
    
    return footnotes


def extract_footnotes_from_text(text: str, page_number: int) -> List[Dict[str, str]]:
    """
    Secondary function to extract footnotes from the end of a page's text.
    This is used as a fallback when extract_footnotes_from_text_primary doesn't find footnotes.
    
    Strategy: Start from the bottom of the page and work upwards.
    - Lines starting with superscript markers are footnotes
    - Lines without markers that follow footnote lines are continuations
    - Stop when we encounter a line without a marker that's not a continuation
    
    Args:
        text: Text content of a page
        page_number: Page number (1-indexed)
        
    Returns:
        List of dictionaries with keys: 'marker', 'marker_number', 'text', 'page_number'
        Note: 'start_pos' and 'end_pos' are added later in extract_text_from_pdf
    """
    footnotes = []
    
    # Pattern to match superscript footnote markers at the start of a line
    # Matches: ¹, ², ³, ¹², ¹³, ²⁵, etc. (single or multi-digit superscript)
    superscript_pattern = r'^([¹²³⁴⁵⁶⁷⁸⁹⁰]+)'
    
    lines = text.split('\n')
    
    # Start from the bottom and work upwards
    # Collect footnote lines and their continuations
    footnote_lines = []  # Store (line_index, is_footnote_start, content)
    in_footnote_section = False
    
    # Iterate from bottom to top
    for i in range(len(lines) - 1, -1, -1):
        line = lines[i].strip()
        
        # Skip empty lines but continue checking
        if not line:
            continue
        
        # Check if line starts with superscript digit(s)
        match = re.match(superscript_pattern, line)
        
        if match:
            # This line starts with a superscript marker - it's a footnote
            superscript_marker = match.group(1)
            remaining_text = line[len(superscript_marker):].strip()
            
            # Check if this looks like a footnote (has text or brackets)
            if remaining_text or '[' in line or ']' in line:
                # This is a footnote line
                footnote_lines.append((i, True, line, superscript_marker, remaining_text))
                in_footnote_section = True
        else:
            # Line doesn't start with superscript marker
            if in_footnote_section:
                # We're in footnote section, check if this is a continuation
                # Continuation lines typically:
                # - Don't start with capital letters (unless it's a proper noun)
                # - Are not section headers (don't start with # or numbers)
                # - Are not too long (footnotes are usually short)
                
                is_continuation = False
                
                # Check if it looks like a continuation:
                # 1. Doesn't start with # (markdown header)
                # 2. Doesn't start with a number followed by period (section number)
                # 3. Doesn't start with common section patterns
                
                if not line.startswith('#') and not re.match(r'^\d+\.', line):
                    # Check if previous line was a footnote
                    if footnote_lines and footnote_lines[-1][1]:  # Last was a footnote start
                        is_continuation = True
                
                if is_continuation:
                    # This is a continuation of the previous footnote
                    footnote_lines.append((i, False, line, None, line))
                else:
                    # This is not a continuation - we've reached normal text
                    # Stop collecting footnotes
                    break
            else:
                # Not in footnote section and no marker - this is normal text
                # We can stop here (though we'll continue checking from bottom)
                # Actually, we should continue until we find footnotes
                pass
    
    # Now process the collected footnote lines (they're in reverse order)
    # Group continuations with their footnote starts
    current_footnote = None
    
    for line_info in reversed(footnote_lines):  # Reverse to get correct order
        if len(line_info) == 5:
            line_index, is_footnote_start, line_content, superscript_marker, remaining_text = line_info
        else:
            # Handle old format if needed
            continue
        
        if is_footnote_start:
            # Save previous footnote if exists
            if current_footnote:
                # Clean page numbers from footnote text before appending
                current_footnote['text'] = remove_page_numbers_from_text(current_footnote['text'])
                footnotes.append(current_footnote)
            
            # Start new footnote
            marker_number = superscript_to_number(superscript_marker)
            current_footnote = {
                'marker': superscript_marker,
                'marker_number': marker_number,
                'text': remaining_text,
                'page_number': page_number
            }
        else:
            # This is a continuation line
            if current_footnote:
                # Append to current footnote text
                current_footnote['text'] += ' ' + line_content.strip()
    
    # Don't forget the last footnote
    if current_footnote:
        # Clean page numbers from footnote text before appending
        current_footnote['text'] = remove_page_numbers_from_text(current_footnote['text'])
        footnotes.append(current_footnote)
    
    return footnotes


def ensure_footnotes_and_page_numbers_at_end(page_text: str) -> str:
    """
    Reorganize page text to ensure footnotes and page numbers appear at the end,
    matching the PDF structure.
    
    Args:
        page_text: Raw text extracted from a page
        
    Returns:
        Reorganized text with main content first, footnotes in the middle, 
        and page numbers at the very end
    """
    lines = page_text.split('\n')
    
    # Patterns to identify different types of lines
    superscript_pattern = r'^([¹²³⁴⁵⁶⁷⁸⁹⁰]+)'  # Lines starting with superscript
    page_number_pattern = re.compile(r'^\s*Page \d+ of \d+\s*$', re.IGNORECASE)
    
    # Separate lines into categories
    main_content_lines = []
    footnote_lines = []
    page_number_lines = []
    
    # Track if we're in a footnote section (scanning from bottom)
    # We'll identify footnotes by scanning from the end
    lines_reversed = list(reversed(lines))
    footnote_indices = set()
    in_footnote_section = False
    
    # Scan from bottom to identify footnote section
    for i, line in enumerate(lines_reversed):
        line_stripped = line.strip()
        
        # Check if it's a page number first
        if line_stripped and page_number_pattern.match(line_stripped):
            # Page numbers are always at the end, skip them
            continue
        
        if not line_stripped:
            # Empty line: if we're in footnote section, it might be part of footnotes
            if in_footnote_section:
                # Keep empty lines that are in footnote section
                original_index = len(lines) - 1 - i
                footnote_indices.add(original_index)
            continue
        
        # Check if line starts with superscript marker
        match = re.match(superscript_pattern, line_stripped)
        if match:
            # This is a footnote line
            original_index = len(lines) - 1 - i
            footnote_indices.add(original_index)
            in_footnote_section = True
        elif in_footnote_section:
            # We're in footnote section, check if this is a continuation
            # Continuation heuristics (similar to extract_footnotes_from_text):
            # - Doesn't start with # (markdown header)
            # - Doesn't start with number followed by period (section number)
            # - Doesn't look like a new main content paragraph
            is_continuation = False
            
            if (not line_stripped.startswith('#') and 
                not re.match(r'^\d+\.', line_stripped)):
                # Likely a continuation
                is_continuation = True
            
            if is_continuation:
                original_index = len(lines) - 1 - i
                footnote_indices.add(original_index)
            else:
                # We've left the footnote section - this is main content
                break
    
    # Now categorize all lines
    for i, line in enumerate(lines):
        line_stripped = line.strip()
        
        # Check if it's a page number first
        if line_stripped and page_number_pattern.match(line_stripped):
            page_number_lines.append(line_stripped)
        elif i in footnote_indices:
            # This is a footnote line (including empty lines in footnote section)
            footnote_lines.append(line)
        elif not line_stripped:
            # Empty line not in footnote section - preserve in main content
            main_content_lines.append(line)
        else:
            # This is main content
            main_content_lines.append(line)
    
    # Reconstruct: main content + footnotes + page numbers
    reorganized_lines = []
    
    # Add main content
    reorganized_lines.extend(main_content_lines)
    
    # Add footnotes if any
    if footnote_lines:
        # Ensure there's a blank line before footnotes if main content doesn't end with one
        if reorganized_lines and reorganized_lines[-1].strip():
            reorganized_lines.append('')
        reorganized_lines.extend(footnote_lines)
    
    # Add page numbers at the very end
    if page_number_lines:
        # Ensure there's a blank line before page numbers if content doesn't end with one
        if reorganized_lines and reorganized_lines[-1].strip():
            reorganized_lines.append('')
        reorganized_lines.extend(page_number_lines)
    
    return '\n'.join(reorganized_lines)


def extract_text_from_pdf(pdf_path: str) -> Tuple[str, List[Dict[str, str]], Dict[int, int]]:
    """
    Extract text from a PDF file using LlamaParser and extract footnotes.
    
    Args:
        pdf_path: Path to the PDF file
        
    Returns:
        Tuple of (extracted_text, footnotes_list, position_to_page)
        - extracted_text: Full extracted text as a string
        - footnotes_list: List of dictionaries with footnote information
        - position_to_page: Dictionary mapping character position to page number (1-indexed)
        
    Raises:
        FileNotFoundError: If the PDF file doesn't exist
        Exception: If there's an error reading the PDF
    """
    if not os.path.exists(pdf_path):
        raise FileNotFoundError(f"PDF file not found: {pdf_path}")
    
    try:
        # Get LlamaParser API key from environment
        llama_api_key = os.getenv("LLAMA_CLOUD_API_KEY")
        if not llama_api_key:
            env_path = Path(__file__).parent.parent.parent / ".env"
            raise Exception(f"LLAMA_CLOUD_API_KEY not found in environment variables.\n"
                          f"Please add LLAMA_CLOUD_API_KEY=your_key to {env_path} or set it as an environment variable.")
        
        # print("Initializing LlamaParser...")
        
        # Initialize LlamaParser with enhanced superscript footnote configuration
        parser = LlamaParse(
            api_key=llama_api_key,
            result_type="markdown",
            num_workers=4,
            verbose=True,
            language="en",
           
            # Use premium mode for better accuracy
            premium_mode=True,
            # Enable layout extraction to detect graphical elements (separators, lines, borders, etc.)
            extract_layout=True,
            # Enhanced prompt to force superscript preservation and ensure last page extraction
            user_prompt="""You are extracting high-quality markdown from Pakistani legal PDFs. Follow these rules strictly.

========================
1. GENERAL BEHAVIOUR
========================
- Extract ALL real document text in reading order.
- Ignore headers/footers except page numbers like "Page X of Y".
- Never invent or summarize; preserve the original wording.

========================
2. FOOTNOTES (SUPERSCRIPTS)
========================
- Footnote numbers MUST be output as Unicode superscript digits.
  - 1 → ¹, 2 → ², 3 → ³, …, 10 → ¹⁰, 25 → ²⁵, 123 → ¹²³, etc.
- Convert every digit of the footnote number to its superscript form.
- Preserve brackets and content exactly, e.g.:
  - "3[* * *]" → "³[* * *]"
  - "10Added by Act" → "¹⁰Added by Act"
- Extract ALL footnotes on ALL pages, including the last page.

========================
3. IMAGES, WATERMARKS, LOGOS
========================
- Completely IGNORE all images and picture content:
  - Do NOT OCR or extract any text from images.
  - Do NOT extract text from scanned stamps, signatures, or logos.
- Ignore watermarks and background text such as:
  - "THE PAKISTAN CODE" or other repeated background logos/phrases.
- Only extract normal foreground document text.

========================
4. SECTION HEADINGS (BOLD)
========================
- Section headings that are bold in the PDF MUST be wrapped in markdown bold **…**.
- Typical patterns:
  - "1. Short title"
  - "2. Local extent."
  - "30. Power to make rules"
  - "22-A. Definitions"
- When a heading is bold, output it as:
  - **1. Short title**
  - **2. Local extent.**
  - **30. Power to make rules**
  - **22-A. Definitions**
- The ENTIRE heading (number + title) must be inside ** **.

========================
5. PAGE STRUCTURE & FOOTNOTE SEPARATOR
========================
For EACH page, preserve this order:

1) Main page content  
   (sections, paragraphs, tables, forms, etc.)

2) A separator line:
   ------
   (exactly six or more dashes on its own line)

3) All footnotes for that page  
   (each starting with a superscript number)

4) The page number line:
   Page X of Y

Rules:
- Do NOT move content across pages.
- Do NOT put footnotes before the separator.
- Do NOT put page numbers anywhere except LAST on the page.
- If the PDF has no obvious separator between text and footnotes, still insert "------" between them.

========================
FORM & TABLE HANDLING — STRICT AND MANDATORY
========================

You MUST accurately detect, preserve, and wrap ALL FORMS and TABLES.
Missing, splitting, or prematurely terminating a FORM or TABLE is NOT acceptable.

Pages are layout artifacts. Forms and tables are LOGICAL structures.
Page breaks MUST NOT terminate or split them.

Always think in terms of: “Is this still the SAME form or table?”  
If YES, you MUST keep it in ONE continuous block, even if it spans many pages or has multiple sections.

---------------------------------------------------
PART 1 — FORM DETECTION (HIGHEST PRIORITY)
--------------------------------------------------
FORMS ALWAYS TAKE PRIORITY over TABLES.

Once a FORM starts, EVERYTHING inside it (including tables) belongs to THAT FORM
until the form explicitly ends.

Treat a block as a FORM if ANY of the following apply:

A) Form keywords in headings

Headings containing words such as:

“FORM”, “FORM A”, “FORM B”, “FORM C”, “FORM D”, etc.

“FORM OF APPLICATION”, “FORM OF CERTIFICATE”

“FORM OF WARRANT”, “FORM OF NOTICE”, “FORM OF REGISTRATION”

Standalone headings like “APPLICATION”, “CERTIFICATE”, “DECLARATION”, “AFFIDAVIT”
WHEN followed by fill-in content

B) Schedule behaving like a fill-in template

“SCHEDULE I”, “SCHEDULE II”, “THE FIRST SCHEDULE”, “THE SECOND SCHEDULE”, etc.
AND the content contains:

blanks

instructions like “to be filled by…”

structured fields

signature / verification blocks

C) Labeled blanks / fields

Any of the following (even with imperfect OCR or dots instead of lines):

“Name ___________” or “Name…………………..”

“Address ___________”

“CNIC:”

“Date:”

Dotted or underlined blanks

Long underscore rows

D) “Who fills this” language

“to be filled by the applicant”

“for official use only”

“to be completed by”

“for completion by the court / office”

E) Signature / verification language

“Signature of applicant”

“Signature of authorized officer”

“Signature and thumb impression”

“Thumb impression”

“Seal of Court”

“Seal of the authorized officer”

“Verification”, “Affidavit”

“Given under my hand”

F) Multi-section templates

A single FORM may contain:

PART I / PART II / PART III

SECTION 1 / SECTION 2

Section I / Section II / Section III

“ENDORSEMENT”, “RENEWAL”, “NOTE(S)”

“INSTRUCTIONS”

“PARTICULARS TO BE FURNISHED…”

“PARTICULARS TO BE RECORDED…”

ALL of these belong to ONE FORM if they follow the same form heading
(even if they appear on later pages).

If ANY of A–F apply, treat the ENTIRE block as ONE FORM.

--------------------------------------------------
SPECIAL RULE — SCHEDULE HEADINGS INSIDE FORMS / TABLES
--------------------------------------------------

When a FORM or TABLE appears under a SCHEDULE:

If there is a heading that contains the word “SCHEDULE” (e.g. “SCHEDULE”, “FIRST SCHEDULE”, “THE FOURTH SCHEDULE”, “SCHEDULE II”, etc.), and that heading is part of the SCHEDULE section:

You MUST NOT include that SCHEDULE heading line inside any FORM or TABLE block.

The SCHEDULE heading belongs to the parent SCHEDULE section, not to the FORM/TABLE itself.

Instead:

Include any form-specific or table-specific headings above or below it (e.g. “FORM C”, “FORM OF APPLICATION…”, “PARTICULARS TO BE RECORDED ON LICENCE”, “Table of court fees”) as part of the FORM/TABLE where appropriate.

Treat all form/table content under the SCHEDULE heading as normal FORM/TABLE content, but the actual “SCHEDULE …” heading line must stay outside the FORM/TABLE wrapping.

In short:

Do NOT wrap the heading that contains “SCHEDULE” inside a FORM or TABLE.
Only wrap the FORM/TABLE body plus any non-SCHEDULE titles/captions that label that specific form/table.

--------------------------------------------------
FORM TITLES / CAPTIONS (MANDATORY)
--------------------------------------------------
Every FORM must include its title/caption together with the body:

If there is a line directly ABOVE the form that names it, such as:

“FORM A”

“FORM C”

“FORM OF APPLICATION FOR LICENCE TO DRIVE A ROAD VEHICLE”

“PARTICULARS TO BE RECORDED ON LICENCE”
then you MUST include those title lines INSIDE the same form block,
immediately before the form content.

If there is a bold or centered heading that clearly labels the form,
include that heading in the form as well.

Exception with SCHEDULE headings:
If the heading line itself contains “SCHEDULE” (e.g. “THE FIRST SCHEDULE”, “SCHEDULE II”),
that heading MUST NOT be included inside the FORM. It stays with the SCHEDULE section.
You only include the form-specific caption/heading (like “FORM C”, “PARTICULARS TO BE RECORDED…”) in the FORM block.

The title/caption lines MUST appear in the extracted form text so they are
available to any child chunks created later.

--------------------------------------------------
FORM WRAPPING (MANDATORY)
--------------------------------------------------

Wrap each detected form EXACTLY as:

<<<FORM_START>>>
[complete form text including:
 - all headings and titles (FORM / SCHEDULE + any caption lines above)
 - internal parts / sections
 - blanks
 - instructions
 - any tables belonging to the form
 - signature, thumb impression, date, seal & verification blocks]
<<<FORM_END>>>

Do NOT summarize, normalize, or restructure forms.
Preserve layout and fill-in intent.

--------------------------------------------------
MULTI-PAGE FORMS (CRITICAL)
--------------------------------------------------

If a form continues across pages:

- It is STILL ONE SINGLE FORM.
- <<<FORM_START>>> appears ONLY once at the very first line of the form
  (before the title/heading or at “FORM …” / “FORM OF APPLICATION …”).
- <<<FORM_END>>> appears ONLY once after the final line of the SAME form.

Page breaks MUST be ignored when deciding form boundaries.

You MUST continue the SAME form across pages whenever:

- Sections like “Section II”, “Section III”, “PART II”, “PART III” appear,
  and they still contain form-style fields, blanks, or instructions.
- The content still looks like the same template (fields, blanks, “to be filled by…”, etc.).
- Signature/date/thumb-impression lines appear near the bottom of a page:
  these are part of the SAME form, not a new section.

ONLY after the FINAL SIGNATURE/DATE/THUMB IMPRESSION/VERIFICATION block and 
after any immediately following instructions related to that form may the form end.

--------------------------------------------------
CRITICAL FORM BOUNDARY RULE — DO NOT TERMINATE EARLY
--------------------------------------------------

The following MUST NOT end a form if they appear after a form heading:
- ENDORSEMENT
- RENEWAL
- NOTE / NOTES
- INSTRUCTIONS
- EXPLANATION
- “[See section …]”
- Explanatory statutory text about how the form is used
- Sections like “Section II”, “Section III” that still contain fields/blanks
- Continuations of “PARTICULARS TO BE FURNISHED / RECORDED”

A FORM may ONLY end when:

- A new, clearly different FORM begins (e.g. “FORM D”, “FORM E”), OR
- A new, unrelated SCHEDULE begins, OR
- There is a final signature / thumb impression / date / seal block AND
  afterwards the text clearly switches back to normal narrative law text
  (no more blanks, no more form fields).

If uncertain, DEFAULT to keeping content INSIDE the same FORM.

--------------------------------------------------
PART 2 — TABLE HANDLING (OUTSIDE FORMS)
--------------------------------------------------

Tables are detected ONLY OUTSIDE FORMS.
Any table inside a FORM stays INSIDE the FORM and is NOT extracted separately.

Treat a block as a TABLE if ANY of the following apply:

A) Tabular structure

- Rows and columns
- Aligned content
- Pipe, spacing, or OCR-aligned grids
- Borderless but clearly column-based layouts

B) Column headers

Examples:
- “S. No | Name | CNIC”
- “Description | Quantity | Rate | Amount”
- “Offence | Punishment | Section”

C) Repeating structured rows

- Lists of items with multiple attributes
- Fee schedules
- Rate tables
- Registers
- Category listings

D) Multi-section tables

A single TABLE may contain:
- PART I / PART II
- SECTION 1 / SECTION 2
- Section I / Section II
- “ENDORSEMENT”, “RENEWAL”, “INSTRUCTIONS”
- “PARTICULARS TO BE RECORDED…”

ALL of these belong to ONE TABLE if they follow the same table heading
and share the same columns/structure (even across multiple pages).

--------------------------------------------------
TABLE TITLES / CAPTIONS (MANDATORY)
--------------------------------------------------

Every TABLE must include its title/caption together with the rows:

- If there is a line directly ABOVE the table that names or describes it, such as:
  - “TABLE OF FEES”
  - “SCHEDULE OF PENALTIES”
  - “FORM F – Registration details”
  then you MUST include that title line immediately above the markdown table,
  INSIDE the same table block.

- If there is a bold/centered heading that clearly labels the table,
  include that heading with the table.

These title/caption lines MUST be part of the table output so they are available
in any later child chunks.

--------------------------------------------------
TABLE PRESERVATION (MANDATORY)
--------------------------------------------------

ALL tables MUST be preserved as GitHub-style markdown:

| Col A | Col B |
| ----- | ----- |
| ...   | ...   |

Rules:
- Do NOT flatten tables.
- Do NOT convert to plain text or lists.
- Preserve row order exactly.
- ONE logical table = ONE markdown table block.

--------------------------------------------------
MULTI-PAGE TABLES (CRITICAL)
--------------------------------------------------

If a table continues across pages:

✅ Treat it as ONE SINGLE TABLE.  
✅ Do NOT terminate on page breaks.  
✅ Do NOT restart with a new table block.

Rules:
- Ignore page numbers and footers.
- If headers repeat on later pages, include the header row only once at the top.
- Append all following rows in the correct logical order.
- Do NOT insert “continued”.

--------------------------------------------------
TABLE CONTINUATION RULES
--------------------------------------------------

A table MUST continue if:
- Columns stay consistent, OR
- Headers repeat, OR
- Row numbering continues, OR
- OCR formatting still clearly forms a grid/columns.

A table ends ONLY when:
- A new unrelated table starts with DIFFERENT columns, OR
- Normal narrative paragraphs resume and the grid/column structure stops.

--------------------------------------------------
OCR ROBUSTNESS
--------------------------------------------------

- Assume OCR may introduce broken lines, extra spaces, or partial words.
- If content still visually/logically behaves like a form (fields, blanks, labels)
  or a table (columns, repeated row structure), you MUST treat it as such,
  even if alignment is imperfect.
- Over-detecting forms/tables is acceptable. Missing or splitting them is NOT.

--------------------------------------------------
SAFETY DEFAULT (VERY IMPORTANT)
--------------------------------------------------

When uncertain:
- If content looks like a FORM → treat as FORM.
- If content looks like a TABLE → treat as TABLE.
- Over-detecting is acceptable.
- Missing, splitting, or prematurely ending FORMS or TABLES is NOT acceptable.

--------------------------------------------------
FINAL RULE
--------------------------------------------------

Think in terms of LOGICAL DOCUMENT STRUCTURE,
NOT pages, NOT layout, NOT visual breaks.

Pages NEVER terminate forms or tables.


========================
OCR HANDLING (CONTROLLED)
========================

OCR may be used when visual layout is required (forms, tables, boxes, multi-column layouts).

If OCR text overlaps with native PDF text:
- Prefer the version that preserves STRUCTURE (forms, tables, grids).
- Do NOT duplicate content.
- Do NOT repeat the same text twice.

OCR errors (minor spelling mistakes) are acceptable if structure is preserved.
Losing or breaking a FORM or TABLE is NOT acceptable.

When OCR is enabled for a page, focus on logical continuity
across pages rather than visual page boundaries.


8. FINAL REMINDERS
========================
- Preserve the exact reading order within each page.
- Use markdown consistently: **bold** for headings, proper table syntax, no HTML.
- Do NOT drop any real content (sections, tables, forms, footnotes).
- Do NOT include images, watermarks, or decorative text.
""")
        
        # print(f"Parsing PDF: {pdf_path}")
        
        # Parse the PDF - LlamaParser will extract all pages
        # The enhanced user_prompt should ensure footnotes on last page are included
        documents = parser.load_data(pdf_path)
        
        # print(f"Successfully parsed {len(documents)} document(s)")
        
        # Extract text from all documents and collect footnotes
        extracted_text = ""
        all_footnotes = []
        position_to_page = {}  # Map character position to page number
        
        for i, doc in enumerate(documents):
            doc_text = doc.text
            page_number = i + 1
            # print(f"Document {page_number}: {len(doc_text)} characters extracted")
            
            # Extract footnotes from this page (before reorganization)
            # Try primary function first (checks separators)
            page_footnotes = extract_footnotes_from_text_primary(doc_text, page_number)
            
            # If primary function didn't find any footnotes, fall back to secondary function
            if not page_footnotes:
                page_footnotes = extract_footnotes_from_text(doc_text, page_number)
            
            # Reorganize page text to ensure footnotes and page numbers are at the end
            doc_text = ensure_footnotes_and_page_numbers_at_end(doc_text)
            
            # Calculate page offset in the extracted text (after reorganization, before adding this page)
            page_offset = len(extracted_text)
            
            # Now find positions of footnotes in the reorganized text and add to extracted_text
            for footnote in page_footnotes:
                # Build search key from footnote marker and text
                # Use first 100 chars of footnote text for matching
                footnote_text = footnote['text'].strip()
                search_key = f"{footnote['marker']}{footnote_text[:min(100, len(footnote_text))]}"
                
                # Find the position of this footnote in the reorganized doc_text
                start_pos = doc_text.find(search_key)
                if start_pos != -1:
                    # Found the footnote, calculate end position
                    end_pos = start_pos + len(footnote['marker']) + len(footnote_text)
                    # Add global offset
                    footnote['start_pos'] = page_offset + start_pos
                    footnote['end_pos'] = page_offset + end_pos
                else:
                    # Fallback: try to find just the marker
                    marker_search = doc_text.find(footnote['marker'])
                    if marker_search != -1:
                        # Estimate end position
                        estimated_length = len(footnote['marker']) + len(footnote_text) + 50  # Add buffer
                        footnote['start_pos'] = page_offset + marker_search
                        footnote['end_pos'] = page_offset + marker_search + estimated_length
                    else:
                        # Could not find footnote in reorganized text
                        footnote['start_pos'] = -1
                        footnote['end_pos'] = -1
            
            all_footnotes.extend(page_footnotes)

            # Track positions for the document text (no separator)
            current_pos = len(extracted_text)
            extracted_text += doc_text
            for pos in range(current_pos, len(extracted_text)):
                position_to_page[pos] = page_number
            
            # Add a newline between pages
            extracted_text += "\n"
            position_to_page[len(extracted_text) - 1] = page_number
        
        return extracted_text, all_footnotes, position_to_page
        
    except Exception as e:
        raise Exception(f"Error parsing PDF with LlamaParser: {str(e)}")


def get_all_pdf_entries() -> List[Tuple[str, Path]]:
    """
    Return a sorted list of (category, pdf_path) for all PDFs under data/raw_pdfs/<category>/.
    Order: civil (sorted by name), then criminal, then family.
    """
    entries = []
    for category in CATEGORIES:
        cat_dir = RAW_PDFS_DIR / category
        if not cat_dir.is_dir():
            continue
        for path in sorted(cat_dir.iterdir()):
            if path.suffix.lower() == ".pdf":
                entries.append((category, path))
    return entries


def load_last_processed() -> Optional[Tuple[str, str]]:
    """
    Load last successfully processed file from state.
    Returns (category, filename) or None if no state or file missing.
    """
    if not LAST_PROCESSED_FILE.exists():
        return None
    try:
        with open(LAST_PROCESSED_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        cat = data.get("category")
        name = data.get("filename")
        if cat and name:
            return (cat, name)
    except (json.JSONDecodeError, OSError):
        pass
    return None


def save_last_processed(category: str, filename: str) -> None:
    """Store last successfully processed file so next run can resume after it."""
    LAST_PROCESSED_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(LAST_PROCESSED_FILE, "w", encoding="utf-8") as f:
        json.dump({"category": category, "filename": filename}, f, indent=2)


# Minimum chars to consider extraction valid; below this we treat as limit/empty response
MIN_EXTRACTED_LENGTH = 100


def _is_limit_error(exc: Exception) -> bool:
    """Heuristic: treat as LlamaParser limit/rate-limit so we stop and save state."""
    msg = str(exc).lower()
    return (
        "limit" in msg
        or "rate" in msg
        or "quota" in msg
        or "429" in msg
        or "too many" in msg
        or "exceeded" in msg
    )


def process_all_pdfs() -> None:
    """
    Process all PDFs in data/raw_pdfs/{civil,criminal,family}/ and save to
    data/extracted_text/{civil,criminal,family}/. Uses last-processed state to resume.
    On LlamaParser limit (or similar), stops and leaves state so next run continues.
    """
    entries = get_all_pdf_entries()
    if not entries:
        print("No PDFs found under data/raw_pdfs/(civil|criminal|family)/.")
        return

    last = load_last_processed()
    start_index = 0
    if last is not None:
        last_cat, last_name = last
        for i, (cat, path) in enumerate(entries):
            if (cat, path.name) == (last_cat, last_name):
                start_index = i + 1
                break
        if start_index > 0:
            print(f"Resuming after last processed: {last_cat}/{last_name} (skipping {start_index} already done).")

    for idx in range(start_index, len(entries)):
        category, pdf_path = entries[idx]
        assert isinstance(pdf_path, Path)
        out_dir = EXTRACTED_TEXT_DIR / category
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / (pdf_path.stem + ".json")

        print(f"[{idx + 1}/{len(entries)}] Processing: {category}/{pdf_path.name}")
        try:
            extracted_text, footnotes, position_to_page = extract_text_from_pdf(str(pdf_path))
        except Exception as e:
            print(f"Error processing {pdf_path.name}: {e}", file=sys.stderr)
            if _is_limit_error(e):
                print("Stopping (limit/rate-limit). Re-run to resume from next file.")
                sys.exit(1)
            raise

        # Do not save or update state if extraction is empty (limit often returns no/empty data)
        if not extracted_text or len(extracted_text.strip()) < MIN_EXTRACTED_LENGTH:
            print(
                f"Empty or too-short extraction for {pdf_path.name} ({len(extracted_text or '')} chars). "
                "Likely API limit. Not saving; re-run to retry this file.",
                file=sys.stderr,
            )
            sys.exit(1)

        position_to_page_str = {str(k): v for k, v in position_to_page.items()}
        out_data = {
            "extracted_text": extracted_text,
            "footnotes": footnotes,
            "position_to_page": position_to_page_str,
        }
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(out_data, f, ensure_ascii=False, indent=2)
        print(f"  Saved: {out_path.relative_to(PROJECT_ROOT)}")

        save_last_processed(category, pdf_path.name)

    print("All PDFs processed.")


def main():
    """
    Process all PDFs in data/raw_pdfs/{civil,criminal,family}/ and save to
    data/extracted_text/{civil,criminal,family}/. Resumes from last processed file;
    on LlamaParser limit, stops and saves state for next run.
    """
    try:
        process_all_pdfs()
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
