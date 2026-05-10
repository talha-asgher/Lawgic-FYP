#!/usr/bin/env python3
"""Select clean Lawgic legal chunks for later RAG evaluation dataset generation.

This script is intentionally read-only for the application database. It does not
generate questions, call an LLM, modify embeddings, or touch production code.

DB mode uses the existing Backend app.database configuration, so DATABASE_URL or
the existing project DB config must be available. It also requires backend
dependencies such as SQLAlchemy to be installed in the active Python environment.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = REPO_ROOT / "Backend"
DEFAULT_OUTPUT = REPO_ROOT / "evaluation" / "datasets" / "clean_chunks.jsonl"
RAG_CHUNKING_ROOT = REPO_ROOT / "RAG" / "data" / "chunking"
CATEGORIES = ("civil", "criminal", "family")

if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))


_WS_RE = re.compile(r"\s+")
_TOKEN_RE = re.compile(r"[A-Za-z0-9\u0600-\u06FF]+", re.UNICODE)
_MOSTLY_PUNCT_RE = re.compile(r"^[\W_]+$", re.UNICODE)
_PAGE_MARKER_RE = re.compile(
    r"(?i)^\s*(?:page\s*)?\d{1,4}\s*(?:of\s*\d{1,4})?\s*$"
)
_HEADER_FOOTER_RE = re.compile(
    r"(?i)^\s*(?:the\s+)?(?:gazette|act|ordinance|rules?|schedule|chapter|section)\s+"
    r"(?:of\s+)?(?:pakistan|india)?\s*[A-Z0-9 .,-]*\s*$"
)
_CROSS_SECTION_RE = re.compile(
    r"(?i)\b(?:section|sections|sec\.?|s\.)\s+(\d+[A-Za-z]?(?:\s*\(\d+[A-Za-z]?\))?)"
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Load Lawgic legal chunks and select clean chunks for evaluation."
    )
    parser.add_argument("--limit", type=int, default=None, help="Maximum clean chunks to write.")
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help="JSONL output path. Default: evaluation/datasets/clean_chunks.jsonl",
    )
    parser.add_argument("--act-name", default=None, help="Optional exact act_name filter.")
    parser.add_argument("--category", default=None, help="Optional exact category filter.")
    parser.add_argument(
        "--source",
        choices=("auto", "db", "files"),
        default="auto",
        help=(
            "Load source. auto tries DB then local chunk files. "
            "db uses Backend app.database and requires DATABASE_URL plus backend dependencies."
        ),
    )
    parser.add_argument(
        "--min-text-length",
        type=int,
        default=150,
        help="Minimum normalized text length. Default: 150.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Run selection and print summary without writing JSONL.",
    )
    parser.add_argument(
        "--max-per-act",
        type=int,
        default=None,
        help="Optional cap on selected clean chunks per act_name after scoring.",
    )
    parser.add_argument(
        "--max-per-category",
        type=int,
        default=None,
        help="Optional cap on selected clean chunks per category after scoring.",
    )
    parser.add_argument(
        "--allow-missing-section",
        action="store_true",
        help=(
            "Allow chunks without section_number when act_name, text, and child_id "
            "or parent_id are present. Default is strict."
        ),
    )
    return parser.parse_args()


def clean_str(value: Any) -> str:
    if value is None:
        return ""
    return _WS_RE.sub(" ", str(value).replace("\u00a0", " ")).strip()


def normalize_text(text: str) -> str:
    return _WS_RE.sub(" ", text.replace("\u00a0", " ")).strip()


def normalize_for_duplicate(text: str) -> str:
    return normalize_text(text).lower()


def page_numbers(value: Any) -> List[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    return [value]


def first_present(row: Dict[str, Any], *keys: str) -> Any:
    for key in keys:
        value = row.get(key)
        if value is not None and clean_str(value):
            return value
    return None


def row_from_mapping(row: Dict[str, Any]) -> Dict[str, Any]:
    text = clean_str(first_present(row, "text", "chunk_text", "content", "page_content"))
    return {
        "act_name": clean_str(first_present(row, "act_name", "act", "law_name")),
        "category": clean_str(row.get("category")),
        "section_number": clean_str(
            first_present(row, "section_number", "section_no", "section", "sec_no")
        ),
        "section_title": clean_str(first_present(row, "section_title", "title", "heading")),
        "page_numbers": page_numbers(row.get("page_numbers")),
        "child_id": clean_str(first_present(row, "child_id", "object_id", "chunk_id", "id")),
        "parent_id": clean_str(
            first_present(row, "parent_id", "parent_chunk_id", "source_parent_id")
        ),
        "text": normalize_text(text),
    }


def load_db_chunks(act_name: Optional[str], category: Optional[str]) -> List[Dict[str, Any]]:
    try:
        from sqlalchemy import MetaData, Table, and_, select
    except Exception as exc:  # pragma: no cover - environment-dependent
        raise RuntimeError(
            "SQLAlchemy is required for --source db. Install backend requirements first."
        ) from exc

    try:
        from app.database import engine, SessionLocal
    except Exception as exc:  # pragma: no cover - environment-dependent
        raise RuntimeError(f"Could not import backend database config: {exc}") from exc

    meta = MetaData()
    law_child_metadata = Table("law_child_metadata", meta, autoload_with=engine)

    cols = law_child_metadata.c
    required = {
        "child_id",
        "parent_id",
        "act_name",
        "category",
        "section_number",
        "section_title",
        "page_numbers",
        "text",
    }
    missing = sorted(required - set(cols.keys()))
    if missing:
        raise RuntimeError(
            "law_child_metadata is missing expected columns: " + ", ".join(missing)
        )

    filters = []
    if act_name:
        filters.append(cols.act_name == act_name)
    if category:
        filters.append(cols.category == category)

    stmt = select(
        cols.child_id,
        cols.parent_id,
        cols.act_name,
        cols.category,
        cols.section_number,
        cols.section_title,
        cols.page_numbers,
        cols.text,
    )
    if filters:
        stmt = stmt.where(and_(*filters))
    stmt = stmt.order_by(cols.act_name.asc(), cols.section_number.asc(), cols.child_id.asc())

    with SessionLocal() as db:
        return [row_from_mapping(dict(row._mapping)) for row in db.execute(stmt)]


def iter_child_chunk_files() -> Iterable[Path]:
    for cat in CATEGORIES:
        root = RAG_CHUNKING_ROOT / cat / "child_chunks"
        if root.is_dir():
            yield from sorted(root.glob("*_child_chunks.json"))


def load_file_chunks(act_name: Optional[str], category: Optional[str]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for path in iter_child_chunk_files():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:
            print(f"[WARN] skipping unreadable chunk file {path}: {exc}", file=sys.stderr)
            continue
        if not isinstance(data, list):
            continue
        for item in data:
            if not isinstance(item, dict):
                continue
            meta = item.get("metadata") or {}
            row = row_from_mapping(
                {
                    **meta,
                    "text": item.get("text"),
                    "chunk_text": item.get("chunk_text"),
                    "content": item.get("content"),
                    "page_content": item.get("page_content"),
                }
            )
            if act_name and row["act_name"] != act_name:
                continue
            if category and row["category"] != category:
                continue
            rows.append(row)
    return rows


def text_noise_reason(text: str, min_text_length: int) -> Optional[str]:
    if not text:
        return "empty_text"
    if len(text) < min_text_length:
        return "text_too_short"

    lines = [line.strip() for line in text.splitlines() if line.strip()]
    compact = normalize_text(text)
    tokens = _TOKEN_RE.findall(compact)
    if len(tokens) < 25:
        return "too_few_tokens"
    if _PAGE_MARKER_RE.match(compact):
        return "page_number_only"
    if _MOSTLY_PUNCT_RE.match(compact):
        return "punctuation_noise"
    if len(compact) <= 220 and _HEADER_FOOTER_RE.match(compact):
        return "header_footer_like"
    if lines:
        short_lines = sum(1 for line in lines if len(line) <= 4 or _PAGE_MARKER_RE.match(line))
        if short_lines / len(lines) > 0.5:
            return "mostly_page_markers"

    alpha_num = sum(ch.isalnum() for ch in compact)
    if alpha_num / max(1, len(compact)) < 0.45:
        return "ocr_noise"

    unique_tokens = {t.lower() for t in tokens}
    if len(unique_tokens) / max(1, len(tokens)) < 0.18:
        return "repetitive_noise"

    return None


def single_chunk_answerable_reason(row: Dict[str, Any]) -> Optional[str]:
    text = row["text"]
    section_number = normalize_section_number(row["section_number"])
    refs = [normalize_section_number(m.group(1)) for m in _CROSS_SECTION_RE.finditer(text)]
    refs = [ref for ref in refs if ref]
    # When section_number is missing (--allow-missing-section), "every ref is external"
    # and we would over-skip. Only apply cross-section counts when we have a gold section.
    if section_number:
        external_refs = [ref for ref in refs if ref != section_number]
        if len(external_refs) >= 4:
            return "too_many_cross_section_refs"
    if re.search(r"(?i)\b(?:see|as provided in|subject to)\s+sections?\s+\d+", text):
        return "depends_on_other_sections"
    return None


def normalize_section_number(value: Any) -> str:
    raw = clean_str(value).lower()
    if not raw:
        return ""
    raw = raw.replace("section", "").replace("sec.", "").replace("sec", "")
    raw = raw.replace("s.", "")
    raw = re.sub(r"\s+", "", raw)
    raw = raw.replace("-", "")
    raw = re.sub(r"\(\s*", "(", raw)
    raw = re.sub(r"\s*\)", ")", raw)
    return raw


def candidate_score(row: Dict[str, Any]) -> Tuple[int, int]:
    score = 0
    if row["section_title"]:
        score += 3
    if row["child_id"]:
        score += 2
    if row["parent_id"]:
        score += 2
    if row["page_numbers"]:
        score += 1
    text_len = len(row["text"])
    if 250 <= text_len <= 2500:
        score += 2
    elif text_len > 2500:
        score += 1
    return score, text_len


def select_clean_chunks(
    rows: List[Dict[str, Any]],
    min_text_length: int,
    limit: Optional[int],
    max_per_act: Optional[int] = None,
    max_per_category: Optional[int] = None,
    allow_missing_section: bool = False,
) -> Tuple[List[Dict[str, Any]], Counter]:
    skip_reasons: Counter = Counter()
    seen: set[str] = set()
    selected: List[Dict[str, Any]] = []

    for row in rows:
        if not row["act_name"]:
            skip_reasons["missing_act_name"] += 1
            continue
        if not row["section_number"]:
            if not allow_missing_section:
                skip_reasons["missing_section_number"] += 1
                continue
            if not (row["child_id"] or row["parent_id"]):
                skip_reasons["missing_section_and_source_id"] += 1
                continue

        noise = text_noise_reason(row["text"], min_text_length)
        if noise:
            skip_reasons[noise] += 1
            continue

        answerability = single_chunk_answerable_reason(row)
        if answerability:
            skip_reasons[answerability] += 1
            continue

        dup_key = hashlib.sha256(
            (
                row["act_name"].lower()
                + "\n"
                + row["section_number"].lower()
                + "\n"
                + normalize_for_duplicate(row["text"])
            ).encode("utf-8", errors="ignore")
        ).hexdigest()
        if dup_key in seen:
            skip_reasons["duplicate_chunk"] += 1
            continue
        seen.add(dup_key)
        selected.append(row)

    selected.sort(key=lambda r: candidate_score(r), reverse=True)

    if max_per_act is not None or max_per_category is not None:
        capped: List[Dict[str, Any]] = []
        act_counts: Counter = Counter()
        category_counts: Counter = Counter()
        for row in selected:
            act_key = row["act_name"] or "(missing)"
            category_key = row["category"] or "(missing)"
            if max_per_act is not None and act_counts[act_key] >= max_per_act:
                skip_reasons["max_per_act_excluded"] += 1
                continue
            if (
                max_per_category is not None
                and category_counts[category_key] >= max_per_category
            ):
                skip_reasons["max_per_category_excluded"] += 1
                continue
            capped.append(row)
            act_counts[act_key] += 1
            category_counts[category_key] += 1
        selected = capped

    if limit is not None:
        if len(selected) > max(0, limit):
            skip_reasons["limit_excluded"] += len(selected) - max(0, limit)
        selected = selected[: max(0, limit)]
    return selected, skip_reasons


def deterministic_chunk_hash(row: Dict[str, Any]) -> str:
    basis = "\n".join(
        [
            row["act_name"].lower(),
            normalize_section_number(row["section_number"]),
            normalize_for_duplicate(row["text"]),
        ]
    )
    return "chunk_" + hashlib.sha256(basis.encode("utf-8", errors="ignore")).hexdigest()[:16]


def stable_object_id(row: Dict[str, Any]) -> str:
    """Align with RAG child rows: gold id must be law_child_metadata.child_id when present.
    Do not use parent_id — retrieval object_id is the child chunk, not the parent."""
    return row["child_id"] or deterministic_chunk_hash(row)


def to_jsonl_rows(chunks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for idx, row in enumerate(chunks, start=1):
        object_id = stable_object_id(row)
        out.append(
            {
                "id": object_id,
                "object_id": object_id,
                "dataset_row_id": f"chunk_{idx:04d}",
                "act_name": row["act_name"],
                "category": row["category"],
                "section_number": row["section_number"],
                "section_title": row["section_title"],
                "page_numbers": row["page_numbers"],
                "child_id": row["child_id"],
                "parent_id": row["parent_id"],
                "text": row["text"],
                "notes": "selected_clean_chunk",
            }
        )
    return out


def write_jsonl(path: Path, rows: List[Dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def load_source(args: argparse.Namespace) -> Tuple[str, List[Dict[str, Any]], Optional[str]]:
    if args.source == "db":
        return "db", load_db_chunks(args.act_name, args.category), None
    if args.source == "files":
        return "files", load_file_chunks(args.act_name, args.category), None

    db_error = None
    try:
        rows = load_db_chunks(args.act_name, args.category)
        if rows:
            return "db", rows, None
    except Exception as exc:
        db_error = str(exc)

    rows = load_file_chunks(args.act_name, args.category)
    return "files", rows, db_error


def print_summary(
    source: str,
    total_read: int,
    selected: int,
    skip_reasons: Counter,
    output: Path,
    dry_run: bool,
    db_error: Optional[str],
) -> None:
    print("Summary")
    print(f"  source used: {source}")
    if db_error:
        print(f"  db fallback reason: {db_error}")
    print(f"  total chunks read: {total_read}")
    print(f"  clean chunks selected: {selected}")
    print(f"  chunks skipped: {sum(skip_reasons.values())}")
    print("  skip reasons:")
    if skip_reasons:
        for reason, count in skip_reasons.most_common():
            print(f"    {reason}: {count}")
    else:
        print("    none: 0")
    print(f"  output path: {output}")
    if dry_run:
        print("  dry run: no file written")


def main() -> int:
    args = parse_args()
    if args.limit is not None and args.limit < 0:
        print("[ERROR] --limit must be zero or greater", file=sys.stderr)
        return 2
    if args.max_per_act is not None and args.max_per_act < 1:
        print("[ERROR] --max-per-act must be greater than zero", file=sys.stderr)
        return 2
    if args.max_per_category is not None and args.max_per_category < 1:
        print("[ERROR] --max-per-category must be greater than zero", file=sys.stderr)
        return 2
    if args.min_text_length < 1:
        print("[ERROR] --min-text-length must be greater than zero", file=sys.stderr)
        return 2

    try:
        source, rows, db_error = load_source(args)
    except Exception as exc:
        print(f"[ERROR] failed to load chunks: {exc}", file=sys.stderr)
        return 1

    if not rows:
        print("[ERROR] no legal chunks found for the selected source/filters", file=sys.stderr)
        if db_error:
            print(f"[ERROR] db fallback reason: {db_error}", file=sys.stderr)
        return 1

    clean_chunks, skip_reasons = select_clean_chunks(
        rows,
        min_text_length=args.min_text_length,
        limit=args.limit,
        max_per_act=args.max_per_act,
        max_per_category=args.max_per_category,
        allow_missing_section=args.allow_missing_section,
    )
    jsonl_rows = to_jsonl_rows(clean_chunks)

    if not args.dry_run:
        write_jsonl(args.output, jsonl_rows)

    print_summary(
        source=source,
        total_read=len(rows),
        selected=len(jsonl_rows),
        skip_reasons=skip_reasons,
        output=args.output,
        dry_run=args.dry_run,
        db_error=db_error,
    )

    if not jsonl_rows:
        print("[ERROR] chunks were found, but none passed the clean chunk filters", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
