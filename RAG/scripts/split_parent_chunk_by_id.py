#!/usr/bin/env python3
"""
Split a parent chunk by ID using LangChain RecursiveCharacterTextSplitter.

Usage:
  python scripts/split_parent_chunk_by_id.py <parent_chunks_filename> <chunk_id>

Example:
  python scripts/split_parent_chunk_by_id.py ISLAMABAD_CONSUMERS_PROTECTION_ACT,_1995_parent_chunks.json ISLAMABAD_CONSUMERS_PROTECTION_ACT,_1995_3

The script:
  1. Finds the file under data/chunks/{civil,criminal,family}/parent_chunks/
  2. Loads JSON and finds the chunk whose metadata.parent_id equals chunk_id
  3. Builds separators from regex patterns (number + punctuation + space + word with capital), then \\n\\n, \\n, ". ", " ", ""
  4. Uses RecursiveCharacterTextSplitter with those separators and prints each segment.

Use --separators-only to split strictly on separators only (no size-based logic); every
separator starts a new segment. Otherwise the splitter only splits when a chunk exceeds
chunk_size (use --split-at-all or smaller --chunk-size to get more splits). Whitespace is
normalized so "6.  Authority" and "6. Authority" both match (use --no-normalize-whitespace to disable).
"""

import argparse
import json
import re
import sys
from pathlib import Path
from typing import List, Optional

try:
    from langchain_text_splitters import RecursiveCharacterTextSplitter
except ModuleNotFoundError:
    from langchain.text_splitter import RecursiveCharacterTextSplitter

# Project root (script lives in scripts/)
PROJECT_ROOT = Path(__file__).resolve().parents[1]
CHUNKS_ROOT = PROJECT_ROOT / "data" / "chunks"
CATEGORIES = ["civil", "criminal", "family"]

# Regex separator patterns — number + punctuation + space(s) + single word (first letter capital)
SEPARATOR_PATTERNS = [
    r"\d+\.\s+[A-Z][a-zA-Z]*",           # numbers + . + space(s) + word (e.g. 5. Objects)
    r"\d+\s+\.\s*[A-Z][a-zA-Z]*",        # numbers + space(s) + . + optional space + word
    r"\d+-\s+[A-Z][a-zA-Z]*",            # numbers + - + space(s) + word
    r"\d+\s+-\s*[A-Z][a-zA-Z]*",         # numbers + space(s) + - + optional space + word
    r"\d+_\s+[A-Z][a-zA-Z]*",            # numbers + _ + space(s) + word
    r"\d+\s+_\s*[A-Z][a-zA-Z]*",         # numbers + space(s) + _ + optional space + word
]

# Fallback literal separators for RecursiveCharacterTextSplitter
LITERAL_SEPARATORS = ["\n\n", "\n", ". ", " ", ""]


def find_parent_chunk_file(filename: str) -> Optional[Path]:
    """Find parent chunk file in civil/criminal/family/parent_chunks. Returns path or None."""
    if not filename.endswith(".json"):
        filename = filename if filename.endswith("_parent_chunks.json") else f"{filename}_parent_chunks.json"
    for category in CATEGORIES:
        path = CHUNKS_ROOT / category / "parent_chunks" / filename
        if path.exists():
            return path
    return None


def load_and_find_chunk(filepath: Path, chunk_id: str) -> Optional[dict]:
    """Load JSON and return the chunk whose metadata.parent_id == chunk_id, or None."""
    with open(filepath, "r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, list):
        return None
    for item in data:
        meta = item.get("metadata") or {}
        if meta.get("parent_id") == chunk_id:
            return item
    return None


def normalize_separator_whitespace(s: str) -> str:
    """Collapse any run of whitespace between number+punctuation and word to a single space (e.g. '6.  Authority' -> '6. Authority')."""
    return re.sub(r"(\d+[._-])\s+([A-Z][a-zA-Z]*)", r"\1 \2", s)


def build_separators_from_text(text: str, normalize_whitespace: bool = True) -> List[str]:
    """
    Collect all unique literal strings in text that match SEPARATOR_PATTERNS (in order),
    then append LITERAL_SEPARATORS. RecursiveCharacterTextSplitter uses these in order.

    If normalize_whitespace is True, separator strings are normalized so "6.  Authority" and "6. Authority"
    both become "6. Authority", and we also normalize the text before splitting so they match.
    """
    seen = set()
    separators: List[str] = []
    for pattern in SEPARATOR_PATTERNS:
        for m in re.finditer(pattern, text):
            s = m.group(0)
            if not s:
                continue
            if normalize_whitespace:
                s = normalize_separator_whitespace(s)
            if s not in seen:
                seen.add(s)
                separators.append(s)
    separators.extend(LITERAL_SEPARATORS)
    return separators


def _is_trivial_split_fragment(s: str) -> bool:
    """
    True if this segment is only sentence/closing punctuation (and whitespace).
    Such fragments appear when a markdown heading (e.g. '## CHAPTER IV') is a separator
    immediately after a line that ended with '.' or a line that closed with ']'; the strict
    splitter would otherwise emit a parent chunk that is just '.' or ']'.
    """
    t = s.strip()
    if not t or len(t) > 4:
        return False
    allowed = frozenset(".…,;:!?)]}([\"'")
    return all(c in allowed or c.isspace() for c in t)


def _merge_trivial_trailing_splits(segments: List[str]) -> List[str]:
    """Append punctuation-only segments onto the previous segment."""
    if not segments:
        return segments
    out: List[str] = []
    for seg in segments:
        if not seg.strip():
            continue
        if out and _is_trivial_split_fragment(seg):
            out[-1] = out[-1] + seg
        else:
            out.append(seg)
    return out


def split_strictly_on_separators(text: str, separators: List[str]) -> List[str]:
    """
    Split text only at separator boundaries. Every occurrence of any separator starts a new
    segment; chunk size is ignored. Each segment (after the first) starts with the separator.
    """
    # Only use non-empty separators for searching (empty string would match everywhere)
    seps = [s for s in separators if s]
    if not seps:
        return [text.strip()] if text.strip() else []

    segments: List[str] = []
    remaining = text
    while remaining:
        # Find the earliest occurrence of any separator
        best_pos = -1
        for sep in seps:
            pos = remaining.find(sep)
            if pos != -1 and (best_pos == -1 or pos < best_pos):
                best_pos = pos

        if best_pos == -1:
            if remaining.strip():
                segments.append(remaining.strip())
            break

        if best_pos == 0:
            # Remainder starts with a separator; find the next separator so we get a segment "6. A...\n\n" then "7. P..."
            next_pos = -1
            for sep in seps:
                p = remaining.find(sep, 1)
                if p != -1 and (next_pos == -1 or p < next_pos):
                    next_pos = p
            if next_pos == -1:
                if remaining.strip():
                    segments.append(remaining.strip())
                break
            segments.append(remaining[:next_pos].strip())
            remaining = remaining[next_pos:]
            continue

        before = remaining[:best_pos].strip()
        if before:
            segments.append(before)
        remaining = remaining[best_pos:]
    return _merge_trivial_trailing_splits(segments)


def main():
    parser = argparse.ArgumentParser(
        description="Find a parent chunk by file and ID, then split it with recursive custom separators and print results.",
    )
    parser.add_argument(
        "filename",
        type=str,
        help="Parent chunks filename (e.g. ISLAMABAD_CONSUMERS_PROTECTION_ACT,_1995_parent_chunks.json or just the act name part)",
    )
    parser.add_argument(
        "chunk_id",
        type=str,
        help="Parent chunk ID (e.g. ISLAMABAD_CONSUMERS_PROTECTION_ACT,_1995_3)",
    )
    parser.add_argument(
        "--chunk-size",
        type=int,
        default=10_000,
        help="Max character size before trying next separator (default: 10000)",
    )
    parser.add_argument(
        "--chunk-overlap",
        type=int,
        default=0,
        help="Overlap between consecutive chunks (default: 0)",
    )
    parser.add_argument(
        "--split-at-all",
        action="store_true",
        help="Split at every separator (use chunk_size=1 so e.g. '6. A' and '5. O' both start new segments)",
    )
    parser.add_argument(
        "--no-normalize-whitespace",
        action="store_true",
        help="Do not normalize whitespace in separators (e.g. keep '6.  Authority' as-is); may miss matches if spacing differs",
    )
    parser.add_argument(
        "--separators-only",
        action="store_true",
        help="Split strictly on separators only (ignore chunk size). Every separator starts a new segment; no size-based logic.",
    )
    args = parser.parse_args()

    # Resolve filename
    fname = args.filename.strip()
    if not fname.endswith(".json"):
        fname = f"{fname}_parent_chunks.json"

    path = find_parent_chunk_file(fname)
    if path is None:
        print(f"File not found under {CHUNKS_ROOT}/{{civil,criminal,family}}/parent_chunks/: {fname}", file=sys.stderr)
        sys.exit(1)

    chunk = load_and_find_chunk(path, args.chunk_id)
    if chunk is None:
        print(f"Chunk with parent_id '{args.chunk_id}' not found in {path}", file=sys.stderr)
        sys.exit(1)

    text = (chunk.get("text") or "").strip()
    if not text:
        print("Chunk text is empty.", file=sys.stderr)
        sys.exit(1)

    meta = chunk.get("metadata") or {}
    print(f"Found chunk: {meta.get('parent_id')} ({meta.get('section_number')} - {meta.get('section_title', '')})")
    print(f"Text length: {len(text)} chars")
    print("-" * 60)

    # Normalize whitespace so "6.  A" and "6. A" both match the same separator
    normalize_ws = not args.no_normalize_whitespace
    if normalize_ws:
        text = normalize_separator_whitespace(text)

    separators = build_separators_from_text(text, normalize_whitespace=normalize_ws)

    # Remove fallback separators for strict heading splitting
    strict_separators = [
        s for s in separators
        if s not in [" ", ". ", "\n", "\n\n", ""]
    ]

    if args.separators_only:
        print("Using --separators-only: heading-only division (fallback separators removed).")
        segments = split_strictly_on_separators(text, strict_separators)
    else:
        chunk_size = 1 if args.split_at_all else args.chunk_size
        if args.split_at_all:
            print("Using --split-at-all: chunk_size=1 so every separator starts a new segment.")
        splitter = RecursiveCharacterTextSplitter(
            separators=separators,
            chunk_size=chunk_size,
            chunk_overlap=args.chunk_overlap,
            length_function=len,
            strip_whitespace=True,
        )
        segments = splitter.split_text(text)

    print(f"Separators used: {len(separators)} (regex-derived + fallbacks)")
    print(f"Number of segments: {len(segments)}\n")
    for i, seg in enumerate(segments, 1):
        print(f"--- Segment {i} ({len(seg)} chars) ---")
        print(seg)
        print()


if __name__ == "__main__":
    main()
