#!/usr/bin/env python3
"""
Process raw legal text from Pakistani legal PDFs into Parent and Child chunks.

This script processes LlamaParse-extracted markdown text and creates:
- LegalParentChunk: Full sections with metadata
- LegalChildChunk: Search fragments with parent links
"""

import re
import json
import sys
from pathlib import Path
from typing import List, Optional, Dict, Tuple, Any, Callable

# Prefer langchain_text_splitters (new package), but fall back to classic langchain import if unavailable.
try:
    from langchain_text_splitters import RecursiveCharacterTextSplitter
except ImportError:
    from langchain.text_splitter import RecursiveCharacterTextSplitter

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))
# Allow importing from scripts/ (e.g. split_parent_chunk_by_id)
sys.path.insert(0, str(Path(__file__).parent))

from models.legal_chunks import LegalParentChunk, LegalChildChunk, LegalTableChunk, LegalFormChunk

# Use split_strictly_on_separators from split_parent_chunk_by_id when creating parent chunks (heading-only splits first, then size limit)
try:
    from split_parent_chunk_by_id import (
        split_strictly_on_separators,
        _merge_trivial_trailing_splits,
        _is_trivial_split_fragment,
    )
except ImportError:
    split_strictly_on_separators = None  # fallback: use RecursiveCharacterTextSplitter only

    def _merge_trivial_trailing_splits(segments):  # type: ignore
        return list(segments) if segments else segments

    def _is_trivial_split_fragment(s: str) -> bool:  # type: ignore
        t = (s or "").strip()
        if not t or len(t) > 4:
            return False
        allowed = frozenset(".…,;:!?)]}([\"'")
        return all(c in allowed or c.isspace() for c in t)


# Table extraction pattern - matches GitHub-style markdown tables,
# including tables without an explicit header separator row.
TABLE_PATTERN = re.compile(
    r"""
    (                       # full table block
      (?:^|\n)              # start of line / block
      \|[^\n]*\|\s*         # first row that looks like a table row
      (?:\n\|[^\n]*\|\s*)+  # at least one more table row (2+ rows total)
    )
    (?=\n\s*\n|\Z)          # stop at blank line or end of text
    """,
    re.MULTILINE | re.VERBOSE
)


# Heuristic pattern for "forms without markers" - unwrapped templates
# Looks for blocks of 2+ consecutive lines containing common form labels
# (Name, Address, CNIC, Signature, Thumb impression, Seal, etc.) followed
# by dotted/underscored blanks.
IMPLICIT_FORM_PATTERN = re.compile(
    r"""
    (                                   # full candidate form block
      (?:^|\n)                          # start of line / block
      (?:                               # a single "form-like" line:
        [^\n]*                          # some text
        (?:Name|Address|CNIC|C\.N\.I\.C|
           Identity\s+Card|Signature|
           Thumb\s+impression|Seal)     # label keywords
        [^\n]*                          # trailing text
        [._]{5,}                        # dotted / underscored blanks
        [^\n]*                          # rest of line
        \n                              # line end
      ){2,}                             # at least 2 such lines in a row
    )
    """,
    re.IGNORECASE | re.MULTILINE | re.VERBOSE
)


# Form extraction pattern - matches forms between <<<FORM_START>>> and <<<FORM_END>>> markers
# Use greedy matching to handle multi-page forms correctly
# The pattern should match from the first <<<FORM_START>>> to the LAST <<<FORM_END>>> before the next <<<FORM_START>>>
FORM_PATTERN = re.compile(
    r"<<<FORM_START>>>([\s\S]*?)<<<FORM_END>>>",
    re.MULTILINE | re.DOTALL
)



def _build_post_form_to_raw_mapper(
    source_raw_text: str,
    forms: List[Dict[str, Any]],
) -> Callable[[int, int], Tuple[int, int]]:
    """Map positions from text-after-form-replacement back to raw_text coordinates."""
    segments: List[Tuple[int, int, int, int, bool]] = []
    forms_sorted = sorted(
        [f for f in forms if isinstance(f.get("char_start"), int) and isinstance(f.get("char_end"), int)],
        key=lambda x: x["char_start"],
    )
    raw_cursor = 0
    transformed_cursor = 0
    for f in forms_sorted:
        start_raw = int(f["char_start"])
        end_raw = int(f["char_end"])
        if start_raw < raw_cursor:
            start_raw = raw_cursor
        if end_raw < start_raw:
            continue
        if start_raw > raw_cursor:
            seg_len = start_raw - raw_cursor
            segments.append((transformed_cursor, transformed_cursor + seg_len, raw_cursor, start_raw, False))
            transformed_cursor += seg_len
        placeholder_text = f"\n[{f.get('form_id', 'FORM')}]\n"
        p_len = len(placeholder_text)
        if p_len > 0:
            segments.append((transformed_cursor, transformed_cursor + p_len, start_raw, end_raw, True))
            transformed_cursor += p_len
        raw_cursor = end_raw
    if raw_cursor < len(source_raw_text):
        tail_len = len(source_raw_text) - raw_cursor
        segments.append((transformed_cursor, transformed_cursor + tail_len, raw_cursor, len(source_raw_text), False))

    def map_index(transformed_pos: int) -> int:
        if transformed_pos <= 0:
            return 0
        for t_start, t_end, r_start, r_end, is_placeholder in segments:
            if t_start <= transformed_pos < t_end:
                return r_start if is_placeholder else r_start + (transformed_pos - t_start)
        return len(source_raw_text)

    def map_range(t_start: int, t_end: int) -> Tuple[int, int]:
        r_start = map_index(t_start)
        if t_end <= t_start:
            return r_start, r_start
        r_end = map_index(t_end - 1) + 1
        return max(0, min(r_start, len(source_raw_text))), max(r_start, min(r_end, len(source_raw_text)))

    return map_range


def _build_combined_transformed_to_raw(
    raw_text: str,
    forms: List[Dict[str, Any]],
    tables: List[Dict[str, Any]],
):
    """
    Map positions from text with both form+table placeholders back to raw_text coordinates.
    Returns (transformed_to_raw, raw_to_transformed) for mapping both ways.
    """
    replacements: List[Tuple[int, int, int]] = []  # (raw_start, raw_end, placeholder_len)
    for f in forms:
        if isinstance(f.get("char_start"), int) and isinstance(f.get("char_end"), int):
            s, e = int(f["char_start"]), int(f["char_end"])
            replacements.append((s, e, len(f"\n[{f.get('form_id', 'FORM')}]\n")))
    post_form_to_raw = _build_post_form_to_raw_mapper(raw_text, forms)
    for t in tables:
        ts, te = t.get("char_start"), t.get("char_end")
        if isinstance(ts, int) and isinstance(te, int):
            rs, re = post_form_to_raw(ts, te)
            replacements.append((rs, re, len(f"\n[{t.get('table_id', 'TABLE')}]\n")))
    replacements.sort(key=lambda x: x[0])
    segments: List[Tuple[int, int, int, int, bool]] = []
    raw_cursor = 0
    trans_cursor = 0
    for r_start, r_end, plen in replacements:
        if r_start >= raw_cursor and r_end > r_start:
            if r_start > raw_cursor:
                seg_len = r_start - raw_cursor
                segments.append((trans_cursor, trans_cursor + seg_len, raw_cursor, r_start, False))
                trans_cursor += seg_len
            segments.append((trans_cursor, trans_cursor + plen, r_start, r_end, True))
            trans_cursor += plen
            raw_cursor = r_end
    if raw_cursor < len(raw_text):
        tail_len = len(raw_text) - raw_cursor
        segments.append((trans_cursor, trans_cursor + tail_len, raw_cursor, len(raw_text), False))

    def trans_to_raw_index(t_pos: int) -> int:
        if t_pos <= 0:
            return 0
        for t_s, t_e, r_s, r_e, is_ph in segments:
            if t_s <= t_pos < t_e:
                return r_s if is_ph else r_s + (t_pos - t_s)
        return len(raw_text)

    def raw_to_trans_index(r_pos: int) -> int:
        if r_pos <= 0:
            return 0
        for t_s, t_e, r_s, r_e, is_ph in segments:
            if r_s <= r_pos < r_e:
                return t_s if is_ph else t_s + (r_pos - r_s)
        max_t = segments[-1][1] if segments else 0
        return max_t

    def transformed_to_raw(t_start: int, t_end: int) -> Tuple[int, int]:
        r_start = trans_to_raw_index(t_start)
        if t_end <= t_start:
            return r_start, r_start
        r_end = trans_to_raw_index(t_end - 1) + 1
        return max(0, min(r_start, len(raw_text))), max(r_start, min(r_end, len(raw_text)))

    def raw_to_transformed(r_start: int, r_end: int) -> Tuple[int, int]:
        t_start = raw_to_trans_index(r_start)
        if r_end <= r_start:
            return t_start, t_start
        t_end = raw_to_trans_index(r_end - 1) + 1
        max_t = segments[-1][1] if segments else 0
        return max(0, min(t_start, max_t)), max(t_start, min(t_end, max_t))

    return transformed_to_raw, raw_to_transformed


def apply_form_and_table_placeholders_to_sections(
    sections: List[Dict[str, Any]],
    raw_text: str,
    extracted_forms: List[Dict[str, Any]],
    extracted_tables: List[Dict[str, Any]],
) -> None:
    """
    For each section, replace raw form/table text with placeholders [FORM_n] / [TABLE_n].
    Uses position-based replacement. Counters are per-file (FORM_1, TABLE_1, etc.).
    """
    form_spans: List[Tuple[int, int, str]] = []
    for f in extracted_forms:
        s, e = f.get("char_start"), f.get("char_end")
        fid = f.get("form_id", "FORM")
        if isinstance(s, int) and isinstance(e, int) and s < e:
            form_spans.append((s, e, f"[{fid}]"))

    table_spans: List[Tuple[int, int, str]] = []
    for t in extracted_tables:
        s, e = t.get("char_start"), t.get("char_end")
        tid = t.get("table_id", "TABLE")
        if isinstance(s, int) and isinstance(e, int) and s < e:
            table_spans.append((s, e, f"[{tid}]"))

    if not form_spans and not table_spans:
        return

    for section in sections:
        sec_start = section.get("start_pos", -1)
        sec_end = section.get("end_pos", -1)
        if not isinstance(sec_start, int) or not isinstance(sec_end, int):
            continue
        if sec_start < 0 or sec_end <= sec_start or sec_start >= len(raw_text):
            continue

        section_text = raw_text[sec_start:sec_end]
        local_replacements: List[Tuple[int, int, str]] = []

        for start, end, placeholder in form_spans:
            if end <= sec_start or start >= sec_end:
                continue
            rel_start = max(0, start - sec_start)
            rel_end = min(len(section_text), end - sec_start)
            if rel_start < rel_end:
                local_replacements.append((rel_start, rel_end, placeholder))

        for start, end, placeholder in table_spans:
            if end <= sec_start or start >= sec_end:
                continue
            rel_start = max(0, start - sec_start)
            rel_end = min(len(section_text), end - sec_start)
            if rel_start < rel_end:
                local_replacements.append((rel_start, rel_end, placeholder))

        if not local_replacements:
            section["text"] = section_text
            continue

        local_replacements.sort(key=lambda x: x[0])
        out_parts: List[str] = []
        cursor = 0
        for rel_start, rel_end, placeholder in local_replacements:
            if rel_start > cursor:
                out_parts.append(section_text[cursor:rel_start])
            out_parts.append(f"\n{placeholder}\n")
            cursor = max(cursor, rel_end)
        if cursor < len(section_text):
            out_parts.append(section_text[cursor:])
        section["text"] = "".join(out_parts)



def extract_tables_from_text(
    raw_text: str,
    skip_spans: Optional[List[Tuple[int, int]]] = None
):
    """
    Finds markdown tables and replaces them with placeholders.

    If skip_spans is provided, any table whose span overlaps one of the
    (start, end) ranges will NOT be extracted and the text will be left as-is
    for that region. This is used to avoid extracting tables that live inside
    FORM blocks.

    Returns:
      cleaned_text: Text with tables replaced by placeholders
      tables: list of dicts containing:
        table_id, markdown, char_start, char_end
    """
    tables = []
    table_counter = 1

    def _overlaps_form(start: int, end: int) -> bool:
        if not skip_spans:
            return False
        for s, e in skip_spans:
            # overlap if the ranges intersect in any way
            if not (end <= s or start >= e):
                return True
        return False

    def _replace(match):
        nonlocal table_counter
        table_start = match.start()
        table_end = match.end()

        # If this table lies inside any FORM span, skip it (no extraction)
        if _overlaps_form(table_start, table_end):
            return match.group(0)  # leave the original table text unchanged

        table_md = match.group(0)
        table_id = f"TABLE_{table_counter}"
        tables.append({
            "table_id": table_id,
            "markdown": table_md.strip(),
            "char_start": table_start,  # positions in raw_text
            "char_end": table_end,
        })
        table_counter += 1
        return f"\n[{table_id}]\n"

    cleaned_text = TABLE_PATTERN.sub(_replace, raw_text)
    return cleaned_text, tables


def extract_forms_from_text(raw_text: str):
    """
    Finds forms and replaces them with placeholders.

    This has TWO passes:

    1) Explicit forms:
       - Anything between <<<FORM_START>>> and <<<FORM_END>>> (FORM_PATTERN)

    2) Implicit / unmarked forms:
       - Heuristic blocks that look like fill-in templates, even if they
         were not wrapped with markers (IMPLICIT_FORM_PATTERN).

    Returns:
      cleaned_text: Text with forms replaced by [FORM_n] placeholders
      forms: list of dicts: {form_id, markdown, char_start, char_end}
             where char_start / char_end are positions in the ORIGINAL raw_text.
    """
    spans = []  # list of dicts describing each form span

    # 1) Collect explicit (marker-based) forms
    for m in FORM_PATTERN.finditer(raw_text):
        # full span including markers
        full_start = m.start()
        full_end = m.end()

        # inner content between markers (group 1)
        inner_start = m.start(1)
        inner_end = m.end(1)

        spans.append({
            "kind": "explicit",
            "match_start": full_start,
            "match_end": full_end,
            "content_start": inner_start,
            "content_end": inner_end,
        })

    # Helper: check if a [start, end) overlaps any existing span
    existing_ranges = [(s["match_start"], s["match_end"]) for s in spans]

    def _overlaps_existing(start: int, end: int) -> bool:
        for s, e in existing_ranges:
            if not (end <= s or start >= e):
                return True
        return False

    # 2) Collect implicit / unmarked forms (heuristic)
    #    These are form-like blocks that were not wrapped with markers.
    for m in IMPLICIT_FORM_PATTERN.finditer(raw_text):
        block_start = m.start(1)
        block_end = m.end(1)

        # Skip anything that overlaps an explicit form
        if _overlaps_existing(block_start, block_end):
            continue

        spans.append({
            "kind": "implicit",
            "match_start": block_start,
            "match_end": block_end,
            "content_start": block_start,
            "content_end": block_end,
        })

    # If no forms found, return original text
    if not spans:
        return raw_text, []

    # Sort spans in document order
    spans.sort(key=lambda s: s["match_start"])

    # Build cleaned text and assign FORM_1, FORM_2, ...
    cleaned_parts = []
    forms = []
    cursor = 0
    form_counter = 1

    for span in spans:
        start = span["match_start"]
        end = span["match_end"]

        # Keep text before this form
        if cursor < start:
            cleaned_parts.append(raw_text[cursor:start])

        form_id = f"FORM_{form_counter}"
        content_start = span["content_start"]
        content_end = span["content_end"]
        markdown = raw_text[content_start:content_end].strip()

        forms.append({
            "form_id": form_id,
            "markdown": markdown,
            "char_start": start,  # span in original raw_text
            "char_end": end,
        })

        # Insert placeholder in cleaned text
        cleaned_parts.append(f"\n[{form_id}]\n")

        cursor = end
        form_counter += 1

    # Add trailing text after last form
    if cursor < len(raw_text):
        cleaned_parts.append(raw_text[cursor:])

    cleaned_text = "".join(cleaned_parts)

    return cleaned_text, forms



def clean_text(raw_text: str, position_to_page: Optional[Dict[int, int]] = None, skip_toc_detection: bool = False) -> Tuple[str, Dict[int, int]]:
    """
    Pre-process and clean the raw text.
    
    Removes:
    - Table of Contents (everything before "Act No." or first "Section 1") - only if skip_toc_detection=False
    - Repetitive headers/footers like "THE PAKISTAN CODE"
    - Page markers (but tracks page numbers if position_to_page not provided)
    
    Args:
        raw_text: Raw extracted text
        position_to_page: Optional pre-existing position to page mapping.
                         If None, will be built from page markers in the text.
        skip_toc_detection: If True, skip TOC detection logic (use when processing section text, not full document)
        
    Returns:
        Tuple of (cleaned_text, position_to_page_dict)
    """
    lines = raw_text.split('\n')
    cleaned_lines = []
    
    position_to_page = {}  # Always return empty dict
    
    # Patterns
    page_pattern = re.compile(r'Page\s+(\d+)\s+of\s+\d+', re.IGNORECASE)
    page_marker_pattern = re.compile(r'^```\s*$')
    toc_end_pattern = re.compile(r'Act\s+No\.|^\s*\*\*?\s*1\.', re.IGNORECASE)
    pakistan_code_pattern = re.compile(r'THE\s+PAKISTAN\s+CODE', re.IGNORECASE)
    
    # Track if we've found the start of actual content
    # Skip TOC detection if skip_toc_detection=True (for section text)
    found_content_start = True if skip_toc_detection else False
    in_toc = False if skip_toc_detection else True
    
    for line in lines:
        # Check for page number markers
        page_match = page_pattern.search(line)
        if page_match:
            # if build_position_mapping:
            #     current_page = int(page_match.group(1))
            # Don't add page marker lines to cleaned text
            continue
        
        # Check for page marker (```)
        if page_marker_pattern.match(line.strip()):
            continue
        
        # Remove "THE PAKISTAN CODE" headers
        if pakistan_code_pattern.search(line):
            continue
        
        # Detect end of TOC
        if in_toc and toc_end_pattern.search(line):
            in_toc = False
            found_content_start = True
        
        # Skip TOC content (only if TOC detection is enabled)
        if not skip_toc_detection and in_toc and not found_content_start:
            # Check if this line looks like TOC (contains "CONTENTS" or is a list item)
            if re.search(r'CONTENTS|^\s*\d+\.', line, re.IGNORECASE):
                continue
        
        # Add line to cleaned text
        cleaned_lines.append(line)
        
    
    cleaned_text = '\n'.join(cleaned_lines)

    return cleaned_text, position_to_page


def clean_markdown_artifacts(text: str) -> str:
    """
    Remove markdown artifacts from text.
    
    Args:
        text: Text with markdown artifacts
        
    Returns:
        Cleaned text
    """
    # Remove bold markers
    text = re.sub(r'\*\*', '', text)
    # Remove other markdown artifacts
    text = re.sub(r'```', '', text)
    return text


def remove_separators_from_text(text: str) -> str:
    """
    Remove separator lines from text.
    Separators are lines that contain only dashes (----) with no other text.
    
    Args:
        text: Text that may contain separator lines
        
    Returns:
        Text with separator lines removed
    """
    if not text:
        return text
    
    lines = text.split('\n')
    cleaned_lines = []
    
    # Pattern to match separator lines (only dashes, underscores, equals, dots with optional spaces)
    # Must be at least 3 characters and contain only separator characters
    separator_pattern = re.compile(r'^[\s]*[-_=\.]{3,}[\s]*$')
    
    for line in lines:
        # Check if this line is a separator
        if separator_pattern.match(line.strip()):
            # Skip separator lines
            continue
        cleaned_lines.append(line)

    return '\n'.join(cleaned_lines)


def normalize_schedule_section_text(text: str) -> str:
    """
    Normalize SCHEDULE section text - preserve numbered list items and content.
    
    This function is specifically for SCHEDULE sections to preserve numbered list items
    like "5. Galvanized plain sheets." which would otherwise be removed by clean_text.
    
    Args:
        text: SCHEDULE section text
        
    Returns:
        Normalized SCHEDULE text with preserved content
    """
    if not text:
        return text
    
    
    lines = text.split('\n')
    cleaned_lines = []
    
    # Pattern for page markers
    page_pattern = re.compile(r'Page\s+(\d+)\s+of\s+\d+', re.IGNORECASE)
    page_marker_pattern = re.compile(r'^```\s*$')
    pakistan_code_pattern = re.compile(r'THE\s+PAKISTAN\s+CODE', re.IGNORECASE)
    
    for line in lines:
        # Remove page number markers
        if page_pattern.search(line):
            continue
        
        # Remove page marker (```)
        if page_marker_pattern.match(line.strip()):
            continue
        
        # Remove "THE PAKISTAN CODE" headers
        if pakistan_code_pattern.search(line):
            continue
        
        # DO NOT remove numbered list items (like "5. Galvanized plain sheets.")
        # This is the key difference from clean_text - we preserve all content
        
        # Add line to cleaned text
        cleaned_lines.append(line)
    
    cleaned_text = '\n'.join(cleaned_lines)
    
    # Remove SCHEDULE headings (all formats: SCHEDULE, THE FOURTH SCHEDULE, SCHEDULE I, etc.)
    # Pattern: SCHEDULE, THE FOURTH SCHEDULE, FOURTH SCHEDULE, SCHEDULE I, SCHEDULE 1, etc.
    cleaned_text = re.sub(
        r'^\s*(?:THE\s+)?(?:[A-Z]+\s+)?SCHEDULE\s*(?:[IVX]+|\d+)?\s*$',
        '',
        cleaned_text,
        flags=re.IGNORECASE | re.MULTILINE
    )
    
    # Remove SCHEDULE subsections/headings (with or without number prefixes)
    # These are lines that look like subsection titles (all caps or title case, not content)
    lines = cleaned_text.split('\n')
    cleaned_lines = []
    i = 0
    while i < len(lines):
        line = lines[i]
        line_stripped = line.strip()
        
        if not line_stripped:
            cleaned_lines.append(line)
            i += 1
            continue
        
        # Check if this is a SCHEDULE subsection heading
        # Criteria: all uppercase or title case, not starting with section markers, not content
        is_schedule_subsection = False
        
        if (not line_stripped.startswith('**') and
            not re.match(r'^\d+[\.\)]', line_stripped) and  # Not section number
            not re.match(r'^\([a-z0-9]', line_stripped) and  # Not subsection marker
            not re.match(r'^[a-z]', line_stripped) and  # Not starting with lowercase
            len(line_stripped) > 2):  # Has meaningful content
            
            # Check if it's all uppercase or title case
            is_all_caps = line_stripped.isupper() and len(line_stripped) > 3
            is_title_case = (
                line_stripped[0].isupper() and
                not line_stripped[1:].islower() and
                len(line_stripped) > 3
            )
            
            # Check if it looks like content (sentence-like)
            looks_like_content = (
                re.match(r'^[a-z]', line_stripped) or
                line_stripped.count('.') > 2 or
                line_stripped.count(',') > 3
            )
            
            if (is_all_caps or is_title_case) and not looks_like_content:
                # This could be a SCHEDULE subsection (with or without number prefix)
                # Check if it has a number prefix (SCHEDULE subsection pattern: 1. Title, I. Title, etc.)
                has_number_prefix = re.match(r'^(\d+|[IVX]+)\.?[—\-\.\s]*\s*', line_stripped, re.IGNORECASE)
                
                # Remove if:
                # - It's all caps (like "FORM OF NOTICE") - SCHEDULE subsection heading
                # - It has a number prefix (like "1. FORM OF NOTICE") - SCHEDULE subsection
                # - It's title case and not content (like "Form of Notice") - SCHEDULE subsection
                if is_all_caps or has_number_prefix or (is_title_case and not has_number_prefix):
                    is_schedule_subsection = True
        
        if is_schedule_subsection:
            # Skip this line and check if title continues on next lines
            i += 1
            while i < len(lines):
                next_line = lines[i].strip()
                if not next_line:
                    i += 1
                    continue
                
                # Check if next line is continuation of heading
                is_continuation = (
                    next_line.isupper() and len(next_line) > 3 and
                    not re.match(r'^\d+[\.\)]', next_line) and
                    not re.match(r'^\([a-z0-9]', next_line) and
                    not re.match(r'^[a-z]', next_line) and
                    not re.match(r'^\*\*', next_line)
                )
                
                if is_continuation:
                    i += 1
                    continue
                else:
                    break
            continue
        
        cleaned_lines.append(line)
        i += 1
    
    cleaned_text = '\n'.join(cleaned_lines)
    cleaned_text = re.sub(r'\n{3,}', '\n\n', cleaned_text)  # Remove excessive newlines
    
    # Fix broken words
    cleaned_text = fix_broken_words(cleaned_text)
    
    # Remove markdown artifacts
    cleaned_text = clean_markdown_artifacts(cleaned_text)
    
    # Remove separator lines (----)
    cleaned_text = remove_separators_from_text(cleaned_text)
    
    # # Restore placeholders
    # for protected, original in placeholder_map.items():
    #     cleaned_text = cleaned_text.replace(protected, original)
    
    return cleaned_text


def remove_chapters_articles_parts_headings(text: str) -> str:
    """
    Removes chapters, articles, parts, and headings from text.
    
    Handles various formats:
    - CHAPTER VI / CHAPTER 5 (with or without title on same/next line)
    - PART I / PART 1 (with or without title on same/next line)
    - ARTICLE III / ARTICLE 3 (with or without title on same/next line)
    - A.—Application (single letter headings)
    - Various separators: spaces, periods, em dashes, double em dashes
    - Optional markdown headers: 0-4 # characters followed by optional space (e.g., # CHAPTER VI, ## PART I, ### ARTICLE III)
    
    Args:
        text: Text that may contain chapters, articles, parts, or headings
        
    Returns:
        Text with chapters, articles, parts, and headings removed
    """
    if not text:
        return text
    
    lines = text.split('\n')
    cleaned_lines = []
    
    # Pattern for Roman numerals (I, II, III, IV, V, VI, VII, VIII, IX, X, etc.)
    roman_numeral = r'[IVX]+'
    # Pattern for Arabic numerals
    arabic_numeral = r'\d+'
    # Pattern for single letter (A, B, C, etc.)
    single_letter = r'[A-Z]'
    
    # Combined pattern for numbers (Roman or Arabic)
    number_pattern = f'({roman_numeral}|{arabic_numeral})'
    
    # Pattern for CHAPTER/PART/ARTICLE with various separators and optional title
    # Handles: CHAPTER VI, CHAPTER 5, PART I, PART 1, ARTICLE III, ARTICLE 3
    # With optional markdown headers: 0-4 # characters followed by optional space
    # With optional separators: spaces, periods, em dashes (—), double em dashes (––), regular dashes (-)
    # With optional title on same line or next line
    chapter_part_article_pattern = re.compile(
        r'^\s*#{0,4}\s*(CHAPTER|PART|ARTICLE)\s+' + number_pattern + r'\.?\s*[—\-\.\s]*\s*([A-Z][^\n]*)?\s*$',
        re.IGNORECASE | re.MULTILINE
    )
    
    # Pattern for single letter headings like "A.—Application"
    # With optional markdown headers: 0-4 # characters followed by optional space
    single_letter_pattern = re.compile(
        r'^\s*#{0,4}\s*' + single_letter + r'\.?\s*[—\-\.\s]+\s*([A-Z][^\n]*)?\s*$',
        re.MULTILINE
    )
    
    i = 0
    while i < len(lines):
        # if re.fullmatch(r'\[(FORM|TABLE)_\d+\]', line_stripped):
        #     cleaned_lines.append(line)
        #     i += 1
        #     continue
        line = lines[i]
        line_stripped = line.strip()
        if re.search(r'\[(?:FORM|TABLE)_\d+\]$', line_stripped) or re.search(r'__PLACEHOLDER_(?:FORM|TABLE)_\d+__$', line_stripped):
            cleaned_lines.append(line)
            i += 1
            continue
        
        # Check if this line matches CHAPTER/PART/ARTICLE pattern
        if chapter_part_article_pattern.match(line_stripped):
            # Check if title is on the same line (indicated by .— after the number)
            # Pattern: CHAPTER 1.—Title or PART I.—Title or ARTICLE III.—Title
            has_title_on_same_line = re.search(r'\.\s*—', line_stripped) is not None
            
            # Skip the CHAPTER/PART/ARTICLE line
            i += 1
            
            # Only check subsequent lines for title if title is NOT on the same line
            if not has_title_on_same_line:
                # Check subsequent lines for title (may span multiple lines)
                # Titles are typically all uppercase or title case, and don't start with section numbers
                while i < len(lines):
                    next_line = lines[i].strip()
                    # Skip empty lines (they're part of the title spacing)
                    if not next_line:
                        i += 1
                        continue
                    
                    # Check if this line looks like a title continuation
                    # Title lines characteristics:
                    # - All uppercase (typical for chapter/part/article titles)
                    # - Title case (first letter uppercase, rest mixed)
                    # - Not starting with section numbers (1., 2., etc.)
                    # - Not starting with subsection markers ((1), (a), etc.)
                    # - Not starting with lowercase (regular content)
                    
                    # Check if it's all uppercase (very likely a title)
                    is_all_uppercase = next_line.isupper() and len(next_line) > 1
                    
                    # Check if it's title case (starts with capital, rest mixed case)
                    is_title_case = (
                        next_line[0].isupper() and 
                        not re.match(r'^\d+[\.\)]', next_line) and  # Not section number
                        not re.match(r'^\([a-z0-9]', next_line) and  # Not subsection marker
                        not re.match(r'^[a-z]', next_line)  # Not starting with lowercase
                    )
                    
                    # Check if it's NOT regular content
                    is_not_content = not (
                        re.match(r'^[a-z]', next_line) or  # Starts with lowercase
                        re.match(r'^\([a-z0-9]', next_line) or  # Starts with subsection like "(a)" or "(1)"
                        re.match(r'^\d+[\.\)]', next_line) or  # Starts with section number
                        re.match(r'^\*\*', next_line)  # Starts with bold markers (next section)
                    )
                    
                    # If it looks like a title line, skip it
                    if (is_all_uppercase or (is_title_case and is_not_content)):
                        # This is part of the title, skip it
                        i += 1
                        continue
                    else:
                        # This is content, stop skipping
                        break
            continue
        
        # Check if this line matches single letter heading pattern
        if single_letter_pattern.match(line_stripped):
            # Check if title is on the same line (indicated by .— after the letter)
            # Pattern: A.—Title or B.—Title
            has_title_on_same_line = re.search(r'\.\s*—', line_stripped) is not None
            
            # Skip the single letter heading line
            i += 1
            
            # Only check subsequent lines for title if title is NOT on the same line
            if not has_title_on_same_line:
                # Check subsequent lines for title (may span multiple lines)
                # Same logic as CHAPTER/PART/ARTICLE for multi-line titles
                while i < len(lines):
                    next_line = lines[i].strip()
                    # Skip empty lines (they're part of the title spacing)
                    if not next_line:
                        i += 1
                        continue
                    
                    # Check if this line looks like a title continuation
                    # Check if it's all uppercase (very likely a title)
                    is_all_uppercase = next_line.isupper() and len(next_line) > 1
                    
                    # Check if it's title case (starts with capital, rest mixed case)
                    is_title_case = (
                        next_line[0].isupper() and 
                        not re.match(r'^\d+[\.\)]', next_line) and  # Not section number
                        not re.match(r'^\([a-z0-9]', next_line) and  # Not subsection marker
                        not re.match(r'^[a-z]', next_line)  # Not starting with lowercase
                    )
                    
                    # Check if it's NOT regular content
                    is_not_content = not (
                        re.match(r'^[a-z]', next_line) or  # Starts with lowercase
                        re.match(r'^\([a-z0-9]', next_line) or  # Starts with subsection like "(a)" or "(1)"
                        re.match(r'^\d+[\.\)]', next_line) or  # Starts with section number
                        re.match(r'^\*\*', next_line)  # Starts with bold markers (next section)
                    )
                    
                    # If it looks like a title line, skip it
                    if (is_all_uppercase or (is_title_case and is_not_content)):
                        # This is part of the title, skip it
                        i += 1
                        continue
                    else:
                        # This is content, stop skipping
                        break
            continue
        
        # Keep the line
        cleaned_lines.append(line)

        i += 1
    
    # Also remove patterns that might span multiple lines or appear in the middle of text
    # Use regex to remove remaining patterns
    text_result = '\n'.join(cleaned_lines)
    
    # Remove CHAPTER patterns (handles all variations, including markdown headers with 0-4 #)
    text_result = re.sub(
        r'^\s*#{0,4}\s*CHAPTER\s+([IVX]+|\d+)\.?\s*[—\-\.\s]*\s*([A-Z][^\n]*)?\s*$',
        '',
        text_result,
        flags=re.IGNORECASE | re.MULTILINE
    )
    
    # Remove PART patterns (handles all variations, including markdown headers with 0-4 #)
    text_result = re.sub(
        r'^\s*#{0,4}\s*PART\s+([IVX]+|\d+)\.?\s*[—\-\.\s]*\s*([A-Z][^\n]*)?\s*$',
        '',
        text_result,
        flags=re.IGNORECASE | re.MULTILINE
    )
    
    # Remove ARTICLE patterns (handles all variations, including markdown headers with 0-4 #)
    text_result = re.sub(
        r'^\s*#{0,4}\s*ARTICLE\s+([IVX]+|\d+)\.?\s*[—\-\.\s]*\s*([A-Z][^\n]*)?\s*$',
        '',
        text_result,
        flags=re.IGNORECASE | re.MULTILINE
    )
    
    # Remove single letter headings (A.—, B.—, etc., including markdown headers with 0-4 #)
    text_result = re.sub(
        r'^\s*#{0,4}\s*[A-Z]\.?\s*[—\-\.\s]+\s*([A-Z][^\n]*)?\s*$',
        '',
        text_result,
        flags=re.MULTILINE
    )
    
    # Remove SCHEDULE patterns (all formats from extract_schedule_sections)
    # Pattern: SCHEDULE, THE FOURTH SCHEDULE, FOURTH SCHEDULE, SCHEDULE I, SCHEDULE 1, etc.
    text_result = re.sub(
        r'^\s*(?:THE\s+)?(?:[A-Z]+\s+)?SCHEDULE\s*(?:[IVX]+|\d+)?\s*$',
        '',
        text_result,
        flags=re.IGNORECASE | re.MULTILINE
    )
    
    # Remove SCHEDULE subsections (with or without number prefixes)
    # Pattern: 1. Title, 1 Title, 1.-- Title, I Title, I. Title, I.-- Title, or just Title
    # These are lines that look like subsection titles (all caps or title case, not content)
    lines = text_result.split('\n')
    cleaned_lines = []
    i = 0
    while i < len(lines):
        # if re.fullmatch(r'\[(FORM|TABLE)_\d+\]', line_stripped):
        #     cleaned_lines.append(line)
        #     i += 1
        #     continue
        line = lines[i]
        line_stripped = line.strip()
        if re.search(r'\[(?:FORM|TABLE)_\d+\]$', line_stripped) or re.search(r'__PLACEHOLDER_(?:FORM|TABLE)_\d+__$', line_stripped):
            cleaned_lines.append(line)
            i += 1
            continue
        
        if not line_stripped:
            cleaned_lines.append(line)
            i += 1
            continue
        
        # Check if this is a standalone heading (like "FORM OF NOTICE")
        # This includes headings that appear independently (not as SCHEDULE subsections)
        # Criteria: all uppercase or title case, not starting with section markers, not content
        # BE CONSERVATIVE: Only remove lines that are clearly headings, not content
        is_standalone_heading = False
        
        if (not line_stripped.startswith('**') and
            not re.fullmatch(r'\[(FORM|TABLE)_\d+\]', line_stripped) and
            not re.match(r'^\d+[\.\)]', line_stripped) and  # Not section number
            not re.match(r'^\([a-z0-9]', line_stripped) and  # Not subsection marker
            not re.match(r'^[a-z]', line_stripped) and  # Not starting with lowercase
            len(line_stripped) > 2):  # Has meaningful content
            
            # Check if it's all uppercase or title case
            is_all_caps = line_stripped.isupper() and len(line_stripped) > 3
            is_title_case = (
                line_stripped[0].isupper() and
                not line_stripped[1:].islower() and
                len(line_stripped) > 3
            )
            
            # Check if it looks like content (sentence-like)
            # Be more conservative: if it has ANY punctuation or is long, it's likely content
            looks_like_content = (
                re.match(r'^[a-z]', line_stripped) or  # Starts with lowercase
                line_stripped.count('.') > 1 or  # Has more than 1 period (sentence-like)
                line_stripped.count(',') > 1 or  # Has more than 1 comma (sentence-like)
                line_stripped.count(';') > 0 or  # Has semicolon (sentence-like)
                line_stripped.count(':') > 0 or  # Has colon (could be content)
                len(line_stripped) > 100 or  # Long line is likely content, not heading
                re.search(r'\b(that|which|when|where|provided|shall|may|must|if|unless)\b', line_stripped, re.IGNORECASE)  # Contains common content words
            )
            
            # Check if it has a number prefix (SCHEDULE subsection pattern: 1. Title, I. Title, etc.)
            has_number_prefix = re.match(r'^(\d+|[IVX]+)\.?[—\-\.\s]*\s*', line_stripped, re.IGNORECASE)
            
            # Only remove if it's clearly a heading:
            # 1. All caps (like "FORM OF NOTICE") - but must be short and no punctuation
            # 2. Has number prefix (like "1. FORM OF NOTICE") - SCHEDULE subsection
            # 3. Title case but short, no punctuation, and no content words
            if not looks_like_content:
                if is_all_caps:
                    # All caps: only remove if it's short (likely a heading)
                    # Headings are typically short (less than 50 chars) and don't have much punctuation
                    if len(line_stripped) < 50 and line_stripped.count(',') == 0:
                        is_standalone_heading = True
                elif has_number_prefix:
                    # Has number prefix: likely a SCHEDULE subsection
                    is_standalone_heading = True
                elif is_title_case:
                    # Title case: only remove if it's very short and looks like a heading
                    # Headings are typically short, no punctuation, no content words
                    if (len(line_stripped) < 50 and 
                        line_stripped.count(',') == 0 and 
                        line_stripped.count('.') == 0 and
                        not re.search(r'\b(that|which|when|where|provided|shall|may|must|if|unless)\b', line_stripped, re.IGNORECASE)):
                        is_standalone_heading = True
        
        if is_standalone_heading:
            # Skip this line and check if title continues on next lines
            i += 1
            while i < len(lines):
                next_line = lines[i].strip()
                if not next_line:
                    i += 1
                    continue
                
                # Check if next line is continuation of heading
                is_continuation = (
                    next_line.isupper() and len(next_line) > 3 and
                    not re.match(r'^\d+[\.\)]', next_line) and
                    not re.match(r'^\([a-z0-9]', next_line) and
                    not re.match(r'^[a-z]', next_line) and
                    not re.match(r'^\*\*', next_line)
                )
                
                if is_continuation:
                    i += 1
                    continue
                else:
                    break
            continue
        
        cleaned_lines.append(line)
        i += 1
    
    text_result = '\n'.join(cleaned_lines)
    
    # Clean up multiple consecutive newlines
    text_result = re.sub(r'\n{3,}', '\n\n', text_result)
    
    return text_result.strip()




def fix_broken_words(text: str) -> str:
    """
    Fix words broken across lines (e.g., "punish-\nment" -> "punishment").
    
    Only fixes words with lowercase/word characters to avoid merging things like
    "U.S.-\nPakistan" incorrectly.
    
    Args:
        text: Text with potentially broken words
        
    Returns:
        Text with broken words fixed
    """
    # Pattern to match: word character(s) + hyphen + newline + word character(s)
    # Only merge if both parts are lowercase (to avoid merging "U.S.-\nPakistan" or "Section-\n1")
    
    # Match lowercase letters/word chars before hyphen, then newline, then lowercase letters/word chars after
    pattern = re.compile(
        r'([a-z][a-z0-9]*)-(\s*)\n([a-z][a-z0-9]*)',
        re.IGNORECASE
    )
    
    def replace_broken_word(match):
        before = match.group(1)
        whitespace = match.group(2)
        after = match.group(3)
        
        # Only merge if both parts start with lowercase letters
        # This prevents merging "U.S." or "Section" type patterns
        if before and after:
            if before[0].islower() and after[0].islower():
                return before + after
        return match.group(0)  # Return original if conditions not met
    
    text = pattern.sub(replace_broken_word, text)
    
    return text


def normalize_for_parent(text: str) -> str:
    """
    Normalize text for parent chunks - preserve visual structure.
    
    Goal: Clean the text but preserve the visual structure (paragraphs and lists) for the LLM.
    
    Args:
        text: Raw text
        
    Returns:
        Normalized text with preserved structure
    """
    # Protect placeholders before removing forms/tables
    # Placeholders like [FORM_1] and [TABLE_1] should be preserved
    placeholder_map = {}
    placeholder_counter = 0
    
    # Protect [FORM_i] placeholders
    def protect_form_placeholder(match):
        nonlocal placeholder_counter
        placeholder = match.group(0)
        protected = f"__PLACEHOLDER_FORM_{placeholder_counter}__"
        placeholder_map[protected] = placeholder
        placeholder_counter += 1
        return protected
    
    # Protect [TABLE_i] placeholders
    def protect_table_placeholder(match):
        nonlocal placeholder_counter
        placeholder = match.group(0)
        protected = f"__PLACEHOLDER_TABLE_{placeholder_counter}__"
        placeholder_map[protected] = placeholder
        placeholder_counter += 1
        return protected
    
    # Protect placeholders before removing forms/tables
    text = re.sub(r"\[FORM_\d+\]", protect_form_placeholder, text)
    text = re.sub(r"\[TABLE_\d+\]", protect_table_placeholder, text)
    
    # # Remove forms first, then tables (using same patterns as extraction)
    # # This removes actual form/table content, not placeholders
    # text = remove_forms_from_text(text)
    # text = remove_tables_from_text(text)
    
    # Restore placeholders
    for protected, original in placeholder_map.items():
        text = text.replace(protected, original)
    
    # Remove underscores that appear 5 or more times consecutively
    text = re.sub(r'_{5,}', '', text)
    
    # Remove lines with long underscores (e.g., " _________________________________________________________________________________")
    text = re.sub(r'^[_\s]{20,}$', '', text, flags=re.MULTILINE)
    
    # Remove RGN dates (patterns like "RGN Date: 05-09-2024", "RGN 123/2024", etc.)
    text = re.sub(r'\bRGN\s+Date:\s*\d{2}-\d{2}-\d{4}\b', '', text, flags=re.IGNORECASE)
    text = re.sub(r'\bRGN\s+\d+/\d+\b', '', text, flags=re.IGNORECASE)
    
    # Replace 3 or more consecutive newlines with exactly 2 newlines
    text = re.sub(r'\n{3,}', '\n\n', text)
    
    # Ensure bullet points like (a) or (i) stay on their own lines
    # Add newline before bullet points if they're not already on their own line
    # Pattern: text immediately before (a), (b), (i), (ii), etc. without preceding newline
    # Match lowercase letter bullets: (a), (b), (c), etc. - must be single letter
    text = re.sub(r'([^\n])(\s*\([a-z]\)\s)', r'\1\n\2', text, flags=re.IGNORECASE)
    # Match roman numeral bullets: (i), (ii), (iii), (iv), etc. - must be valid roman numerals
    text = re.sub(r'([^\n])(\s*\([ivxlcdm]+\)\s)', r'\1\n\2', text, flags=re.IGNORECASE)
    
    # Remove leading/trailing whitespace from each line
    lines = text.split('\n')
    cleaned_lines = [line.strip() for line in lines]
    text = '\n'.join(cleaned_lines)
    
    # Remove leading/trailing whitespace from entire text
    text = text.strip()
    
    return text


def remove_footnotes_from_section_text(
    text: str, 
    raw_text: str, 
    start_pos: int, 
    end_pos: int, 
    position_to_page: Optional[Dict[int, int]] = None,
    all_footnotes: Optional[List[Dict[str, str]]] = None
) -> str:
    """
    Remove footnote text from section text by comparing with all_footnotes dictionary.
    
    This function:
    1. Gets page numbers for the section
    2. Filters footnotes for those pages from all_footnotes
    3. Finds superscript markers in the section text
    4. For each marker, compares the following text with footnote text
    5. If text matches → it's the footnote itself → remove it
    6. If text doesn't match → it's a reference marker → keep it
    
    Args:
        text: Section text (may be normalized, used for reference)
        raw_text: Raw text to search for footnotes
        start_pos: Start position of section in raw_text
        end_pos: End position of section in raw_text
        position_to_page: Dictionary mapping character position to page number
        all_footnotes: List of all footnote dictionaries with keys: marker, text, page_number
        
    Returns:
        Text with footnote text removed (but reference markers kept)
    """
   
    if start_pos == -1 or end_pos == -1:
        return text
    
    if start_pos >= len(raw_text) or end_pos > len(raw_text):
        return text
    
    # If no footnotes provided, return text as-is
    if not all_footnotes:
        return text
    
    # Protect placeholders before processing
    placeholder_map = {}
    placeholder_counter = 0
    
    def protect_form_placeholder(match):
        nonlocal placeholder_counter
        placeholder = match.group(0)
        protected = f"__PLACEHOLDER_FORM_{placeholder_counter}__"
        placeholder_map[protected] = placeholder
        placeholder_counter += 1
        return protected
    
    def protect_table_placeholder(match):
        nonlocal placeholder_counter
        placeholder = match.group(0)
        protected = f"__PLACEHOLDER_TABLE_{placeholder_counter}__"
        placeholder_map[protected] = placeholder
        placeholder_counter += 1
        return protected
    
    # Protect placeholders in the text parameter (which may have placeholders)
    text_with_protected_placeholders = re.sub(r"\[FORM_\d+\]", protect_form_placeholder, text)
    text_with_protected_placeholders = re.sub(r"\[TABLE_\d+\]", protect_table_placeholder, text_with_protected_placeholders)
    
    # Get the section text span from raw_text (for footnote detection)
    section_text_span = raw_text[start_pos:end_pos]
    
    # Get page numbers for this section
    section_pages = []
    if position_to_page:
        section_pages = get_pages_for_span(position_to_page, start_pos, end_pos)
    
    if not section_pages:
        # No page numbers found, return text as-is
        return text
    
    # Filter footnotes for pages in this section
    section_footnotes = []
    for footnote in all_footnotes:
        footnote_page = footnote.get('page_number')
        if footnote_page is not None:
            try:
                footnote_page_int = int(footnote_page) if not isinstance(footnote_page, int) else footnote_page
                if footnote_page_int in section_pages:
                    section_footnotes.append(footnote)
            except (ValueError, TypeError):
                continue
    
    if not section_footnotes:
        # No footnotes for this section's pages
        return text
    
    # Map Unicode superscripts to regular digits for normalization
    marker_map = {
        '¹': '1', '²': '2', '³': '3', '⁴': '4', '⁵': '5',
        '⁶': '6', '⁷': '7', '⁸': '8', '⁹': '9', '⁰': '0'
    }
    
    # Pattern to match Unicode superscript digits (¹, ², ³, ⁴, ⁵, ⁶, ⁷, ⁸, ⁹, ⁰)
    superscript_pattern = re.compile(r'([¹²³⁴⁵⁶⁷⁸⁹⁰]+)')
    # Subsection-shaped lines (footnote continuations + orphan cleanup); must be defined here —
    # not inside the per-marker loop — or it is unset when no marker path reaches that block.
    subsection_pattern = re.compile(
        r'^[¹²³⁴⁵⁶⁷⁸⁹⁰]*\[?\s*(?:\([ivx]+\)|[ivx]+\.|\([a-z]\)|[a-z]\.|\(\d+\)|\d+\.)',
        re.IGNORECASE,
    )

    # Split text into lines for processing
    lines = section_text_span.split('\n')
    lines_to_remove = set()  # Track line indices to remove
    
    # Calculate cumulative character positions for each line start in section_text_span
    line_start_positions = []
    current_pos = 0
    for line in lines:
        line_start_positions.append(current_pos)
        current_pos += len(line) + 1  # +1 for newline character
    
    # Process each line
    line_idx = 0
    while line_idx < len(lines):
        line = lines[line_idx]
        line_stripped = line.strip()
        
        # Skip empty lines
        if not line_stripped:
            line_idx += 1
            continue
                
        # Find all superscript markers in this line
        matches = list(superscript_pattern.finditer(line_stripped))
        if not matches:
            line_idx += 1
            continue
        
        # Process each superscript marker found in the line
        for match in matches:
            marker_unicode = match.group(1)
            marker_start_in_stripped = match.start()
            marker_end_in_stripped = match.end()
            marker_page = None
            
            # Normalize marker for comparison
            marker_key = ''.join(marker_map.get(char, char) for char in marker_unicode)
            
            # Get text after the marker on the current line
            text_after_marker_on_line = line_stripped[marker_end_in_stripped:].strip()
            
            # Find matching footnotes for this marker and page
            matching_footnote = None
            for footnote in section_footnotes:
                footnote_marker = str(footnote.get('marker', ''))
                footnote_text = footnote.get('text', '').strip()
                footnote_page = footnote.get('page_number')
                
                # Normalize footnote marker for comparison
                footnote_marker_normalized = ''.join(marker_map.get(char, char) for char in footnote_marker)
                
                # Check if markers match
                if footnote_marker_normalized != marker_key:
                            continue
                        
                # Check if page matches (if we have page info)
                if footnote_page is not None and position_to_page:
                    # Calculate marker position in raw_text
                    leading_whitespace = len(line) - len(line.lstrip())
                    marker_pos_in_line = leading_whitespace + marker_start_in_stripped
                    marker_pos_in_section = line_start_positions[line_idx] + marker_pos_in_line
                    marker_pos_in_raw = start_pos + marker_pos_in_section
                    
                    marker_page = position_to_page.get(marker_pos_in_raw)
                    if marker_page is not None:
                        try:
                            footnote_page_int = int(footnote_page) if not isinstance(footnote_page, int) else footnote_page
                            marker_page_int = int(marker_page) if not isinstance(marker_page, int) else marker_page
                            if footnote_page_int != marker_page_int:
                                continue
                        except (ValueError, TypeError):
                            pass
                
                # Found a matching footnote - store it for multi-line comparison
                matching_footnote = footnote
                break
                    
            # If no matching footnote found, continue to next marker
            if not matching_footnote:
                continue
                        
            # Now collect multi-line text starting from this marker
            # Collect all text after the marker until the next marker or end of section
            collected_lines = []
            collected_text_parts = []
            
            # Start with text after marker on current line
            if text_after_marker_on_line:
                collected_text_parts.append(text_after_marker_on_line)
                collected_lines.append(line_idx)
            
            # Continue collecting subsequent lines until we find:
            # 1. Next superscript marker (new footnote)
            # 2. Section boundary (next section header)
            # 3. Separator line (------) - content after separator should be preserved as section content
            # 4. End of section
            next_line_idx = line_idx + 1
            separator_pattern = re.compile(r'^[\s]*[-_=\.]{3,}[\s]*$')  # Pattern for separator lines
            # Pattern for page markers (e.g., "Page 11 of 14")
            page_marker_pattern = re.compile(r'Page\s+\d+\s+of\s+\d+', re.IGNORECASE)
            
            # Check if we're already past a separator (marker appears after separator)
            # In this case, be more conservative - only collect if it's clearly a footnote
            past_separator = False
            for check_idx in range(line_idx - 1, -1, -1):
                check_line = lines[check_idx].strip()
                if separator_pattern.match(check_line):
                    past_separator = True
                    break
                # If we hit a non-empty line that's not a separator, we haven't passed a separator yet
                if check_line and not separator_pattern.match(check_line):
                    break
            
            while next_line_idx < len(lines):
                next_line = lines[next_line_idx]
                next_line_stripped = next_line.strip()
                
                # Check if next line is a separator
                if separator_pattern.match(next_line_stripped):
                    # Found separator - stop collecting
                    # Content after separator (like subsections) should be preserved as section content
                    # Footnotes appear BEFORE separators, not after
                    found_separator = True
                    break
                
                # Check if next line has a superscript marker (new footnote)
                if next_line_stripped:
                    next_marker_match = superscript_pattern.match(next_line_stripped)
                    if next_marker_match:
                        # Found next marker - stop collecting
                        break
                
                # Check if next line looks like a section header (starts with **)
                if next_line_stripped.startswith('**'):
                    # Found section header - stop collecting
                    break
                
                # Check if next line looks like subsection content (starts with (i), (ii), (a), (1), etc.)
                # Usually this indicates section body content, but footnotes can also have enumerated continuations
                # like "(1) ... (2) ...". In that case, keep collecting if the line exists in matching footnote text.
                if subsection_pattern.match(next_line_stripped):
                    footnote_text_for_check = matching_footnote.get('text', '') if matching_footnote else ''
                    next_line_norm = re.sub(r'\s+', ' ', next_line_stripped).strip().lower()
                    footnote_norm = re.sub(r'\s+', ' ', footnote_text_for_check).strip().lower()
                    if not (next_line_norm and footnote_norm and next_line_norm in footnote_norm):
                        # Not an enumerated continuation of the matched footnote -> treat as section content.
                        break
                
                # Check if we've reached the end of the page
                # Stop collecting when we hit a page marker or move to a different page
                if page_marker_pattern.search(next_line_stripped):
                    # Found page marker - stop collecting (end of page)
                    break
                
                # Check if we've moved to a different page (if we have page tracking)
                if marker_page is not None and position_to_page:
                    # Calculate position of current line in raw_text
                    line_pos_in_section = line_start_positions[next_line_idx] if next_line_idx < len(line_start_positions) else len(section_text_span)
                    line_pos_in_raw = start_pos + line_pos_in_section
                    line_page = position_to_page.get(line_pos_in_raw)
                    
                    # If line is on a different page, stop collecting
                    if line_page is not None and line_page != marker_page:
                        break
                    
                # Add this line to collected text (even if empty, to preserve paragraph structure)
                collected_lines.append(next_line_idx)
                if next_line_stripped:
                    collected_text_parts.append(next_line_stripped)
                else:
                    # Preserve empty lines as newlines in the collected text
                    collected_text_parts.append('')
                
                next_line_idx += 1
            
            # Combine collected text (preserve paragraph breaks)
            # Join all parts, including empty strings to preserve paragraph structure
            collected_text = '\n'.join(collected_text_parts).strip()
            
            # Get footnote text for comparison
            footnote_text = matching_footnote.get('text', '').strip()
            
            # Normalize both texts for comparison
            # Remove extra whitespace but preserve paragraph structure for comparison
            collected_text_normalized = re.sub(r'\s+', ' ', collected_text).strip().lower()
            footnote_text_normalized = re.sub(r'\s+', ' ', footnote_text).strip().lower()
            
            # Also try comparing with preserved newlines (for multi-paragraph footnotes)
            collected_text_with_newlines = collected_text.lower()
            footnote_text_with_newlines = footnote_text.lower()
            
            # Compare texts to decide if this is the footnote itself or a reference marker
            # CRITICAL: Only remove if there's a STRONG match - be very strict to avoid false positives
            # We check multiple conditions, but prioritize exact/strong matches
            # If we're past a separator, be EXTRA conservative - content after separators is usually section content
            is_footnote_text = False
            
            # If we're past a separator, require even stronger evidence
            # Content after separators (like subsections) should be preserved
            if past_separator:
                # Only remove if it's an exact match or very strong match
                # This prevents removing section content that happens to contain footnote-like text
                if footnote_text_normalized and collected_text_normalized:
                    # Require exact match or collected text is very short (likely just the footnote)
                    if collected_text_normalized == footnote_text_normalized:
                        is_footnote_text = True
                    elif len(collected_text_normalized) <= len(footnote_text_normalized) * 1.2:
                        # Collected text is similar length to footnote - might be the footnote
                        # But still require it to start with footnote text
                        if collected_text_normalized.startswith(footnote_text_normalized[:min(30, len(footnote_text_normalized))]):
                            is_footnote_text = True
            
            if not is_footnote_text and footnote_text_normalized:
                # Check 1: Exact match (highest confidence)
                if collected_text_normalized == footnote_text_normalized:
                    is_footnote_text = True
                
                # Check 2: Collected text starts with footnote text (footnote is at the beginning)
                # This is a strong indicator that it's the footnote itself
                elif collected_text_normalized.startswith(footnote_text_normalized):
                    # Additional validation: the match should be substantial
                    # If footnote is very short (< 20 chars), require it to be at the very start
                    if len(footnote_text_normalized) >= 20:
                        is_footnote_text = True
                    elif len(footnote_text_normalized) < 20:
                        # For short footnotes, only match if collected text is also short (likely just the footnote)
                        if len(collected_text_normalized) <= len(footnote_text_normalized) * 1.5:
                            is_footnote_text = True
                
                # Check 3: Footnote text starts with collected text (collected text is a prefix of footnote)
                # This is less common but can happen with partial footnotes
                elif footnote_text_normalized.startswith(collected_text_normalized):
                    # Only match if collected text is substantial (at least 30 chars) to avoid false matches
                    if len(collected_text_normalized) >= 30:
                        is_footnote_text = True
                
                # Check 4: With preserved newlines (for multi-paragraph footnotes)
                if not is_footnote_text:
                    if collected_text_with_newlines == footnote_text_with_newlines:
                        is_footnote_text = True
                    elif collected_text_with_newlines.startswith(footnote_text_with_newlines):
                        if len(footnote_text_with_newlines) >= 20:
                            is_footnote_text = True
                
                # IMPORTANT: Do NOT use "in" operator for substring matching - it's too lenient
                # and causes false positives when footnote text appears as part of section content
                # (e.g., "Federal Government" appearing in "Provided that... Federal Government may...")
            
            # If text matches, this is the footnote itself - mark all collected lines for removal
            if is_footnote_text:
                for idx in collected_lines:
                    lines_to_remove.add(idx)
                # Skip to after the collected lines (next_line_idx is already the next line to process)
                line_idx = next_line_idx - 1  # Set to one before next_line_idx so increment makes it next_line_idx
                break  # Processed this marker, move to next line
            # If text doesn't match, it's a reference marker - keep it and continue
        
        # Move to next line
        line_idx += 1
    
    # Build cleaned text by removing lines marked for removal
    # Secondary cleanup:
    # In some OCR/layout cases, a multi-line footnote continuation (e.g., "(1) ...", "(2) ...")
    # can be split into a later section without the superscript marker line. Remove those orphan
    # continuation lines if they exactly match lines from footnotes on the same page(s).
    footnote_line_norms = set()
    for footnote in section_footnotes:
        foot_text = str(footnote.get('text', '') or '')
        for foot_line in foot_text.split('\n'):
            foot_line_stripped = foot_line.strip()
            if not foot_line_stripped:
                continue
            # Focus on substantial lines and common continuation-item lines.
            if len(foot_line_stripped) >= 18 or subsection_pattern.match(foot_line_stripped):
                norm = re.sub(r'\s+', ' ', foot_line_stripped).strip().lower()
                if norm:
                    footnote_line_norms.add(norm)

    if footnote_line_norms:
        for i, line in enumerate(lines):
            if i in lines_to_remove:
                continue
            ls = line.strip()
            if not ls:
                continue
            norm = re.sub(r'\s+', ' ', ls).strip().lower()
            # Prefer removing lines that look like continuation items; allow exact full-line matches too.
            if norm in footnote_line_norms and (subsection_pattern.match(ls) or len(ls) >= 30):
                lines_to_remove.add(i)

    # Apply the same line removals to the text parameter (which has placeholders)
    # Since placeholders might change line structure, we need to align lines carefully
    text_lines = text_with_protected_placeholders.split('\n')
    
    if len(text_lines) == len(lines):
        # Line counts match - apply removals directly
        cleaned_text_lines = [
            line for i, line in enumerate(text_lines) if i not in lines_to_remove
        ]
        cleaned_text = '\n'.join(cleaned_text_lines)
    else:
        # Line counts differ (e.g. placeholders / OCR). Footnote lines were detected on the raw
        # slice `lines`; remove those contiguous raw blocks from the working copy when possible.
        if text == section_text_span:
            cleaned_text = '\n'.join(
                lines[i] for i in range(len(lines)) if i not in lines_to_remove
            )
        else:
            sorted_rm = sorted(lines_to_remove)
            groups: List[Tuple[int, int]] = []
            gi = 0
            while gi < len(sorted_rm):
                g0 = sorted_rm[gi]
                g1 = g0
                while gi + 1 < len(sorted_rm) and sorted_rm[gi + 1] == sorted_rm[gi] + 1:
                    gi += 1
                    g1 = sorted_rm[gi]
                groups.append((g0, g1))
                gi += 1
            result = text_with_protected_placeholders
            # Remove from the end of the string upward (footnotes usually trail the page).
            for s, e in reversed(groups):
                block = '\n'.join(lines[k] for k in range(s, e + 1))
                if not block.strip():
                    continue
                pos = result.rfind(block)
                if pos == -1:
                    pos = result.find(block)
                if pos == -1:
                    continue
                before, after = result[:pos], result[pos + len(block) :]
                if before.endswith('\n') and after.startswith('\n'):
                    after = after[1:]
                result = before + after
            cleaned_text = result
    
    # Restore placeholders
    for protected, original in placeholder_map.items():
        cleaned_text = cleaned_text.replace(protected, original)
    
    return cleaned_text


def normalize_for_child(text: str) -> str:
    """
    Normalize text for child chunks - create dense, flat string for vector embeddings.
    
    Goal: Create a dense, flat string for Vector Embeddings.
    
    Args:
        text: Raw text
        
    Returns:
        Normalized dense text (all whitespace replaced with single space)
    """
    # 1) Remove full form blocks if any leaked (but preserve placeholders)
    # First, protect placeholders by temporarily replacing them
    placeholder_map = {}
    placeholder_counter = 0
    
    # Protect [FORM_i] placeholders
    def protect_form_placeholder(match):
        nonlocal placeholder_counter
        placeholder = match.group(0)
        protected = f"__PLACEHOLDER_FORM_{placeholder_counter}__"
        placeholder_map[protected] = placeholder
        placeholder_counter += 1
        return protected
    
    # Protect [TABLE_i] placeholders
    def protect_table_placeholder(match):
        nonlocal placeholder_counter
        placeholder = match.group(0)
        protected = f"__PLACEHOLDER_TABLE_{placeholder_counter}__"
        placeholder_map[protected] = placeholder
        placeholder_counter += 1
        return protected
    
    # Protect placeholders before removing forms/tables
    text = re.sub(r"\[FORM_\d+\]", protect_form_placeholder, text)
    text = re.sub(r"\[TABLE_\d+\]", protect_table_placeholder, text)
    
    # # Now remove any remaining form blocks (actual forms, not placeholders)
    # text = remove_forms_from_text(text)
    # text = remove_tables_from_text(text)
    
    # Restore placeholders
    for protected, original in placeholder_map.items():
        text = text.replace(protected, original)

    # 3) Remove explicit page separators if any leaked
    text = text.replace("------", "")

    # existing cleanup continues here...
    text = text.replace("Page **", "Page ")
    # Note: remove_tables_from_text is already called above, no need to call again
    # Tables should already be removed or replaced with placeholders
    # Remove underscores that appear 5 or more times consecutively
    text = re.sub(r'_{5,}', '', text)
    
    # Remove lines with long underscores (e.g., " _________________________________________________________________________________")
    text = re.sub(r'^[_\s]{20,}$', '', text, flags=re.MULTILINE)
    
    # Remove RGN dates (patterns like "RGN Date: 05-09-2024", "RGN 123/2024", etc.)
    text = re.sub(r'\bRGN\s+Date:\s*\d{2}-\d{2}-\d{4}\b', '', text, flags=re.IGNORECASE)
    text = re.sub(r'\bRGN\s+\d+/\d+\b', '', text, flags=re.IGNORECASE)
    
    # Normalize spaces around brackets to ensure consistent matching
    # Remove spaces immediately after [ and before ]
    text = re.sub(r'\[\s+', '[', text)
    text = re.sub(r'\s+\]', ']', text)
    
    # Replace all whitespace characters (newlines, tabs, multiple spaces) with a single space
    text = re.sub(r'\s+', ' ', text)
    
    # Strip leading/trailing whitespace
    text = text.strip()
    
    return text


def extract_schedule_sections(text: str, raw_text: str, position_to_page: Optional[Dict[int, int]] = None, start_search_position: Optional[int] = None) -> List[Dict]:
    """
    Extract SCHEDULE sections from text.
    
    This function:
    1. First finds all actual SCHEDULE sections by matching the word "SCHEDULE" in various formats
    2. Then within each SCHEDULE section, finds subsections using section patterns
    
    SCHEDULE sections can appear in various formats:
    1. SCHEDULE
    2. THE FOURTH SCHEDULE
    3. FOURTH SCHEDULE
    4. SCHEDULE (with subsection on next line)
    5. SCHEDULE I
    6. SCHEDULE 1
    7. SCHEDULE I (with subsection on same/next line)
    8. THE SCHEDULE
    
    Subsections within a SCHEDULE can appear:
    - On the same line as SCHEDULE (e.g., "SCHEDULE I Ad valorem fees")
    - On the next line (e.g., "SCHEDULE\nFORM OF NOTICE")
    - Can be single line or multi-line (e.g., "SCHEDULE\nFORM OF NOTICE\nFOR REGISTRATION")
    
    Subsections can have number prefixes before the title:
    - 1. Title
    - 1 Title
    - 1.-- Title
    - I Title
    - I. Title
    - I.-- Title
    - Title (without number)
    
    Args:
        text: Text to search for SCHEDULE sections
        raw_text: Raw unprocessed text (for finding actual positions)
        position_to_page: Dictionary mapping character position to page number
        start_search_position: Optional position to start searching from (preamble end or second law name end).
                              If None, will be calculated from second law name position.
        
    Returns:
        List of SCHEDULE section dictionaries with:
        - number: "-"
        - title: "SCHEDULE" (if no subsections) or "SCHEDULE-SUBSECTION_NAME" (if subsections exist)
        - text: the schedule text
        - start_pos, end_pos, page_numbers
    """
    schedule_sections = []
    
    # Determine the start search position (only search after preamble/second law name)
    search_start_pos = 0
    if start_search_position is not None:
        search_start_pos = start_search_position
    else:
        # Calculate second law name end position as backup
        # Pattern to match law names (same as in extract_sections)
        law_name_pattern1 = re.compile(
            r'^#\s*([¹²³⁴⁵⁶⁷⁸⁹⁰A-Z][¹²³⁴⁵⁶⁷⁸⁹⁰A-Z\s()]*(?:ACT|ORDINANCE|LAW)[¹²³⁴⁵⁶⁷⁸⁹⁰A-Z\s(),]*)',
            re.MULTILINE | re.IGNORECASE
        )
        law_name_pattern2 = re.compile(
            r'^([¹²³⁴⁵⁶⁷⁸⁹⁰A-Z][¹²³⁴⁵⁶⁷⁸⁹⁰A-Z\s()]*(?:ACT|ORDINANCE|LAW)[¹²³⁴⁵⁶⁷⁸⁹⁰A-Z\s(),]*)',
            re.MULTILINE
        )
        
        law_name_matches1 = list(law_name_pattern1.finditer(text))
        law_name_matches2 = list(law_name_pattern2.finditer(text))
        
        # Combine and sort all matches
        all_law_name_matches = sorted(
            law_name_matches1 + law_name_matches2,
            key=lambda m: m.start()
        )
        
        # Find second occurrence (skip first one which is usually before CONTENTS)
        if len(all_law_name_matches) >= 2:
            search_start_pos = all_law_name_matches[1].end()
        elif len(all_law_name_matches) == 1:
            search_start_pos = all_law_name_matches[0].end()
        else:
            search_start_pos = 0  # If no law name found, search_start_pos remains 0
    
    # Only search in text after the start position
    text_to_search = text[search_start_pos:]
    
    # Step 1: Find all actual SCHEDULE sections by matching the word "SCHEDULE" in various formats
    # Pattern to match SCHEDULE in various formats:
    # - SCHEDULE
    # - ## SCHEDULE (markdown header)
    # - ## SCHEDULE I (markdown header with number)
    # - **SCHEDULE III** (bold markers)
    # - THE FOURTH SCHEDULE / THE SCHEDULE
    # - FOURTH SCHEDULE
    # - SCHEDULE I / SCHEDULE 1
    schedule_pattern = re.compile(
        r'^\s*(?:#{1,6}\s+)?(?:THE\s+)?(?:[A-Z]+\s+)?SCHEDULE\s*([IVX]+|\d+)?\s*',
        re.MULTILINE | re.IGNORECASE
    )
    
    # Pattern for **SCHEDULE III** format (bold markers)
    schedule_pattern_bold = re.compile(
        r'^\s*\*\*SCHEDULE\s*([IVX]+|\d+)?\s*\*\*',
        re.MULTILINE | re.IGNORECASE
    )
    
    # Find all SCHEDULE occurrences in the text after start position
    schedule_matches_raw = list(schedule_pattern.finditer(text_to_search))
    
    # Also find SCHEDULE with bold markers (**SCHEDULE III**)
    schedule_bold_matches_raw = list(schedule_pattern_bold.finditer(text_to_search))
    
    # Adjust match positions to account for the offset - create wrapper objects
    class MatchWrapper:
        def __init__(self, match, offset):
            self._match = match
            self._offset = offset
        
        def start(self):
            return self._match.start() + self._offset
        
        def end(self):
            return self._match.end() + self._offset
        
        def group(self, *args):
            return self._match.group(*args)
        
        def groups(self):
            return self._match.groups()
        
        @property
        def lastindex(self):
            return self._match.lastindex
        
        @property
        def re(self):
            return self._match.re
    
    schedule_matches = [MatchWrapper(m, search_start_pos) for m in schedule_matches_raw]
    schedule_bold_matches = [MatchWrapper(m, search_start_pos) for m in schedule_bold_matches_raw]
    
    # Combine both types of matches and sort by position
    all_schedule_matches = sorted(schedule_matches + schedule_bold_matches, key=lambda m: m.start())
    
    # Remove duplicates (if a SCHEDULE matches both patterns, keep only one)
    unique_schedule_matches = []
    seen_positions = set()
    for match in all_schedule_matches:
        match_start = match.start()
        # If this position is within 10 characters of a seen position, skip it (duplicate)
        is_duplicate = any(abs(match_start - pos) < 10 for pos in seen_positions)
        if not is_duplicate:
            unique_schedule_matches.append(match)
            seen_positions.add(match_start)
    
    schedule_matches = unique_schedule_matches
    
    # Debug: Print search boundary
    print(f"\nSCHEDULE SEARCH: Starting from position {search_start_pos} (after second law name/preamble)")
    if search_start_pos > 0:
        print(f"  Text before search start: {text[:min(100, search_start_pos)]}...")
    print(f"  Found {len(schedule_matches)} SCHEDULE matches after position {search_start_pos}\n")
    
    if not schedule_matches:
        return schedule_sections
    
    # Step 2: For each SCHEDULE section, extract its text and find subsections within it
    print(f"\nDEBUG: Processing {len(schedule_matches)} SCHEDULE matches")
    for schedule_idx, schedule_match in enumerate(schedule_matches):
        try:
            schedule_start = schedule_match.start()
            schedule_end = schedule_match.end()
            
            # Extract schedule number from the match
            schedule_number = '-'
            try:
                schedule_number_match = schedule_match.group(1)
                if schedule_number_match:
                    schedule_number = schedule_number_match.strip()
            except (IndexError, AttributeError):
                # Group 1 doesn't exist or match is None - schedule has no number
                schedule_number = '-'
            
            # Find the end of this SCHEDULE section
            # SCHEDULE ends at the end of text, but if there are multiple SCHEDULE sections,
            # each one ends at the start of the next SCHEDULE
            schedule_text_end = len(text)  # Default: end of text
            
            # Check if there's a next SCHEDULE section
            if schedule_idx + 1 < len(schedule_matches):
                next_schedule_start = schedule_matches[schedule_idx + 1].start()
                if next_schedule_start > schedule_start:
                    schedule_text_end = next_schedule_start
            
            # Extract SCHEDULE text (only the text within this SCHEDULE section)
            schedule_text = text[schedule_start:schedule_text_end].strip()
            
            if not schedule_text:
                print(f"  WARNING: Schedule text is empty, skipping")
                continue
            
            # print(f"  DEBUG: About to process schedule text (length: {len(schedule_text)})")
            
            # Step 3: Within this SCHEDULE text, find subsections using section patterns
            # Import all section patterns from extract_sections function
            # These patterns require bold markers (**) - all sections must start with bold markers
            # Fixed: The lookahead should stop at closing ** or em dash, not at any space+capital
            # The issue was that \s+[A-Z¹²³⁴⁵⁶⁷⁸⁹⁰] was matching within the title itself (e.g., "Persons serving National")
            # Now we check for closing ** first, then em dash, then next section
            subsection_section_pattern = re.compile(
                r'^\s*\*\*(\d+[A-Za-z-]*)\s*\.?\s*([¹²³⁴⁵⁶⁷⁸⁹⁰\w\s.,;:()\[\]—\-]*?)(?:\s*\*\*\s*\.?)?(?=\s*\*\*\s*\.?\s*—|\s*—|\n\s*\*\*\d+[A-Za-z-]*\s*\.|\n|$)',
                re.MULTILINE | re.DOTALL
            )
            
            subsection_pattern_bold_separated = re.compile(
                r'^\s*\*\*(\d+[A-Za-z-]*)\s*\.\s+\*\*\s*([¹²³⁴⁵⁶⁷⁸⁹⁰]*)(\[Omitted\]|\[Repealed\]|\[Deleted\])',
                re.MULTILINE
            )
            
            subsection_pattern_bold_no_space = re.compile(
                r'^\s*\*\*(\d+[A-Za-z-]*)\s*\.\s*\*\*\s*([¹²³⁴⁵⁶⁷⁸⁹⁰]*)(\[Omitted\]|\[Repealed\]|\[Deleted\])',
                re.MULTILINE
            )
            
            subsection_pattern_bold_omitted_superscript = re.compile(
                r'^\s*\*\*(\d+[A-Za-z-]*)\s*\.\s*\*\*\s+([¹²³⁴⁵⁶⁷⁸⁹⁰]+)\s*\*\*(\[Omitted\]|\[Repealed\]|\[Deleted\])\s*\*\*',
                re.MULTILINE
            )
            
            subsection_pattern_superscript_bold = re.compile(
                r'^\s*([¹²³⁴⁵⁶⁷⁸⁹⁰]+)\s*\*\*(\d+[A-Za-z-]*)\s*\.?\s*([¹²³⁴⁵⁶⁷⁸⁹⁰\w\s.,;:()\[\]—\-]*?)(?=\n\s*(?:[¹²³⁴⁵⁶⁷⁸⁹⁰]+\s*)?\*\*\d+[A-Za-z-]*\s*\.|$)',
                re.MULTILINE | re.DOTALL
            )
            
            subsection_pattern_superscript_bracket_bold = re.compile(
                r'^\s*([¹²³⁴⁵⁶⁷⁸⁹⁰]+)\s*\[\s*\*\*(\d+[A-Za-z-]*)\s*\.?\s*([¹²³⁴⁵⁶⁷⁸⁹⁰\w\s.,;:()\[\]—\-]*?)(?=\n\s*(?:[¹²³⁴⁵⁶⁷⁸⁹⁰]+\s*)?\[?\s*\*\*\d+[A-Za-z-]*\s*\.|$)',
                re.MULTILINE | re.DOTALL
            )
            
            subsection_pattern_bold_superscript = re.compile(
                r'^\s*\*\*([¹²³⁴⁵⁶⁷⁸⁹⁰]+)(\d+[A-Za-z-]*)\s*\.?\s*([¹²³⁴⁵⁶⁷⁸⁹⁰\w\s.,;:()\[\]—\-]*?)(?=\n\s*\*\*[¹²³⁴⁵⁶⁷⁸⁹⁰]*\d+[A-Za-z-]*\s*\.|$)',
                re.MULTILINE | re.DOTALL
            )
            
            subsection_pattern_bold_superscript_bracket = re.compile(
                r'^\s*\*\*([¹²³⁴⁵⁶⁷⁸⁹⁰]+)\[\s*(\d+[A-Za-z-]*)\s*\.?\s*([¹²³⁴⁵⁶⁷⁸⁹⁰\w\s.,;:()\[\]—\-]*?)(?=\n\s*\*\*[¹²³⁴⁵⁶⁷⁸⁹⁰]*\[?\s*\d+[A-Za-z-]*\s*\.|$)',
                re.MULTILINE | re.DOTALL
            )
            
            subsection_pattern_superscript_bold_bracket = re.compile(
                r'^\s*([¹²³⁴⁵⁶⁷⁸⁹⁰]+)\s*\*\*\s*\[\s*(\d+[A-Za-z-]*)\s*\.?\s*([¹²³⁴⁵⁶⁷⁸⁹⁰\w\s.,;:()\[\]—\-]*?)(?:\s*\*\*\s*\.?)?(?=\s*—|\n\s*(?:[¹²³⁴⁵⁶⁷⁸⁹⁰]+\s*)?\*\*\s*\[?\s*\d+[A-Za-z-]*\s*\.|\n|$)',
                re.MULTILINE | re.DOTALL
            )
            
            subsection_pattern_asterisk_bold = re.compile(
                r'^\s*\*\*\*(\d+[A-Za-z-]*)\s*\.?\s*([¹²³⁴⁵⁶⁷⁸⁹⁰\w\s.,;:()\[\]—\-]+?)\s*\*\*\s*\.?(?=\s*—|\s+[A-Z¹²³⁴⁵⁶⁷⁸⁹⁰]|\n\s*\*\*\*\d+[A-Za-z-]*\s*\.|\n|$)',
                re.MULTILINE | re.DOTALL
            )
            
            # Pattern 7: **NUMBER. Title.--** (e.g., **6. Material to be placed before the Minister.--**)
            subsection_pattern_bold_period_emdash = re.compile(
                r'^\s*\*\*(\d+[A-Za-z-]*)\s*\.\s*([¹²³⁴⁵⁶⁷⁸⁹⁰\w\s.,;:()\[\]—\-]*?)\s*\.\s*—\s*\*\*',
                re.MULTILINE | re.DOTALL
            )
            
            # Pattern 8: **NUMBER. Title.** – (e.g., **27. Oversight by Review Committee.** –)
            subsection_pattern_bold_period_space_emdash = re.compile(
                r'^\s*\*\*(\d+[A-Za-z-]*)\s*\.\s*([¹²³⁴⁵⁶⁷⁸⁹⁰\w\s.,;:()\[\]—\-]*?)\s*\.\s*\*\*\s*—',
                re.MULTILINE | re.DOTALL
            )
            
            # List of all subsection patterns
            all_subsection_patterns = [
                subsection_section_pattern,
                subsection_pattern_bold_separated,
                subsection_pattern_bold_no_space,
                subsection_pattern_bold_omitted_superscript,
                subsection_pattern_superscript_bold,
                subsection_pattern_superscript_bracket_bold,
                subsection_pattern_bold_superscript,
                subsection_pattern_bold_superscript_bracket,
                subsection_pattern_superscript_bold_bracket,
                subsection_pattern_asterisk_bold,
                subsection_pattern_bold_period_emdash,
                subsection_pattern_bold_period_space_emdash
            ]
            
            # Helper function to check if a line matches any section pattern
            def is_subsection_title_line(line_stripped: str) -> bool:
                """Check if a line matches any section pattern (subsections use same patterns as sections)."""
                if not line_stripped or len(line_stripped) <= 2:
                    return False
        
                # Check if line matches any section pattern
                for pattern in all_subsection_patterns:
                    if pattern.match(line_stripped):
                        return True
                return False
            
            # Helper function to extract subsection number and title from a matched line
            def extract_subsection_number_and_title_from_match(line_stripped: str) -> tuple:
                """Extract subsection number and title from a line that matches a section pattern.
            
                Returns:
                    Tuple of (number, title) where:
                    - number: The section number if present, or None
                    - title: The title text, or None if not found
                """
                # Try each pattern to find which one matches
                for pattern in all_subsection_patterns:
                    match = pattern.match(line_stripped)
                    if match:
                        # Extract number and title based on pattern type
                        if pattern == subsection_pattern_superscript_bold:
                            number = match.group(2).strip() if match.lastindex >= 2 else None
                            title = match.group(3).strip() if match.lastindex >= 3 else None
                        elif pattern == subsection_pattern_superscript_bracket_bold:
                            number = match.group(2).strip() if match.lastindex >= 2 else None
                            title = match.group(3).strip() if match.lastindex >= 3 else None
                        elif pattern == subsection_pattern_bold_superscript:
                            number = match.group(2).strip() if match.lastindex >= 2 else None
                            title = match.group(3).strip() if match.lastindex >= 3 else None
                        elif pattern == subsection_pattern_bold_superscript_bracket:
                            number = match.group(2).strip() if match.lastindex >= 2 else None
                            title = match.group(3).strip() if match.lastindex >= 3 else None
                        elif pattern == subsection_pattern_superscript_bold_bracket:
                            number = match.group(2).strip() if match.lastindex >= 2 else None
                            title = match.group(3).strip() if match.lastindex >= 3 else None
                        elif pattern == subsection_pattern_asterisk_bold:
                            number = match.group(1).strip() if match.lastindex >= 1 else None
                            title = match.group(2).strip() if match.lastindex >= 2 else None
                        elif pattern == subsection_pattern_bold_separated or pattern == subsection_pattern_bold_no_space:
                            number = match.group(1).strip() if match.lastindex >= 1 else None
                            title = match.group(3).strip() if match.lastindex >= 3 else None
                        elif pattern == subsection_pattern_bold_omitted_superscript:
                            number = match.group(1).strip() if match.lastindex >= 1 else None
                            title = match.group(3).strip() if match.lastindex >= 3 else None
                        else:
                            # Main pattern: **1. Title** - group 1 = number, group 2 = title
                            number = match.group(1).strip() if match.lastindex >= 1 else None
                            title = match.group(2).strip() if match.lastindex >= 2 else None
                        
                        return (number, title)
                
                # No pattern matched
                return (None, None)
            
            # Helper function to extract subsection title from a line (removes number prefix if present)
            def extract_subsection_title(line_stripped: str) -> str:
                """Extract subsection title from a line that matches a section pattern."""
                _, title = extract_subsection_number_and_title_from_match(line_stripped)
                return title if title else ""
            
            # Split schedule text into lines for processing
            schedule_lines = schedule_text.split('\n')
            # print(f"  DEBUG: Split schedule into {len(schedule_lines)} lines")
            
            # Get the first line (should be the SCHEDULE header, may contain subsection on same line)
            first_line_full = schedule_lines[0] if schedule_lines else ""
            first_line_stripped = first_line_full.strip()
            # print(f"  DEBUG: First line: {repr(first_line_stripped[:100])}")
            
            # Extract SCHEDULE header part (everything up to and including "SCHEDULE" and optional number)
            schedule_header_match = schedule_pattern.match(first_line_stripped)
            # print(f"  DEBUG: Schedule header match: {bool(schedule_header_match)}")
            if schedule_header_match:
                schedule_header_end = schedule_header_match.end()
                # Check if there's text after the SCHEDULE header on the same line (subsection on same line)
                text_after_header = first_line_stripped[schedule_header_end:].strip()
            else:
                text_after_header = ""
            
            # Find all subsections within this SCHEDULE text
            subsections = []
            
            # Calculate line start positions relative to schedule_start
            line_start_positions = [0]  # First line starts at position 0 within schedule_text
            current_pos = 0
            for line_idx in range(len(schedule_lines) - 1):
                line = schedule_lines[line_idx]
                current_pos += len(line) + 1  # +1 for newline
                line_start_positions.append(current_pos)
            
            # Check if subsection appears on the same line as SCHEDULE
            if text_after_header and is_subsection_title_line(text_after_header):
                # Subsection starts on the same line as SCHEDULE
                subsection_number, subsection_title_first_part = extract_subsection_number_and_title_from_match(text_after_header)
                subsection_title_parts = [subsection_title_first_part] if subsection_title_first_part else []
                subsection_start_pos_rel = len(schedule_header_match.group(0))  # Position relative to schedule_text start
                
                # Check if subsection title continues on next lines (multi-line title)
                line_idx = 1
                while line_idx < len(schedule_lines):
                    next_line = schedule_lines[line_idx].strip()
                    if not next_line:
                        line_idx += 1
                        continue
                    
                    if is_subsection_title_line(next_line):
                        if subsection_title_parts and not subsection_title_parts[-1].rstrip().endswith(('.', ':', ';', ',')):
                            subsection_title_parts.append(extract_subsection_title(next_line))
                            line_idx += 1
                            continue
                        else:
                            # Title line but condition failed - this is a new subsection, stop collecting title
                            break
                    else:
                        break
                
                subsection_title = ' '.join(subsection_title_parts).strip()
                subsection_content_start_line_idx = line_idx
                
                # Find where this subsection ends (next subsection or end of schedule)
                next_subsection_line_idx = None
                for check_idx in range(subsection_content_start_line_idx, len(schedule_lines)):
                    check_line = schedule_lines[check_idx].strip()
                    if check_line and is_subsection_title_line(check_line):
                        next_subsection_line_idx = check_idx
                        break
            
                if next_subsection_line_idx is not None:
                    subsection_end_pos_rel = line_start_positions[next_subsection_line_idx]
                else:
                    subsection_end_pos_rel = len(schedule_text)
                
                # Extract subsection text (relative to schedule_text)
                subsection_text = schedule_text[subsection_start_pos_rel:subsection_end_pos_rel].strip()
                
                if subsection_text:
                    subsection_start_pos = schedule_start + subsection_start_pos_rel
                    subsection_end_pos = schedule_start + subsection_end_pos_rel
                    subsection_pages = []
                    if position_to_page:
                        subsection_pages = get_pages_for_span(position_to_page, subsection_start_pos, subsection_end_pos)
                    
                    subsections.append({
                        'number': subsection_number,
                        'title': subsection_title,
                        'text': subsection_text,
                        'start_pos': subsection_start_pos,
                        'end_pos': subsection_end_pos,
                        'page_numbers': subsection_pages
                    })
            
            # Find subsections on subsequent lines (not on same line as SCHEDULE)
            processed_lines = set()
            if subsections:
                for sub in subsections:
                    sub_start_rel = sub['start_pos'] - schedule_start
                    sub_end_rel = sub['end_pos'] - schedule_start
                    for line_idx, line_pos in enumerate(line_start_positions):
                        if line_pos >= sub_start_rel and line_pos < sub_end_rel:
                            processed_lines.add(line_idx)
            
            subsection_line_indices = []
            for line_idx in range(1, len(schedule_lines)):
                if line_idx in processed_lines:
                    continue
                
                line = schedule_lines[line_idx]
                line_stripped = line.strip()
                
                if not line_stripped:
                    continue
                
                if is_subsection_title_line(line_stripped):
                    subsection_line_indices.append(line_idx)
            
            # Process subsections found on subsequent lines
            for sub_idx, subsection_line_idx in enumerate(subsection_line_indices):
                if subsection_line_idx in processed_lines:
                    continue
                
                subsection_start_pos_rel = line_start_positions[subsection_line_idx]
                already_processed = False
                for existing_sub in subsections:
                    existing_start_rel = existing_sub['start_pos'] - schedule_start
                    existing_end_rel = existing_sub['end_pos'] - schedule_start
                    if existing_start_rel <= subsection_start_pos_rel < existing_end_rel:
                        already_processed = True
                        break
                if already_processed:
                    continue
                
                subsection_number, subsection_title_first_part = extract_subsection_number_and_title_from_match(schedule_lines[subsection_line_idx].strip())
                subsection_title_parts = [subsection_title_first_part] if subsection_title_first_part else []
                current_line_idx = subsection_line_idx + 1
                
                # Check if title continues on next lines
                while current_line_idx < len(schedule_lines):
                    next_line = schedule_lines[current_line_idx].strip()
                    if not next_line:
                        current_line_idx += 1
                        continue
                    
                    if is_subsection_title_line(next_line):
                        if subsection_title_parts and not subsection_title_parts[-1].rstrip().endswith(('.', ':', ';', ',')):
                            subsection_title_parts.append(extract_subsection_title(next_line))
                            current_line_idx += 1
                            continue
                        else:
                            # Title line but condition failed - this is a new subsection, stop collecting title
                            break
                    else:
                        break
                
                subsection_title = ' '.join(subsection_title_parts).strip()
                
                # Find end position (start of next subsection or end of schedule)
                next_subsection_line_idx = None
                if sub_idx + 1 < len(subsection_line_indices):
                    next_subsection_line_idx = subsection_line_indices[sub_idx + 1]
                else:
                    for check_idx in range(current_line_idx, len(schedule_lines)):
                        check_line = schedule_lines[check_idx].strip()
                        if check_line and is_subsection_title_line(check_line):
                            next_subsection_line_idx = check_idx
                            break
                
                if next_subsection_line_idx is not None:
                    subsection_end_pos_rel = line_start_positions[next_subsection_line_idx]
                else:
                    subsection_end_pos_rel = len(schedule_text)
                
                subsection_text = schedule_text[subsection_start_pos_rel:subsection_end_pos_rel].strip()
                
                if subsection_text:
                    subsection_start_pos = schedule_start + subsection_start_pos_rel
                    subsection_end_pos = schedule_start + subsection_end_pos_rel
                    subsection_pages = []
                    if position_to_page:
                        subsection_pages = get_pages_for_span(position_to_page, subsection_start_pos, subsection_end_pos)
                    
                    subsections.append({
                        'number': subsection_number,
                        'title': subsection_title,
                        'text': subsection_text,
                        'start_pos': subsection_start_pos,
                        'end_pos': subsection_end_pos,
                        'page_numbers': subsection_pages
                    })
            
            if subsections:
                print(f"  Creating {len(subsections)} subsection sections")
                # Create a section for each subsection
                for subsection in subsections:
                    section_number = subsection.get('number', '-') if subsection.get('number') else '-'
                    # Combine schedule number with subsection number if both exist
                    if schedule_number != '-' and section_number != '-':
                        combined_number = f"{schedule_number}-{section_number}"
                    elif schedule_number != '-':
                        combined_number = schedule_number
                    else:
                        combined_number = section_number
                    
                    schedule_sections.append({
                        'number': combined_number,
                        'title': f"SCHEDULE {schedule_number}-{subsection['title']}" if schedule_number != '-' else f"SCHEDULE-{subsection['title']}",
                        'text': subsection['text'],
                        'start_pos': subsection['start_pos'],
                        'end_pos': subsection['end_pos'],
                        'page_numbers': subsection['page_numbers']
                    })
            else:
                print(f"  No subsections found - creating single SCHEDULE section")
                # No subsections - create single SCHEDULE section
                schedule_pages = []
                if position_to_page:
                    schedule_pages = get_pages_for_span(position_to_page, schedule_start, schedule_text_end)
                
                schedule_sections.append({
                    'number': schedule_number,
                    'title': f'SCHEDULE {schedule_number}' if schedule_number != '-' else 'SCHEDULE',
                    'text': schedule_text,
                    'start_pos': schedule_start,
                    'end_pos': schedule_text_end,
                    'page_numbers': schedule_pages
                })
                # print(f"  Added SCHEDULE section. Total schedule_sections now: {len(schedule_sections)}")
        except Exception as e:
            print(f"  ERROR processing SCHEDULE {schedule_idx + 1}: {e}")
            import traceback
            traceback.print_exc()
            continue
    
    
    return schedule_sections


def extract_sections(text: str, raw_text: str, position_to_page: Optional[Dict[int, int]] = None, schedule_sections: Optional[List[Dict]] = None) -> List[Dict]:
    # position_to_page parameter is kept for compatibility but not used
    """
    Extract sections from text using regex, and find positions in raw_text.
    
    Sections are identified by patterns like:
    - **1. Short title...**
    - **2. Definitions.**
    - **1. ** (with title on next line or separate)
    - 22-A. Some section
    
    Also extracts preamble (text between second law name and first numbered section).
    
    Args:
        text: Text to search for sections (can be cleaned_text or raw_text)
        raw_text: Raw unprocessed text (for finding actual positions)
        position_to_page: Dictionary mapping character position to page number
        
    Returns:
        List of section dictionaries with text, number, title, start_pos, end_pos, and page_numbers
    """
    PLACEHOLDER_PATTERN = re.compile(r'\[(FORM|TABLE)_\d+\]')

    def protect_placeholders(text):
        mapping = {}
        counter = 0

        def repl(match):
            nonlocal counter
            token = f"__PLACEHOLDER_{counter}__"
            mapping[token] = match.group(0)
            counter += 1
            return token

        return PLACEHOLDER_PATTERN.sub(repl, text), mapping


    def restore_placeholders(text, mapping):
        for k, v in mapping.items():
            text = text.replace(k, v)
        return text
    sections = []
    
    # Pattern to match section headers:
    # - **1. Title** or **1 Title** (with or without period)
    # - **22-A. Title** (with alphanumeric section numbers)
    # - **1. ** (with title potentially on next line or separate)
    # - **1.** (with closing ** immediately after period, title on next line)
    # - **1. Title.** (with closing ** and period after title)
    # - **1. Title**.—(1) (with closing **, period, and em dash)
    # - Superscripts may appear in titles
    # Note: Bold markers (**) are REQUIRED - all sections must start with bold markers
    # Note: The lookahead stops at the next section header, but we'll extract full content manually
    # General pattern that handles all formats:
    # **NUMBER. TITLE** or **NUMBER. TITLE.** or **NUMBER. TITLE**.—(1)
    # The pattern captures: opening **, number, period, title (with optional closing ** and period)
    # Made period optional after number to handle both "**1. Title**" and "**1 Title**" formats
    # The lookahead is flexible: matches em dash, newline+next section, newline, content on same line, or end of string
    # Note: We extract full content manually from match start to next match, so lookahead is just for matching
    # Made lookahead more permissive to handle cases where content starts on same line or new line after closing **
    # Fixed: The lookahead should stop at closing ** or em dash, not at any space+capital
    # The issue was that \s+[A-Z¹²³⁴⁵⁶⁷⁸⁹⁰] was matching within the title itself (e.g., "Persons serving National")
    # Now we check for closing ** first, then em dash, then next section
    section_pattern = re.compile(
        r'^\s*\*\*(\d+[A-Za-z-]*)\s*\.?\s*([¹²³⁴⁵⁶⁷⁸⁹⁰\w\s.,;:()\[\]—\-]*?)\s*\*\*\s*\.?(?=\s*\*\*\s*\.?\s*(?:—|–)|\s*(?:—|–)|\n\s*\*\*\d+[A-Za-z-]*\s*\.|\n|$)',
        re.MULTILINE | re.DOTALL
    )
    
    # Pattern for **1. ** format - check for [Omitted], [Repealed], [Deleted] on the same line
    # May have superscript marker before the brackets (e.g., ¹[Omitted])
    section_pattern_bold_separated = re.compile(
        r'^\s*\*\*(\d+[A-Za-z-]*)\.\s+\*\*\s*([¹²³⁴⁵⁶⁷⁸⁹⁰]*)(\[Omitted\]|\[Repealed\]|\[Deleted\])',
        re.MULTILINE
    )
    
    # Pattern for **1.** format - check for [Omitted], [Repealed], [Deleted] on the same line
    # May have superscript marker before the brackets (e.g., ¹[Omitted])
    section_pattern_bold_no_space = re.compile(
        r'^\s*\*\*(\d+[A-Za-z-]*)\.\*\*\s*([¹²³⁴⁵⁶⁷⁸⁹⁰]*)(\[Omitted\]|\[Repealed\]|\[Deleted\])',
        re.MULTILINE
    )
    
    # Pattern for **7.** ³**[Omitted]** format - number, closing **, then superscript and brackets
    section_pattern_bold_omitted_superscript = re.compile(
        r'^\s*\*\*(\d+[A-Za-z-]*)\.\*\*\s+([¹²³⁴⁵⁶⁷⁸⁹⁰]+)\s*\*\*(\[Omitted\]|\[Repealed\]|\[Deleted\])\s*\*\*',
        re.MULTILINE
    )
    
    # Pattern 1: superscript + bold markers + 1. Title (e.g., ¹**1. Title**)
    # Superscript may appear before bold markers and in the title as well
    # Bold markers are REQUIRED
    section_pattern_superscript_bold = re.compile(
        r'^\s*([¹²³⁴⁵⁶⁷⁸⁹⁰]+)\s*\*\*(\d+[A-Za-z-]*)\s*\.?\s*([¹²³⁴⁵⁶⁷⁸⁹⁰\w\s.,;:()\[\]—\-]*?)(?=\n\s*(?:[¹²³⁴⁵⁶⁷⁸⁹⁰]+\s*)?\*\*\d+[A-Za-z-]*\s*\.|$)',
        re.MULTILINE | re.DOTALL
    )
    
    # Pattern 2: superscript + [ + bold markers + 1. Title (e.g., ¹[**1. Title**])
    # Superscript may appear in the title as well
    # Bold markers are REQUIRED
    section_pattern_superscript_bracket_bold = re.compile(
        r'^\s*([¹²³⁴⁵⁶⁷⁸⁹⁰]+)\s*\[\s*\*\*(\d+[A-Za-z-]*)\s*\.?\s*([¹²³⁴⁵⁶⁷⁸⁹⁰\w\s.,;:()\[\]—\-]*?)(?=\n\s*(?:[¹²³⁴⁵⁶⁷⁸⁹⁰]+\s*)?\[?\s*\*\*\d+[A-Za-z-]*\s*\.|$)',
        re.MULTILINE | re.DOTALL
    )
    
    # Pattern 3: Bold markers + superscript + 1. Title (e.g., **¹1. Title**)
    # Superscript may appear in the title as well
    # Bold markers are REQUIRED
    section_pattern_bold_superscript = re.compile(
        r'^\s*\*\*([¹²³⁴⁵⁶⁷⁸⁹⁰]+)(\d+[A-Za-z-]*)\s*\.?\s*([¹²³⁴⁵⁶⁷⁸⁹⁰\w\s.,;:()\[\]—\-]*?)(?=\n\s*\*\*[¹²³⁴⁵⁶⁷⁸⁹⁰]*\d+[A-Za-z-]*\s*\.|$)',
        re.MULTILINE | re.DOTALL
    )
    
    # Pattern 4: Bold markers + superscript + [ + 1. Title (e.g., **¹[1. Title** or **¹[8. Powers and functions of the Executive Board.**—)
    # Superscript may appear in the title as well
    # Bold markers are REQUIRED
    # The title may end with closing ** followed by em dash — or period
    section_pattern_bold_superscript_bracket = re.compile(
        r'^\s*\*\*([¹²³⁴⁵⁶⁷⁸⁹⁰]+)\[\s*(\d+[A-Za-z-]*)\s*\.?\s*([¹²³⁴⁵⁶⁷⁸⁹⁰\w\s.,;:()\[\]—\-]*?)(?:\s*\*\*\s*\.?)?(?=\s*\*\*\s*\.?\s*—|\s*—|\n\s*\*\*[¹²³⁴⁵⁶⁷⁸⁹⁰]*\[?\s*\d+[A-Za-z-]*\s*\.|\n|$)',
        re.MULTILINE | re.DOTALL
    )
    
    # Pattern 5: Superscript + bold markers + [ + 1. Title (e.g., ²**[3A. Title**—)
    # This is different from Pattern 2: Pattern 2 is ¹[**1. Title**], Pattern 5 is ²**[3A. Title**—
    # Superscript may appear in the title as well
    # Bold markers are REQUIRED
    section_pattern_superscript_bold_bracket = re.compile(
        r'^\s*([¹²³⁴⁵⁶⁷⁸⁹⁰]+)\s*\*\*\s*\[\s*(\d+[A-Za-z-]*)\s*\.?\s*([¹²³⁴⁵⁶⁷⁸⁹⁰\w\s.,;:()\[\]—\-]*?)(?:\s*\*\*\s*\.?)?(?=\s*—|\n\s*(?:[¹²³⁴⁵⁶⁷⁸⁹⁰]+\s*)?\*\*\s*\[?\s*\d+[A-Za-z-]*\s*\.|\n|$)',
        re.MULTILINE | re.DOTALL
    )
    
    # Pattern 6: * + bold markers + 1. Title (e.g., *\***15. Trial of offences.**— or **\*19. Appeals from Court.**—)
    # Three asterisks at start (can be *\*** or **\* - both are *** in actual text)
    # Pattern matches: ***NUMBER. TITLE**— or ***NUMBER. TITLE**.—
    # Try both start-of-line and anywhere patterns
    section_pattern_asterisk_bold = re.compile(
        r'(?:^|\n)\s*\*\*\*(\d+[A-Za-z-]*)\s*\.?\s*([¹²³⁴⁵⁶⁷⁸⁹⁰\w\s.,;:()\[\]—\-]+?)\s*\*\*\s*\.?(?=\s*—|\s+[A-Z¹²³⁴⁵⁶⁷⁸⁹⁰]|\n\s*\*\*\*\d+[A-Za-z-]*\s*\.|\n|$)',
        re.MULTILINE | re.DOTALL
    )
    
    # Pattern 7: **NUMBER. Title.--** (e.g., **6. Material to be placed before the Minister.--**)
    # Section heading ending with period, em dash or double hyphen (with optional spaces), and closing bold markers
    # Handles both -- (double hyphen) and — (em dash)
    section_pattern_bold_period_emdash = re.compile(
        r'^\s*\*\*(\d+[A-Za-z-]*)\s*\.\s*([¹²³⁴⁵⁶⁷⁸⁹⁰\w\s.,;:()\[\]—\-]*?)\s*\.\s*(?:—|--)\s*\*\*',
        re.MULTILINE | re.DOTALL
    )
    
    # Pattern 8: **NUMBER. Title.** – (e.g., **27. Oversight by Review Committee.** – or **28. Representation.** –)
    # Section heading ending with period, closing bold markers, optional space, and em dash or en dash
    # Handles both — (em dash) and – (en dash)
    section_pattern_bold_period_space_emdash = re.compile(
        r'^\s*\*\*(\d+[A-Za-z-]*)\s*\.\s*([¹²³⁴⁵⁶⁷⁸⁹⁰\w\s.,;:()\[\]—\-]*?)\s*\.\s*\*\*\s*(?:—|–)',
        re.MULTILINE | re.DOTALL
    )
    
    # Pattern 9: **NUMBER. Title.** (e.g., **15. Sanction in case of arbitrary request for warrant.**)
    # Bold marker + optional space + number + optional space + period + optional space + title + optional space + period + optional space + bold marker closing
    section_pattern_bold_number_title_period = re.compile(
        r'^\s*\*\*\s*(\d+[A-Za-z-]*)\s*\.\s*([¹²³⁴⁵⁶⁷⁸⁹⁰\w\s.,;:()\[\]—\-]*?)\s*\.\s*\*\*',
        re.MULTILINE | re.DOTALL
    )
    
    # Pattern 10: NUMBER. **Title.** (e.g., 15. **Sanction in case of arbitrary request for warrant.**)
    # Number + optional space + period + optional space + bold marker + optional space + title + optional space + period + optional space + bold marker closing
    section_pattern_number_bold_title_period = re.compile(
        r'^\s*(\d+[A-Za-z-]*)\s*\.\s*\*\*\s*([¹²³⁴⁵⁶⁷⁸⁹⁰\w\s.,;:()\[\]—\-]*?)\s*\.\s*\*\*',
        re.MULTILINE | re.DOTALL
    )
    
    # Try bold pattern first
    matches = list(section_pattern.finditer(text))
    
    # Also check for **1. ** format and merge matches
    bold_separated_matches = list(section_pattern_bold_separated.finditer(text))
    for match in bold_separated_matches:
        # Check if this match is not already captured by the main pattern
        is_duplicate = any(
            abs(m.start() - match.start()) < 10 for m in matches
        )
        if not is_duplicate:
            matches.append(match)
    
    # Also check for **1.** format and merge matches
    bold_no_space_matches = list(section_pattern_bold_no_space.finditer(text))
    for match in bold_no_space_matches:
        # Check if this match is not already captured by the main pattern
        is_duplicate = any(
            abs(m.start() - match.start()) < 10 for m in matches
        )
        if not is_duplicate:
            matches.append(match)
    
    # Check for **7.** ³**[Omitted]** format
    bold_omitted_superscript_matches = list(section_pattern_bold_omitted_superscript.finditer(text))
    for match in bold_omitted_superscript_matches:
        is_duplicate = any(
            abs(m.start() - match.start()) < 10 for m in matches
        )
        if not is_duplicate:
            matches.append(match)
    
    # Check for Pattern 1: superscript + bold markers + 1. Title
    superscript_bold_matches = list(section_pattern_superscript_bold.finditer(text))
    for match in superscript_bold_matches:
        is_duplicate = any(
            abs(m.start() - match.start()) < 10 for m in matches
        )
        if not is_duplicate:
            matches.append(match)
    
    # Check for Pattern 2: superscript + [ + bold markers + 1. Title
    superscript_bracket_bold_matches = list(section_pattern_superscript_bracket_bold.finditer(text))
    for match in superscript_bracket_bold_matches:
        is_duplicate = any(
            abs(m.start() - match.start()) < 10 for m in matches
        )
        if not is_duplicate:
            matches.append(match)
    
    # Check for Pattern 3: Bold markers + superscript + 1. Title
    bold_superscript_matches = list(section_pattern_bold_superscript.finditer(text))
    for match in bold_superscript_matches:
        is_duplicate = any(
            abs(m.start() - match.start()) < 10 for m in matches
        )
        if not is_duplicate:
            matches.append(match)
    
    # Check for Pattern 4: Bold markers + superscript + [ + 1. Title
    bold_superscript_bracket_matches = list(section_pattern_bold_superscript_bracket.finditer(text))
    for match in bold_superscript_bracket_matches:
        is_duplicate = any(
            abs(m.start() - match.start()) < 10 for m in matches
        )
        if not is_duplicate:
            matches.append(match)
    
    # Check for Pattern 5: Superscript + bold markers + [ + 1. Title (e.g., ²**[3A. Title**—)
    superscript_bold_bracket_matches = list(section_pattern_superscript_bold_bracket.finditer(text))
    for match in superscript_bold_bracket_matches:
        is_duplicate = any(
            abs(m.start() - match.start()) < 10 for m in matches
        )
        if not is_duplicate:
            matches.append(match)
    
    # Check for Pattern 7: **NUMBER. Title.--** (e.g., **6. Material to be placed before the Minister.--**)
    bold_period_emdash_matches = list(section_pattern_bold_period_emdash.finditer(text))
    for match in bold_period_emdash_matches:
        is_duplicate = any(
            abs(m.start() - match.start()) < 10 for m in matches
        )
        if not is_duplicate:
            matches.append(match)
    
    # Check for Pattern 8: **NUMBER. Title.** – (e.g., **27. Oversight by Review Committee.** –)
    bold_period_space_emdash_matches = list(section_pattern_bold_period_space_emdash.finditer(text))
    for match in bold_period_space_emdash_matches:
        is_duplicate = any(
            abs(m.start() - match.start()) < 10 for m in matches
        )
        if not is_duplicate:
            matches.append(match)
    
    # Check for Pattern 9: **NUMBER. Title.** (e.g., **15. Sanction in case of arbitrary request for warrant.**)
    bold_number_title_period_matches = list(section_pattern_bold_number_title_period.finditer(text))
    for match in bold_number_title_period_matches:
        is_duplicate = any(
            abs(m.start() - match.start()) < 10 for m in matches
        )
        if not is_duplicate:
            matches.append(match)
    
    # Check for Pattern 10: NUMBER. **Title.** (e.g., 15. **Sanction in case of arbitrary request for warrant.**)
    number_bold_title_period_matches = list(section_pattern_number_bold_title_period.finditer(text))
    for match in number_bold_title_period_matches:
        is_duplicate = any(
            abs(m.start() - match.start()) < 10 for m in matches
        )
        if not is_duplicate:
            matches.append(match)
    
    # Check for Pattern 6: * + bold markers + 1. Title (e.g., *\***15. Trial of offences.**—)
    # Also Pattern 6b: **\*NUMBER. Title**— (e.g., **\*18. Jurisdiction of the Tribunals.**—)
    # Search for ***NUMBER pattern anywhere in text (not just start of line)
    asterisk_bold_pattern_anywhere = re.compile(
        r'\*\*\*(\d+[A-Za-z-]*)\s*\.?\s*([¹²³⁴⁵⁶⁷⁸⁹⁰\w\s.,;:()\[\]—\-]+?)\s*\*\*\s*\.?(?=\s*—|\s+[A-Z¹²³⁴⁵⁶⁷⁸⁹⁰]|\n\s*\*\*\*\d+[A-Za-z-]*\s*\.|\n|$)',
        re.MULTILINE | re.DOTALL
    )
    asterisk_bold_matches_anywhere = list(asterisk_bold_pattern_anywhere.finditer(text))
    
    # Pattern for **\*NUMBER. Title**— format (two asterisks, backslash, asterisk)
    asterisk_bold_pattern_backslash = re.compile(
        r'\*\*\\\*(\d+[A-Za-z-]*)\s*\.?\s*([¹²³⁴⁵⁶⁷⁸⁹⁰\w\s.,;:()\[\]—\-]+?)\s*\*\*\s*\.?(?=\s*—|\s+[A-Z¹²³⁴⁵⁶⁷⁸⁹⁰]|\n\s*\*\*\\\*\d+[A-Za-z-]*\s*\.|\n|$)',
        re.MULTILINE | re.DOTALL
    )
    asterisk_bold_matches_backslash = list(asterisk_bold_pattern_backslash.finditer(text))
    
    # Also try the original pattern (start of line)
    asterisk_bold_matches = list(section_pattern_asterisk_bold.finditer(text))
  
    # Search for actual occurrences of *** or **\* followed by number in text
    simple_search1 = re.finditer(r'\*\*\*\d+', text)
    simple_search2 = re.finditer(r'\*\*\\\*\d+', text)
    simple_matches1 = list(simple_search1)
    simple_matches2 = list(simple_search2)
  
    # Combine all matches (use anywhere pattern as primary since it's more flexible)
    all_asterisk_matches = asterisk_bold_matches_anywhere + asterisk_bold_matches_backslash + asterisk_bold_matches
    
    for match in all_asterisk_matches:
        print(f"  Match at position {match.start()}: {repr(text[match.start():match.start()+60])}")
        is_duplicate = any(
            abs(m.start() - match.start()) < 10 for m in matches
        )
        if not is_duplicate:
            # Create a wrapper to make all matches work with the same extraction logic
            class AsteriskMatchWrapper:
                def __init__(self, match_obj):
                    self._match = match_obj
                    self.re = section_pattern_asterisk_bold  # Use the main pattern for extraction logic
                
                def start(self):
                    return self._match.start()
                
                def end(self):
                    return self._match.end()
                
                def group(self, *args):
                    # Map groups: all patterns have number in group 1, title in group 2
                    return self._match.group(*args)
                
                @property
                def lastindex(self):
                    return self._match.lastindex
                
                def groups(self):
                    return self._match.groups()
            
            matches.append(AsteriskMatchWrapper(match))
        else:
            print(f"  Skipped duplicate at position {match.start()}")
    
    # Sort matches by position
    matches = sorted(matches, key=lambda m: m.start())
    
    # Find the second occurrence of the law name pattern to determine where CONTENTS ends
        # Law names are typically in all caps or title case, often with "ACT" or "ORDINANCE"
    # Superscripts (¹²³⁴⁵⁶⁷⁸⁹⁰) may appear anywhere in the law name
    # Pattern 1: Markdown header with # (e.g., "# THE ABANDONED PROPERTIES ACT", "# ¹THE ABANDONED PROPERTIES ACT")
    # Allow superscripts anywhere and parentheses in law names
    law_name_pattern1 = re.compile(
        r'^#\s*([¹²³⁴⁵⁶⁷⁸⁹⁰A-Z][¹²³⁴⁵⁶⁷⁸⁹⁰A-Z\s()]*(?:ACT|ORDINANCE|LAW)[¹²³⁴⁵⁶⁷⁸⁹⁰A-Z\s(),]*)',
            re.MULTILINE | re.IGNORECASE
        )
        
    # Pattern 2: Plain text law name (all caps, often centered or standalone)
    # Superscripts may appear anywhere (e.g., "¹THE ABANDONED PROPERTIES ACT", "THE ABANDONED PROPERTIES¹ ACT")
    # Allow superscripts anywhere and parentheses in law names
    law_name_pattern2 = re.compile(
        r'^([¹²³⁴⁵⁶⁷⁸⁹⁰A-Z][¹²³⁴⁵⁶⁷⁸⁹⁰A-Z\s()]*(?:ACT|ORDINANCE|LAW)[¹²³⁴⁵⁶⁷⁸⁹⁰A-Z\s(),]*)',
        re.MULTILINE
    )
    
    law_name_matches1 = list(law_name_pattern1.finditer(text))
    law_name_matches2 = list(law_name_pattern2.finditer(text))
    
    # Combine and sort all matches
    all_law_name_matches = sorted(
        law_name_matches1 + law_name_matches2,
        key=lambda m: m.start()
    )
    
    # Find second occurrence (skip first one which is usually before CONTENTS)
    # The second law name indicates the end of CONTENTS section
    second_law_name_end = None
    if len(all_law_name_matches) >= 2:
        # Second occurrence of law name - this marks the end of CONTENTS
        second_law_name_end = all_law_name_matches[1].end()
    elif len(all_law_name_matches) == 1:
        # Only one law name found, use it as the boundary
        second_law_name_end = all_law_name_matches[0].end()
    
    # Extract preamble if it exists BEFORE filtering sections
    # Preamble is everything after the second law name until the first numbered section
    if second_law_name_end is not None:
        # Find first section start (before filtering)
        first_section_start = len(text)  # Default to end of text
        if matches:
            first_section_start = matches[0].start()
        
        if second_law_name_end < first_section_start:
            # Preamble starts from second_law_name_end
            preamble_start_pos_raw = second_law_name_end
            
            # Extract preamble text from second_law_name_end to first section
            # preamble_text = text[preamble_start_pos_raw:first_section_start].strip()
            preamble_text, _ = protect_placeholders(
            text[preamble_start_pos_raw:first_section_start].strip()
            )
            
            # Include everything - no length check or filtering
            if preamble_text:
                # Extract title (first line or first sentence)
                preamble_lines = preamble_text.split('\n')
                preamble_title = "Preamble"
                for line in preamble_lines:
                    line_stripped = line.strip()
                    if line_stripped and not line_stripped.startswith('Page') and len(line_stripped) > 10:
                        preamble_title = line_stripped[:200] if len(line_stripped) <= 200 else line_stripped[:200] + "..."
                        break
                
                # Find preamble end position
                preamble_end_pos_raw = first_section_start
                
                # Calculate page numbers from position_to_page using start_pos and end_pos
                preamble_pages = []
                if position_to_page:
                    for pos in range(preamble_start_pos_raw, preamble_end_pos_raw):
                        if pos in position_to_page:
                            preamble_pages.append(position_to_page[pos])
                    preamble_pages = sorted(list(set(preamble_pages)))  # Remove duplicates and sort
                
                # Add preamble as a special section (insert at beginning)
                # For preamble: section_number = "-", section_name = "PREAMBLE"
                sections.insert(0, {
                    'number': '-',  # Section number is "-" for preamble
                    'title': 'PREAMBLE',  # Section name is "PREAMBLE"
                    'text': preamble_text,
                    'start_pos': preamble_start_pos_raw,
                    'end_pos': preamble_end_pos_raw,
                    'page_numbers': preamble_pages
                })
    
    # Filter out sections that appear before the second law name (i.e., in CONTENTS section)
    # Only process sections that appear after CONTENTS
    if second_law_name_end is not None:
        matches = [m for m in matches if m.start() >= second_law_name_end]
    
    for match in matches:
        # Handle different pattern types for section number extraction
        section_number = ""
        captured_content = ""
        
        if match.re == section_pattern_superscript_bold:
            # Pattern 1: superscript + bold markers + 1. Title
            # group 1 = superscript, group 2 = section number, group 3 = title/content
            section_number = match.group(2).strip() if match.lastindex >= 2 else ""
            captured_content = match.group(3).strip() if match.lastindex >= 3 else ""
        elif match.re == section_pattern_superscript_bracket_bold:
            # Pattern 2: superscript + [ + bold markers + 1. Title
            # group 1 = superscript, group 2 = section number, group 3 = title/content
            section_number = match.group(2).strip() if match.lastindex >= 2 else ""
            captured_content = match.group(3).strip() if match.lastindex >= 3 else ""
        elif match.re == section_pattern_bold_superscript:
            # Pattern 3: Bold markers + superscript + 1. Title
            # group 1 = superscript, group 2 = section number, group 3 = title/content
            section_number = match.group(2).strip() if match.lastindex >= 2 else ""
            captured_content = match.group(3).strip() if match.lastindex >= 3 else ""
        elif match.re == section_pattern_bold_superscript_bracket:
            # Pattern 4: Bold markers + superscript + [ + 1. Title
            # group 1 = superscript, group 2 = section number, group 3 = title/content
            section_number = match.group(2).strip() if match.lastindex >= 2 else ""
            captured_content = match.group(3).strip() if match.lastindex >= 3 else ""
        elif match.re == section_pattern_superscript_bold_bracket:
            # Pattern 5: Superscript + bold markers + [ + 1. Title (e.g., ²**[3A. Title**—)
            # group 1 = superscript, group 2 = section number, group 3 = title/content
            section_number = match.group(2).strip() if match.lastindex >= 2 else ""
            captured_content = match.group(3).strip() if match.lastindex >= 3 else ""
        elif match.re == section_pattern_asterisk_bold:
            # Pattern 6: * + bold markers + 1. Title (e.g., *\***15. Trial of offences.**—)
            # group 1 = section number, group 2 = title/content
            section_number = match.group(1).strip() if match.lastindex >= 1 else ""
            captured_content = match.group(2).strip() if match.lastindex >= 2 else ""
        elif match.re == section_pattern_bold_period_emdash:
            # Pattern 7: **NUMBER. Title.--** (e.g., **6. Material to be placed before the Minister.--**)
            # group 1 = section number, group 2 = title/content (without the .--** ending)
            section_number = match.group(1).strip() if match.lastindex >= 1 else ""
            captured_content = match.group(2).strip() if match.lastindex >= 2 else ""
        elif match.re == section_pattern_bold_period_space_emdash:
            # Pattern 8: **NUMBER. Title.** – (e.g., **27. Oversight by Review Committee.** –)
            # group 1 = section number, group 2 = title/content (without the .** – ending)
            section_number = match.group(1).strip() if match.lastindex >= 1 else ""
            captured_content = match.group(2).strip() if match.lastindex >= 2 else ""
        elif match.re == section_pattern_bold_number_title_period:
            # Pattern 9: **NUMBER. Title.** (e.g., **15. Sanction in case of arbitrary request for warrant.**)
            # group 1 = section number, group 2 = title/content (without the .** ending)
            section_number = match.group(1).strip() if match.lastindex >= 1 else ""
            captured_content = match.group(2).strip() if match.lastindex >= 2 else ""
        elif match.re == section_pattern_number_bold_title_period:
            # Pattern 10: NUMBER. **Title.** (e.g., 15. **Sanction in case of arbitrary request for warrant.**)
            # group 1 = section number, group 2 = title/content (without the .** ending)
            section_number = match.group(1).strip() if match.lastindex >= 1 else ""
            captured_content = match.group(2).strip() if match.lastindex >= 2 else ""
        else:
            # Original patterns
            section_number = match.group(1).strip()
            captured_content = match.group(2).strip() if match.lastindex >= 2 else ""
        
        # Check if this is an omitted/repealed/deleted section
        is_omitted_section = False
        omitted_status = None
        if match.re == section_pattern_bold_separated or match.re == section_pattern_bold_no_space:
            # For these patterns, group 2 is superscript (optional), group 3 is the status
            if match.lastindex >= 3:
                status_text = match.group(3).strip()
                if status_text in ['[Omitted]', '[Repealed]', '[Deleted]']:
                    is_omitted_section = True
                    omitted_status = status_text
            elif match.lastindex >= 2:
                # Fallback: check if captured_content is the status (for backward compatibility)
                if captured_content in ['[Omitted]', '[Repealed]', '[Deleted]']:
                    is_omitted_section = True
                    omitted_status = captured_content
        elif match.re == section_pattern_bold_omitted_superscript:
            # Pattern: **7.** ³**[Omitted]** - group 1 = number, group 2 = superscript, group 3 = status
            if match.lastindex >= 3:
                status_text = match.group(3).strip()
                if status_text in ['[Omitted]', '[Repealed]', '[Deleted]']:
                    is_omitted_section = True
                    omitted_status = status_text
                    # Extract section number from group 1
                    section_number = match.group(1).strip() if match.lastindex >= 1 else ""
                    captured_content = status_text
        
        # Get positions for this section directly from text (which is now raw_text)
        # Since text is raw_text, positions are already in raw_text coordinates
        start_pos = match.start()  # Position in raw_text
        # Find the start of the next section (either another section match or a SCHEDULE section)
        next_match_start = len(text)
        for other_match in matches:
            if other_match.start() > start_pos:
                next_match_start = other_match.start()
                break
        section_content=""
        # Also check for SCHEDULE sections that might come after this section
        if schedule_sections:
            for schedule_section in schedule_sections:
                schedule_start = schedule_section.get('start_pos', -1)
                if schedule_start != -1 and start_pos < schedule_start < next_match_start:
                    next_match_start = schedule_start
        
        # Extract the FULL section text from the match start to next section
        # This ensures we capture all subsections like (2), (3), etc., even across page boundaries
        # The regex might have stopped early, so we extract the full range
        # full_section_text = text[match.start():next_match_start].strip()
        full_section_text_raw = text[match.start():next_match_start].strip()
        full_section_text, placeholder_map = protect_placeholders(full_section_text_raw)
        
        # Positions are directly from raw_text (since text is raw_text)
        section_start_pos_raw = start_pos
        section_end_pos_raw = next_match_start
        
        # Handle omitted/repealed/deleted sections
        if is_omitted_section:
            section_title = omitted_status
            section_content = omitted_status
        else:
            # Remove the section header pattern to get just the content
            # Pattern: **1. Title** or 1. Title or superscript variants
            # IMPORTANT: Only remove the header at the START, not anywhere in the text
            # The header is at the beginning of full_section_text
            # Handle different patterns: original, superscript before, superscript after, with brackets
            if match.re == section_pattern_superscript_bold:
                # Pattern: ¹**1. Title**
                header_pattern = re.compile(r'^\s*[¹²³⁴⁵⁶⁷⁸⁹⁰]+\s*\*\*\d+[A-Za-z-]*\s*\.?\s*', re.MULTILINE)
            elif match.re == section_pattern_superscript_bracket_bold:
                # Pattern: ¹[**1. Title**
                header_pattern = re.compile(r'^\s*[¹²³⁴⁵⁶⁷⁸⁹⁰]+\s*\[\s*\*\*\d+[A-Za-z-]*\s*\.?\s*', re.MULTILINE)
            elif match.re == section_pattern_bold_superscript:
                # Pattern: **¹1. Title**
                header_pattern = re.compile(r'^\s*\*\*[¹²³⁴⁵⁶⁷⁸⁹⁰]+\d+[A-Za-z-]*\s*\.?\s*', re.MULTILINE)
            elif match.re == section_pattern_bold_superscript_bracket:
                # Pattern: **¹[1. Title** or **¹[8. Powers and functions of the Executive Board.**—
                # Need to match up to and including the closing ** (with optional spaces)
                header_pattern = re.compile(r'^\s*\*\*[¹²³⁴⁵⁶⁷⁸⁹⁰]+\[\s*\d+[A-Za-z-]*\s*\.?\s*[¹²³⁴⁵⁶⁷⁸⁹⁰\w\s.,;:()\[\]—\-]*?\s*\*\*\s*\.?', re.MULTILINE)
            elif match.re == section_pattern_superscript_bold_bracket:
                # Pattern: ²**[3A. Title**—
                header_pattern = re.compile(r'^\s*[¹²³⁴⁵⁶⁷⁸⁹⁰]+\s*\*\*\s*\[\s*\d+[A-Za-z-]*\s*\.?\s*', re.MULTILINE)
            elif match.re == section_pattern_asterisk_bold:
                # Pattern: *\***15. Trial of offences.**— or **\*19. Appeals from Court.**—
                # Need to match: ***NUMBER. TITLE** or **\*NUMBER. TITLE** (with closing **) - with optional spaces
                # Try both formats: *** and **\*
                header_pattern1 = re.compile(r'^\s*\*\*\*\d+[A-Za-z-]*\s*\.?\s*[¹²³⁴⁵⁶⁷⁸⁹⁰\w\s.,;:()\[\]—\-]*?\s*\*\*\s*\.?', re.MULTILINE)
                header_pattern2 = re.compile(r'^\s*\*\*\\\*\d+[A-Za-z-]*\s*\.?\s*[¹²³⁴⁵⁶⁷⁸⁹⁰\w\s.,;:()\[\]—\-]*?\s*\*\*\s*\.?', re.MULTILINE)
                
                if header_pattern1.match(full_section_text):
                    section_content = header_pattern1.sub('', full_section_text, count=1).strip()
                elif header_pattern2.match(full_section_text):
                    section_content = header_pattern2.sub('', full_section_text, count=1).strip()
                else:
                    # Fallback: remove just the opening part (try both formats) - with optional spaces
                    header_pattern_simple1 = re.compile(r'^\s*\*\*\*\d+[A-Za-z-]*\s*\.?\s*', re.MULTILINE)
                    header_pattern_simple2 = re.compile(r'^\s*\*\*\\\*\d+[A-Za-z-]*\s*\.?\s*', re.MULTILINE)
                    if header_pattern_simple1.match(full_section_text):
                        section_content = header_pattern_simple1.sub('', full_section_text, count=1).strip()
                    elif header_pattern_simple2.match(full_section_text):
                        section_content = header_pattern_simple2.sub('', full_section_text, count=1).strip()
                    else:
                        section_content = full_section_text.strip()
            elif match.re == section_pattern_bold_omitted_superscript:
                # Pattern: **7.** ³**[Omitted]** or **7.** ³**[Repealed]** or **7.** ³**[Deleted]**
                header_pattern = re.compile(r'^\s*\*\*\d+[A-Za-z-]*\.\*\*\s+[¹²³⁴⁵⁶⁷⁸⁹⁰]+\s*\*\*(\[Omitted\]|\[Repealed\]|\[Deleted\])\s*\*\*', re.MULTILINE)
            elif match.re == section_pattern_bold_period_emdash:
                # Pattern: **NUMBER. Title.--** (e.g., **6. Material to be placed before the Minister.--**)
                # Need to match up to and including the .--** ending (with optional spaces)
                # Handle both em dash (—) and double hyphen (--)
                header_pattern = re.compile(r'^\s*\*\*\d+[A-Za-z-]*\s*\.\s*[¹²³⁴⁵⁶⁷⁸⁹⁰\w\s.,;:()\[\]—\-]*?\s*\.\s*(?:—|--)\s*\*\*', re.MULTILINE)
                if header_pattern.match(full_section_text):
                    section_content = header_pattern.sub('', full_section_text, count=1).strip()
                else:
                    # Fallback: remove just the opening part
                    header_pattern_simple = re.compile(r'^\s*\*\*\d+[A-Za-z-]*\s*\.\s*', re.MULTILINE)
                    section_content = header_pattern_simple.sub('', full_section_text, count=1).strip()
            elif match.re == section_pattern_bold_period_space_emdash:
                # Pattern: **NUMBER. Title.** – (e.g., **27. Oversight by Review Committee.** –)
                # Need to match up to and including the .** – ending (with optional spaces)
                # Handle both em dash (—) and en dash (–)
                header_pattern = re.compile(r'^\s*\*\*\d+[A-Za-z-]*\s*\.\s*[¹²³⁴⁵⁶⁷⁸⁹⁰\w\s.,;:()\[\]—\-]*?\s*\.\s*\*\*\s*(?:—|–)', re.MULTILINE)
                if header_pattern.match(full_section_text):
                    section_content = header_pattern.sub('', full_section_text, count=1).strip()
                else:
                    section_content = full_section_text.strip()
            elif match.re == section_pattern_bold_number_title_period:
                # Pattern: **NUMBER. Title.** (e.g., **15. Sanction in case of arbitrary request for warrant.**)
                # Need to match up to and including the .** ending (with optional spaces)
                header_pattern = re.compile(r'^\s*\*\*\s*\d+[A-Za-z-]*\s*\.\s*[¹²³⁴⁵⁶⁷⁸⁹⁰\w\s.,;:()\[\]—\-]*?\s*\.\s*\*\*', re.MULTILINE)
                if header_pattern.match(full_section_text):
                    section_content = header_pattern.sub('', full_section_text, count=1).strip()
                else:
                    section_content = full_section_text.strip()
            elif match.re == section_pattern_number_bold_title_period:
                # Pattern: NUMBER. **Title.** (e.g., 15. **Sanction in case of arbitrary request for warrant.**)
                # Need to match up to and including the .** ending (with optional spaces)
                header_pattern = re.compile(r'^\s*\d+[A-Za-z-]*\s*\.\s*\*\*\s*[¹²³⁴⁵⁶⁷⁸⁹⁰\w\s.,;:()\[\]—\-]*?\s*\.\s*\*\*', re.MULTILINE)
                if header_pattern.match(full_section_text):
                    section_content = header_pattern.sub('', full_section_text, count=1).strip()
                else:
                    # Fallback: remove just the opening part
                    header_pattern_simple = re.compile(r'^\s*\d+[A-Za-z-]*\s*\.\s*\*\*\s*', re.MULTILINE)
                    section_content = header_pattern_simple.sub('', full_section_text, count=1).strip()
            else:
                # Original patterns: **1. Title** (bold markers are REQUIRED)
                # The main pattern now requires closing ** (compulsory)
                # Handle both **1. Title.** and **1. Title** formats
                # Pattern should remove: **1. Title** or **1. Title.** up to the closing ** and optional period
                # Try to match header with period before closing ** first (handles **1. Title.** format)
                header_pattern_with_period_closing = re.compile(r'^\s*\*\*\d+[A-Za-z-]*\.?\s+[^*]*?\.\s*\*\*', re.MULTILINE)
                header_pattern_with_closing = re.compile(r'^\s*\*\*\d+[A-Za-z-]*\.?\s+[^*]*?\*\*\.?', re.MULTILINE)
                if header_pattern_with_period_closing.match(full_section_text):
                    section_content = header_pattern_with_period_closing.sub('', full_section_text, count=1).strip()
                elif header_pattern_with_closing.match(full_section_text):
                    section_content = header_pattern_with_closing.sub('', full_section_text, count=1).strip()
                else:
                    # Fallback: remove just the opening part (shouldn't happen with compulsory closing **, but safety)
                    header_pattern_simple = re.compile(r'^\s*\*\*\d+[A-Za-z-]*\.?\s*', re.MULTILINE)
                    section_content = header_pattern_simple.sub('', full_section_text, count=1).strip()
            # Restore form/table placeholders AFTER all regex cleanup
            section_content = restore_placeholders(section_content, placeholder_map)
            
            # Remove markdown bold markers from content (in case any remain)
            section_content = re.sub(r'\*\*', '', section_content)
            
            # Extract section title - prioritize captured_content for ALL patterns
            section_title = ""
            
            # For ALL patterns, captured_content should contain the title
            # This includes both superscript patterns and the main pattern
            if captured_content:
                # Extract title from captured_content (before em dash, closing **, or period)
                # The title might end with closing **, period, or em dash
                # First, remove any closing ** and period
                title_text = captured_content.strip()
                # Remove closing ** and period if present
                title_text = re.sub(r'\*\*\.?$', '', title_text).strip()
                # Extract title before em dash or en dash if present
                # Handle both — (em dash) and – (en dash)
                title_match = re.match(r'^([^—–]+)', title_text)
                if title_match:
                    section_title = title_match.group(1).strip()

                    # Remove trailing period or markdown bold markers
                    section_title = re.sub(r'[.\*\*]+$', '', section_title).strip()
                else:
                    # Use the whole title_text as title
                    section_title = title_text
                    # Remove trailing period or markdown bold markers
                    section_title = re.sub(r'[.\*\*]+$', '', section_title).strip()
                  
            if not section_title:

                # Pakistani legal sections often have format: "Title.—(1) Content" or "Title.**—(1) Content"
                # Try to extract title before the em dash
                title_match = re.match(r'^([^.—]+(?:\.|—|$))', section_content)
                if title_match:
                    section_title = title_match.group(1).strip()
                    # Remove trailing em dash, period, or markdown bold markers
                    section_title = re.sub(r'[.—\*\*]+$', '', section_title).strip()

                else:
                # Fallback: first line
                    lines = section_content.split('\n')
                    section_title = lines[0].strip() if lines else ""
                # Remove markdown artifacts
                section_title = re.sub(r'\*\*', '', section_title).strip()
                # Take first sentence if too long
                if len(section_title) > 100:
                    sentence_match = re.match(r'^([^.]{1,100})\.', section_title)
                    if sentence_match:
                        section_title = sentence_match.group(1).strip()
                    
            # Final fallback: if title is still empty, use section number as title
            if not section_title or section_title.strip() == "":
                section_title = f"Section {section_number}"
            
            # SAFEGUARD: Normal sections (with numeric section numbers) should NEVER have SCHEDULE titles
            # If a normal section somehow got a SCHEDULE title, it's a bug - fix it
            if section_number != '-' and section_title.startswith('SCHEDULE-'):
                # This is a normal section that incorrectly got a SCHEDULE title
                # Extract the actual title by removing "SCHEDULE-" prefix
                actual_title = section_title.replace('SCHEDULE-', '', 1).strip()
                if actual_title:
                    section_title = actual_title
                else:
                    # If removing SCHEDULE- leaves nothing, use fallback
                    section_title = f"Section {section_number}"
            
            # Limit title length
            if len(section_title) > 200:
                section_title = section_title[:200] + "..."
        
        # Ensure both section_number and section_title are present
        # Final validation: ensure section_number is not empty
        if not section_number or section_number.strip() == "":
            # Try to extract from full_section_text as fallback
            number_match = re.search(r'(\d+[A-Za-z-]*)\.', full_section_text[:100])
            if number_match:
                section_number = number_match.group(1).strip()
            else:
                section_number = "Unknown"
        
        # Final validation: ensure section_title is not empty
        if not section_title or section_title.strip() == "":
            # Use section number as fallback title
            section_title = f"Section {section_number}"
        
        # Prepend section number and title to section_content (as it appears in original PDF)
        # Format: **{number}. {title}**— (consistent format as in PDF)
        if section_number and section_title and not is_omitted_section:
            # Format the header as it appears in PDF: **6. Title**—
            section_header = f"**{section_number}. {section_title}**—"
            # Remove leading em dash from section_content if present (it's part of the header)
            if section_content.startswith('—'):
                section_content = section_content[1:].lstrip()
            # Prepend header to section_content
            section_content = section_header + section_content
        
        # Calculate page numbers from position_to_page using start_pos and end_pos
        section_pages = []
        if position_to_page:
            for pos in range(section_start_pos_raw, section_end_pos_raw):
                if pos in position_to_page:
                    section_pages.append(position_to_page[pos])
            section_pages = sorted(list(set(section_pages)))  # Remove duplicates and sort
        
        # Only append section if both number and title are present
        if section_number and section_title:
            sections.append({
                'number': section_number.strip(),
                'title': section_title.strip(),
                'text': section_content,
                'start_pos': section_start_pos_raw,
                'end_pos': section_end_pos_raw,
                'page_numbers': section_pages
            })
        elif match.re == section_pattern_asterisk_bold:
            # Debug: Print why asterisk_bold section was skipped
            print(f"DEBUG: Skipped asterisk_bold section at position {match.start()}")
            print(f"  Section number: {repr(section_number)}")
            print(f"  Section title: {repr(section_title)}")
            print(f"  Captured content: {repr(captured_content)}")
            print(f"  Match text: {repr(text[match.start():match.end()])}")
            print(f"  Full section text preview: {repr(full_section_text[:200])}")
    
    return sections


def assign_footnotes_to_child_chunk(
    child_chunk: LegalChildChunk,
    raw_text: str,
    position_to_page: Dict[int, int],
    all_footnotes: List[Dict[str, str]]
) -> None:
    """
    Find and assign footnotes to a child chunk based on superscript markers in its text span.
    
    Args:
        child_chunk: The child chunk to assign footnotes to
        raw_text: The raw text from which positions are calculated
        position_to_page: Dictionary mapping character position to page number
        all_footnotes: List of all footnote dictionaries from llamaparser_extractor
    """
    # Get child chunk positions from metadata
    start_pos_raw = child_chunk.metadata.get('start_pos_raw', -1)
    end_pos_raw = child_chunk.metadata.get('end_pos_raw', -1)
    
    if start_pos_raw == -1 or end_pos_raw == -1:
        # No valid positions, cannot assign footnotes
        return
    
    # Slice raw_text to get the exact text span for this child
    if start_pos_raw >= len(raw_text) or end_pos_raw > len(raw_text):
        return
    
    child_text_span = raw_text[start_pos_raw:end_pos_raw]
    
    # Pattern to match Unicode superscript digits (¹, ², ³, ⁴, ⁵, ⁶, ⁷, ⁸, ⁹, ⁰)
    superscript_pattern = re.compile(r'([¹²³⁴⁵⁶⁷⁸⁹⁰]+)')
    
    # Find all superscript markers in the child text span
    found_footnotes = []
    seen_marker_page_pairs = set()
    
    # Map Unicode superscripts to regular digits for normalization
    marker_map = {
        '¹': '1', '²': '2', '³': '3', '⁴': '4', '⁵': '5',
        '⁶': '6', '⁷': '7', '⁸': '8', '⁹': '9', '⁰': '0'
    }
    
    for match in superscript_pattern.finditer(child_text_span):
        # Get the superscript marker
        marker_unicode = match.group(1)
        
        # Get the local position of the marker in the child span
        local_pos = match.start()
        
        # Compute global character position in raw_text
        global_pos = start_pos_raw + local_pos
        
        # Get page number for this marker position
        marker_page_num = position_to_page.get(global_pos)
        if marker_page_num is None:
            continue
        
        # Normalize superscript marker to simple marker key
        marker_key = ''.join(marker_map.get(char, char) for char in marker_unicode)
        
        # Check if this superscript position matches a footnote's start_pos exactly
        # If it matches, it's the footnote itself in the text, not a reference, so skip it
        is_footnote_position = False
        for footnote_dict in all_footnotes:
            footnote_marker = str(footnote_dict.get('marker', ''))
            footnote_page = footnote_dict.get('page_number')
            footnote_start_pos = footnote_dict.get('start_pos', -1)
            
            # Skip if footnote doesn't have start_pos
            if footnote_start_pos == -1:
                continue
            
            # Normalize footnote marker for comparison
            footnote_marker_normalized = ''.join(marker_map.get(char, char) for char in footnote_marker)
            
            # Ensure both page numbers are comparable (convert to int if needed)
            try:
                footnote_page_int = int(footnote_page) if not isinstance(footnote_page, int) else footnote_page
                marker_page_int = int(marker_page_num) if not isinstance(marker_page_num, int) else marker_page_num
            except (ValueError, TypeError):
                continue
            
            # Check if marker and page match, and if the position matches exactly
            if (footnote_marker_normalized == marker_key and 
                footnote_page_int == marker_page_int and
                footnote_start_pos == global_pos):
                # This superscript is at the exact position of a footnote's start
                # It's the footnote itself, not a reference - skip it
                is_footnote_position = True
                break
        
        # Skip if this superscript is at a footnote's start position
        if is_footnote_position:
            continue
        
        # Create a key for deduplication (marker + page combination)
        dedup_key = (marker_key, marker_page_num)
        if dedup_key in seen_marker_page_pairs:
            continue
        seen_marker_page_pairs.add(dedup_key)
        
        # Search in all_footnotes for entries matching this marker AND page number
        for footnote_dict in all_footnotes:
            footnote_marker = str(footnote_dict.get('marker', ''))
            footnote_page = footnote_dict.get('page_number')
            footnote_text = footnote_dict.get('text', '')
            
            # Skip if footnote_page is None or doesn't match
            if footnote_page is None:
                continue
            
            # Ensure both page numbers are comparable (convert to int if needed)
            try:
                footnote_page_int = int(footnote_page) if not isinstance(footnote_page, int) else footnote_page
                marker_page_int = int(marker_page_num) if not isinstance(marker_page_num, int) else marker_page_num
            except (ValueError, TypeError):
                continue
            
            # Normalize footnote marker for comparison
            footnote_marker_normalized = ''.join(marker_map.get(char, char) for char in footnote_marker)
            
            # Check if marker AND page number match (both must match exactly)
            if footnote_marker_normalized == marker_key and footnote_page_int == marker_page_int:
                # Create structured footnote entry
                if footnote_text:
                    footnote_entry = f"{marker_unicode}{footnote_text}".strip()
                else:
                    footnote_entry = marker_unicode
                found_footnotes.append(footnote_entry)
                break  # Found match for this (marker, page) pair, move to next marker
    
    # Assign found footnotes to child chunk
    child_chunk.footnotes = found_footnotes


def check_and_assign_missing_footnotes(
    child_chunk: LegalChildChunk,
    all_footnotes: List[Dict[str, str]]
) -> None:
    """
    Additional check: Iterate through child chunk text and assign any missing footnotes
    based on superscript markers found in the text.
    
    This function checks if footnotes with matching superscript markers and page numbers
    are already assigned. If not, it assigns them.
    
    Args:
        child_chunk: The child chunk to check and assign missing footnotes to
        all_footnotes: List of all footnote dictionaries from llamaparser_extractor
    """
    if not child_chunk.text or not all_footnotes:
        return
    
    # Get page numbers for this child chunk from metadata
    child_pages = child_chunk.metadata.get('page_numbers', [])
    if not child_pages:
        return
    
    # Pattern to match Unicode superscript digits (¹, ², ³, ⁴, ⁵, ⁶, ⁷, ⁸, ⁹, ⁰)
    superscript_pattern = re.compile(r'([¹²³⁴⁵⁶⁷⁸⁹⁰]+)')
    
    # Map Unicode superscripts to regular digits for normalization
    marker_map = {
        '¹': '1', '²': '2', '³': '3', '⁴': '4', '⁵': '5',
        '⁶': '6', '⁷': '7', '⁸': '8', '⁹': '9', '⁰': '0'
    }
    
    # Get already assigned footnotes and extract their markers for quick lookup
    # Format of footnotes in child_chunk.footnotes: "¹text" or just "¹"
    assigned_markers = set()
    for footnote_entry in child_chunk.footnotes:
        # Extract the superscript marker from the footnote entry
        if footnote_entry:
            # The first character(s) should be the superscript marker
            marker_match = superscript_pattern.match(footnote_entry)
            if marker_match:
                marker_unicode = marker_match.group(1)
                marker_key = ''.join(marker_map.get(char, char) for char in marker_unicode)
                # Store (marker_key, page) pairs that are already assigned
                # We need to check against all pages in the chunk
                for page in child_pages:
                    assigned_markers.add((marker_key, page))
    
    # Find all superscript markers in the child chunk text
    found_markers = []
    for match in superscript_pattern.finditer(child_chunk.text):
        marker_unicode = match.group(1)
        marker_key = ''.join(marker_map.get(char, char) for char in marker_unicode)
        found_markers.append((marker_unicode, marker_key))
    
    # Check each found marker against all pages in the chunk
    missing_footnotes = []
    seen_marker_page_pairs = set()
    
    for marker_unicode, marker_key in found_markers:
        for page in child_pages:
            # Create deduplication key
            dedup_key = (marker_key, page)
            
            # Skip if already assigned or already processed
            if dedup_key in assigned_markers or dedup_key in seen_marker_page_pairs:
                continue
            
            seen_marker_page_pairs.add(dedup_key)
            
            # Search for matching footnote in all_footnotes
            for footnote_dict in all_footnotes:
                footnote_marker = str(footnote_dict.get('marker', ''))
                footnote_page = footnote_dict.get('page_number')
                footnote_text = footnote_dict.get('text', '')
                
                # Skip if footnote_page is None
                if footnote_page is None:
                    continue
                
                # Normalize footnote marker for comparison
                footnote_marker_normalized = ''.join(marker_map.get(char, char) for char in footnote_marker)
                
                # Ensure both page numbers are comparable (convert to int if needed)
                try:
                    footnote_page_int = int(footnote_page) if not isinstance(footnote_page, int) else footnote_page
                    chunk_page_int = int(page) if not isinstance(page, int) else page
                except (ValueError, TypeError):
                    continue
                
                # Check if marker AND page number match
                if footnote_marker_normalized == marker_key and footnote_page_int == chunk_page_int:
                    # Create structured footnote entry
                    if footnote_text:
                        footnote_entry = f"{marker_unicode}{footnote_text}".strip()
                    else:
                        footnote_entry = marker_unicode
                    missing_footnotes.append(footnote_entry)
                    break  # Found match for this (marker, page) pair, move to next
    
    # Add missing footnotes to the child chunk
    if missing_footnotes:
        child_chunk.footnotes.extend(missing_footnotes)


def normalize_raw_section_span_like_pipeline(
    raw_text: str,
    start_pos: int,
    end_pos: int,
    position_to_page: Optional[Dict[int, int]],
    all_footnotes: Optional[List[Dict[str, str]]],
    section_title: str,
) -> str:
    """
    Mirror process_legal_text() section-body normalization on raw_text[start:end]
    (through remove_footnotes → clean_text / schedule → … → normalize_for_parent),
    so the result aligns with section['text'] used for parent splitting.
    """
    if start_pos < 0 or end_pos > len(raw_text) or start_pos >= end_pos:
        return ""
    span = raw_text[start_pos:end_pos]
    if all_footnotes:
        span = remove_footnotes_from_section_text(
            span, raw_text, start_pos, end_pos, position_to_page, all_footnotes
        )
    is_schedule = (section_title or "").strip().startswith("SCHEDULE")
    if is_schedule:
        span = normalize_schedule_section_text(span)
    else:
        span, _ = clean_text(span, None, skip_toc_detection=True)
    span = fix_broken_words(span)
    span = clean_markdown_artifacts(span)
    span = remove_separators_from_text(span)
    span = remove_chapters_articles_parts_headings(span)
    span = normalize_for_parent(span)
    return span


def find_parent_chunk_in_raw_text(
    parent_text_normalized: str,
    section_start_pos_raw: int,
    section_end_pos_raw: int,
    raw_text: str,
    position_to_page: Optional[Dict[int, int]] = None,
    all_footnotes: Optional[List[Dict[str, str]]] = None,
    section_title: str = "",
    hint_rel_start: Optional[int] = None,
    hint_rel_end: Optional[int] = None,
    section_text_normalized: Optional[str] = None,
) -> Tuple[int, int]:
    """
    Find the exact start_pos and end_pos of a normalized parent chunk in raw_text.
    
    Strategy: Normalize the section segment from raw_text the same way the parent chunk was normalized,
    then find where the parent text appears in the normalized segment, and map the position back to raw_text.
    
    This accounts for:
    - Markdown removal (** and ```)
    - Long underscore line removal
    - RGN date removal
    - Whitespace normalization (for parent: preserve structure but normalize newlines)
    
    When position_to_page is provided, uses the full section pipeline (footnote removal only if
    all_footnotes is non-empty) so normalized offsets match section['text'] (Problem 1).

    Args:
        parent_text_normalized: The normalized parent chunk text
        section_start_pos_raw: Start position of section in raw_text
        section_end_pos_raw: End position of section in raw_text
        raw_text: The raw unprocessed text
        position_to_page: If set, run full pipeline normalization on raw spans
        all_footnotes: Footnote list (optional); empty/None skips footnote stripping step
        section_title: Section title (SCHEDULE branch)
        hint_rel_start / hint_rel_end: Offsets of this part within normalized section text (ratio fallback)
        section_text_normalized: Full normalized section string (hints / ratio denominator)

    Returns:
        Tuple of (start_pos_raw, end_pos_raw) in raw_text, or (-1, -1) if not found
    """
    if section_start_pos_raw == -1 or section_end_pos_raw == -1:
        return (-1, -1)
    
    if section_start_pos_raw >= len(raw_text) or section_end_pos_raw > len(raw_text):
        return (-1, -1)
    
    # Extract the section's segment from raw_text
    section_segment_raw = raw_text[section_start_pos_raw:section_end_pos_raw]
    # Full pipeline needs page map; footnote list may be empty (no footnotes on document).
    use_pipeline = position_to_page is not None

    def norm_raw_span(rel_a: int, rel_b: int) -> str:
        """Normalize raw_text[section_start+rel_a : section_start+rel_b] like section pipeline."""
        rel_a = max(0, min(rel_a, len(section_segment_raw)))
        rel_b = max(rel_a, min(rel_b, len(section_segment_raw)))
        ra = section_start_pos_raw + rel_a
        rb = section_start_pos_raw + rel_b
        if ra >= rb:
            return ""
        if use_pipeline:
            return normalize_raw_section_span_like_pipeline(
                raw_text, ra, rb, position_to_page, all_footnotes or [], section_title
            )
        return normalize_for_parent(clean_markdown_artifacts(raw_text[ra:rb]))

    # Normalize the section segment to match section['text'] + final normalize_for_parent
    if use_pipeline:
        section_segment_normalized = norm_raw_span(0, len(section_segment_raw))
    else:
        section_segment_normalized = clean_markdown_artifacts(section_segment_raw)
        section_segment_normalized = normalize_for_parent(section_segment_normalized)
    
    # Find the parent text in the normalized section segment
    # Try with progressively shorter search keys for robustness
    search_keys = [
        parent_text_normalized[:min(200, len(parent_text_normalized))],
        parent_text_normalized[:min(100, len(parent_text_normalized))],
        parent_text_normalized[:min(50, len(parent_text_normalized))],
        parent_text_normalized[:min(20, len(parent_text_normalized))]
    ]
    
    rel_start_normalized = -1
    for search_key in search_keys:
        rel_start_normalized = section_segment_normalized.find(search_key)
        if rel_start_normalized != -1:
            break
    
    if rel_start_normalized == -1:
        # Could not find match - return fallback using ratio (prefer hints in normalized section text)
        hint_denom = len(section_text_normalized) if section_text_normalized else len(section_segment_normalized)
        if hint_denom > 0 and len(parent_text_normalized) > 0:
            if (
                section_text_normalized
                and hint_rel_start is not None
                and hint_rel_end is not None
                and hint_rel_start >= 0
                and hint_rel_end > hint_rel_start
            ):
                estimated_start_ratio = max(0.0, min(1.0, hint_rel_start / hint_denom))
                estimated_end_ratio = max(estimated_start_ratio, min(1.0, hint_rel_end / hint_denom))
            else:
                estimated_start_ratio = 0.0
                estimated_end_ratio = min(
                    1.0, len(parent_text_normalized) / len(section_segment_normalized)
                ) if len(section_segment_normalized) > 0 else 0.0
            rel_start_raw = int(estimated_start_ratio * len(section_segment_raw))
            rel_end_raw = int(estimated_end_ratio * len(section_segment_raw))
            return (section_start_pos_raw + rel_start_raw, section_start_pos_raw + rel_end_raw)
        return (-1, -1)
    
    # Find the exact end position in normalized segment by matching the end of parent_text_normalized
    # Use the last portion of parent_text_normalized as a search key for end position
    end_search_keys = [
        parent_text_normalized[-min(200, len(parent_text_normalized)):],
        parent_text_normalized[-min(100, len(parent_text_normalized)):],
        parent_text_normalized[-min(50, len(parent_text_normalized)):],
        parent_text_normalized[-min(20, len(parent_text_normalized)):]
    ]
    
    rel_end_normalized = -1
    used_end_search_key = None
    for end_search_key in end_search_keys:
        # Search for end key starting from rel_start_normalized
        search_start = rel_start_normalized
        found_pos = section_segment_normalized.find(end_search_key, search_start)
        if found_pos != -1:
            # Found the end key, calculate the end position
            rel_end_normalized = found_pos + len(end_search_key)
            used_end_search_key = end_search_key
            break
    
    # If end search failed, use length-based calculation as fallback
    if rel_end_normalized == -1:
        rel_end_normalized = rel_start_normalized + len(parent_text_normalized)
    
    # Now map normalized positions back to raw positions
    # Strategy: Use a sliding window approach to find the corresponding text in raw segment
    # by normalizing windows of the raw segment and matching
    
    # For start position: search_key is a prefix of parent_text_normalized (already pipeline-normalized).
    sk0 = search_keys[0] if search_keys else parent_text_normalized[:50]
    if use_pipeline:
        search_key_normalized = sk0
    else:
        search_key_normalized = normalize_for_parent(clean_markdown_artifacts(sk0))
    
    # Use ratio-based estimation with refinement
    if len(section_segment_normalized) > 0:
        start_ratio = rel_start_normalized / len(section_segment_normalized)
        end_ratio = rel_end_normalized / len(section_segment_normalized)
        
        # Estimate raw positions
        estimated_rel_start_raw = int(start_ratio * len(section_segment_raw))
        estimated_rel_end_raw = int(end_ratio * len(section_segment_raw))
        
        # Refine start position by searching around estimated position
        search_window = min(500, len(section_segment_raw) // 2)
        search_start = max(0, estimated_rel_start_raw - search_window)
        search_end = min(len(section_segment_raw), estimated_rel_start_raw + search_window + len(search_key_normalized))
        
        # Normalize search window and find exact match
        search_window_normalized = norm_raw_span(search_start, search_end)
        
        window_match_pos = search_window_normalized.find(search_key_normalized)
        
        if window_match_pos != -1:
            # Found exact match - refine start position
            rel_start_raw = search_start + window_match_pos
            
            # For end position, use a similar sliding window approach
            remaining_raw = section_segment_raw[rel_start_raw:]
            remaining_normalized = norm_raw_span(rel_start_raw, len(section_segment_raw))
            
            # Find where full parent_text_normalized appears
            if parent_text_normalized in remaining_normalized:
                parent_start_in_remaining = remaining_normalized.find(parent_text_normalized)
                parent_end_in_remaining = parent_start_in_remaining + len(parent_text_normalized)
                
                # Map back using ratio
                if len(remaining_normalized) > 0:
                    end_ratio_remaining = parent_end_in_remaining / len(remaining_normalized)
                    rel_end_raw = rel_start_raw + int(end_ratio_remaining * len(remaining_raw))
                else:
                    rel_end_raw = estimated_rel_end_raw
            elif used_end_search_key:
                # Try to find the end search key in remaining normalized text
                if use_pipeline:
                    end_key_normalized = used_end_search_key
                else:
                    end_key_normalized = normalize_for_parent(clean_markdown_artifacts(used_end_search_key))
                
                end_key_pos = remaining_normalized.find(end_key_normalized)
                if end_key_pos != -1:
                    # Found end key, calculate end position
                    end_key_end_in_remaining = end_key_pos + len(end_key_normalized)
                    if len(remaining_normalized) > 0:
                        end_ratio_remaining = end_key_end_in_remaining / len(remaining_normalized)
                        rel_end_raw = rel_start_raw + int(end_ratio_remaining * len(remaining_raw))
                    else:
                        rel_end_raw = estimated_rel_end_raw
                else:
                    # Use ratio-based estimation
                    rel_end_raw = estimated_rel_end_raw
            else:
                # Use ratio-based estimation
                rel_end_raw = estimated_rel_end_raw
        else:
            # Use ratio-based estimation
            rel_start_raw = estimated_rel_start_raw
            rel_end_raw = estimated_rel_end_raw
    else:
        return (-1, -1)
    
    # Verify end position is after start position
    if rel_end_raw <= rel_start_raw:
        # End should be after start, use minimum length
        rel_end_raw = rel_start_raw + max(len(parent_text_normalized) // 2, 100)
    
    # Map to global raw_text positions
    parent_start_pos_raw = section_start_pos_raw + rel_start_raw
    parent_end_pos_raw = section_start_pos_raw + rel_end_raw
    
    # Verify the found positions by checking if the extracted text matches
    if parent_start_pos_raw != -1 and parent_end_pos_raw != -1:
        # Extract text from raw_text at found positions
        found_raw_text = raw_text[parent_start_pos_raw:parent_end_pos_raw]
        if use_pipeline:
            found_normalized = normalize_raw_section_span_like_pipeline(
                raw_text,
                parent_start_pos_raw,
                parent_end_pos_raw,
                position_to_page,
                all_footnotes or [],
                section_title,
            )
        else:
            found_normalized = normalize_for_parent(clean_markdown_artifacts(found_raw_text))
        
        # Check if found text contains the parent text (allowing for small differences)
        # The found text should start with parent_text_normalized or vice versa
        if found_normalized.startswith(parent_text_normalized[:min(50, len(parent_text_normalized))]) or \
           parent_text_normalized.startswith(found_normalized[:min(50, len(found_normalized))]):
            # Positions are likely correct
            pass
        else:
            # Try to refine end position by searching for exact match
            remaining_raw_verify = section_segment_raw[rel_start_raw:]
            remaining_normalized = norm_raw_span(rel_start_raw, len(section_segment_raw))
            
            # Find exact match of parent_text_normalized
            exact_match_pos = remaining_normalized.find(parent_text_normalized)
            if exact_match_pos != -1:
                exact_end_in_remaining = exact_match_pos + len(parent_text_normalized)
                if len(remaining_normalized) > 0:
                    end_ratio_refined = exact_end_in_remaining / len(remaining_normalized)
                    rel_end_raw_refined = rel_start_raw + int(end_ratio_refined * len(remaining_raw_verify))
                    parent_end_pos_raw = section_start_pos_raw + rel_end_raw_refined
    
    return (parent_start_pos_raw, parent_end_pos_raw)


def find_child_chunk_in_raw_text(
    child_text_normalized: str,
    parent_start_pos_raw: int,
    parent_end_pos_raw: int,
    raw_text: str
) -> Tuple[int, int]:
    """
    Find the exact start_pos and end_pos of a normalized child chunk in raw_text.
    
    This function normalizes a segment of raw_text the same way the child chunk was normalized,
    then finds where the child chunk text appears in that normalized segment, and maps the
    position back to raw_text by building a character mapping during normalization.
    
    The key insight: We normalize the parent segment from raw_text the same way we normalized
    the child chunk, then find the child text in the normalized segment, and use position
    mapping to translate back to raw_text coordinates.
    
    Args:
        child_text_normalized: The normalized child chunk text
        parent_start_pos_raw: Start position of parent chunk in raw_text
        parent_end_pos_raw: End position of parent chunk in raw_text
        raw_text: The raw unprocessed text
        
    Returns:
        Tuple of (start_pos_raw, end_pos_raw) in raw_text, or (-1, -1) if not found
    """
    if parent_start_pos_raw == -1 or parent_end_pos_raw == -1:
        return (-1, -1)
    
    if parent_start_pos_raw >= len(raw_text) or parent_end_pos_raw > len(raw_text):
        return (-1, -1)
    
    # Extract the parent's segment from raw_text
    parent_segment_raw = raw_text[parent_start_pos_raw:parent_end_pos_raw]
    
    # Build a mapping from normalized positions to raw positions
    # by tracking character positions during normalization step-by-step
    normalized_to_raw_map = {}  # Maps normalized position -> list of raw positions
    
    # Step 1: Apply clean_markdown_artifacts and track positions
    # Build mapping by processing character by character to track position changes
    text_after_markdown_list = []
    raw_to_intermediate_map = {}  # Maps intermediate position -> raw position
    
    i = 0
    while i < len(parent_segment_raw):
        # Check for ** pattern (bold markers) - skip both characters
        if i + 1 < len(parent_segment_raw) and parent_segment_raw[i:i+2] == '**':
            i += 2  # Skip **
            continue
        # Check for ``` pattern (code blocks) - skip all three characters
        if i + 2 < len(parent_segment_raw) and parent_segment_raw[i:i+3] == '```':
            i += 3  # Skip ```
            continue
        
        # Keep this character
        intermediate_pos = len(text_after_markdown_list)
        text_after_markdown_list.append(parent_segment_raw[i])
        raw_to_intermediate_map[intermediate_pos] = i
        i += 1
    
    text_after_markdown_str = ''.join(text_after_markdown_list)
    
    # Step 2: Apply normalize_for_child transformations
    # normalize_for_child does:
    # 1. Remove underscores that appear 5 or more times consecutively
    # 2. Remove long underscore lines (^[_\s]{20,}$)
    # 3. Remove RGN dates
    # 4. Replace all whitespace with single space
    
    # First, remove underscores that appear 5 or more times consecutively
    temp_text = re.sub(r'_{5,}', '', text_after_markdown_str)
    
    # Then, remove long underscore lines and RGN dates (these use regex, harder to track exactly)
    # We'll apply the regex and note that positions may shift slightly
    temp_text = re.sub(r'^[_\s]{20,}$', '', temp_text, flags=re.MULTILINE)
    temp_text = re.sub(r'\bRGN\s+Date:\s*\d{2}-\d{2}-\d{4}\b', '', temp_text, flags=re.IGNORECASE)
    temp_text = re.sub(r'\bRGN\s+\d+/\d+\b', '', temp_text, flags=re.IGNORECASE)
    
    # Normalize spaces around brackets (same as normalize_for_child does)
    # Remove spaces immediately after [ and before ]
    temp_text = re.sub(r'\[\s+', '[', temp_text)
    temp_text = re.sub(r'\s+\]', ']', temp_text)
    
    # For position mapping after regex removals, we'll use a simpler approach:
    # Build a new mapping by finding where characters from temp_text appear in text_after_markdown_str
    # This is approximate but should work for most cases
    temp_to_intermediate_map = {}
    temp_idx = 0
    for intermediate_pos in range(len(text_after_markdown_str)):
        if temp_idx < len(temp_text):
            # Check if this character matches
            if text_after_markdown_str[intermediate_pos] == temp_text[temp_idx]:
                temp_to_intermediate_map[temp_idx] = intermediate_pos
                temp_idx += 1
    
    # Step 3: Replace all whitespace with single space
    final_normalized = []
    normalized_to_raw_map_final = {}
    
    prev_was_space = False
    for temp_pos, char in enumerate(temp_text):
        if char.isspace():
            # Replace with single space (only if previous wasn't space)
            if not prev_was_space:
                final_norm_pos = len(final_normalized)
                final_normalized.append(' ')
                # Map to the raw position via intermediate
                if temp_pos in temp_to_intermediate_map:
                    intermediate_pos = temp_to_intermediate_map[temp_pos]
                    if intermediate_pos in raw_to_intermediate_map:
                        raw_pos = raw_to_intermediate_map[intermediate_pos]
                        if final_norm_pos not in normalized_to_raw_map_final:
                            normalized_to_raw_map_final[final_norm_pos] = []
                        normalized_to_raw_map_final[final_norm_pos].append(raw_pos)
                prev_was_space = True
        else:
            final_norm_pos = len(final_normalized)
            final_normalized.append(char)
            # Map to the raw position via intermediate
            if temp_pos in temp_to_intermediate_map:
                intermediate_pos = temp_to_intermediate_map[temp_pos]
                if intermediate_pos in raw_to_intermediate_map:
                    raw_pos = raw_to_intermediate_map[intermediate_pos]
                    if final_norm_pos not in normalized_to_raw_map_final:
                        normalized_to_raw_map_final[final_norm_pos] = []
                    normalized_to_raw_map_final[final_norm_pos].append(raw_pos)
            prev_was_space = False
    
    parent_segment_normalized = ''.join(final_normalized)
    
    # Find the child text in the normalized parent segment
    # Try with progressively shorter search keys for robustness
    # Also create normalized versions that handle spacing differences around brackets
    # Note: re is already imported at module level
    
    # Normalize spaces around brackets for more flexible matching
    def normalize_bracket_spaces(text):
        # Remove spaces immediately after [ and before ]
        text = re.sub(r'\[\s+', '[', text)
        text = re.sub(r'\s+\]', ']', text)
        return text
    
    child_normalized_no_bracket_spaces = normalize_bracket_spaces(child_text_normalized)
    parent_normalized_no_bracket_spaces = normalize_bracket_spaces(parent_segment_normalized)
    
    search_keys = [
        child_text_normalized[:min(200, len(child_text_normalized))],
        child_text_normalized[:min(100, len(child_text_normalized))],
        child_text_normalized[:min(50, len(child_text_normalized))],
        child_text_normalized[:min(20, len(child_text_normalized))]
    ]
    
    # Also try with normalized bracket spaces
    search_keys_no_bracket_spaces = [
        child_normalized_no_bracket_spaces[:min(200, len(child_normalized_no_bracket_spaces))],
        child_normalized_no_bracket_spaces[:min(100, len(child_normalized_no_bracket_spaces))],
        child_normalized_no_bracket_spaces[:min(50, len(child_normalized_no_bracket_spaces))],
        child_normalized_no_bracket_spaces[:min(20, len(child_normalized_no_bracket_spaces))]
    ]
    
    rel_start_normalized = -1
    used_search_key = None
    used_parent_segment = parent_segment_normalized
    
    # First try exact matches
    for search_key in search_keys:
        rel_start_normalized = parent_segment_normalized.find(search_key)
        if rel_start_normalized != -1:
            used_search_key = search_key
            break
    
    # If exact match fails, try with normalized bracket spaces
    if rel_start_normalized == -1:
        for search_key in search_keys_no_bracket_spaces:
            rel_start_normalized = parent_normalized_no_bracket_spaces.find(search_key)
            if rel_start_normalized != -1:
                used_search_key = search_key
                used_parent_segment = parent_normalized_no_bracket_spaces
                break
    
    if rel_start_normalized == -1:
        # Could not find exact match - try more flexible matching strategies
        # Strategy 1: Try word-based matching (extract first few words and search)
        child_words = child_text_normalized.split()[:10]  # First 10 words
        if len(child_words) >= 3:
            # Try to find a sequence of words from child in parent
            word_sequence = ' '.join(child_words)
            rel_start_normalized = parent_segment_normalized.find(word_sequence)
            if rel_start_normalized != -1:
                used_search_key = word_sequence
                # Adjust to find the actual start (might be mid-word)
                # Look backwards to find the start of the word/sentence
                while rel_start_normalized > 0 and parent_segment_normalized[rel_start_normalized - 1] not in ' \n':
                    rel_start_normalized -= 1
        
        # Strategy 2: Try with normalized bracket spaces (already tried above, but try again with word-based)
        if rel_start_normalized == -1:
            child_words_no_brackets = child_normalized_no_bracket_spaces.split()[:10]
            if len(child_words_no_brackets) >= 3:
                word_sequence = ' '.join(child_words_no_brackets)
                rel_start_normalized = parent_normalized_no_bracket_spaces.find(word_sequence)
                if rel_start_normalized != -1:
                    used_search_key = word_sequence
                    used_parent_segment = parent_normalized_no_bracket_spaces
                    while rel_start_normalized > 0 and used_parent_segment[rel_start_normalized - 1] not in ' \n':
                        rel_start_normalized -= 1
        
        # Strategy 3: Try to find by matching significant words (non-common words)
        if rel_start_normalized == -1:
            # Extract significant words (longer than 4 chars, not common words)
            common_words = {'the', 'and', 'or', 'but', 'for', 'with', 'this', 'that', 'from', 'shall', 'may', 'any'}
            child_significant_words = [w for w in child_text_normalized.split() 
                                     if len(w) > 4 and w.lower() not in common_words][:5]
            if len(child_significant_words) >= 2:
                # Try to find these words in sequence in parent
                for i in range(len(child_significant_words) - 1):
                    word1 = child_significant_words[i]
                    word2 = child_significant_words[i + 1]
                    # Find word1, then check if word2 appears nearby
                    pos1 = parent_segment_normalized.find(word1)
                    if pos1 != -1:
                        # Look for word2 within reasonable distance (up to 200 chars)
                        search_end = min(pos1 + 200, len(parent_segment_normalized))
                        pos2 = parent_segment_normalized.find(word2, pos1, search_end)
                        if pos2 != -1:
                            # Found both words, use pos1 as start
                            rel_start_normalized = pos1
                            used_search_key = word1
                            break
        
        # Strategy 4: Use ratio-based estimation as last resort
        # If child text is a significant portion of parent, estimate position
        if rel_start_normalized == -1:
            # Try to estimate based on the assumption that child appears somewhere in parent
            # Use a simple heuristic: if child length is reasonable compared to parent,
            # estimate it's in the middle portion (where most content usually is)
            if len(child_text_normalized) > 50 and len(child_text_normalized) < len(parent_segment_normalized) * 0.8:
                # Estimate start position (try middle 60% of parent segment)
                estimated_start_ratio = 0.2  # Start searching from 20% into parent
                rel_start_normalized = int(len(parent_segment_normalized) * estimated_start_ratio)
                # Try to find any matching substring from this estimated position
                # Look for first 30 chars of child
                search_key_short = child_text_normalized[:30]
                found_pos = parent_segment_normalized.find(search_key_short, rel_start_normalized)
                if found_pos != -1:
                    rel_start_normalized = found_pos
                    used_search_key = search_key_short
                else:
                    # Even this failed, use ratio-based estimation
                    # Assume child starts at estimated position
                    rel_start_normalized = int(len(parent_segment_normalized) * estimated_start_ratio)
                    used_search_key = child_text_normalized[:20]  # Use short key for reference
    
    # Find the exact end position in normalized segment by matching the end of child_text_normalized
    # Use the last portion of child_text_normalized as a search key for end position
    end_search_keys = [
        child_text_normalized[-min(200, len(child_text_normalized)):],
        child_text_normalized[-min(100, len(child_text_normalized)):],
        child_text_normalized[-min(50, len(child_text_normalized)):],
        child_text_normalized[-min(20, len(child_text_normalized)):]
    ]
    
    rel_end_normalized = -1
    used_end_search_key = None
    
    # Try to find end position using the same parent segment that was used for start
    search_start = max(rel_start_normalized, 0)
    for end_search_key in end_search_keys:
        found_pos = used_parent_segment.find(end_search_key, search_start)
        if found_pos != -1:
            # Found the end key, calculate the end position
            rel_end_normalized = found_pos + len(end_search_key)
            used_end_search_key = end_search_key
            break
    
    # If exact match fails, try word-based matching for end
    if rel_end_normalized == -1:
        child_end_words = child_text_normalized.split()[-5:]  # Last 5 words
        if len(child_end_words) >= 2:
            word_sequence = ' '.join(child_end_words)
            found_pos = used_parent_segment.find(word_sequence, search_start)
            if found_pos != -1:
                rel_end_normalized = found_pos + len(word_sequence)
                used_end_search_key = word_sequence
    
    # If end search still failed, use length-based calculation as fallback
    if rel_end_normalized == -1:
        # Calculate end based on start + child length, but ensure it's within parent bounds
        estimated_end = rel_start_normalized + len(child_text_normalized)
        rel_end_normalized = min(estimated_end, len(used_parent_segment))
    
    # Map normalized start position back to raw position
    # Find the raw position that corresponds to rel_start_normalized
    rel_start_raw = -1
    if rel_start_normalized in normalized_to_raw_map_final:
        raw_start_positions = normalized_to_raw_map_final[rel_start_normalized]
        rel_start_raw = min(raw_start_positions)  # Use earliest position
    else:
        # Find closest mapped position
        if normalized_to_raw_map_final:
            closest_norm_pos = min(normalized_to_raw_map_final.keys(), 
                                  key=lambda x: abs(x - rel_start_normalized))
            rel_start_raw = min(normalized_to_raw_map_final[closest_norm_pos])
        else:
            # Last resort: use ratio-based estimation
            if len(parent_segment_normalized) > 0:
                ratio = rel_start_normalized / len(parent_segment_normalized)
                rel_start_raw = int(ratio * len(parent_segment_raw))
            else:
                rel_start_raw = 0
    
    # Map normalized end position back to raw position
    # First, try to find the end search key in the remaining raw segment
    if used_end_search_key and rel_start_raw != -1:
        # Get remaining raw segment from start position
        remaining_raw = parent_segment_raw[rel_start_raw:]
        remaining_normalized = clean_markdown_artifacts(remaining_raw)
        remaining_normalized = normalize_for_child(remaining_normalized)
        
        # Find where the full child_text_normalized appears in remaining normalized
        if child_text_normalized in remaining_normalized:
            child_start_in_remaining = remaining_normalized.find(child_text_normalized)
            child_end_in_remaining = child_start_in_remaining + len(child_text_normalized)
            
            # Map back using ratio
            if len(remaining_normalized) > 0:
                end_ratio_remaining = child_end_in_remaining / len(remaining_normalized)
                rel_end_raw = rel_start_raw + int(end_ratio_remaining * len(remaining_raw))
            else:
                # Fallback to mapping from normalized position
                end_search_pos = min(rel_end_normalized - 1, len(parent_segment_normalized) - 1)
                if end_search_pos in normalized_to_raw_map_final:
                    raw_end_positions = normalized_to_raw_map_final[end_search_pos]
                    rel_end_raw = max(raw_end_positions)
                else:
                    # Use ratio fallback
                    if len(parent_segment_normalized) > 0:
                        ratio = rel_end_normalized / len(parent_segment_normalized)
                        rel_end_raw = int(ratio * len(parent_segment_raw))
                    else:
                        rel_end_raw = len(parent_segment_raw)
        else:
            # Try to find the end search key
            end_key_normalized = clean_markdown_artifacts(used_end_search_key)
            end_key_normalized = normalize_for_child(end_key_normalized)
            
            end_key_pos = remaining_normalized.find(end_key_normalized)
            if end_key_pos != -1:
                # Found end key, calculate end position
                end_key_end_in_remaining = end_key_pos + len(end_key_normalized)
                if len(remaining_normalized) > 0:
                    end_ratio_remaining = end_key_end_in_remaining / len(remaining_normalized)
                    rel_end_raw = rel_start_raw + int(end_ratio_remaining * len(remaining_raw))
                else:
                    # Fallback to mapping from normalized position
                    end_search_pos = min(rel_end_normalized - 1, len(parent_segment_normalized) - 1)
                    if end_search_pos in normalized_to_raw_map_final:
                        raw_end_positions = normalized_to_raw_map_final[end_search_pos]
                        rel_end_raw = max(raw_end_positions)
                    else:
                        if len(parent_segment_normalized) > 0:
                            ratio = rel_end_normalized / len(parent_segment_normalized)
                            rel_end_raw = int(ratio * len(parent_segment_raw))
                        else:
                            rel_end_raw = len(parent_segment_raw)
            else:
                # Fallback to mapping from normalized position
                end_search_pos = min(rel_end_normalized - 1, len(parent_segment_normalized) - 1)
                if end_search_pos in normalized_to_raw_map_final:
                    raw_end_positions = normalized_to_raw_map_final[end_search_pos]
                    rel_end_raw = max(raw_end_positions)
                else:
                    if len(parent_segment_normalized) > 0:
                        ratio = rel_end_normalized / len(parent_segment_normalized)
                        rel_end_raw = int(ratio * len(parent_segment_raw))
                    else:
                        rel_end_raw = len(parent_segment_raw)
    else:
        # Fallback: map from normalized position
        end_search_pos = min(rel_end_normalized - 1, len(parent_segment_normalized) - 1)
        if end_search_pos in normalized_to_raw_map_final:
            raw_end_positions = normalized_to_raw_map_final[end_search_pos]
            rel_end_raw = max(raw_end_positions)  # Use latest position
        else:
            # Find closest mapped position
            if normalized_to_raw_map_final:
                closest_norm_pos = min(normalized_to_raw_map_final.keys(), 
                                      key=lambda x: abs(x - end_search_pos))
                rel_end_raw = max(normalized_to_raw_map_final[closest_norm_pos])
            else:
                # Fallback: estimate based on length ratio
                if len(parent_segment_normalized) > 0:
                    ratio = rel_end_normalized / len(parent_segment_normalized)
                    rel_end_raw = int(ratio * len(parent_segment_raw))
                else:
                    rel_end_raw = len(parent_segment_raw)
    
    # Verify end position is after start position
    if rel_end_raw <= rel_start_raw:
        # End should be after start, use minimum length
        rel_end_raw = rel_start_raw + max(len(child_text_normalized) // 2, 100)
    
    # Map to global raw_text positions
    child_start_pos_raw = parent_start_pos_raw + rel_start_raw
    child_end_pos_raw = parent_start_pos_raw + rel_end_raw
    
    # Verify and adjust the found positions
    # Ensure positions are valid and within parent bounds
    if child_start_pos_raw != -1 and child_end_pos_raw != -1:
        # Ensure positions are within parent chunk bounds
        if child_start_pos_raw < parent_start_pos_raw:
            child_start_pos_raw = parent_start_pos_raw
        if child_end_pos_raw > parent_end_pos_raw:
            child_end_pos_raw = parent_end_pos_raw
        if child_end_pos_raw <= child_start_pos_raw:
            # Invalid positions, use fallback
            child_start_pos_raw = parent_start_pos_raw
            child_end_pos_raw = min(parent_start_pos_raw + len(child_text_normalized) * 2, parent_end_pos_raw)
        
        # Verify positions are within raw_text bounds
        if child_start_pos_raw < 0:
            child_start_pos_raw = 0
        if child_end_pos_raw > len(raw_text):
            child_end_pos_raw = len(raw_text)
        
        # Optional verification: Extract text and check for reasonable match
        # This is a sanity check but we'll be lenient to handle edge cases
        if child_start_pos_raw < len(raw_text) and child_end_pos_raw <= len(raw_text) and child_end_pos_raw > child_start_pos_raw:
            found_raw_text = raw_text[child_start_pos_raw:child_end_pos_raw]
            found_normalized = clean_markdown_artifacts(found_raw_text)
            found_normalized = normalize_for_child(found_raw_text)
            
            # Check if found text contains significant portion of child text
            # Be lenient - if we find at least 30% match, accept it
            min_match_length = min(30, len(child_text_normalized) // 3)
            if min_match_length > 0 and len(found_normalized) >= min_match_length:
                child_start_snippet = child_text_normalized[:min_match_length]
                found_start_snippet = found_normalized[:min_match_length]
                
                # If there's reasonable overlap, positions are acceptable
                # Even if verification fails, we'll still return the positions
                # as they're the best estimate we have based on the matching strategies
    
    return (child_start_pos_raw, child_end_pos_raw)


def get_pages_for_span(position_to_page: Dict[int, int], start_pos: int, end_pos: int) -> List[int]:
    """
    Get all page numbers for a span of positions in raw_text.
    
    Args:
        position_to_page: Dictionary mapping character position to page number
        start_pos: Start position (inclusive)
        end_pos: End position (exclusive)
        
    Returns:
        Sorted list of unique page numbers
    """
    pages = set()
    for pos in range(start_pos, end_pos):
        if pos in position_to_page:
            pages.add(position_to_page[pos])
    return sorted(list(pages))


# ---------------------------------------------------------------------------
# Multi-level section extraction (used in process_legal_text):
#   Level 1: CHAPTER, PART, SCHEDULE (regexes with optional bold); section_name = type, number = Roman or '-'
#   Level 2: Within each Level-1 section, ORDER/ARTICLE+Roman, all-caps, Roman.—Title; updates section_name/number
#   Level 3: RecursiveCharacterTextSplitter with heading separators (+ '4.' and '2.__', optional bold); updates segment section_number/section_name
#   parent_id: base_name_{parent_idx} or base_name_{parent_idx}_{part_idx} when split by size (two iterators, no duplicate IDs)
# ---------------------------------------------------------------------------

# Level 1: Unnumbered structural headings (CHAPTER, PART, SCHEDULE) - search only after preamble
LEVEL1_PATTERN_CHAPTER_PART = re.compile(
    r"^\s*#{0,6}\s*(?:\*\*|__)?\s*(?:\s*[⁰¹²³⁴⁵⁶⁷⁸⁹]+\s*)*(CHAPTER|PART)(?:\s*[⁰¹²³⁴⁵⁶⁷⁸⁹]+\s*)*\s+([IVXLCDM]+)?(?:\s*[⁰¹²³⁴⁵⁶⁷⁸⁹]+\s*)*\s*(?:\*\*|__)?\s*$",
    re.MULTILINE | re.IGNORECASE
)
LEVEL1_PATTERN_SCHEDULE = re.compile(
    r"^\s*#{0,6}\s*(?:\*\*|__)?\s*(?:\s*[⁰¹²³⁴⁵⁶⁷⁸⁹]+\s*)*(?:THE(?:\s*[⁰¹²³⁴⁵⁶⁷⁸⁹]+\s*)*\s+)?(?:FIRST(?:\s*[⁰¹²³⁴⁵⁶⁷⁸⁹]+\s*)*\s+)?SCHEDULE(?:\s*[⁰¹²³⁴⁵⁶⁷⁸⁹]+\s*)*(?:\s+([IVXLCDM]+))?(?:\s*[⁰¹²³⁴⁵⁶⁷⁸⁹]+\s*)*\s*(?:\*\*|__)?\s*$",
    re.MULTILINE | re.IGNORECASE
)
LEVEL1_PATTERN_SCHEDULE_BRACKET = re.compile(
    r"^\s*#{0,6}\s*(?:\*\*|__)?\s*\[(?:\s*[⁰¹²³⁴⁵⁶⁷⁸⁹]+\s*)*SCHEDULE(?:\s*[⁰¹²³⁴⁵⁶⁷⁸⁹]+\s*)*\s*(?:\*\*|__)?\s*\]?\s*$",
    re.MULTILINE | re.IGNORECASE
)

# Level 2: ORDER/ARTICLE, all-caps headings, Roman.—Title (run within each Level-1 section)
LEVEL2_PATTERN_ALLCAPS = re.compile(
    r"^\s*(?:(\*\*|__)\s*(?:\s*[⁰¹²³⁴⁵⁶⁷⁸⁹]+\s*)*[A-Z][A-Z\s,'&\-()]+(?:\s*[⁰¹²³⁴⁵⁶⁷⁸⁹]+\s*)*\s*\1|(?:\s*[⁰¹²³⁴⁵⁶⁷⁸⁹]+\s*)*[A-Z][A-Z\s,'&\-()]+(?:\s*[⁰¹²³⁴⁵⁶⁷⁸⁹]+\s*)*)\s*$",
    re.MULTILINE
)
LEVEL2_PATTERN_ORDER_ARTICLE = re.compile(
    r"^\s*(?:(\*\*|__)\s*(?:\s*[⁰¹²³⁴⁵⁶⁷⁸⁹]+\s*)*(ORDER|ARTICLE)(?:\s*[⁰¹²³⁴⁵⁶⁷⁸⁹]+\s*)*\s+([IVXLCDM]+)(?:\s*[⁰¹²³⁴⁵⁶⁷⁸⁹]+\s*)*\s*\1|(?:\s*[⁰¹²³⁴⁵⁶⁷⁸⁹]+\s*)*(ORDER|ARTICLE)(?:\s*[⁰¹²³⁴⁵⁶⁷⁸⁹]+\s*)*\s+([IVXLCDM]+)(?:\s*[⁰¹²³⁴⁵⁶⁷⁸⁹]+\s*)*)\s*$",
    re.MULTILINE | re.IGNORECASE
)
LEVEL2_PATTERN_ROMAN_TITLE = re.compile(
    r"^\s*(?:(\*\*|__)\s*(?:\s*[⁰¹²³⁴⁵⁶⁷⁸⁹]+\s*)*([IVXLCDM]+)(?:\s*[⁰¹²³⁴⁵⁶⁷⁸⁹]+\s*)*\.(?:\s*[—-]\s*)?(?:\s*[⁰¹²³⁴⁵⁶⁷⁸⁹]+\s*)*[A-Za-z][A-Za-z\s,'&()\-]+(?:\s*[⁰¹²³⁴⁵⁶⁷⁸⁹]+\s*)*\s*\1|(?:\s*[⁰¹²³⁴⁵⁶⁷⁸⁹]+\s*)*([IVXLCDM]+)(?:\s*[⁰¹²³⁴⁵⁶⁷⁸⁹]+\s*)*\.(?:\s*[—-]\s*)?(?:\s*[⁰¹²³⁴⁵⁶⁷⁸⁹]+\s*)*[A-Za-z][A-Za-z\s,'&()\-]+(?:\s*[⁰¹²³⁴⁵⁶⁷⁸⁹]+\s*)*)\s*$",
    re.MULTILINE
)
LEVEL2_PATTERN_LETTER_TITLE = re.compile(
    r"^\s*#{0,6}\s*(?:\*\*|__|\*)?\s*([A-Z])\s*\.\s*[—–-]\s*([A-Za-z][^\n*]{0,220})\s*(?:\*\*|__|\*)?\s*$",
    re.MULTILINE
)

# Level 3: Separator patterns for RecursiveCharacterTextSplitter.
# Aligned with process_legal_text.py extract_sections + split_parent_chunk_by_id + '4.' and '2.__'.
# Order: full heading lines first, then patterns that match section headers (including variants from process_legal_text.py).
SEPARATOR_REGEXES_LEVEL3 = [
 # **NUMBER. Title**.  (period after closing bold, e.g. **10. Appeal**.)
 r"(?:\*\*|__)\s*\d+[A-Za-z-]*\.\s*[A-Za-z][^\n*]{0,220}(?:\*\*|__)\s*\.",
 # **NUMBER. Title** or **NUMBER. Title**— (no period required after closing bold)
 r"(?:\*\*|__)\s*\d+[A-Za-z-]*\.\s*[A-Za-z][^\n*]{0,220}(?:\*\*|__)\s*(?:—|–)?",
 # superscript + [ + number heading (e.g. ¹[8A. Power to try summarily.—...)
 r"[¹²³⁴⁵⁶⁷⁸⁹⁰]+\s*\[\s*\d+[A-Za-z-]*\.\s*[A-Z][^\n]{0,220}",
 # Full heading line:
# allowed:
#   **6. Authority.**
#   **6.** Authority.
#   6. **Authority.**
#   **5. ... etc.—**
r"(?:\*\*|__)\s*\d+[A-Za-z-]*\.\s+[A-Za-z][A-Za-z\s,'&()\-\u2014]*(?:\.|\.—|\.\u2014|\.--)\s*(?:\*\*|__)\s*(?:—|–)?|(?:\*\*|__)\s*\d+[A-Za-z-]*\.\s*(?:\*\*|__)\s+[A-Za-z][A-Za-z\s,'&()\-\u2014]*(?:\.|\.—|\.\u2014|\.--)\s*(?:—|–)?|\d+[A-Za-z-]*\.\s*(?:\*\*|__)\s*[A-Za-z][A-Za-z\s,'&()\-\u2014]*(?:\.|\.—|\.\u2014|\.--)\s*(?:\*\*|__)?\s*(?:—|–)?"

# **NUMBER. Title.** –
r"(?:\*\*|__)\s*\d+[A-Za-z-]*\s*\.\s+[¹²³⁴⁵⁶⁷⁸⁹⁰\w\s.,;:()\[\]—\-]+?\.\s*(?:\*\*|__)\s*(?:—|–)"

# Number outside bold, text bold:
# 15. **Sanction in case...**
r"\d+[A-Za-z-]*\s*\.\s*(?:\*\*|__)\s*[A-Za-z]"

# Triple asterisk OCR-ish case:
# ***15. Trial of offences.**—
r"\*\*\*\d+[A-Za-z-]*\s*\.\s*[A-Za-z]"

# superscript + bold whole heading
# ¹**1. Title**
r"[¹²³⁴⁵⁶⁷⁸⁹⁰]+\s*(?:\*\*|__)\s*\d+[A-Za-z-]*\s*\.\s*[A-Z]"

# bold opens before superscript + number
# **¹1. Title**
r"(?:\*\*|__)\s*[¹²³⁴⁵⁶⁷⁸⁹⁰]+\d+[A-Za-z-]*\s*\.\s*[A-Z]"

# bold opens before noisy OCR/superscript marker + number
# **�12. Title** / **⁸12. Title**
r"(?:\*\*|__)\s*[^\dA-Za-z\n]{0,6}\d+[A-Za-z-]*\s*\.\s*[A-Z]"

# superscript + [ + bold heading
# ¹[**1. Title**
r"[¹²³⁴⁵⁶⁷⁸⁹⁰]*\s*\[\s*(?:\*\*|__)\s*\d+[A-Za-z-]*\s*\.\s*[A-Z]"

# Standard full-line variant:
# whole heading bold OR number bold only OR text bold only
r"(?:\*\*|__)\s*\d+[A-Za-z-]*\.\s+[A-Za-z][A-Za-z\s,'&()\-\u2014]*(?:\.|\.—|\.\u2014)\s*(?:\*\*|__)|(?:\*\*|__)\s*\d+[A-Za-z-]*\.\s*(?:\*\*|__)\s+[A-Za-z][A-Za-z\s,'&()\-\u2014]*(?:\.|\.—|\.\u2014)|\d+[A-Za-z-]*\.\s+(?:\*\*|__)[A-Za-z][A-Za-z\s,'&()\-\u2014]*(?:\.|\.—|\.\u2014)\s*(?:\*\*|__)?"

# number + one word heading
# **12. Authority**
# **12.** Authority
# 12. **Authority**
r"(?:\*\*|__)\s*\d+\.\s+[A-Z][a-zA-Z]*(?:\s*(?:\*\*|__))?|(?:\*\*|__)\s*\d+\.\s*(?:\*\*|__)\s+[A-Z][a-zA-Z]*|\d+\.\s*(?:\*\*|__)[A-Z][a-zA-Z]*(?:\*\*|__)?"

# number + spaced dot + one word heading
# **12 . Authority**
# **12 .** Authority
# 12 . **Authority**
r"(?:\*\*|__)\s*\d+\s+\.\s*[A-Z][a-zA-Z]*(?:\s*(?:\*\*|__))?|(?:\*\*|__)\s*\d+\s+\.\s*(?:\*\*|__)\s*[A-Z][a-zA-Z]*|\d+\s+\.\s*(?:\*\*|__)[A-Z][a-zA-Z]*(?:\*\*|__)?"

# number-hyphen-word heading
# **12- Authority**
# **12-** Authority
# 12- **Authority**
r"(?:\*\*|__)\s*\d+-\s+[A-Z][a-zA-Z]*(?:\s*(?:\*\*|__))?|(?:\*\*|__)\s*\d+-\s*(?:\*\*|__)\s+[A-Z][a-zA-Z]*|\d+-\s*(?:\*\*|__)[A-Z][a-zA-Z]*(?:\*\*|__)?"

# number spaced-hyphen word heading
# **12 - Authority**
# **12 -** Authority
# 12 - **Authority**
r"(?:\*\*|__)\s*\d+\s+-\s*[A-Z][a-zA-Z]*(?:\s*(?:\*\*|__))?|(?:\*\*|__)\s*\d+\s+-\s*(?:\*\*|__)\s*[A-Z][a-zA-Z]*|\d+\s+-\s*(?:\*\*|__)[A-Z][a-zA-Z]*(?:\*\*|__)?"

# number_ word heading
# **12_ Authority**
# **12_** Authority
# 12_ **Authority**
r"(?:\*\*|__)\s*\d+_\s+[A-Z][a-zA-Z]*(?:\s*(?:\*\*|__))?|(?:\*\*|__)\s*\d+_\s*(?:\*\*|__)\s+[A-Z][a-zA-Z]*|\d+_\s*(?:\*\*|__)[A-Z][a-zA-Z]*(?:\*\*|__)?"

# number _ word heading
# **12 _ Authority**
# **12 _** Authority
# 12 _ **Authority**
r"(?:\*\*|__)\s*\d+\s+_\s*[A-Z][a-zA-Z]*(?:\s*(?:\*\*|__))?|(?:\*\*|__)\s*\d+\s+_\s*(?:\*\*|__)\s*[A-Z][a-zA-Z]*|\d+\s+_\s*(?:\*\*|__)[A-Z][a-zA-Z]*(?:\*\*|__)?"

# number-only heading: must have bold on the number part
# **12.**
r"(?:\*\*|__)\s*\d+\.\s*(?:\*\*|__)?"

# number + underscores only: must have bold on the number side
# **12 __**
# **12** __ __
r"(?:\*\*|__)\s*\d+\s*_\s*_\s*(?:\*\*|__)?"
# **12.**  or full number-side bold around the number only: **12**.
r"(?:\*\*|__)\s*\d+\.\s*(?:\*\*|__)?"

# **12**. / **12 **. / **12**- / **12 **- / **12**_ / **12 **_
r"(?:\*\*|__)\s*\d+\s*(?:\*\*|__)\s*[._-]"

# **12 __**
r"(?:\*\*|__)\s*\d+\s*_\s*_\s*(?:\*\*|__)?"
]
LITERAL_SEPARATORS_LEVEL3 = ["\n\n", "\n", ". ", " ", ""]

# Section separator patterns copied from process_legal_text.py extract_sections (used when building parent-chunk separators).
# These use ^ and some use . across lines; compile with re.MULTILINE | re.DOTALL when using.
SECTION_SEPARATOR_PATTERNS_FROM_PROCESS_LEGAL_TEXT = [
    # Main: **NUMBER. TITLE** or **NUMBER. TITLE.** with lookahead
    r'^\s*\*\*(\d+[A-Za-z-]*)\s*\.?\s*([¹²³⁴⁵⁶⁷⁸⁹⁰\w\s.,;:()\[\]—\-]*?)\s*\*\*\s*\.?(?=\s*\*\*\s*\.?\s*(?:—|–)|\s*(?:—|–)|\n\s*\*\*\d+[A-Za-z-]*\s*\.|\n|$)',
    # **1. ** [Omitted/Repealed/Deleted]
    r'^\s*\*\*(\d+[A-Za-z-]*)\.\s+\*\*\s*([¹²³⁴⁵⁶⁷⁸⁹⁰]*)(\[Omitted\]|\[Repealed\]|\[Deleted\])',
    # **1.** [Omitted/Repealed/Deleted]
    r'^\s*\*\*(\d+[A-Za-z-]*)\.\*\*\s*([¹²³⁴⁵⁶⁷⁸⁹⁰]*)(\[Omitted\]|\[Repealed\]|\[Deleted\])',
    # **7.** ³**[Omitted]** etc.
    r'^\s*\*\*(\d+[A-Za-z-]*)\.\*\*\s+([¹²³⁴⁵⁶⁷⁸⁹⁰]+)\s*\*\*(\[Omitted\]|\[Repealed\]|\[Deleted\])\s*\*\*',
    # ¹**1. Title**
    r'^\s*([¹²³⁴⁵⁶⁷⁸⁹⁰]+)\s*\*\*(\d+[A-Za-z-]*)\s*\.?\s*([¹²³⁴⁵⁶⁷⁸⁹⁰\w\s.,;:()\[\]—\-]*?)(?=\n\s*(?:[¹²³⁴⁵⁶⁷⁸⁹⁰]+\s*)?\*\*\d+[A-Za-z-]*\s*\.|$)',
    # ¹[**1. Title**]
    r'^\s*([¹²³⁴⁵⁶⁷⁸⁹⁰]+)\s*\[\s*\*\*(\d+[A-Za-z-]*)\s*\.?\s*([¹²³⁴⁵⁶⁷⁸⁹⁰\w\s.,;:()\[\]—\-]*?)(?=\n\s*(?:[¹²³⁴⁵⁶⁷⁸⁹⁰]+\s*)?\[?\s*\*\*\d+[A-Za-z-]*\s*\.|$)',
    # **¹1. Title**
    r'^\s*\*\*([¹²³⁴⁵⁶⁷⁸⁹⁰]+)(\d+[A-Za-z-]*)\s*\.?\s*([¹²³⁴⁵⁶⁷⁸⁹⁰\w\s.,;:()\[\]—\-]*?)(?=\n\s*\*\*[¹²³⁴⁵⁶⁷⁸⁹⁰]*\d+[A-Za-z-]*\s*\.|$)',
    # **�12. Title** / **⁸12. Title** (unknown OCR/superscript marker before number)
    r'^\s*\*\*\s*[^\dA-Za-z\n]{0,6}(\d+[A-Za-z-]*)\s*\.?\s*([^\n*]{1,260}?)\s*\*\*(?=\s*\.\s*(?:—|–)?|\s*(?:—|–)?|\n|$)',
    # **¹[1. Title** or **¹[8. Powers...**—
    r'^\s*\*\*([¹²³⁴⁵⁶⁷⁸⁹⁰]+)\[\s*(\d+[A-Za-z-]*)\s*\.?\s*([¹²³⁴⁵⁶⁷⁸⁹⁰\w\s.,;:()\[\]—\-]*?)(?:\s*\*\*\s*\.?)?(?=\s*\*\*\s*\.?\s*—|\s*—|\n\s*\*\*[¹²³⁴⁵⁶⁷⁸⁹⁰]*\[?\s*\d+[A-Za-z-]*\s*\.|\n|$)',
    # ²**[3A. Title**—
    r'^\s*([¹²³⁴⁵⁶⁷⁸⁹⁰]+)\s*\*\*\s*\[\s*(\d+[A-Za-z-]*)\s*\.?\s*([¹²³⁴⁵⁶⁷⁸⁹⁰\w\s.,;:()\[\]—\-]*?)(?:\s*\*\*\s*\.?)?(?=\s*—|\n\s*(?:[¹²³⁴⁵⁶⁷⁸⁹⁰]+\s*)?\*\*\s*\[?\s*\d+[A-Za-z-]*\s*\.|\n|$)',
    # ***15. Trial of offences.**— (start of line or after newline)
    r'(?:^|\n)\s*\*\*\*(\d+[A-Za-z-]*)\s*\.?\s*([¹²³⁴⁵⁶⁷⁸⁹⁰\w\s.,;:()\[\]—\-]+?)\s*\*\*\s*\.?(?=\s*—|\s+[A-Z¹²³⁴⁵⁶⁷⁸⁹⁰]|\n\s*\*\*\*\d+[A-Za-z-]*\s*\.|\n|$)',
    # *** anywhere in text
    r'\*\*\*(\d+[A-Za-z-]*)\s*\.?\s*([¹²³⁴⁵⁶⁷⁸⁹⁰\w\s.,;:()\[\]—\-]+?)\s*\*\*\s*\.?(?=\s*—|\s+[A-Z¹²³⁴⁵⁶⁷⁸⁹⁰]|\n\s*\*\*\*\d+[A-Za-z-]*\s*\.|\n|$)',
    # **\*NUMBER. Title**—
    r'\*\*\\\*(\d+[A-Za-z-]*)\s*\.?\s*([¹²³⁴⁵⁶⁷⁸⁹⁰\w\s.,;:()\[\]—\-]+?)\s*\*\*\s*\.?(?=\s*—|\s+[A-Z¹²³⁴⁵⁶⁷⁸⁹⁰]|\n\s*\*\*\\\*\d+[A-Za-z-]*\s*\.|\n|$)',
    # **NUMBER. Title.--**
    r'^\s*\*\*(\d+[A-Za-z-]*)\s*\.\s*([¹²³⁴⁵⁶⁷⁸⁹⁰\w\s.,;:()\[\]—\-]*?)\s*\.\s*(?:—|--)\s*\*\*',
    # **NUMBER. Title.** –
    r'^\s*\*\*(\d+[A-Za-z-]*)\s*\.\s*([¹²³⁴⁵⁶⁷⁸⁹⁰\w\s.,;:()\[\]—\-]*?)\s*\.\s*\*\*\s*(?:—|–)',
    # ** NUMBER. Title.**
    r'^\s*\*\*\s*(\d+[A-Za-z-]*)\s*\.\s*([¹²³⁴⁵⁶⁷⁸⁹⁰\w\s.,;:()\[\]—\-]*?)\s*\.\s*\*\*',
    # NUMBER. **Title.**
    r'^\s*(\d+[A-Za-z-]*)\s*\.\s*\*\*\s*([¹²³⁴⁵⁶⁷⁸⁹⁰\w\s.,;:()\[\]—\-]*?)\s*\.\s*\*\*',
]


def extract_level1_heading_sections(
    raw_text: str,
    position_to_page: Optional[Dict[int, int]],
    start_search_position: int,
    search_text: Optional[str] = None,
    transformed_to_raw: Optional[Callable[[int, int], Tuple[int, int]]] = None,
) -> List[Dict]:
    """
    Level 1: Extract CHAPTER, PART, SCHEDULE sections using the three level-1 regexes.
    If search_text and transformed_to_raw are provided, use search_text for pattern matching
    (so form/table placeholders avoid splitting) and map positions back to raw.
    Returns list of section dicts: number, title, text, start_pos, end_pos, page_numbers, section_name.
    """
    text_source = search_text if search_text is not None else raw_text
    if start_search_position >= len(text_source):
        return []
    text_to_search = text_source[start_search_position:]
    matches = []  # (match_start_global, match_end_global, section_name, full_match_text)

    for pattern in (LEVEL1_PATTERN_CHAPTER_PART, LEVEL1_PATTERN_SCHEDULE, LEVEL1_PATTERN_SCHEDULE_BRACKET):
        for m in pattern.finditer(text_to_search):
            g_start = start_search_position + m.start()
            g_end = start_search_position + m.end()
            section_name = "SCHEDULE"
            if pattern == LEVEL1_PATTERN_CHAPTER_PART:
                section_name = m.group(1).strip().upper()  # CHAPTER or PART
            elif pattern == LEVEL1_PATTERN_SCHEDULE:
                section_name = "SCHEDULE"
            elif pattern == LEVEL1_PATTERN_SCHEDULE_BRACKET:
                section_name = "SCHEDULE"
            matches.append((g_start, g_end, section_name, m.group(0)))
    matches.sort(key=lambda x: x[0])
    unique = []
    for t in matches:
        if not unique or t[0] - unique[-1][0] > 20:
            unique.append(t)
    matches = unique

    sections = []
    for i, (start_pos_t, end_pos_t, section_name, full_match_text) in enumerate(matches):
        end_bound_t = matches[i + 1][0] if i + 1 < len(matches) else len(text_source)
        if transformed_to_raw is not None:
            start_pos, end_pos = transformed_to_raw(start_pos_t, end_bound_t)
        else:
            start_pos, end_pos = start_pos_t, end_bound_t
        text = text_source[start_pos_t:end_bound_t].strip()
        page_numbers = get_pages_for_span(position_to_page or {}, start_pos, end_pos)
        title = clean_markdown_artifacts((full_match_text or section_name).strip())
        sections.append({
            "number": "-",
            "title": title,
            "text": text,
            "start_pos": start_pos,
            "end_pos": end_pos,
            "start_pos_t": start_pos_t,
            "end_pos_t": end_bound_t,
            "page_numbers": page_numbers,
            "section_name": section_name,
        })
    return sections


def extract_level2_subsections(
    section: Dict,
    raw_text: str,
    position_to_page: Optional[Dict[int, int]],
) -> List[Dict]:
    """
    Level 2: Within one Level-1 section, find ORDER, ARTICLE, all-caps headings, Roman.—Title.
    Subdivides section into subsections; each gets section_name and section_number updated.
    Returns list of subsection dicts (same shape as section: number, title, text, start_pos, end_pos, page_numbers, section_name).
    """
    text = section.get("text", "")
    base_start = section.get("start_pos", 0)
    if not text or base_start < 0:
        return [section]
    # Find all level-2 matches (position relative to section text start)
    sub_matches = []  # (rel_start, rel_end, section_name, section_number, line_text)
    lines = text.split("\n")
    line_start_offsets = [0]
    for line in lines[:-1]:
        line_start_offsets.append(line_start_offsets[-1] + len(line) + 1)
    for line_idx, line in enumerate(lines):
        line_stripped = line.strip()
        if not line_stripped:
            continue
        rel_start = line_start_offsets[line_idx]
        rel_end = rel_start + len(line)
        section_name = None
        section_number = "-"
        if LEVEL2_PATTERN_ORDER_ARTICLE.match(line_stripped):
            for g in (LEVEL2_PATTERN_ORDER_ARTICLE.finditer(line_stripped)):
                # Group 2,3 = ORDER|ARTICLE and Roman in first alt; group 3,4 in second alt
                name = (g.group(2) or g.group(3) or "").strip().upper()
                if name and name in ("ORDER", "ARTICLE"):
                    section_name = name
                    section_number = "-"
                break
        elif LEVEL2_PATTERN_ROMAN_TITLE.match(line_stripped):
            for g in LEVEL2_PATTERN_ROMAN_TITLE.finditer(line_stripped):
                if g.lastindex >= 1:
                    section_number = "-"
                    section_name = "ROMAN_HEADING"
                break
        elif LEVEL2_PATTERN_LETTER_TITLE.match(line_stripped):
            section_name = "LETTER_HEADING"
            section_number = "-"
        elif LEVEL2_PATTERN_ALLCAPS.match(line_stripped):
            section_name = "HEADING"
            section_number = "-"
        if section_name is not None:
            sub_matches.append((rel_start, rel_end, section_name, section_number, line_stripped))
    if not sub_matches:
        return [section]
    # Build subsections: content before first match (keep original section name/number) + from each match to next
    subsections = []
    first_rel = sub_matches[0][0]
    if first_rel > 0:
        sub_text_before = text[:first_rel].strip()
        if sub_text_before:
            sub_end_global = base_start + first_rel
            page_numbers = get_pages_for_span(position_to_page or {}, base_start, sub_end_global)
            subsections.append({
                "number": section.get("number", "-"),
                "title": section.get("title", ""),
                "text": sub_text_before,
                "start_pos": base_start,
                "end_pos": sub_end_global,
                "page_numbers": page_numbers,
                "section_name": section.get("section_name", "SECTION"),
            })
    for i, (rel_start, _, section_name, section_number, line_text) in enumerate(sub_matches):
        sub_start_global = base_start + rel_start
        sub_end_rel = sub_matches[i + 1][0] if i + 1 < len(sub_matches) else len(text)
        sub_end_global = base_start + sub_end_rel
        sub_text = text[rel_start:sub_end_rel].strip()
        if not sub_text:
            continue
        page_numbers = get_pages_for_span(position_to_page or {}, sub_start_global, sub_end_global)
        title = line_text.strip() if line_text.strip() else section_name
        subsections.append({
            "number": "-",
            "title": title,
            "text": sub_text,
            "start_pos": sub_start_global,
            "end_pos": sub_end_global,
            "page_numbers": page_numbers,
            "section_name": section_name,
        })
    return subsections if subsections else [section]


def extract_level2_subsections_and_remaining(
    section: Dict,
    raw_text: str,
    position_to_page: Optional[Dict[int, int]],
    transformed_to_raw: Optional[Callable[[int, int], Tuple[int, int]]] = None,
    search_text: Optional[str] = None,
    raw_to_transformed: Optional[Callable[[int, int], Tuple[int, int]]] = None,
) -> Tuple[List[Dict], List[Dict]]:
    """
    Extract Level-2 heading sections and explicit remaining_text_2 from one Level-1 section.
    When transformed_to_raw is provided, section text is in placeholder coords; map subsection bounds to raw.
    """
    text = section.get("text", "")
    base_start = section.get("start_pos", 0)
    base_start_t = section.get("start_pos_t", base_start)
    if not text or base_start < 0:
        return [], [section]

    sub_matches = []  # (rel_start, rel_end, section_name, section_number, line_text)
    lines = text.split("\n")
    line_start_offsets = [0]
    for line in lines[:-1]:
        line_start_offsets.append(line_start_offsets[-1] + len(line) + 1)

    for line_idx, line in enumerate(lines):
        line_stripped = line.strip()
        if not line_stripped:
            continue
        rel_start = line_start_offsets[line_idx]
        rel_end = rel_start + len(line)
        section_name = None
        section_number = "-"
        if LEVEL2_PATTERN_ORDER_ARTICLE.match(line_stripped):
            for g in LEVEL2_PATTERN_ORDER_ARTICLE.finditer(line_stripped):
                name = (g.group(2) or g.group(3) or "").strip().upper()
                if name and name in ("ORDER", "ARTICLE"):
                    section_name = name
                    section_number = "-"
                break
        elif LEVEL2_PATTERN_ROMAN_TITLE.match(line_stripped):
            for g in LEVEL2_PATTERN_ROMAN_TITLE.finditer(line_stripped):
                if g.lastindex >= 1:
                    section_number = "-"
                    section_name = "ROMAN_HEADING"
                break
        elif LEVEL2_PATTERN_LETTER_TITLE.match(line_stripped):
            section_name = "LETTER_HEADING"
            section_number = "-"
        elif LEVEL2_PATTERN_ALLCAPS.match(line_stripped):
            section_name = "HEADING"
            section_number = "-"
        if section_name is not None:
            sub_matches.append((rel_start, rel_end, section_name, section_number, line_stripped))

    if not sub_matches:
        return [], [section]

    level2_sections: List[Dict] = []
    covered_ranges: List[Tuple[int, int]] = []
    for i, (rel_start, _, section_name, section_number, line_text) in enumerate(sub_matches):
        sub_end_rel = sub_matches[i + 1][0] if i + 1 < len(sub_matches) else len(text)
        sub_text = text[rel_start:sub_end_rel].strip()
        if not sub_text:
            continue
        if transformed_to_raw is not None:
            sub_start_t = base_start_t + rel_start
            sub_end_t = base_start_t + sub_end_rel
            sub_start_global, sub_end_global = transformed_to_raw(sub_start_t, sub_end_t)
        else:
            sub_start_t = sub_end_t = None
            sub_start_global = base_start + rel_start
            sub_end_global = base_start + sub_end_rel
        covered_ranges.append((sub_start_global, sub_end_global))
        page_numbers = get_pages_for_span(position_to_page or {}, sub_start_global, sub_end_global)
        title = line_text.strip() if line_text.strip() else section_name
        sec_dict = {
            "number": "-",
            "title": title,
            "text": sub_text,
            "start_pos": sub_start_global,
            "end_pos": sub_end_global,
            "page_numbers": page_numbers,
            "section_name": section_name,
        }
        if sub_start_t is not None and sub_end_t is not None:
            sec_dict["start_pos_t"] = sub_start_t
            sec_dict["end_pos_t"] = sub_end_t
        level2_sections.append(sec_dict)

    # Build remaining_text_2 as gaps in Level-1 not covered by Level-2 heading sections.
    remaining_sections: List[Dict] = []
    text_source = search_text if search_text is not None else raw_text
    if covered_ranges:
        covered_ranges.sort(key=lambda x: x[0])
        cursor = base_start
        for start, end in covered_ranges:
            if start > cursor:
                if raw_to_transformed is not None and search_text is not None:
                    t_s, t_e = raw_to_transformed(cursor, start)
                    rem_text = text_source[t_s:t_e].strip()
                else:
                    t_s = t_e = None
                    rem_text = raw_text[cursor:start].strip()
                if rem_text:
                    page_numbers = get_pages_for_span(position_to_page or {}, cursor, start)
                    rem_sec = {
                        "number": section.get("number", "-"),
                        "title": section.get("title", ""),
                        "text": rem_text,
                        "start_pos": cursor,
                        "end_pos": start,
                        "page_numbers": page_numbers,
                        "section_name": section.get("section_name", "SECTION"),
                    }
                    if t_s is not None and t_e is not None:
                        rem_sec["start_pos_t"], rem_sec["end_pos_t"] = t_s, t_e
                    remaining_sections.append(rem_sec)
            cursor = max(cursor, end)
        section_end = section.get("end_pos", base_start + len(text))
        if section_end > cursor:
            if raw_to_transformed is not None and search_text is not None:
                t_s, t_e = raw_to_transformed(cursor, section_end)
                rem_text = text_source[t_s:t_e].strip()
            else:
                t_s = t_e = None
                rem_text = raw_text[cursor:section_end].strip()
            if rem_text:
                page_numbers = get_pages_for_span(position_to_page or {}, cursor, section_end)
                rem_sec = {
                    "number": section.get("number", "-"),
                    "title": section.get("title", ""),
                    "text": rem_text,
                    "start_pos": cursor,
                    "end_pos": section_end,
                    "page_numbers": page_numbers,
                    "section_name": section.get("section_name", "SECTION"),
                }
                if t_s is not None and t_e is not None:
                    rem_sec["start_pos_t"], rem_sec["end_pos_t"] = t_s, t_e
                remaining_sections.append(rem_sec)

    return level2_sections, remaining_sections


def _normalize_separator_whitespace(s: str) -> str:
    """Collapse runs of whitespace between number+punctuation and word to single space."""
    return re.sub(r"(\d+[._-])\s+([A-Z][a-zA-Z]*)", r"\1 \2", s)


def _extract_level3_number_and_bold_title(first_line: str) -> Tuple[Optional[str], Optional[str]]:
    """
    Extract level-3 heading metadata from one heading line.
    - number: first section-like token (e.g., 8A, 10, 22-A)
    - title: heading text found inside bold markers (**...** or __...__)
    """
    if not first_line:
        return None, None

    num_match = re.search(r"\d+[A-Za-z-]*", first_line)
    number = num_match.group(0) if num_match else None

    title = None
    bold_match = re.search(r"(?:\*\*|__)\s*(.+?)\s*(?:\*\*|__)", first_line)
    if bold_match:
        bold_text = bold_match.group(1).strip()
        # Remove leading markers (superscripts/OCR symbols/brackets) + section number from bold text.
        cleaned = re.sub(r"^[^\dA-Za-z]{0,8}\s*\d+[A-Za-z-]*\s*\.?\s*", "", bold_text).strip()
        cleaned = cleaned.strip(" .—–:-")
        title = cleaned if cleaned else None
    return number, title


def build_level3_separators(text: str, normalize_whitespace: bool = True) -> List[str]:
    """Build separator list from LEVEL3 regexes and section patterns (order of first occurrence in text) plus literal fallbacks."""
    seen = set()
    separators = []
    for pattern_str in SEPARATOR_REGEXES_LEVEL3:
        try:
            pat = re.compile(pattern_str)
            for m in pat.finditer(text):
                s = m.group(0).strip()
                if not s:
                    continue
                if normalize_whitespace:
                    s = _normalize_separator_whitespace(s)
                if s not in seen:
                    seen.add(s)
                    separators.append(s)
        except re.error:
            continue
    for pattern_str in SECTION_SEPARATOR_PATTERNS_FROM_PROCESS_LEGAL_TEXT:
        try:
            pat = re.compile(pattern_str, re.MULTILINE | re.DOTALL)
            for m in pat.finditer(text):
                s = m.group(0).strip()
                if not s:
                    continue
                if normalize_whitespace:
                    s = _normalize_separator_whitespace(s)
                if s not in seen:
                    seen.add(s)
                    separators.append(s)
        except re.error:
            continue
    separators.extend(LITERAL_SEPARATORS_LEVEL3)
    return separators


def split_section_by_level3_headings(
    section: Dict,
    raw_text: str,
    position_to_page: Optional[Dict[int, int]],
    max_size: int = 8000,
    transformed_to_raw: Optional[Callable[[int, int], Tuple[int, int]]] = None,
) -> List[Dict]:
    """
    Level 3: Split section text using RecursiveCharacterTextSplitter with heading-based separators.
    When section has start_pos_t (placeholder coords), use transformed_to_raw to map segment bounds to raw.
    Returns list of section dicts (each may be smaller; section_name/number may be updated from first line).
    """
    text = section.get("text", "")
    base_start = section.get("start_pos", 0)
    base_start_t = section.get("start_pos_t", base_start)
    base_end = section.get("end_pos", len(raw_text))
    section_name = section.get("section_name", "SECTION")
    section_number = section.get("number", "-")
    if not text.strip():
        return [section]

    # Use one coordinate space for both splitting and rel_start/rel_end mapping:
    # split on the original section text (not normalized copy), so offsets are stable.
    strict_segments: List[str] = []
    literal_separators = build_level3_separators_literal(text)
    strict_separators = [s for s in literal_separators if s not in ("\n\n", "\n", ". ", " ", "")]
    if split_strictly_on_separators is not None and strict_separators:
        strict_segments = split_strictly_on_separators(text, strict_separators)

    if strict_segments:
        segments = strict_segments
    else:
        separators = build_level3_separators(text, normalize_whitespace=True)
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=max_size,
            chunk_overlap=200,
            separators=separators,
            length_function=len,
            strip_whitespace=True,
        )
        segments = splitter.split_text(text)

    # Same as parent strict split: strip splitter can leave lone ']' or '.' before a heading;
    # merge those onto the previous segment so one heading block stays one section.
    if segments:
        segments = _merge_trivial_trailing_splits(list(segments))

    def _is_level2_heading_only_segment(seg_text: str) -> bool:
        """True when segment contains only a Level-2 heading line (no body text)."""
        if not seg_text:
            return True
        lines = [ln.strip() for ln in seg_text.split("\n") if ln.strip()]
        if not lines:
            return True
        if len(lines) != 1:
            return False
        line = lines[0]
        return (
            bool(LEVEL2_PATTERN_ORDER_ARTICLE.match(line))
            or bool(LEVEL2_PATTERN_ROMAN_TITLE.match(line))
            or bool(LEVEL2_PATTERN_LETTER_TITLE.match(line))
            or bool(LEVEL2_PATTERN_ALLCAPS.match(line))
        )

    result = []
    current_offset = 0
    # Keep subtitle / chapter line title for continuations (e.g. bracket '[Rep. by…]' split from 'AMENDMENT…').
    last_title_for_carry = section.get("title", "")
    for seg in segments:
        if not seg.strip():
            continue
        # Find segment boundaries in original text (approximate by content match)
        search_key = seg[:min(80, len(seg))].strip()
        rel_start = text.find(search_key, current_offset)
        if rel_start == -1:
            rel_start = current_offset
        rel_end = rel_start + len(seg)
        if transformed_to_raw is not None and "start_pos_t" in section:
            seg_start_t = base_start_t + rel_start
            seg_end_t = min(base_start_t + rel_end, section.get("end_pos_t", base_start_t + len(text)))
            seg_start_global, seg_end_global = transformed_to_raw(seg_start_t, seg_end_t)
        else:
            seg_start_global = base_start + rel_start
            seg_end_global = min(base_start + rel_end, base_end)
        current_offset = rel_end
        # Check first non-empty line of segment for heading pattern to update section_number/title.
        first_line = ""
        for ln in seg.split("\n"):
            if ln.strip():
                first_line = ln.strip()
                break
        if not first_line:
            first_line = seg.split("\n")[0].strip()
        seg_number = section_number
        seg_title = section.get("title", "")
        seg_section_name = section_name
        heading_matched = False
        for pat_str in SEPARATOR_REGEXES_LEVEL3:
            try:
                m = re.compile(pat_str).match(first_line)
                if m:
                    heading_matched = True
                    break
            except re.error:
                pass
        if not heading_matched:
            for pat_str in SECTION_SEPARATOR_PATTERNS_FROM_PROCESS_LEGAL_TEXT:
                try:
                    pat = re.compile(pat_str, re.MULTILINE | re.DOTALL)
                    m = pat.match(first_line)
                    if m:
                        heading_matched = True
                        break
                except re.error:
                    pass
        if heading_matched:
            parsed_number, parsed_title = _extract_level3_number_and_bold_title(first_line)
            # Level-3 metadata rules:
            # - both found -> keep both
            # - only number -> title '-'
            # - only title -> number '-'
            # - neither -> both '-'
            if parsed_number and parsed_title:
                seg_number = parsed_number
                seg_title = parsed_title
            elif parsed_number and not parsed_title:
                seg_number = parsed_number
                seg_title = "-"
            elif parsed_title and not parsed_number:
                seg_number = "-"
                seg_title = parsed_title
            else:
                seg_number = "-"
                seg_title = "-"
            seg_section_name = "SECTION"
        else:
            # Continuation of same structural block (repeal note, bracketed editorial matter)
            if first_line.startswith(("[", "(")) or first_line.lower().startswith("rep."):
                seg_title = last_title_for_carry
            else:
                seg_title = section.get("title", "")

        if _is_trivial_split_fragment(seg):
            seg_title = last_title_for_carry

        if seg.strip() and not _is_trivial_split_fragment(seg):
            if heading_matched:
                last_title_for_carry = seg_title
            elif first_line.startswith(("[", "(")) or first_line.lower().startswith("rep."):
                pass  # keep last_title_for_carry as-is
            else:
                last_title_for_carry = seg_title

        page_numbers = get_pages_for_span(position_to_page or {}, seg_start_global, seg_end_global)
        result.append({
            "number": seg_number,
            "title": seg_title,
            "text": seg,
            "start_pos": seg_start_global,
            "end_pos": seg_end_global,
            "page_numbers": page_numbers,
            "section_name": seg_section_name,
        })
    if not result:
        return [section]

    # Drop heading-only scaffold chunks like "### *B.—Registration Establishment*".
    # Keep only chunks with actual section body content.
    filtered_result = [r for r in result if not _is_level2_heading_only_segment(r.get("text", ""))]
    return filtered_result if filtered_result else [section]


def build_level3_separators_literal(text: str) -> List[str]:
    """
    Build separator list from Level-3 regexes and section patterns from process_legal_text.py.
    Uses the exact strings as they appear in text. Order of first occurrence; deduped by normalized form.
    """
    # Collect (start_pos, literal_string) from all patterns so we can sort by first occurrence
    matches_with_pos: List[Tuple[int, str]] = []

    for pattern_str in SEPARATOR_REGEXES_LEVEL3:
        try:
            pat = re.compile(pattern_str)
            for m in pat.finditer(text):
                s = m.group(0).strip()
                if not s:
                    continue
                matches_with_pos.append((m.start(), s))
        except re.error:
            continue

    # Section patterns from process_legal_text.py (require MULTILINE and DOTALL for ^ and .)
    for pattern_str in SECTION_SEPARATOR_PATTERNS_FROM_PROCESS_LEGAL_TEXT:
        try:
            pat = re.compile(pattern_str, re.MULTILINE | re.DOTALL)
            for m in pat.finditer(text):
                s = m.group(0).strip()
                if not s:
                    continue
                matches_with_pos.append((m.start(), s))
        except re.error:
            continue

    # Sort by position, then dedupe by normalized form (keep first occurrence)
    matches_with_pos.sort(key=lambda x: x[0])
    seen_normalized = set()
    separators = []
    for _pos, s in matches_with_pos:
        s_norm = _normalize_separator_whitespace(s)
        if s_norm not in seen_normalized:
            seen_normalized.add(s_norm)
            separators.append(s)
    separators.extend(LITERAL_SEPARATORS_LEVEL3)
    return separators


def split_section_with_level3_separators(text: str, max_size: int = 8000) -> List[Tuple[str, int, int]]:
    """
    Split section text using the same RecursiveCharacterTextSplitter and Level-3 heading separators
    as used in Level-3 extraction. Prefer splitting at heading boundaries (e.g. "5. Objects", "4.", "2.__").
    Returns list of (part_text, rel_start, rel_end) relative to the original text.
    """
    if not text or len(text.strip()) == 0:
        return []
    if len(text) <= max_size:
        return [(text, 0, len(text))]

    separators = build_level3_separators_literal(text)
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=max_size,
        chunk_overlap=200,
        separators=separators,
        length_function=len,
        strip_whitespace=True,
    )
    parts = splitter.split_text(text)

    result = []
    current_pos = 0
    for part_text in parts:
        if not part_text.strip():
            continue
        search_key = part_text[:min(80, len(part_text))]
        rel_start = text.find(search_key, current_pos)
        if rel_start == -1:
            rel_start = current_pos
        rel_end = rel_start + len(part_text)
        current_pos = max(rel_start, rel_end - 200)
        result.append((part_text, rel_start, rel_end))
    return result if result else [(text, 0, len(text))]


def split_section_strictly_then_by_size(text: str, max_size: int = 8000) -> List[Tuple[str, int, int]]:
    """
    Split section text using split_strictly_on_separators (from split_parent_chunk_by_id.py) first:
    every heading separator starts a new segment. Then any segment exceeding max_size is split further
    with RecursiveCharacterTextSplitter (split_section_with_level3_separators).
    Returns list of (part_text, rel_start, rel_end) relative to the original text.
    """
    if not text or len(text.strip()) == 0:
        return []
    if len(text) <= max_size and (split_strictly_on_separators is None):
        return [(text, 0, len(text))]

    separators = build_level3_separators_literal(text)
    # Strict separators: heading-only, no fallback literals (so every split is at a heading)
    strict_separators = [s for s in separators if s not in (" ", ". ", "\n", "\n\n", "")]

    # Use split_strictly_on_separators when available; otherwise fall back to size-based split only
    if split_strictly_on_separators is not None and strict_separators:
        segments = split_strictly_on_separators(text, strict_separators)
    else:
        # Fallback: no strict split, use original size-based split
        return split_section_with_level3_separators(text, max_size=max_size)

    if not segments:
        return [(text, 0, len(text))]

    result = []
    current_pos = 0
    for segment in segments:
        if not segment.strip():
            continue
        # Prefer exact match (segment may be stripped so not always exact in text)
        rel_start = text.find(segment, current_pos)
        if rel_start == -1:
            rel_start = text.find(segment[:min(80, len(segment))], current_pos)
        if rel_start == -1:
            rel_start = current_pos
        rel_end = rel_start + len(segment)
        current_pos = rel_end

        if len(segment) <= max_size:
            result.append((segment, rel_start, rel_end))
        else:
            # Segment too large: split it with size-based splitter and map offsets back
            sub_parts = split_section_with_level3_separators(segment, max_size=max_size)
            for sub_text, sub_rel_start, sub_rel_end in sub_parts:
                if not sub_text.strip():
                    continue
                result.append((sub_text, rel_start + sub_rel_start, rel_start + sub_rel_end))

    return result if result else [(text, 0, len(text))]


def split_large_section(text: str, max_size: int = 8000) -> List[Tuple[str, int, int]]:
    """
    Split a section if it exceeds max_size characters.
    Uses simple separators (legacy). Prefer split_section_with_level3_separators for Level-3 style splitting.
    
    Args:
        text: Section text
        max_size: Maximum characters per part
        
    Returns:
        List of tuples: (part_text, rel_start, rel_end) where rel_start and rel_end are relative offsets in the original text
    """
    if len(text) <= max_size:
        return [(text, 0, len(text))]
    
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=max_size,
        chunk_overlap=200,
        separators=["\n\n", "\n", ". ", " ", ""]
    )
    
    parts = splitter.split_text(text)
    
    # Calculate relative offsets for each part
    result = []
    current_pos = 0
    
    for part_text in parts:
        # Find where this part starts in the original text
        # Use first 50 chars as search key to find the position
        search_key = part_text[:min(50, len(part_text))]
        rel_start = text.find(search_key, current_pos)
        
        if rel_start == -1:
            # Fallback: use current position
            rel_start = current_pos
        
        rel_end = rel_start + len(part_text)
        # Update current_pos to account for overlap (start search from overlap point)
        current_pos = max(rel_start, rel_end - 200)  # Account for overlap
        
        result.append((part_text, rel_start, rel_end))
    
    return result


def derive_act_name(filename: str) -> str:
    """
    Derive act name from filename.
    
    Args:
        filename: Source filename (e.g., "THE ABANDONED PROPERTIES ACT 1975.pdf")
        
    Returns:
        Act name (e.g., "THE ABANDONED PROPERTIES ACT 1975")
    """
    # Remove extension
    name = filename.replace('.pdf', '').replace('.PDF', '')
    # Remove path if present
    name = name.split('/')[-1].split('\\')[-1]
    return name


def determine_category(pdf_path: str) -> str:
    """
    Determine document category from folder path.
    
    Args:
        pdf_path: Full path to the PDF file
        
    Returns:
        Category name based on folder: "civil", "family", "criminal", or "general"
    """
    path = Path(pdf_path)
    # Get the parent folder name (e.g., "civil", "family", "criminal")
    folder_name = path.parent.name.lower()
    
    # Check if it's one of the known categories
    if folder_name in ['civil', 'family', 'criminal']:
        return folder_name
    
    # Default to "general" if folder name doesn't match
    return "general"


def create_parent_chunks(
    sections: List[Dict],
    filename: str,
    pdf_path: str,
    position_to_page: Optional[Dict[int, int]] = None,
    raw_text: Optional[str] = None,
    all_footnotes: Optional[List[Dict[str, str]]] = None,
) -> List[LegalParentChunk]:
    """
    Create LegalParentChunk objects from extracted sections.

    Duplicate chunks can occur if: (1) the same (start_pos, end_pos) or overlapping
    section appears twice in sections (e.g. Level-1/2 boundary overlap); (2) Level-3
    segment position matching (text.find) hits a repeated substring and yields
    overlapping segments; (3) split_strictly_on_separators or size-split produces
    duplicate segments for the same span. Deduplicate by (start_pos, end_pos) or
    by normalized text hash if needed.
    
    Args:
        sections: List of section dictionaries
        filename: Source filename
        pdf_path: Full path to PDF file (for category extraction)
        
    Returns:
        List of LegalParentChunk objects
    """
    act_name = derive_act_name(filename)
    base_name = act_name.replace(' ', '_')
    category = determine_category(pdf_path)
    parent_chunks = []
    # Counter for emitted sections (contiguous for actually created parent chunks).
    parent_idx = 1
    # Enforce monotonic non-overlapping spans across all parent chunks in document order.
    global_last_parent_end_raw = -1

    for idx, section in enumerate(sections):
        section_start_pos = section.get('start_pos', -1)
        section_end_pos = section.get('end_pos', -1)
        clean_text = section['text']
        # First split strictly on heading separators (split_strictly_on_separators from split_parent_chunk_by_id.py);
        # then split any segment > 8000 with RecursiveCharacterTextSplitter (split_section_with_level3_separators).
        # text_parts_with_offsets = split_section_with_level3_separators(clean_text, max_size=8000)  # size-only split (kept for reference)
        text_parts_with_offsets = split_section_strictly_then_by_size(clean_text, max_size=8000)
        num_parts = len(text_parts_with_offsets)
        # Keep parent chunk raw spans monotonic (non-overlapping) within this section.
        # We use this as a lower bound when searching subsequent parts in raw_text.
        last_parent_end_raw = section_start_pos if isinstance(section_start_pos, int) else -1

        section_emitted_parts = []  # (text, start, end, pages) for valid emitted parts in this section
        for part_idx_local, (part_text, rel_start, rel_end) in enumerate(text_parts_with_offsets):
            part_text = clean_markdown_artifacts(part_text)
            part_text_normalized = normalize_for_parent(part_text)

            if section_start_pos != -1 and section_end_pos != -1 and raw_text:
                # rel_start/rel_end are offsets in normalized section text, not raw_text.
                if position_to_page is not None:
                    parent_start_pos_raw, parent_end_pos_raw = find_parent_chunk_in_raw_text(
                        part_text_normalized,
                        section_start_pos,
                        section_end_pos,
                        raw_text,
                        position_to_page=position_to_page,
                        all_footnotes=all_footnotes or [],
                        section_title=section.get("title", "") or "",
                        hint_rel_start=rel_start,
                        hint_rel_end=rel_end,
                        section_text_normalized=clean_text,
                    )
                else:
                    parent_start_pos_raw, parent_end_pos_raw = find_parent_chunk_in_raw_text(
                        part_text_normalized,
                        section_start_pos,
                        section_end_pos,
                        raw_text,
                    )
                # Clamp to section bounds.
                parent_start_pos_raw = max(section_start_pos, min(parent_start_pos_raw, section_end_pos))
                parent_end_pos_raw = max(section_start_pos, min(parent_end_pos_raw, section_end_pos))
                # Final safety clamp: enforce non-overlap even if approximate matching drifts.
                if (
                    last_parent_end_raw != -1
                    and parent_start_pos_raw != -1
                    and parent_start_pos_raw < last_parent_end_raw
                ):
                    parent_start_pos_raw = last_parent_end_raw
                if (
                    parent_start_pos_raw != -1
                    and parent_end_pos_raw != -1
                    and parent_end_pos_raw <= parent_start_pos_raw
                ):
                    # Degenerate span after clamping/re-mapping; skip this part to avoid
                    # creating a duplicate/overlapping parent chunk.
                    continue
                # Cross-section/global safety clamp: prevent any overlap with previously
                # emitted parent chunks in document order.
                if (
                    global_last_parent_end_raw != -1
                    and parent_start_pos_raw != -1
                    and parent_start_pos_raw < global_last_parent_end_raw
                ):
                    parent_start_pos_raw = global_last_parent_end_raw
                if (
                    parent_start_pos_raw != -1
                    and parent_end_pos_raw != -1
                    and parent_end_pos_raw <= parent_start_pos_raw
                ):
                    continue
            else:
                parent_start_pos_raw = -1
                parent_end_pos_raw = -1

            parent_pages = []
            if position_to_page and parent_start_pos_raw != -1 and parent_end_pos_raw != -1:
                parent_pages = get_pages_for_span(position_to_page, parent_start_pos_raw, parent_end_pos_raw)
            section_emitted_parts.append((
                part_text_normalized,
                parent_start_pos_raw,
                parent_end_pos_raw,
                parent_pages,
            ))
            if parent_end_pos_raw != -1:
                last_parent_end_raw = parent_end_pos_raw
                global_last_parent_end_raw = max(global_last_parent_end_raw, parent_end_pos_raw)
        # Only advance parent_idx when at least one parent chunk is actually emitted.
        if not section_emitted_parts:
            continue

        emitted_count = len(section_emitted_parts)
        for emitted_part_idx, (part_text_normalized, parent_start_pos_raw, parent_end_pos_raw, parent_pages) in enumerate(section_emitted_parts, start=1):
            # parent_id rule:
            # - one emitted chunk for this section: base_parentIdx
            # - multiple emitted chunks for this section: base_parentIdx_partIdx
            if emitted_count > 1:
                parent_id = f"{base_name}_{parent_idx}_{emitted_part_idx}"
            else:
                parent_id = f"{base_name}_{parent_idx}"

            # Scan chunk text for [TABLE_n] and [FORM_n] placeholders; attach IDs to metadata
            table_ids: List[str] = []
            form_ids: List[str] = []
            for m in re.finditer(r"\[TABLE_(\d+)\]", part_text_normalized):
                tid = f"TABLE_{m.group(1)}"
                if tid not in table_ids:
                    table_ids.append(tid)
            for m in re.finditer(r"\[FORM_(\d+)\]", part_text_normalized):
                fid = f"FORM_{m.group(1)}"
                if fid not in form_ids:
                    form_ids.append(fid)
            table_ids.sort()
            form_ids.sort()

            metadata = {
                'parent_id': parent_id,
                'act_name': act_name,
                'section_number': section['number'],
                'section_title': section['title'],
                'category': category,
                'start_pos_raw': parent_start_pos_raw,
                'end_pos_raw': parent_end_pos_raw,
                'page_numbers': parent_pages,
                'table_numbers': table_ids,
                'form_numbers': form_ids
            }
            parent_chunks.append(LegalParentChunk(text=part_text_normalized, metadata=metadata))

        parent_idx += 1

    return parent_chunks


def create_child_chunks(
    parent_chunk: LegalParentChunk,
    chunk_size: int = 1000,
    chunk_overlap: int = 200,
    position_to_page: Optional[Dict[int, int]] = None,
    raw_text: Optional[str] = None,
    all_footnotes: Optional[List[Dict[str, str]]] = None
) -> List[LegalChildChunk]:
    """
    Create LegalChildChunk objects from a parent chunk.
    
    Args:
        parent_chunk: Parent chunk to split
        chunk_size: Size of child chunks
        chunk_overlap: Overlap between chunks
        position_to_page: Dictionary mapping character position to page number
        raw_text: Raw text for footnote detection
        all_footnotes: List of all footnote dictionaries for footnote assignment
        
    Returns:
        List of LegalChildChunk objects
    """
    # Check if this is an omitted/repealed/deleted section
    section_title = parent_chunk.metadata['section_title']
    is_omitted = section_title in ['[Omitted]', '[Repealed]', '[Deleted]']
    
    if is_omitted:
        # Create a single child chunk for omitted sections
        # Determine the status word (Omitted, Repealed, or Deleted)
        status_word = section_title.strip('[]')
        status_lower = status_word.lower()
        
        # Create simple text
        child_text = f"This section has been {status_lower}."
        
        # Normalize for child (dense, flat string)
        child_text_normalized = normalize_for_child(child_text)
        
        # Determine section_name
        section_name = section_title
        
        # Create metadata
        metadata = {
            'child_id': f"{parent_chunk.metadata['parent_id']}_CH0",
            'parent_id': parent_chunk.metadata['parent_id'],
            'section_name': section_name,
            'act_name': parent_chunk.metadata['act_name'],
            'section_number': parent_chunk.metadata['section_number'],
            'category': parent_chunk.metadata['category'],
            'start_pos_raw': parent_chunk.metadata.get('start_pos_raw', -1),
            'end_pos_raw': parent_chunk.metadata.get('end_pos_raw', -1),
            'page_numbers': parent_chunk.metadata.get('page_numbers', [])
        }
        
        child_chunk = LegalChildChunk(
            text=child_text_normalized,
            footnotes=[],  # Will be populated by assign_footnotes_to_child_chunk
            metadata=metadata
        )
        
        # Assign footnotes to this child chunk
        if raw_text and position_to_page and all_footnotes:
            assign_footnotes_to_child_chunk(child_chunk, raw_text, position_to_page, all_footnotes)
        
        # Additional check: assign any missing footnotes based on superscript markers in text
        if all_footnotes:
            check_and_assign_missing_footnotes(child_chunk, all_footnotes)
        
        return [child_chunk]
    
    # Regular section - split into multiple child chunks
    # Get parent start position in raw_text
    parent_start_pos_raw = parent_chunk.metadata.get('start_pos_raw', -1)
    
    # Get parent text before normalization to calculate offsets
    # We need to split the original parent text to get accurate offsets
    # But parent_chunk.text is already normalized, so we'll work with it
    # The splitter will give us relative positions within the normalized text
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        separators=["\n\n", "\n", ". ", " ", ""]
    )
    
    # Split parent text into child texts
    child_texts = splitter.split_text(parent_chunk.text)
    
    # Calculate relative offsets for each child chunk
    child_chunks = []
    current_pos = 0
    
    for idx, child_text in enumerate(child_texts):
        child_id = f"{parent_chunk.metadata['parent_id']}_CH{idx}"
        
        # Find where this child text starts in the parent text (hardened search)
        # Try full child_text first, then 100-char prefix, fallback to current_pos
        rel_start = parent_chunk.text.find(child_text, current_pos)
        if rel_start == -1:
            search_key = child_text[:min(100, len(child_text))]
            rel_start = parent_chunk.text.find(search_key, current_pos)
        if rel_start == -1:
            rel_start = current_pos
        
        rel_end = rel_start + len(child_text)
        # Update current_pos to account for overlap
        current_pos = max(rel_start, rel_end - chunk_overlap)
        
        # Calculate child chunk positions in raw_text
        # First, normalize the child text (same as what will be stored)
        clean_child_text = clean_markdown_artifacts(child_text)
        child_text_normalized = normalize_for_child(clean_child_text)
        
        # Find exact positions in raw_text by matching normalized text
        if parent_start_pos_raw != -1 and raw_text:
            parent_end_pos_raw = parent_chunk.metadata.get('end_pos_raw', -1)
            if parent_end_pos_raw != -1:
                child_start_pos_raw, child_end_pos_raw = find_child_chunk_in_raw_text(
                    child_text_normalized,
                    parent_start_pos_raw,
                    parent_end_pos_raw,
                    raw_text
                )
            else:
                # Fallback to relative offset method
                child_start_pos_raw = parent_start_pos_raw + rel_start
                child_end_pos_raw = parent_start_pos_raw + rel_end
        else:
            child_start_pos_raw = -1
            child_end_pos_raw = -1
        
        # Get page numbers for this child chunk
        child_pages = []
        if position_to_page and child_start_pos_raw != -1 and child_end_pos_raw != -1:
            child_pages = get_pages_for_span(position_to_page, child_start_pos_raw, child_end_pos_raw)
        
        # DEBUG: Track page number assignment for specific chunk
        # Note: chunk_idx is the index in the chunks list for this parent
        chunk_idx_local = len(child_chunks)  # Current chunk index

        
        # Clean markdown artifacts from child text
        clean_child_text = clean_markdown_artifacts(child_text)
        
        # Apply child-specific normalization (dense, flat string for embeddings)
        clean_child_text_normalized = normalize_for_child(clean_child_text)
        
        # Determine section_name for child metadata.
        # section_number == '-' is used for: (1) inserted PREAMBLE, (2) Level-1 CHAPTER/PART (see
        # extract_level1_heading_sections), (3) SCHEDULE*. Only the real preamble should show as "PREAMBLE";
        # CHAPTER/PART titles must be preserved (previously everything non-SCHEDULE was wrongly forced to PREAMBLE).
        section_title_meta = parent_chunk.metadata.get('section_title', '')
        if parent_chunk.metadata['section_number'] == '-':
            stm = (section_title_meta or "").strip()
            stm_upper = stm.upper()
            if stm.startswith('SCHEDULE'):
                section_name = section_title_meta  # "SCHEDULE" or "SCHEDULE-..."
            elif stm_upper == 'PREAMBLE' or stm.startswith('PREAMBLE '):
                section_name = "PREAMBLE"
            else:
                section_name = section_title_meta  # e.g. "## CHAPTER IV", chapter subtitle lines, PART I
        else:
            # Normal section: use the section_title directly
            # If somehow a normal section got a SCHEDULE title, it's a bug in extraction
            # But we'll use it as-is to preserve the data
            section_name = section_title_meta
        
        # Create metadata with all fields except text
        metadata = {
            'child_id': child_id,
            'parent_id': parent_chunk.metadata['parent_id'],
            'section_title': section_name,
            'act_name': parent_chunk.metadata['act_name'],
            'section_number': parent_chunk.metadata['section_number'],
            'category': parent_chunk.metadata['category'],
            'start_pos_raw': child_start_pos_raw,
            'end_pos_raw': child_end_pos_raw,
            'page_numbers': child_pages
        }
        
        child_chunk = LegalChildChunk(
            text=clean_child_text_normalized,
            footnotes=[],  # Will be populated by assign_footnotes_to_child_chunk
            metadata=metadata
        )
        
        # Assign footnotes to this child chunk
        if raw_text and position_to_page and all_footnotes:
            assign_footnotes_to_child_chunk(child_chunk, raw_text, position_to_page, all_footnotes)
        
        # Additional check: assign any missing footnotes based on superscript markers in text
        if all_footnotes:
            check_and_assign_missing_footnotes(child_chunk, all_footnotes)
        
        child_chunks.append(child_chunk)
    
    return child_chunks


def process_legal_text(
    raw_text: str, 
    filename: str, 
    position_to_page: Optional[Dict[int, int]] = None,
    pdf_path: Optional[str] = None,
    all_footnotes: Optional[List[Dict[str, str]]] = None
) -> Tuple[List[LegalParentChunk], List[LegalChildChunk], List[LegalTableChunk], List[LegalFormChunk]]:
    """
    Main processing function.
    
    Args:
        raw_text: Raw extracted text
        filename: Source filename
        position_to_page: Optional pre-existing position to page mapping.
                         If provided, should come from extract_text_from_pdf().
                         If None, will be built from page markers in the text.
        pdf_path: Optional full path to PDF file (for category extraction).
                  If None, will try to derive from filename.
        
    Returns:
        Tuple of (parent_chunks, child_chunks, table_chunks)
    """
 
    strict_law_title_pattern1 = re.compile(
        r"^\s*#\s*([A-Z][A-Z\s,()'&\-]*(?:ACT|ORDINANCE|LAW)[A-Z\s,()'&\-]*\d{4})\s*$",
        re.MULTILINE | re.IGNORECASE
    )
    strict_law_title_pattern2 = re.compile(
        r"^\s*([A-Z][A-Z\s,()'&\-]*(?:ACT|ORDINANCE|LAW)[A-Z\s,()'&\-]*\d{4})\s*$",
        re.MULTILINE | re.IGNORECASE
    )
    strict_matches = sorted(
        list(strict_law_title_pattern1.finditer(raw_text)) + list(strict_law_title_pattern2.finditer(raw_text)),
        key=lambda m: m.start()
    )
    # Deduplicate same-span matches from the two strict patterns.
    dedup_strict = []
    seen_spans = set()
    for m in strict_matches:
        span = (m.start(), m.end())
        if span not in seen_spans:
            seen_spans.add(span)
            dedup_strict.append(m)

    second_law_name_end = None
    if len(dedup_strict) >= 2:
        second_law_name_end = dedup_strict[1].end()
    elif len(dedup_strict) == 1:
        second_law_name_end = dedup_strict[0].end()
    else:
        # Fallback to legacy broad patterns if strict title detection fails.
        law_name_pattern1 = re.compile(
            r'^#\s*([¹²³⁴⁵⁶⁷⁸⁹⁰A-Z][¹²³⁴⁵⁶⁷⁸⁹⁰A-Z\s()]*(?:ACT|ORDINANCE|LAW)[¹²³⁴⁵⁶⁷⁸⁹⁰A-Z\s(),]*)',
            re.MULTILINE | re.IGNORECASE
        )
        law_name_pattern2 = re.compile(
            r'^([¹²³⁴⁵⁶⁷⁸⁹⁰A-Z][¹²³⁴⁵⁶⁷⁸⁹⁰A-Z\s()]*(?:ACT|ORDINANCE|LAW)[¹²³⁴⁵⁶⁷⁸⁹⁰A-Z\s(),]*)',
            re.MULTILINE
        )
        all_law_name_matches = sorted(
            list(law_name_pattern1.finditer(raw_text)) + list(law_name_pattern2.finditer(raw_text)),
            key=lambda m: m.start()
        )
        if len(all_law_name_matches) >= 2:
            second_law_name_end = all_law_name_matches[1].end()
        elif len(all_law_name_matches) == 1:
            second_law_name_end = all_law_name_matches[0].end()

    # ========== STEP A: Extract FORMS and TABLES BEFORE section extraction ==========
    # Run form and table extraction (same order: forms first, then tables, like table extraction).
    # Section extraction uses text_with_placeholders so form-internal headings don't split one form into multiple chunks.
    text_with_placeholders, extracted_forms = extract_forms_from_text(raw_text)
    post_form_to_raw = _build_post_form_to_raw_mapper(raw_text, extracted_forms)
    text_with_placeholders, extracted_tables = extract_tables_from_text(text_with_placeholders)
    for tbl in extracted_tables:
        t_s, t_e = int(tbl.get("char_start", 0)), int(tbl.get("char_end", 0))
        r_s, r_e = post_form_to_raw(t_s, t_e)
        tbl["char_start"], tbl["char_end"] = r_s, r_e
    transformed_to_raw, raw_to_transformed = _build_combined_transformed_to_raw(raw_text, extracted_forms, extracted_tables)

    # Multi-level extraction requested:
    # 1) Level-1 sections + remaining_text_1
    # 2) Level-2 sections (from Level-1) + remaining_text_2
    # 3) Pass Level-2 sections through Level-3 (SEPARATOR_REGEXES_LEVEL3 + SECTION_SEPARATOR_PATTERNS_FROM_PROCESS_LEGAL_TEXT)
    # 4) Pass remaining_text_1 and remaining_text_2 through Level-3 too
    # 5) Keep final section order by page/start position
    start_search_pos = second_law_name_end if second_law_name_end is not None else 0
    level1_sections = extract_level1_heading_sections(
        raw_text, position_to_page or {}, start_search_position=start_search_pos,
        search_text=text_with_placeholders, transformed_to_raw=transformed_to_raw
    )
    has_level1_headings = len(level1_sections) > 0

    # remaining_text_1: text not covered by Level-1 heading sections.
    # Use text_with_placeholders for "text" so Level-3 doesn't split on form-internal headings.
    remaining_text_1_sections: List[Dict] = []
    if has_level1_headings:
        cursor = start_search_pos
        for sec in level1_sections:
            sec_start = sec.get("start_pos", cursor)
            if sec_start > cursor:
                t_s, t_e = raw_to_transformed(cursor, sec_start)
                rem_text = text_with_placeholders[t_s:t_e].strip()
                if rem_text:
                    gap_title = "PREAMBLE" if cursor == start_search_pos else "DOCUMENT"
                    remaining_text_1_sections.append({
                        "number": "-",
                        "title": gap_title,
                        "text": rem_text,
                        "start_pos": cursor,
                        "end_pos": sec_start,
                        "start_pos_t": t_s,
                        "end_pos_t": t_e,
                        "page_numbers": get_pages_for_span(position_to_page or {}, cursor, sec_start),
                        "section_name": "SECTION",
                    })
            cursor = max(cursor, sec.get("end_pos", cursor))
        if cursor < len(raw_text):
            t_s, t_e = raw_to_transformed(cursor, len(raw_text))
            rem_text = text_with_placeholders[t_s:t_e].strip()
            if rem_text:
                remaining_text_1_sections.append({
                    "number": "-",
                    "title": "DOCUMENT",
                    "text": rem_text,
                    "start_pos": cursor,
                    "end_pos": len(raw_text),
                    "start_pos_t": t_s,
                    "end_pos_t": t_e,
                    "page_numbers": get_pages_for_span(position_to_page or {}, cursor, len(raw_text)),
                    "section_name": "SECTION",
                })
    else:
        end_pos = len(raw_text)
        t_s, t_e = raw_to_transformed(start_search_pos, end_pos)
        rem_text = text_with_placeholders[t_s:t_e].strip()
        if rem_text:
            remaining_text_1_sections.append({
                "number": "-",
                "title": "PREAMBLE",
                "text": rem_text,
                "start_pos": start_search_pos,
                "end_pos": end_pos,
                "start_pos_t": t_s,
                "end_pos_t": t_e,
                "page_numbers": get_pages_for_span(position_to_page or {}, start_search_pos, end_pos),
                "section_name": "SECTION",
            })

    # Level-2 extraction from Level-1 and explicit remaining_text_2.
    level2_heading_sections: List[Dict] = []
    remaining_text_2_sections: List[Dict] = []
    if has_level1_headings:
        for sec in level1_sections:
            l2_sections, rem2_sections = extract_level2_subsections_and_remaining(
                sec, raw_text, position_to_page or {},
                transformed_to_raw=transformed_to_raw,
                search_text=text_with_placeholders,
                raw_to_transformed=raw_to_transformed,
            )
            level2_heading_sections.extend(l2_sections)
            remaining_text_2_sections.extend(rem2_sections)

    # Pass Level-2 headings and both remaining_text buckets through Level-3.
    sections = []
    level3_inputs = []
    level3_inputs.extend(level2_heading_sections)
    level3_inputs.extend(remaining_text_1_sections)
    level3_inputs.extend(remaining_text_2_sections)

    for sec in level3_inputs:
        parts = split_section_by_level3_headings(
            sec, raw_text, position_to_page or {}, max_size=8000,
            transformed_to_raw=transformed_to_raw
        )
        if parts:
            sections.extend(parts)
        else:
            sections.append(sec)

    # If all paths produced nothing, keep a single-span fallback (same region as intro / preamble).
    if not sections:
        start_pos = start_search_pos
        end_pos = len(raw_text)
        t_s, t_e = raw_to_transformed(start_pos, end_pos)
        sections = [{
            "number": "-",
            "title": "PREAMBLE",
            "text": text_with_placeholders[t_s:t_e],
            "start_pos": start_pos,
            "end_pos": end_pos,
            "start_pos_t": t_s,
            "end_pos_t": t_e,
            "page_numbers": get_pages_for_span(position_to_page or {}, start_pos, end_pos),
            "section_name": "SECTION",
        }]

    # Keep sections ordered by page, then by raw position.
    sections.sort(
        key=lambda s: (
            (s.get("page_numbers") or [10**9])[0],
            s.get("start_pos", 10**12),
            s.get("end_pos", 10**12),
        )
    )


    apply_form_and_table_placeholders_to_sections(
        sections, raw_text, extracted_forms, extracted_tables
    )

    # Remove footnotes from all sections FIRST (before any cleaning)
    # Footnotes appear at the end of pages above page numbers, so we search from the end
    for section in sections:
        section_start_pos = section.get('start_pos', -1)
        section_end_pos = section.get('end_pos', -1)
        # Remove footnotes from section text (search from end since footnotes appear at end of pages)
        section['text'] = remove_footnotes_from_section_text(
            section['text'], 
            raw_text, 
            section_start_pos, 
            section_end_pos, 
            position_to_page,
            all_footnotes
        )
    
    # Normalize sections (title and text) after footnotes are removed.
    # Protect [FORM_n] and [TABLE_n] placeholders before normalization so they are not corrupted.
    for section in sections:
        section_text = section.get('text', '')
        placeholder_map: Dict[str, str] = {}
        placeholder_counter = 0

        def _protect_form(match):  # type: ignore
            nonlocal placeholder_counter
            protected = f"__PLACEHOLDER_FORM_{placeholder_counter}__"
            placeholder_map[protected] = match.group(0)
            placeholder_counter += 1
            return protected

        def _protect_table(match):  # type: ignore
            nonlocal placeholder_counter
            protected = f"__PLACEHOLDER_TABLE_{placeholder_counter}__"
            placeholder_map[protected] = match.group(0)
            placeholder_counter += 1
            return protected

        section_text = re.sub(r"\[FORM_\d+\]", _protect_form, section_text)
        section_text = re.sub(r"\[TABLE_\d+\]", _protect_table, section_text)
        
        # Check if this is a SCHEDULE section - use separate normalization function
        is_schedule_section = section.get('title', '').startswith('SCHEDULE')
        
        if is_schedule_section:
            # Use separate normalization function for SCHEDULE sections
            # This preserves numbered list items like "5. Galvanized plain sheets."
            section_text = normalize_schedule_section_text(section_text)
        else:
            # Normalize regular section text: remove artifacts (using clean_text), fix broken words, and clean markdown
            section_text, _ = clean_text(section_text, None, skip_toc_detection=True)  # Remove page markers, headers (skip TOC detection for section text)
        section_text = fix_broken_words(section_text)  # Fix broken words
        section_text = clean_markdown_artifacts(section_text)  # Remove markdown artifacts
        section_text = remove_separators_from_text(section_text)  # Remove separator lines (----)
        section_text = remove_chapters_articles_parts_headings(section_text)  # Remove chapters, articles, parts, and headings

        for protected, original in placeholder_map.items():
            section_text = section_text.replace(protected, original)

        section['text'] = section_text
        
        # Normalize section title: clean markdown artifacts
        section['title'] = clean_markdown_artifacts(section['title'])
        section['title'] = section['title'].strip()
    
    # Print footnotes received from llamaparser_extractor.py
    if all_footnotes:
        for idx, footnote_dict in enumerate(all_footnotes):
            marker = footnote_dict.get('marker', '')
            marker_number = footnote_dict.get('marker_number', '')
            page_number = footnote_dict.get('page_number', 'N/A')
            footnote_text = footnote_dict.get('text', '')
            text_preview = footnote_text[:50] if len(footnote_text) > 50 else footnote_text
          
    superscript_pattern = re.compile(r'([¹²³⁴⁵⁶⁷⁸⁹⁰]+)')
    marker_map = {
        '¹': '1', '²': '2', '³': '3', '⁴': '4', '⁵': '5',
        '⁶': '6', '⁷': '7', '⁸': '8', '⁹': '9', '⁰': '0'
    }
    
    for idx, section in enumerate(sections):
        section_start_pos = section.get('start_pos', -1)
        section_end_pos = section.get('end_pos', -1)
        
        if section_start_pos == -1 or section_end_pos == -1:
            continue
        
        # Get section text span from raw_text
        if section_start_pos >= len(raw_text) or section_end_pos > len(raw_text):
           # print(f"\nSection {idx} ({section['number']} - {section['title']}): Positions out of range")
            continue
        
        section_text_span = raw_text[section_start_pos:section_end_pos]
        
        # Find all superscript markers in this section
        superscripts_found = []
        for match in superscript_pattern.finditer(section_text_span):
            marker_unicode = match.group(1)
            local_pos = match.start()
            global_pos = section_start_pos + local_pos
            page_num = position_to_page.get(global_pos, "N/A") if position_to_page else "N/A"
            
            # Normalize marker
            marker_key = ''.join(marker_map.get(char, char) for char in marker_unicode)
            
            superscripts_found.append({
                'position': global_pos,
                'marker_unicode': marker_unicode,
                'marker_normalized': marker_key,
                'page': page_num
            })
        

    
    # Step 3: Create parent chunks
    # Use pdf_path if provided, otherwise use filename (may not work for category extraction)
    effective_pdf_path = pdf_path if pdf_path else filename
    # ✅ FINAL NORMALIZATION PASS FOR PARENT TEXT
    for section in sections:
        section["text"] = normalize_for_parent(section.get("text", ""))
    
    parent_chunks = create_parent_chunks(
        sections, filename, effective_pdf_path, position_to_page, raw_text, all_footnotes
    )
    # for chunk in parent_chunks:
    #     print(chunk.text)
    # Step 4: Create child chunks (before table chunks, so we can map tables to child chunks)
    child_chunks = []
    for parent_chunk in parent_chunks:
        children = create_child_chunks(
            parent_chunk, 
            position_to_page=position_to_page,
            raw_text=raw_text,
            all_footnotes=all_footnotes
        )
        child_chunks.extend(children)
    
    # Step 3.5: Create table chunks and map them to parent chunks (position-based assignment)
    act_name = derive_act_name(filename)
    category = determine_category(effective_pdf_path)
    table_chunks = []
    
    # Map tables to parent chunks by finding which parent chunk contains each table
    # Use position-based assignment: find which parent chunk's character range contains the table
    for idx, tbl in enumerate(extracted_tables, start=1):
        table_char_start = tbl["char_start"]
        # Use char_end directly from extracted table (already includes full table span)
        # char_end is set in extract_tables_from_text to match.end() which includes the full table
        # Don't recalculate from markdown length as markdown may have been stripped
        table_char_end = tbl.get("char_end", table_char_start + len(tbl.get("markdown", "")))
        table_id = tbl["table_id"]
        
        # Find which parent chunk(s) contain this table (position-based assignment)
        # A table can overlap multiple parent chunks if it spans across parent chunk boundaries
        linked_parent_ids = []
        section_number = None
        section_title = None
        
        # Find ALL parent chunks that overlap with this table's character range
        # A table overlaps a parent if: table_start < parent_end AND table_end > parent_start
        for parent_chunk in parent_chunks:
            parent_start = parent_chunk.metadata.get('start_pos_raw', -1)
            parent_end = parent_chunk.metadata.get('end_pos_raw', -1)
            if parent_start != -1 and parent_end != -1:
                # Check if table overlaps with parent chunk's character range
                # Table overlaps parent if: table_start < parent_end AND table_end > parent_start
                if table_char_start < parent_end and table_char_end > parent_start:
                    # Table overlaps with this parent chunk
                    parent_id = parent_chunk.metadata.get('parent_id')
                    if parent_id and parent_id not in linked_parent_ids:
                        linked_parent_ids.append(parent_id)
                        # Add this table_id to the parent chunk's table_numbers list
                        # Avoid duplicates - check if table_id is already in the list
                        if table_id not in parent_chunk.metadata['table_numbers']:
                            parent_chunk.metadata['table_numbers'].append(table_id)
                    # Store section info from first matching parent (all parents in same section should have same info)
                    if not section_number:
                        section_number = parent_chunk.metadata.get('section_number', '-')
                        section_title = parent_chunk.metadata.get('section_title', '')
        
        # Use first linked parent_id for table chunk metadata (or None if no match)
        parent_id = linked_parent_ids[0] if linked_parent_ids else None
        
        # If no parent chunk found, try to find section info from sections (fallback for metadata only)
        if not section_number:
            for section in sections:
                section_start = section.get('start_pos', -1)
                section_end = section.get('end_pos', -1)
                if section_start != -1 and section_end != -1:
                    if section_start <= table_char_start < section_end:
                        section_number = section.get('number', '-')
                        section_title = section.get('title', '')
                        break
        

        # Get ALL page numbers for this table based on its char range
        table_pages = set()
        if position_to_page:
            # Clamp end to avoid iterating past the largest mapped position
            max_pos = max(position_to_page.keys())
            end_pos = min(table_char_end, max_pos + 1)

            for pos in range(table_char_start, end_pos):
                page = position_to_page.get(pos)
                if page is not None:
                    table_pages.add(page)

        table_page_numbers = sorted(table_pages)
        table_page = table_page_numbers[0] if table_page_numbers else None
        
        # Count tables in this section for table_index_in_section
        table_index_in_section = 1
        if section_number:
            # Count how many tables we've already seen in this section
            for prev_tbl in extracted_tables[:idx-1]:
                prev_section = None
                prev_start = prev_tbl["char_start"]
                for s in sections:
                    s_start = s.get('start_pos', -1)
                    s_end = s.get('end_pos', -1)
                    if s_start != -1 and s_end != -1 and s_start <= prev_start < s_end:
                        prev_section = s.get('number', '-')
                        break
                if prev_section == section_number:
                    table_index_in_section += 1
        
        table_chunks.append(
            LegalTableChunk(
                text=tbl["markdown"],
                summary="",  # fill later via summarization step
                metadata={
                    "table_id": table_id,
                    "parent_id": parent_id or "",  # Changed from child_id to parent_id
                    "act_name": act_name,
                    "section_number": section_number or "-",
                    "section_title": section_title or "",
                    "category": category,
                    "table_index_in_section": table_index_in_section,
                    "page_numbers": table_page_numbers,
                    "page": table_page,
                    "pdf_path": effective_pdf_path,
                }
            )
        )
    
    # Step 3.6: Create form chunks and map them to parent chunks (position-based assignment)
    form_chunks = []
    
    # Map forms to parent chunks by finding which parent chunk contains each form
    # Use position-based assignment: find which parent chunk's character range contains the form
    for idx, frm in enumerate(extracted_forms, start=1):
        form_char_start = frm["char_start"]
        # Use char_end directly from extracted form (already includes markers)
        # char_end is set in extract_forms_from_text to span["match_end"] which includes the markers
        form_char_end = frm.get("char_end", form_char_start + len(frm.get("markdown", "")))
        form_id = frm["form_id"]
        
        # Find which parent chunk(s) contain this form (position-based assignment)
        # A form can overlap multiple parent chunks if it spans across parent chunk boundaries
        linked_parent_ids = []
        section_number = None
        section_title = None
        
        # Find ALL parent chunks that overlap with this form's character range
        # A form overlaps a parent if: form_start < parent_end AND form_end > parent_start
        for parent_chunk in parent_chunks:
            parent_start = parent_chunk.metadata.get('start_pos_raw', -1)
            parent_end = parent_chunk.metadata.get('end_pos_raw', -1)
            if parent_start != -1 and parent_end != -1:
                # Check if form overlaps with parent chunk's character range
                # Form overlaps parent if: form_start < parent_end AND form_end > parent_start
                if form_char_start < parent_end and form_char_end > parent_start:
                    # Form overlaps with this parent chunk
                    parent_id = parent_chunk.metadata.get('parent_id')
                    if parent_id and parent_id not in linked_parent_ids:
                        linked_parent_ids.append(parent_id)
                        # Add this form_id to the parent chunk's form_numbers list
                        # Avoid duplicates - check if form_id is already in the list
                        if form_id not in parent_chunk.metadata['form_numbers']:
                            parent_chunk.metadata['form_numbers'].append(form_id)
                    # Store section info from first matching parent (all parents in same section should have same info)
                    if not section_number:
                        section_number = parent_chunk.metadata.get('section_number', '-')
                        section_title = parent_chunk.metadata.get('section_title', '')
        
        # Use first linked parent_id for form chunk metadata (or None if no match)
        parent_id = linked_parent_ids[0] if linked_parent_ids else None
        
        # If no parent chunk found, try to find section info from sections (fallback for metadata only)
        if not section_number:
            for section in sections:
                section_start = section.get('start_pos', -1)
                section_end = section.get('end_pos', -1)
                if section_start != -1 and section_end != -1:
                    if section_start <= form_char_start < section_end:
                        section_number = section.get('number', '-')
                        section_title = section.get('title', '')
                        break
        
 
        form_pages = set()
        if position_to_page:
            max_pos = max(position_to_page.keys())
            end_pos = min(form_char_end, max_pos + 1)

            for pos in range(form_char_start, end_pos):
                page = position_to_page.get(pos)
                if page is not None:
                    form_pages.add(page)

        form_page_numbers = sorted(form_pages)
        form_page = form_page_numbers[0] if form_page_numbers else None
        
        # Count forms in this section for form_index_in_section
        form_index_in_section = 1
        if section_number:
            # Count how many forms we've already seen in this section
            for prev_frm in extracted_forms[:idx-1]:
                prev_section = None
                prev_start = prev_frm["char_start"]
                for s in sections:
                    s_start = s.get('start_pos', -1)
                    s_end = s.get('end_pos', -1)
                    if s_start != -1 and s_end != -1 and s_start <= prev_start < s_end:
                        prev_section = s.get('number', '-')
                        break
                if prev_section == section_number:
                    form_index_in_section += 1
        
        form_chunks.append(
            LegalFormChunk(
                text=frm["markdown"],
                summary="",  # fill later via summarization step
                metadata={
                    "form_id": form_id,
                    "parent_id": parent_id or "",  # Changed from child_id to parent_id
                    "act_name": act_name,
                    "section_number": section_number or "-",
                    "section_title": section_title or "",
                    "category": category,
                    "form_index_in_section": form_index_in_section,
                    "page_numbers": form_page_numbers,
                    "page": form_page,
                    "pdf_path": effective_pdf_path,
                }
            )
        )
    
    return parent_chunks, child_chunks, table_chunks, form_chunks


def main():
    """Main function with sample data."""
    
    # Sample raw text (based on typical Pakistani legal document structure)
    sample_text = """
# THE ABANDONED PROPERTIES (MANAGEMENT) ACT, 1975

## CONTENTS

1. Short title, extent and commencement
2. Definitions
3. Vesting of abandoned property in Government
4. Board of Trustees
5. Appointment of Administrator and Deputy Administrators

Page 1 of 12

# THE ABANDONED PROPERTIES (MANAGEMENT) ACT, 1975

WHEREAS it is expedient to provide for the management and administration of abandoned properties in Pakistan;

AND WHEREAS it is necessary to establish a Board of Trustees and appoint an Administrator for this purpose;

NOW, THEREFORE, in pursuance of the objectives set forth above, the following Act is hereby enacted:

**1. Short title, extent and commencement.**—(1) This Act may be called the Abandoned Properties (Management) Act, 1975.

(2) It extends to the whole of Pakistan.

(3) It shall come into force at once.

¹Inserted by Act No. X of 2020.

Page 2 of 12

**2. Definitions.**—In this Act, unless there is anything repugnant in the subject or context,—

(a) "abandoned property" means any property which has been declared as abandoned property under this Act;

(b) "Administrator" means the Administrator appointed under section 5;

(c) "Board" means the Board of Trustees constituted under section 4;

²Substituted by Act No. Y of 2021.

Page 3 of 12

**3. Vesting of abandoned property in Government.**—(1) All abandoned properties shall vest in the Federal Government.

(2) The Administrator shall take possession of such properties.

³Omitted by Act No. Z of 2022.

Page 4 of 12
"""
    
    filename = "THE ABANDONED PROPERTIES ACT 1975.pdf"
    
    # Process the text
    parent_chunks, child_chunks, table_chunks, form_chunks = process_legal_text(sample_text, filename)


if __name__ == "__main__":
    main()

