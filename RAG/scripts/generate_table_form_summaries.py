#!/usr/bin/env python3
"""
Generate final table/form chunks with stricter, retrieval-oriented summaries.
"""

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Literal

CURRENT_FILE = Path(__file__).resolve()
PROJECT_ROOT = CURRENT_FILE.parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from models.slm_summarizer import TableFormSummarizer

DEFAULT_CHUNKS_ROOT = PROJECT_ROOT / "data" / "chunking"

BAD_PHRASES = [
    "financial information",
    "income and expenses",
    "case history",
    "fees charged by the council",
    "typically",
    "generally",
    "used to determine",
    "used to calculate fees",
    "who is expected to fill this form",
    "established under the act",
    "effective functioning",
    "plays a crucial",
    "enacted by the federal",
    "the council consists of the following",
    "this position is appointed",
]

# Substrings that indicate the model echoed instructions or placeholders.
PROMPT_LEAK_MARKERS = [
    "<clear table type>",
    "<clear form type>",
    "<5 to 10",
    "return exactly these 3 lines",
    "--- begin table text ---",
    "--- end table text ---",
    "--- begin form text ---",
    "--- end form text ---",
    "extra rule:",
    "detected type hint:",
    "output exactly three lines and nothing else",
]

PLACEHOLDER_WORDS = {
    "name", "father", "father's", "address", "identity", "card", "date", "birth", "vehicle",
    "licence", "license", "registration", "certificate", "probate", "collector", "court", "judge",
    "applicant", "appellant", "respondent", "plaintiff", "defendant",
}

TABLE_SUMMARY_ALLOWLIST = {
    "member", "members", "chairman", "chairperson", "ministry", "ministries", "representative",
    "representatives", "secretary", "federal", "government", "council", "division", "territory",
    "territories", "islamabad", "pakistan", "authority", "development", "commissioner", "chief",
    "parliament", "livestock", "industries", "industry", "production", "health", "interior", "finance",
    "food", "agriculture", "social", "worker", "workers", "appointed", "appointment", "consumers",
    "consumer", "associations", "association", "shopkeepers", "vendors", "manufacturers", "commerce",
    "ladies", "lady", "rank", "joint", "below", "prominent", "residing", "contains", "lists", "table",
    "title", "type", "composition", "membership", "bodies", "body", "includes", "including", "various",
    "several", "partial", "unclear", "index", "contents", "headings", "topics", "fields",
}


def normalize_whitespace(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def clean_markdown_noise(text: str) -> str:
    text = text or ""
    text = text.replace("&#xA;", " ")
    text = text.replace("<br/>", " ")
    text = text.replace("<br>", " ")
    text = text.replace("\\_", "_")
    text = re.sub(r"\*{1,2}", "", text)
    text = re.sub(r"_+", "_", text)
    text = re.sub(r"\|[- :]+\|", " ", text)
    return normalize_whitespace(text)


def clean_table_for_model(text: str) -> str:
    """Preserve row/column structure instead of flattening the table into one line."""
    text = text or ""
    text = text.replace("&#xA;", "\n")
    text = text.replace("<br/>", " / ")
    text = text.replace("<br>", " / ")
    text = text.replace("\\_", "_")
    text = re.sub(r"\*\*([^*]+)\*\*", r"\1", text)
    text = re.sub(r"\*([^*]+)\*", r"\1", text)
    lines = []
    for raw in text.splitlines():
        line = raw.rstrip()
        if not line.strip():
            continue
        if re.fullmatch(r"\s*\|?\s*[-: ]+(\|\s*[-: ]+)+\|?\s*", line):
            continue
        lines.append(line)
    return "\n".join(lines).strip()


def tokenize(text: str) -> list[str]:
    return re.findall(r"[A-Za-z][A-Za-z0-9\-']+", (text or "").lower())


def unique_preserve_order(items: list[str]) -> list[str]:
    seen = set()
    out = []
    for item in items:
        if item and item not in seen:
            seen.add(item)
            out.append(item)
    return out


def infer_table_type(text: str, metadata: dict[str, Any]) -> str:
    lower = (text or "").lower()
    title = str(metadata.get("section_title", "")).lower()
    if "short title" in lower and "commencement" in lower:
        return "contents/index table"
    if "plaintiff" in lower and "defendant" in lower:
        return "party/case details table"
    if "name of parties" in lower or "date of decree" in lower:
        return "execution/decree details table"
    if "members of parliament" in lower or "chairman" in lower or "ministry of" in lower:
        return "membership/composition table"
    if "description of property" in lower or "owner" in lower:
        return "property details table"
    if "stamp for" in lower or "pleader" in lower or "cost" in lower or "fee" in lower:
        return "fees/costs table"
    if "schedule" in title:
        return "schedule table"
    return "table"


def infer_form_type(text: str, metadata: dict[str, Any]) -> str:
    title = normalize_whitespace(str(metadata.get("section_title", ""))).lower()
    lower = (text or "").lower()
    if "application for licence to drive" in lower:
        return "driving licence application form"
    if "medical certificate" in lower:
        return "medical certificate form"
    if "renewal of driving licence" in lower:
        return "driving licence renewal form"
    if "addition of a new class of vehicle" in lower:
        return "new vehicle class addition form"
    if "registration of road vehicle" in lower:
        return "vehicle registration application form"
    if "certificate of registration" in lower:
        return "vehicle registration certificate form"
    if "probate" in lower:
        return "probate form"
    if "letters of administration" in lower:
        return "letters of administration form"
    if "collector" in lower and "recoverable" in lower:
        return "revenue recovery certificate form"
    if title:
        return title.lower()
    return "form"


def build_hint_metadata(kind: Literal["table", "form"], metadata: dict[str, Any], text: str) -> dict[str, Any]:
    hint = dict(metadata or {})
    hint["summary_style"] = "strict_retrieval_short"
    if kind == "table":
        hint["content_type_hint"] = infer_table_type(text, metadata)
        hint["instructions"] = (
            "Produce exactly 3 short lines. Keep all important visible entities, headings, or row topics, "
            "but avoid long sentences and avoid row numbering tokens."
        )
        tidx = metadata.get("table_index_in_section")
        if isinstance(tidx, int) and tidx > 1:
            hint["instructions"] += (
                " This chunk may continue an earlier table in the same section; summarize only the rows shown "
                "here without restating the whole body's introduction."
            )
    else:
        hint["content_type_hint"] = infer_form_type(text, metadata)
        hint["instructions"] = (
            "Produce exactly 3 short lines. Mention only the visible purpose and main fields. "
            "Keep field names clean and concise."
        )
    return hint


def _strip_cell_markdown(cell: str) -> str:
    s = normalize_whitespace(cell or "")
    s = re.sub(r"^\*+|\*+$", "", s).strip()
    return s


def _is_separator_table_row(cells: list[str]) -> bool:
    if not cells:
        return True
    return all(re.fullmatch(r"[\s\-:]+", c or "") for c in cells)


def _parse_table_row_cells(raw_line: str) -> list[str] | None:
    raw = raw_line.strip()
    if "|" not in raw or not raw.startswith("|"):
        return None
    inner = raw[1:-1] if raw.endswith("|") else raw[1:]
    cells = [_strip_cell_markdown(c) for c in inner.split("|")]
    if _is_separator_table_row(cells) or not cells:
        return None
    return cells


def _clip_at_word(text: str, max_chars: int) -> str:
    """Truncate at a word boundary for cleaner retrieval snippets (no mid-word cut)."""
    t = normalize_whitespace(text or "")
    if len(t) <= max_chars:
        return t
    cut = t[:max_chars].rstrip()
    if " " in cut:
        cut = cut.rsplit(" ", 1)[0].rstrip(",;")
    return cut + "…"


def parse_markdown_table_row_descriptions(
    text: str,
    max_rows: int = 12,
    max_cell_len: int = 200,
    clip_at_word_boundary: bool = False,
) -> list[str]:
    descriptions: list[str] = []
    for line in (text or "").splitlines():
        cells = _parse_table_row_cells(line)
        if cells is None:
            continue
        desc = ""
        if len(cells) >= 3:
            desc = cells[1]
        elif len(cells) == 2:
            a, b = cells[0], cells[1]
            if len(a) <= 12 and re.match(r"^[\(\[]?\s*[ivxlcdm\d]+[\.\)]?\s*[\)\]]?$", a, re.I):
                desc = b
            elif len(b) <= 20 and b.lower() in ("member", "members", "chairman"):
                desc = a
            else:
                desc = a if len(a) >= len(b) else b
        else:
            desc = cells[0]
        if len(desc) < 4:
            continue
        if re.fullmatch(r"[\(\[]?\s*[ivxlcdm\d]+[\.\)]?\s*[\)\]]?", desc, re.I):
            continue
        if clip_at_word_boundary:
            snippet = _clip_at_word(desc, max_cell_len)
        else:
            snippet = desc[:max_cell_len] + ("…" if len(desc) > max_cell_len else "")
        if snippet not in descriptions:
            descriptions.append(snippet)
        if len(descriptions) >= max_rows:
            break
    return descriptions


def prepare_text_for_summarizer(text: str, kind: Literal["table", "form"]) -> str:
    if kind == "table":
        return clean_table_for_model(text or "")
    return (text or "").strip()


def extract_candidate_phrases(text: str, limit: int = 8) -> list[str]:
    cleaned = clean_markdown_noise(text)
    parts = re.split(r"[|:\n;,]", cleaned)
    phrases: list[str] = []
    for part in parts:
        part = normalize_whitespace(part)
        if not part or len(part) < 3 or len(part) > 90:
            continue
        if re.fullmatch(r"[-–—.0-9Rsap/()]+", part):
            continue
        phrases.append(part)
    return unique_preserve_order(phrases)[:limit]


def has_prompt_leakage(summary: str) -> bool:
    low = (summary or "").lower()
    if any(m in low for m in PROMPT_LEAK_MARKERS):
        return True
    if low.count("title:") > 1:
        return True
    if low.count("type:") > 1:
        return True
    if low.count("contains:") > 1:
        return True
    return False


def is_valid_compact_summary(summary: str, kind: Literal["table", "form"]) -> bool:
    """Require exactly three non-empty lines: Title / Type / Contains with real values."""
    s = (summary or "").strip()
    max_len = 1200 if kind == "table" else 750
    if len(s) > max_len:
        return False
    lines = [ln.strip() for ln in s.splitlines() if ln.strip()]
    if len(lines) != 3:
        return False
    a, b, c = lines[0].lower(), lines[1].lower(), lines[2].lower()
    if not a.startswith("title:"):
        return False
    if not b.startswith("type:"):
        return False
    if not c.startswith("contains:"):
        return False
    type_body = lines[1][5:].strip()
    contains_body = lines[2][9:].strip()
    if not type_body or not contains_body:
        return False
    if "<" in lines[1] or ">" in lines[1]:
        return False
    if len(contains_body) < 6:
        return False
    return True


def _normalize_contains_segment(phrase: str) -> str:
    """Trim whitespace and trailing list punctuation so joins do not produce ';;'."""
    t = normalize_whitespace(phrase or "")
    return t.rstrip(" ;,\t")


def join_contains_phrases(phrases: list[str], max_before_note: int = 7) -> str:
    cleaned: list[str] = []
    for p in phrases:
        n = _normalize_contains_segment(p)
        if n:
            cleaned.append(n)
    if not cleaned:
        return "partial or unclear table"
    if len(cleaned) <= max_before_note:
        return "; ".join(cleaned)
    head = cleaned[: max_before_note - 1]
    n_more = len(cleaned) - len(head)
    return "; ".join(head) + f"; … and {n_more} further rows or topics"


def polish_compact_summary_contains_line(summary: str) -> str:
    """Re-split Contains on ';' and rejoin so ';;' and stray spacing from the model are fixed."""
    raw = (summary or "").strip()
    lines = [ln.rstrip() for ln in raw.splitlines()]
    nonempty = [ln for ln in lines if ln.strip()]
    if len(nonempty) != 3:
        return summary
    third = nonempty[2]
    low3 = third.lower()
    if not low3.startswith("contains:"):
        return summary
    idx = third.find(":")
    body = third[idx + 1 :].strip()
    parts = [p.strip() for p in body.split(";")]
    cleaned = [_normalize_contains_segment(p) for p in parts if _normalize_contains_segment(p)]
    if not cleaned:
        return summary
    nonempty[2] = third[: idx + 1].rstrip() + " " + "; ".join(cleaned)
    return "\n".join(nonempty)


def extract_key_fields_from_form(text: str, limit: int = 12) -> list[str]:
    cleaned = clean_markdown_noise(text)
    fields = []
    for line in re.split(r"\n+|(?<=\.)\s{2,}", cleaned):
        line = normalize_whitespace(line)
        if not line:
            continue
        if re.match(r"^\d+\.\s*", line):
            line = re.sub(r"^\d+\.\s*", "", line).strip()
            line = re.split(r"\.{2,}|…+", line)[0].strip(" :.-")
            if line:
                fields.append(line)
    if not fields:
        fields = extract_candidate_phrases(cleaned, limit=limit)
    return unique_preserve_order(fields)[:limit]


def summary_supported_by_text(summary: str, text: str, kind: Literal["table", "form"] = "table") -> bool:
    text_tokens = set(tokenize(text))
    summary_tokens = tokenize(summary)
    allow = PLACEHOLDER_WORDS | (TABLE_SUMMARY_ALLOWLIST if kind == "table" else set())
    unsupported = []
    for tok in summary_tokens:
        if len(tok) <= 4 or tok in allow:
            continue
        if tok not in text_tokens:
            unsupported.append(tok)
    threshold = 0.48 if kind == "table" else 0.35
    min_tokens = 10 if kind == "table" else 8
    if len(summary_tokens) >= min_tokens and len(unsupported) / max(len(summary_tokens), 1) > threshold:
        return False
    return True


def looks_unreliable(summary: str, text: str, kind: Literal["table", "form"]) -> bool:
    summary_norm = normalize_whitespace(summary)
    if not summary_norm:
        return True
    if has_prompt_leakage(summary_norm):
        return True
    if not is_valid_compact_summary(summary_norm, kind):
        return True
    lower = summary_norm.lower()
    if len(summary_norm) < 24:
        return True
    max_total = 1250 if kind == "table" else 720
    if len(summary_norm) > max_total:
        return True
    if any(bad in lower for bad in BAD_PHRASES):
        return True
    if lower.endswith(("under the", "within the", "by the", "for the")):
        return True
    if not summary_supported_by_text(summary_norm, text, kind):
        return True
    if kind == "table" and lower.count("this table") > 1:
        return True
    return False


def format_compact_table_summary(text: str, metadata: dict[str, Any]) -> str:
    title = normalize_whitespace(str(metadata.get("section_title", ""))) or "Untitled"
    table_type = infer_table_type(text, metadata)
    if table_type == "membership/composition table":
        row_descs = parse_markdown_table_row_descriptions(
            text,
            max_rows=24,
            max_cell_len=130,
            clip_at_word_boundary=True,
        )
    else:
        row_descs = parse_markdown_table_row_descriptions(text, max_rows=24, max_cell_len=200)
    if row_descs:
        contains = row_descs
    else:
        contains = extract_candidate_phrases(text, limit=10)
    contains_text = join_contains_phrases(contains, max_before_note=8)
    return f"Title: {title}\nType: {table_type}\nContains: {contains_text}"


def format_compact_form_summary(text: str, metadata: dict[str, Any]) -> str:
    title = normalize_whitespace(str(metadata.get("section_title", ""))) or "Untitled"
    form_type = infer_form_type(text, metadata)
    fields = extract_key_fields_from_form(text, limit=8)
    fields_text = ", ".join(fields[:8]) if fields else "partial form with visible fields only"
    return f"Title: {title}\nType: {form_type}\nContains: {fields_text}"


def call_summarizer(
    summarizer: TableFormSummarizer,
    kind: Literal["table", "form"],
    text: str,
    metadata: dict[str, Any],
    temperature: float | None = None,
    top_p: float | None = None,
    max_new_tokens: int | None = None,
) -> str:
    if kind == "table":
        return summarizer.summarize_table(text=text, metadata=metadata, temperature=temperature, top_p=top_p, max_new_tokens=max_new_tokens)
    return summarizer.summarize_form(text=text, metadata=metadata, temperature=temperature, top_p=top_p, max_new_tokens=max_new_tokens)


def summarize_item(
    item: dict[str, Any],
    kind: Literal["table", "form"],
    summarizer: TableFormSummarizer,
    max_new_tokens_table: int = 160,
    max_new_tokens_form: int = 96,
) -> str:
    text = (item.get("text") or "").strip()
    metadata = item.get("metadata", {}) or {}
    if not text:
        return item.get("summary", "")

    text_for_model = prepare_text_for_summarizer(text, kind)
    hint_metadata = build_hint_metadata(kind, metadata, text)
    primary_tokens = max_new_tokens_table if kind == "table" else max_new_tokens_form
    retry_tokens = min(primary_tokens + 32, 192)

    summary = call_summarizer(
        summarizer,
        kind,
        text_for_model,
        hint_metadata,
        temperature=0.0,
        top_p=0.8,
        max_new_tokens=primary_tokens,
    )

    if looks_unreliable(summary, text, kind):
        retry_metadata = dict(hint_metadata)
        retry_metadata["instructions"] += " Keep it to exactly 3 short lines and keep the Contains line compact."
        summary = call_summarizer(
            summarizer,
            kind,
            text_for_model,
            retry_metadata,
            temperature=0.0,
            top_p=0.7,
            max_new_tokens=retry_tokens,
        )

    if looks_unreliable(summary, text, kind):
        if kind == "table":
            summary = format_compact_table_summary(text, metadata)
        else:
            summary = format_compact_form_summary(text, metadata)

    if kind == "table":
        summary = polish_compact_summary_contains_line(summary)
    return summary.strip()


def maybe_configure_summarizer(summarizer: TableFormSummarizer, temperature: float, top_p: float, max_new_tokens: int) -> None:
    summarizer.temperature = temperature
    summarizer.top_p = top_p
    summarizer.max_new_tokens = max_new_tokens


def summarize_file(
    in_path: Path,
    out_path: Path,
    kind: Literal["table", "form"],
    summarizer: TableFormSummarizer,
    max_new_tokens_table: int = 160,
    max_new_tokens_form: int = 96,
) -> None:
    print(f"\nProcessing {in_path} ({kind})")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    data = json.loads(in_path.read_text(encoding="utf-8"))
    new_data = []
    for idx, item in enumerate(data, start=1):
        new_item = dict(item)
        new_item["summary"] = summarize_item(item, kind, summarizer, max_new_tokens_table=max_new_tokens_table, max_new_tokens_form=max_new_tokens_form)
        new_data.append(new_item)
        print(f"  [{idx}/{len(data)}] summarized")
    out_path.write_text(json.dumps(new_data, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"  -> Wrote {len(new_data)} chunks to {out_path}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--chunks-root", type=Path, default=DEFAULT_CHUNKS_ROOT)
    parser.add_argument("--temperature", type=float, default=0.0)
    parser.add_argument("--top-p", type=float, default=0.8)
    parser.add_argument(
        "--max-new-tokens",
        type=int,
        default=160,
        help="Max new tokens for table summarization (and default cap for forms unless --form-max-new-tokens).",
    )
    parser.add_argument("--form-max-new-tokens", type=int, default=None, help="If set, max new tokens for form chunks only.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    summarizer = TableFormSummarizer(temperature=args.temperature, top_p=args.top_p, max_new_tokens=args.max_new_tokens)
    maybe_configure_summarizer(summarizer=summarizer, temperature=args.temperature, top_p=args.top_p, max_new_tokens=args.max_new_tokens)
    chunks_root = args.chunks_root
    form_tok = args.form_max_new_tokens if args.form_max_new_tokens is not None else min(96, args.max_new_tokens)

    table_chunk_dirs = [chunks_root / "civil" / "table_chunks", chunks_root / "family" / "table_chunks", chunks_root / "criminal" / "table_chunks"]
    print("=== TABLES ===")
    for in_dir in table_chunk_dirs:
        if not in_dir.exists():
            continue
        domain = in_dir.parent.name
        out_dir = chunks_root / domain / "table_summaries"
        files = sorted(in_dir.glob("*.json"))
        print(f"\nDomain: {domain} | Found {len(files)} table chunk files.")
        for in_path in files:
            out_path = out_dir / in_path.name
            summarize_file(in_path, out_path, "table", summarizer, max_new_tokens_table=args.max_new_tokens, max_new_tokens_form=form_tok)

    form_chunk_dirs = [chunks_root / "civil" / "form_chunks", chunks_root / "family" / "form_chunks", chunks_root / "criminal" / "form_chunks"]
    print("\n=== FORMS ===")
    for in_dir in form_chunk_dirs:
        if not in_dir.exists():
            continue
        domain = in_dir.parent.name
        out_dir = chunks_root / domain / "form_summaries"
        files = sorted(in_dir.glob("*.json"))
        print(f"\nDomain: {domain} | Found {len(files)} form chunk files.")
        for in_path in files:
            out_path = out_dir / in_path.name
            summarize_file(in_path, out_path, "form", summarizer, max_new_tokens_table=args.max_new_tokens, max_new_tokens_form=form_tok)


if __name__ == "__main__":
    main()
