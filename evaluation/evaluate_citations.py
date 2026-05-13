#!/usr/bin/env python3
"""Citation-focused evaluation for Lawgic RAG (production path: retrieve + LLM).

Measures citation and source alignment against dataset gold fields only—not full answer
faithfulness, entailment, or legal correctness of free text beyond cited passages.

Runs the same stack as ``POST /rag/ask``: ``retrieve_for_rag_ask`` then ``finalize_rag_ask``,
with the same ``RagAskRequest`` defaults as ``Frontend/lib/api.js`` ``ragAsk`` (top_k 15 / 6).
Requires PostgreSQL, embeddings, optional reranker, and Ollama.

**Indexing (same as chatbot / ``finalize_rag_ask``):**
``used_source_indexes`` are **1-based** positions into ``RagAskResponse.retrieved_chunks``, in
the same order as ``chunks_to_sources`` / prompt labels ``[1]``, ``[2]``, … (see
``chunks_to_retrieved_out`` and ``chunks_to_sources`` on ``deduped_top``).

Example:
  python evaluation/evaluate_citations.py --dataset evaluation/datasets/new_dataset.jsonl \\
      --output-dir evaluation/results

  # Verbose: tqdm / extra prints
  python evaluation/evaluate_citations.py --dataset evaluation/datasets/new_dataset.jsonl \\
      --output-dir evaluation/results --verbose

  # Long runs: fixed details file + resume after interrupt
  python evaluation/evaluate_citations.py --details-file evaluation/results/citation_run.jsonl \\
      --resume --output-dir evaluation/results

Each run also writes ``citation_eval_failures_<timestamp>.jsonl`` (same directory, same stamp as
summary) for rows tagged with citation issues (see ``failure_tags`` in those lines).
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import re
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple


REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = REPO_ROOT / "Backend"
DEFAULT_DATASET = REPO_ROOT / "evaluation" / "datasets" / "new_dataset.jsonl"
DEFAULT_OUTPUT_DIR = REPO_ROOT / "evaluation" / "results"

CHATBOT_TOP_K_RETRIEVAL = 15
CHATBOT_TOP_K_CONTEXT = 6

BRACKET_CITE_RE = re.compile(r"\[(\d+)\]")

if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))


def norm_text(value: Any) -> str:
    if value is None:
        return ""
    return re.sub(r"\s+", " ", str(value).replace("\u00a0", " ")).strip().lower()


def norm_section(value: Any) -> str:
    text = norm_text(value)
    if not text:
        return ""
    text = re.sub(r"^(?:section|sec\.?|s\.?)\s*", "", text)
    text = text.replace("-", "")
    text = re.sub(r"\s+", "", text)
    text = re.sub(r"\(\s*", "(", text)
    text = re.sub(r"\s*\)", ")", text)
    return text


def safe_str(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def load_jsonl(path: Path) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as f:
        for line_no, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid JSON on line {line_no}: {exc}") from exc
            if not isinstance(row, dict):
                raise ValueError(f"Expected JSON object on line {line_no}")
            rows.append(row)
    return rows


def filter_rows(rows: List[Dict[str, Any]], args: argparse.Namespace) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for row in rows:
        if args.language != "all" and safe_str(row.get("language")) != args.language:
            continue
        if args.question_type and safe_str(row.get("question_type")) != args.question_type:
            continue
        out.append(row)
        if args.limit is not None and len(out) >= args.limit:
            break
    return out


def _citation_success_error_counts(metrics: List[CitationRowMetrics]) -> Tuple[int, int]:
    err_n = sum(1 for m in metrics if m.error)
    return len(metrics) - err_n, err_n


def progress_iter(rows: List[Dict[str, Any]], verbose: bool) -> Iterable[Tuple[int, Dict[str, Any]]]:
    total = len(rows)
    if verbose:
        try:
            from tqdm import tqdm

            yield from enumerate(tqdm(rows, desc="Citation eval"), start=1)
            return
        except Exception:
            pass
    for idx, row in enumerate(rows, start=1):
        if verbose and (idx == 1 or idx == total or idx % 10 == 0):
            print(f"Citation eval {idx}/{total}")
        yield idx, row


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate citations in Lawgic RAG answers.")
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument(
        "--candidate-k",
        type=int,
        default=CHATBOT_TOP_K_RETRIEVAL,
        help="RagAskRequest.top_k_retrieval (default 15; same as ragAsk).",
    )
    parser.add_argument(
        "--context-k",
        type=int,
        default=None,
        help="RagAskRequest.top_k_context (default 6).",
    )
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--language", choices=("en", "ur", "all"), default="all")
    parser.add_argument("--question-type", default=None)
    parser.add_argument("--verbose", action="store_true")
    parser.add_argument(
        "--details-file",
        type=Path,
        default=None,
        help="JSONL path for per-row output. Required for --resume.",
    )
    parser.add_argument(
        "--summary-file",
        type=Path,
        default=None,
        help="JSON summary path (default: citation_eval_summary_<stamp>.json in output-dir).",
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Skip eval_id rows already present in --details-file; append new lines.",
    )
    parser.add_argument(
        "--context-dump-chars",
        type=int,
        default=2000,
        help="Truncate each retrieved chunk text in details JSONL (0 = omit text).",
    )
    return parser.parse_args()


def configure_logging(verbose: bool) -> None:
    if verbose:
        return
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.pool").setLevel(logging.WARNING)


def effective_context_k(arg_value: Optional[int]) -> int:
    if arg_value is not None:
        return int(arg_value)
    return CHATBOT_TOP_K_CONTEXT


def import_backend(verbose: bool) -> Dict[str, Any]:
    try:
        from sqlalchemy import text
        from app.database import SessionLocal, engine
        from app.schemas import RagAskRequest
        from app.services.rag_service import finalize_rag_ask, retrieve_for_rag_ask
        from app.services.query_embedder import get_bge_query_model_id
        from app.services.reranker_service import (
            get_reranker_model_id,
            is_reranker_enabled,
            max_rerank_candidates,
        )
        from app.services.ollama_service import OllamaServiceError
    except Exception as exc:
        raise RuntimeError(
            "Could not import Lawgic backend. Install Backend requirements, set DB config, "
            "run from repo root."
        ) from exc
    if not verbose:
        engine.echo = False
    return {
        "SessionLocal": SessionLocal,
        "text": text,
        "RagAskRequest": RagAskRequest,
        "retrieve_for_rag_ask": retrieve_for_rag_ask,
        "finalize_rag_ask": finalize_rag_ask,
        "get_bge_query_model_id": get_bge_query_model_id,
        "get_reranker_model_id": get_reranker_model_id,
        "is_reranker_enabled": is_reranker_enabled,
        "max_rerank_candidates": max_rerank_candidates,
        "OllamaServiceError": OllamaServiceError,
    }


def preflight_database(SessionLocal: Any, text: Any) -> None:
    db = SessionLocal()
    try:
        db.execute(text("SELECT 1"))
    finally:
        db.close()


def expected_gold_id(row: Dict[str, Any]) -> str:
    return safe_str(row.get("expected_child_id") or row.get("expected_object_id"))


def pages_norm_list(value: Any) -> List[int]:
    if value is None:
        return []
    if isinstance(value, (int, float)):
        return [int(value)]
    if isinstance(value, str) and value.strip():
        try:
            return [int(value.strip())]
        except ValueError:
            return []
    if isinstance(value, list):
        out: List[int] = []
        for x in value:
            try:
                out.append(int(x))
            except (TypeError, ValueError):
                continue
        return out
    return []


def pages_overlap(expected: List[int], actual: Any) -> bool:
    if not expected:
        return False
    act = pages_norm_list(actual)
    if not act:
        return False
    return bool(set(expected) & set(act))


def act_matches(expected: str, actual: Optional[str]) -> bool:
    if not safe_str(expected):
        return False
    return norm_text(expected) == norm_text(actual)


def section_matches(expected: str, actual: Optional[str]) -> bool:
    if not safe_str(expected):
        return False
    return norm_section(expected) == norm_section(actual)


def _chunk_to_context_dict(ch: Any, max_text: int) -> Dict[str, Any]:
    text = safe_str(getattr(ch, "text", ""))
    if max_text > 0 and len(text) > max_text:
        text = text[: max_text - 3] + "..."
    elif max_text <= 0:
        text = ""
    pages = getattr(ch, "page_numbers", None)
    return {
        "chunk_type": safe_str(getattr(ch, "chunk_type", "")),
        "object_id": safe_str(getattr(ch, "object_id", "")),
        "parent_id": safe_str(getattr(ch, "parent_id", "")),
        "act_name": safe_str(getattr(ch, "act_name", "")),
        "category": safe_str(getattr(ch, "category", "")),
        "section_number": safe_str(getattr(ch, "section_number", "")),
        "section_title": safe_str(getattr(ch, "section_title", "")),
        "page_numbers": pages if isinstance(pages, list) else pages,
        "text": text,
    }


def _sources_to_dicts(resp: Any) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    def dump_list(attr: str) -> List[Dict[str, Any]]:
        out: List[Dict[str, Any]] = []
        for s in getattr(resp, attr, None) or []:
            if hasattr(s, "model_dump"):
                out.append(s.model_dump())
            elif hasattr(s, "dict"):
                out.append(s.dict())
            else:
                out.append(dict(s))
        return out

    return dump_list("sources"), dump_list("retrieved_sources")


@dataclass
class CitationRowMetrics:
    eval_id: str
    question: str
    language: str
    low_retrieval_confidence: bool
    insufficient_context: bool
    error: Optional[str]

    n_context_passages: int
    used_source_indexes: List[int]
    used_source_ids: List[str]
    bracket_indexes_in_answer: List[int]

    n_index_mentions: int
    n_invalid_indices: int
    n_invalid_source_ids: int
    citation_structurally_valid: bool
    has_model_citation: bool
    has_bracket_citation: bool
    json_and_bracket_consistent: bool

    gold_object_id: str
    gold_in_context: bool
    gold_cited: bool
    gold_cited_via_indexes: bool
    gold_cited_via_used_source_ids: bool
    cited_act_correct: bool
    cited_section_correct: bool
    cited_page_correct: bool
    has_expected_pages: bool
    answer_soft_supported_by_citation: bool
    cited_object_ids_union: List[str]


def metrics_from_detail_dict(d: Dict[str, Any]) -> CitationRowMetrics:
    def _list(key: str, alt: Optional[str] = None) -> List[Any]:
        if alt is not None and key not in d and alt in d:
            v = d.get(alt)
        else:
            v = d.get(key)
        return list(v) if isinstance(v, list) else []

    def _int(key: str, default: int = 0) -> int:
        try:
            return int(d.get(key, default))
        except (TypeError, ValueError):
            return default

    idxs: List[int] = []
    for x in _list("used_source_indexes"):
        try:
            idxs.append(int(x))
        except (TypeError, ValueError):
            pass

    has_mod = bool(d.get("has_model_citation"))
    if not has_mod and ("has_json_citation" in d):
        has_mod = bool(d.get("has_json_citation"))
    if not has_mod:
        has_mod = bool(idxs) or bool([safe_str(x) for x in _list("used_source_ids") if safe_str(x)])

    struct = d.get("citation_structurally_valid")
    if struct is None:
        struct = bool(d.get("all_indices_valid", False)) and _int("n_invalid_source_ids", 0) == 0

    brackets: List[int] = []
    for b in _list("bracket_indexes_in_answer"):
        try:
            brackets.append(int(b))
        except (TypeError, ValueError):
            pass

    if "has_expected_pages" in d:
        has_ep = bool(d.get("has_expected_pages"))
    else:
        has_ep = bool(pages_norm_list(d.get("expected_page_numbers")))

    return CitationRowMetrics(
        eval_id=safe_str(d.get("eval_id")),
        question=safe_str(d.get("question")),
        language=safe_str(d.get("language")),
        low_retrieval_confidence=bool(d.get("low_retrieval_confidence", False)),
        insufficient_context=bool(d.get("insufficient_context", False)),
        error=d.get("error"),
        n_context_passages=_int("n_context_passages"),
        used_source_indexes=idxs,
        used_source_ids=[safe_str(x) for x in _list("used_source_ids") if safe_str(x)],
        bracket_indexes_in_answer=brackets,
        n_index_mentions=_int("n_index_mentions"),
        n_invalid_indices=_int("n_invalid_indices"),
        n_invalid_source_ids=_int("n_invalid_source_ids"),
        citation_structurally_valid=bool(struct),
        has_model_citation=has_mod,
        has_bracket_citation=bool(d.get("has_bracket_citation", False)),
        json_and_bracket_consistent=bool(d.get("json_and_bracket_consistent", True)),
        gold_object_id=safe_str(d.get("gold_object_id")),
        gold_in_context=bool(d.get("gold_in_context", False)),
        gold_cited=bool(d.get("gold_cited", False)),
        gold_cited_via_indexes=bool(d.get("gold_cited_via_indexes", False)),
        gold_cited_via_used_source_ids=bool(d.get("gold_cited_via_used_source_ids", False)),
        cited_act_correct=bool(d.get("cited_act_correct", False)),
        cited_section_correct=bool(d.get("cited_section_correct", False)),
        cited_page_correct=bool(d.get("cited_page_correct", False)),
        has_expected_pages=has_ep,
        answer_soft_supported_by_citation=bool(d.get("answer_soft_supported_by_citation", False)),
        cited_object_ids_union=[safe_str(x) for x in _list("cited_object_ids_union")],
    )


def analyze_one_response(
    row: Dict[str, Any],
    resp: Any,
    retrieved_chunks: List[Any],
) -> CitationRowMetrics:
    eval_id = safe_str(row.get("id"))
    question = safe_str(row.get("question"))
    language = safe_str(row.get("language"))
    gold = expected_gold_id(row)

    used_idx_raw = list(getattr(resp, "used_source_indexes", None) or [])
    used_idx: List[int] = []
    index_parse_failures = 0
    for u in used_idx_raw:
        try:
            used_idx.append(int(u))
        except (TypeError, ValueError):
            index_parse_failures += 1

    used_ids = [safe_str(x) for x in (getattr(resp, "used_source_ids", None) or []) if safe_str(x)]
    answer = safe_str(getattr(resp, "answer", ""))
    brackets: List[int] = []
    for m in BRACKET_CITE_RE.finditer(answer):
        try:
            brackets.append(int(m.group(1)))
        except ValueError:
            continue
    n_ctx = len(retrieved_chunks)
    context_oids = {safe_str(getattr(ch, "object_id", "")) for ch in retrieved_chunks if safe_str(getattr(ch, "object_id", ""))}

    invalid_idx = index_parse_failures
    for u in used_idx:
        if u < 1 or u > n_ctx:
            invalid_idx += 1

    invalid_source_ids = [oid for oid in used_ids if oid not in context_oids]
    n_invalid_source_ids = len(invalid_source_ids)

    has_indexes = len(used_idx_raw) > 0
    has_model_citation = has_indexes or len(used_ids) > 0

    indices_ok = (not has_indexes) or (invalid_idx == 0)
    ids_ok = (not used_ids) or (n_invalid_source_ids == 0)
    citation_structurally_valid = has_model_citation and indices_ok and ids_ok

    has_br = len(brackets) > 0
    bset = set(brackets)
    jset = set(used_idx)
    brackets_in_range = bool(brackets) and all(1 <= b <= n_ctx for b in brackets)
    json_and_bracket_consistent = (not has_br) or (
        brackets_in_range and bset.issubset(jset)
    )

    cited_oids_from_indexes: List[str] = []
    if has_indexes and invalid_idx == 0:
        for u in used_idx:
            ch = retrieved_chunks[u - 1]
            cited_oids_from_indexes.append(safe_str(getattr(ch, "object_id", "")))

    cited_oids_from_ids = [oid for oid in used_ids if oid in context_oids]
    union_set = set(cited_oids_from_indexes) | set(cited_oids_from_ids)
    cited_object_ids_union = sorted(union_set)

    cited_acts: List[str] = []
    cited_secs: List[str] = []
    for oid in sorted(union_set):
        for ch in retrieved_chunks:
            if safe_str(getattr(ch, "object_id", "")) == oid:
                cited_acts.append(safe_str(getattr(ch, "act_name", "")))
                cited_secs.append(safe_str(getattr(ch, "section_number", "")))
                break

    gold_in_ctx = False
    if gold:
        for ch in retrieved_chunks:
            if safe_str(getattr(ch, "object_id", "")) == gold:
                gold_in_ctx = True
                break

    gold_via_idx = bool(gold) and gold in set(cited_oids_from_indexes)
    gold_via_ids = bool(gold) and gold in set(cited_oids_from_ids)
    gold_cited = gold_via_idx or gold_via_ids

    exp_act = safe_str(row.get("expected_act_name"))
    exp_sec = safe_str(row.get("expected_section_number"))
    exp_pages = pages_norm_list(row.get("expected_page_numbers"))
    has_expected_pages = bool(exp_pages)

    act_ok = (
        citation_structurally_valid
        and bool(union_set)
        and any(act_matches(exp_act, a) for a in cited_acts)
    )
    sec_ok = (
        citation_structurally_valid
        and bool(union_set)
        and any(section_matches(exp_sec, s) for s in cited_secs)
    )
    page_ok = False
    if citation_structurally_valid and bool(union_set) and has_expected_pages:
        for u in used_idx:
            if 1 <= u <= n_ctx and pages_overlap(exp_pages, getattr(retrieved_chunks[u - 1], "page_numbers", None)):
                page_ok = True
                break
        if not page_ok:
            for oid in cited_oids_from_ids:
                for ch in retrieved_chunks:
                    if safe_str(getattr(ch, "object_id", "")) == oid:
                        if pages_overlap(exp_pages, getattr(ch, "page_numbers", None)):
                            page_ok = True
                        break
                if page_ok:
                    break

    soft_supported = gold_cited or (
        bool(gold)
        and citation_structurally_valid
        and bool(union_set)
        and any(
            act_matches(exp_act, a) and section_matches(exp_sec, s)
            for a, s in zip(cited_acts, cited_secs)
        )
    )

    return CitationRowMetrics(
        eval_id=eval_id,
        question=question,
        language=language,
        low_retrieval_confidence=bool(getattr(resp, "low_retrieval_confidence", False)),
        insufficient_context=bool(getattr(resp, "insufficient_context", False)),
        error=None,
        n_context_passages=n_ctx,
        used_source_indexes=used_idx,
        used_source_ids=used_ids,
        bracket_indexes_in_answer=brackets,
        n_index_mentions=len(used_idx_raw),
        n_invalid_indices=invalid_idx,
        n_invalid_source_ids=n_invalid_source_ids,
        citation_structurally_valid=citation_structurally_valid,
        has_model_citation=has_model_citation,
        has_bracket_citation=has_br,
        json_and_bracket_consistent=json_and_bracket_consistent,
        gold_object_id=gold,
        gold_in_context=gold_in_ctx,
        gold_cited=gold_cited,
        gold_cited_via_indexes=gold_via_idx,
        gold_cited_via_used_source_ids=gold_via_ids,
        cited_act_correct=act_ok,
        cited_section_correct=sec_ok,
        cited_page_correct=page_ok,
        has_expected_pages=has_expected_pages,
        answer_soft_supported_by_citation=soft_supported,
        cited_object_ids_union=cited_object_ids_union,
    )


def row_metrics_to_dict(m: CitationRowMetrics) -> Dict[str, Any]:
    return m.__dict__.copy()


def empty_metrics(row: Dict[str, Any], question: str, err: Optional[str]) -> CitationRowMetrics:
    has_ep = bool(pages_norm_list(row.get("expected_page_numbers")))
    return CitationRowMetrics(
        eval_id=safe_str(row.get("id")),
        question=question,
        language=safe_str(row.get("language")),
        low_retrieval_confidence=False,
        insufficient_context=False,
        error=err,
        n_context_passages=0,
        used_source_indexes=[],
        used_source_ids=[],
        bracket_indexes_in_answer=[],
        n_index_mentions=0,
        n_invalid_indices=0,
        n_invalid_source_ids=0,
        citation_structurally_valid=False,
        has_model_citation=False,
        has_bracket_citation=False,
        json_and_bracket_consistent=True,
        gold_object_id=expected_gold_id(row),
        gold_in_context=False,
        gold_cited=False,
        gold_cited_via_indexes=False,
        gold_cited_via_used_source_ids=False,
        cited_act_correct=False,
        cited_section_correct=False,
        cited_page_correct=False,
        has_expected_pages=has_ep,
        answer_soft_supported_by_citation=False,
        cited_object_ids_union=[],
    )


def expected_metadata_from_row(row: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "expected_act_name": safe_str(row.get("expected_act_name")),
        "expected_section_number": safe_str(row.get("expected_section_number")),
        "expected_section_title": safe_str(row.get("expected_section_title")),
        "expected_page_numbers": pages_norm_list(row.get("expected_page_numbers")),
    }


def build_detail_record(
    m: CitationRowMetrics,
    resp: Optional[Any],
    retrieved_chunks: List[Any],
    context_dump_chars: int,
    dataset_row: Dict[str, Any],
) -> Dict[str, Any]:
    d = row_metrics_to_dict(m)
    d.update(expected_metadata_from_row(dataset_row))
    d["indexing_note"] = (
        "used_source_indexes are 1-based positions into retrieved_chunks, matching "
        "finalize_rag_ask (same order as chunks_to_sources / prompt [1]..[n])."
    )
    d["answer"] = safe_str(getattr(resp, "answer", "")) if resp is not None else ""
    d["retrieval_meta"] = dict(getattr(resp, "retrieval_meta", None) or {})
    q_trans_meta = {}
    if isinstance(d["retrieval_meta"].get("query_translation"), dict):
        q_trans_meta = d["retrieval_meta"]["query_translation"]
    d["translated_question_en"] = safe_str(q_trans_meta.get("retrieval_query_english")) or None
    d["translation_used"] = bool(q_trans_meta.get("retrieval_query_translated", False))
    d["confidence_score"] = getattr(resp, "confidence_score", None)
    d["confidence_label"] = getattr(resp, "confidence_label", None)
    d["low_retrieval_confidence"] = bool(getattr(resp, "low_retrieval_confidence", False))
    d["retrieved_context"] = [_chunk_to_context_dict(c, context_dump_chars) for c in retrieved_chunks]
    shown, fallback = _sources_to_dicts(resp) if resp is not None else ([], [])
    d["sources_shown_to_user"] = shown
    d["retrieved_sources_full"] = fallback
    return d


def citation_failure_tags(m: CitationRowMetrics) -> List[str]:
    tags: List[str] = []
    if m.error:
        return ["pipeline_error"]
    if m.low_retrieval_confidence:
        return ["low_retrieval_confidence_block"]
    if not m.has_model_citation and not m.has_bracket_citation:
        tags.append("missing_citation")
    if m.has_model_citation and not m.citation_structurally_valid:
        tags.append("invalid_citation")
    if (
        m.citation_structurally_valid
        and m.gold_object_id
        and m.has_model_citation
        and not m.gold_cited
    ):
        tags.append("gold_missing_from_citations")
    if (
        m.has_expected_pages
        and m.citation_structurally_valid
        and m.has_model_citation
        and not m.cited_page_correct
    ):
        tags.append("expected_page_not_in_cited_sources")
    if (m.has_bracket_citation or m.has_model_citation) and not m.json_and_bracket_consistent:
        tags.append("bracket_json_mismatch")
    return tags


def write_failure_record_if_needed(
    failures_f,
    m: CitationRowMetrics,
    resp: Optional[Any],
    retrieved_chunks: List[Any],
    context_dump_chars: int,
    dataset_row: Dict[str, Any],
) -> None:
    tags = citation_failure_tags(m)
    if not tags:
        return
    rec = build_detail_record(m, resp, retrieved_chunks, context_dump_chars, dataset_row)
    rec["failure_tags"] = tags
    failures_f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    failures_f.flush()


def aggregate(rows: List[CitationRowMetrics], run_config: Dict[str, Any]) -> Dict[str, Any]:
    n = len(rows)
    if n == 0:
        return {"error": "no rows", "run_config": run_config}

    ok = [r for r in rows if r.error is None]
    errors = [r for r in rows if r.error is not None]
    n_ok = len(ok)

    def rate(subset: List[CitationRowMetrics], pred) -> float:
        if not subset:
            return 0.0
        return sum(1 for r in subset if pred(r)) / len(subset)

    answered = [r for r in ok if not r.low_retrieval_confidence]
    cited_rows = [r for r in answered if r.has_model_citation]
    valid_cited = [r for r in cited_rows if r.citation_structurally_valid]

    citation_presence_rate = rate(answered, lambda r: r.has_model_citation or r.has_bracket_citation)
    model_citation_presence_rate = rate(answered, lambda r: r.has_model_citation)

    citation_validity_rate = rate(cited_rows, lambda r: r.citation_structurally_valid)

    total_mentions = sum(r.n_index_mentions for r in cited_rows)
    total_invalid_idx = sum(r.n_invalid_indices for r in cited_rows)
    hallucinated_index_rate_micro = (
        (total_invalid_idx / total_mentions) if total_mentions > 0 else 0.0
    )
    hallucinated_index_row_rate = rate(cited_rows, lambda r: r.n_invalid_indices > 0)

    total_id_mentions = sum(len(r.used_source_ids) for r in cited_rows)
    total_invalid_ids = sum(r.n_invalid_source_ids for r in cited_rows)
    hallucinated_source_id_rate_micro = (
        (total_invalid_ids / total_id_mentions) if total_id_mentions > 0 else 0.0
    )
    hallucinated_source_id_row_rate = rate(cited_rows, lambda r: r.n_invalid_source_ids > 0)

    gold_valid_subset = [r for r in valid_cited if r.gold_object_id]
    correct_citation_exact_match_rate = rate(gold_valid_subset, lambda r: r.gold_cited)

    correct_act_citation_rate = rate(valid_cited, lambda r: r.cited_act_correct)
    correct_section_citation_rate = rate(valid_cited, lambda r: r.cited_section_correct)
    valid_cited_with_expected_pages = [r for r in valid_cited if r.has_expected_pages]
    correct_page_citation_rate = rate(
        valid_cited_with_expected_pages,
        lambda r: r.cited_page_correct,
    )

    gold_missing_from_citation = [
        r for r in gold_valid_subset if not r.gold_cited
    ]
    gold_missing_from_citation_rate = (
        len(gold_missing_from_citation) / len(gold_valid_subset) if gold_valid_subset else 0.0
    )

    soft_citation_support_rate = rate(gold_valid_subset, lambda r: r.answer_soft_supported_by_citation)

    bracket_json_mismatch_rate = rate(
        [r for r in answered if r.has_bracket_citation or r.has_model_citation],
        lambda r: not r.json_and_bracket_consistent,
    )

    notes = {
        "evaluation_scope": (
            "These metrics measure citation and source-list alignment to dataset gold metadata "
            "(object id, act, section, where applicable pages). They do not evaluate full answer "
            "faithfulness, NLI-style grounding, or legal correctness of the prose beyond cited passages."
        ),
        "citation_presence_rate": "Share of non-blocked answers with model citation (indexes or used_source_ids) or bracket [n] in answer text.",
        "model_citation_presence_rate": "Non-empty used_source_indexes or used_source_ids in model JSON.",
        "citation_validity_rate": "Among rows with model citation: indices in [1, n_context] and every used_source_id appears on some retrieved chunk.",
        "hallucinated_index_rate_micro": "invalid index slots / count of used_source_indexes list entries (parse failures + OOB).",
        "hallucinated_source_id_rate_micro": "invalid used_source_ids / len(used_source_ids) summed over cited rows.",
        "correct_citation_exact_match_rate": "Among structurally valid cited rows with gold id: gold ∈ cited chunks via index or id.",
        "correct_act_citation_rate": "Among structurally valid cited rows with any cited chunk: act match (see code).",
        "correct_section_citation_rate": "Same for section (normalized).",
        "correct_page_citation_rate": "Among structurally valid cited rows that have non-empty expected_page_numbers in the dataset: any cited chunk shares a page with expected.",
        "gold_missing_from_citation_rate": "Among structurally valid cited rows with gold id: gold object_id not in the cited union (indexes + valid used_source_ids).",
        "soft_citation_support_rate": "Same denominator as gold_missing_from_citation_rate: gold cited OR cited act+section matches expected (soft).",
        "json_bracket_inconsistency_rate": "Bracket [n] not subset of used_source_indexes or OOB.",
    }

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "evaluation_scope": notes["evaluation_scope"],
        "run_config": run_config,
        "counts": {
            "dataset_rows": n,
            "successful_runs": n_ok,
            "ollama_or_other_errors": len(errors),
            "answered_not_low_conf_block": len(answered),
            "rows_with_model_citation": len(cited_rows),
            "rows_with_structurally_valid_citation": len(valid_cited),
            "rows_gold_evaluable": len(gold_valid_subset),
            "rows_with_expected_pages_in_valid_cited": len(valid_cited_with_expected_pages),
        },
        "rates": {
            "citation_presence_rate": citation_presence_rate,
            "model_citation_presence_rate": model_citation_presence_rate,
            "citation_validity_rate": citation_validity_rate,
            "hallucinated_index_rate_micro": hallucinated_index_rate_micro,
            "hallucinated_index_row_rate": hallucinated_index_row_rate,
            "hallucinated_source_id_rate_micro": hallucinated_source_id_rate_micro,
            "hallucinated_source_id_row_rate": hallucinated_source_id_row_rate,
            "correct_citation_exact_match_rate": correct_citation_exact_match_rate,
            "correct_act_citation_rate": correct_act_citation_rate,
            "correct_section_citation_rate": correct_section_citation_rate,
            "correct_page_citation_rate": correct_page_citation_rate,
            "gold_missing_from_citation_rate": gold_missing_from_citation_rate,
            "soft_citation_support_rate": soft_citation_support_rate,
            "json_bracket_inconsistency_rate": bracket_json_mismatch_rate,
        },
        "extra": {
            "insufficient_context_rate": rate(answered, lambda r: r.insufficient_context),
            "low_retrieval_confidence_block_rate": rate(ok, lambda r: r.low_retrieval_confidence),
            "gold_in_context_rate": rate(answered, lambda r: r.gold_in_context),
            "gold_cited_via_indexes_rate_on_gold_subset": rate(
                gold_valid_subset, lambda r: r.gold_cited_via_indexes
            ),
            "gold_cited_via_used_source_ids_rate_on_gold_subset": rate(
                gold_valid_subset, lambda r: r.gold_cited_via_used_source_ids
            ),
        },
        "metric_notes": notes,
    }


def _load_completed_ids(details_path: Path) -> Tuple[set, List[Dict[str, Any]]]:
    done: set = set()
    prior: List[Dict[str, Any]] = []
    if not details_path.is_file():
        return done, prior
    with details_path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            eid = safe_str(rec.get("eval_id"))
            if eid:
                done.add(eid)
            prior.append(rec)
    return done, prior


def main() -> int:
    args = parse_args()
    configure_logging(args.verbose)
    if args.limit is not None and args.limit < 1:
        print("[ERROR] --limit must be positive", file=sys.stderr)
        return 2
    ctx_k = effective_context_k(args.context_k)
    if not args.dataset.is_file():
        print(f"[ERROR] dataset not found: {args.dataset}", file=sys.stderr)
        return 1

    rows_all = filter_rows(load_jsonl(args.dataset), args)
    if not rows_all:
        print("[ERROR] no rows matched filters", file=sys.stderr)
        return 1

    try:
        deps = import_backend(args.verbose)
        preflight_database(deps["SessionLocal"], deps["text"])
    except Exception as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 1

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_dir = args.output_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    if args.resume and args.details_file is None:
        print("[ERROR] --resume requires --details-file", file=sys.stderr)
        return 2

    details_path: Path
    if args.details_file is not None:
        details_path = args.details_file
    else:
        details_path = out_dir / f"citation_eval_details_{stamp}.jsonl"

    if args.resume and not details_path.is_file() and args.verbose:
        print(f"[INFO] --resume: details file not found yet, will create {details_path}")

    completed_ids, prior_records = _load_completed_ids(details_path) if args.resume else (set(), [])

    rows_in = [r for r in rows_all if safe_str(r.get("id")) not in completed_ids]
    if args.resume and completed_ids:
        print(f"[resume] skipping {len(completed_ids)} eval_ids already in {details_path}")

    summary_path = args.summary_file or (out_dir / f"citation_eval_summary_{stamp}.json")
    failures_path = out_dir / f"citation_eval_failures_{stamp}.jsonl"

    def safe_ollama_model() -> str:
        try:
            from app.services.ollama_service import get_ollama_model

            return get_ollama_model()
        except Exception:
            return os.environ.get("OLLAMA_MODEL", "")

    run_config = {
        "dataset_path_resolved": str(args.dataset.resolve()),
        "dataset_path_as_given": str(args.dataset),
        "candidate_k": int(max(args.candidate_k, 1)),
        "context_k": int(max(ctx_k, 1)),
        "limit": args.limit,
        "language": args.language,
        "question_type": args.question_type,
        "resume": bool(args.resume),
        "details_file": str(details_path.resolve()) if details_path else None,
        "failures_file": str(failures_path.resolve()),
        "bge_query_model": deps["get_bge_query_model_id"](),
        "lawgic_embed_model_env": os.environ.get("LAWGIC_EMBED_MODEL"),
        "lawgic_embed_model_effective": os.environ.get("LAWGIC_EMBED_MODEL", "BAAI/bge-m3"),
        "reranker_enabled": deps["is_reranker_enabled"](),
        "reranker_model": deps["get_reranker_model_id"](),
        "max_rerank_candidates": deps["max_rerank_candidates"](),
        "ollama_model": safe_ollama_model(),
        "ollama_base_url_env": os.environ.get("OLLAMA_BASE_URL", ""),
        "rag_low_confidence_threshold_env": os.environ.get("RAG_LOW_CONFIDENCE_THRESHOLD", ""),
        "lawgic_reranker_enabled_env": os.environ.get("LAWGIC_RERANKER_ENABLED", ""),
    }

    metrics_rows: List[CitationRowMetrics] = []
    if args.resume and prior_records:
        for pr in prior_records:
            try:
                metrics_rows.append(metrics_from_detail_dict(pr))
            except Exception:
                continue

    RagAskRequest = deps["RagAskRequest"]
    SessionLocal = deps["SessionLocal"]
    retrieve = deps["retrieve_for_rag_ask"]
    finalize = deps["finalize_rag_ask"]
    OllamaServiceError = deps["OllamaServiceError"]

    details_mode = "a" if args.resume and details_path.is_file() else "w"
    details_f = details_path.open(details_mode, encoding="utf-8")
    failures_f = failures_path.open("w", encoding="utf-8")

    total_rows = len(rows_in)
    try:
        for idx, row in progress_iter(rows_in, args.verbose):
            s0, e0 = _citation_success_error_counts(metrics_rows)
            print(
                f"\nStarting query {idx}/{total_rows} | Success: {s0} | Errors: {e0}",
                flush=True,
            )
            q = safe_str(row.get("question"))
            if not q:
                m = empty_metrics(row, "", "missing_question")
                metrics_rows.append(m)
                rec = build_detail_record(m, None, [], args.context_dump_chars, row)
                details_f.write(json.dumps(rec, ensure_ascii=False) + "\n")
                details_f.flush()
                write_failure_record_if_needed(failures_f, m, None, [], args.context_dump_chars, row)
                s1, e1 = _citation_success_error_counts(metrics_rows)
                print(
                    f"Completed row {idx}/{total_rows} | Success: {s1} | Errors: {e1}",
                    flush=True,
                )
                continue

            req = RagAskRequest(
                query=q,
                top_k_retrieval=max(args.candidate_k, 1),
                top_k_context=max(ctx_k, 1),
                query_language=safe_str(row.get("language")) or None,
            )
            resp = None
            rchunks: List[Any] = []
            try:
                db = SessionLocal()
                try:
                    retrieval = retrieve(db, req)
                finally:
                    db.close()
                resp = finalize(req, retrieval)
                rchunks = list(getattr(resp, "retrieved_chunks", None) or [])
                m = analyze_one_response(row, resp, rchunks)
                metrics_rows.append(m)
                rec = build_detail_record(m, resp, rchunks, args.context_dump_chars, row)
                details_f.write(json.dumps(rec, ensure_ascii=False) + "\n")
                details_f.flush()
                write_failure_record_if_needed(failures_f, m, resp, rchunks, args.context_dump_chars, row)
            except OllamaServiceError as exc:
                m = empty_metrics(row, q, f"ollama: {exc}")
                metrics_rows.append(m)
                rec = build_detail_record(m, resp, rchunks, args.context_dump_chars, row)
                details_f.write(json.dumps(rec, ensure_ascii=False) + "\n")
                details_f.flush()
                write_failure_record_if_needed(failures_f, m, resp, rchunks, args.context_dump_chars, row)
            except Exception as exc:
                m = empty_metrics(row, q, str(exc))
                metrics_rows.append(m)
                rec = build_detail_record(m, resp, rchunks, args.context_dump_chars, row)
                details_f.write(json.dumps(rec, ensure_ascii=False) + "\n")
                details_f.flush()
                write_failure_record_if_needed(failures_f, m, resp, rchunks, args.context_dump_chars, row)

            s1, e1 = _citation_success_error_counts(metrics_rows)
            print(
                f"Completed row {idx}/{total_rows} | Success: {s1} | Errors: {e1}",
                flush=True,
            )
    finally:
        details_f.close()
        failures_f.close()

    summary = aggregate(metrics_rows, run_config)
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    err_n = int(summary.get("counts", {}).get("ollama_or_other_errors", 0))
    if args.verbose:
        print(f"Wrote {summary_path}")
        print(f"Wrote {details_path}")
        print(f"Wrote {failures_path}")
    else:
        print(
            f"Citation eval done: {total_rows} rows, {err_n} pipeline errors → "
            f"{summary_path.name}, {details_path.name}, {failures_path.name}"
        )
    n_ok = int(summary.get("counts", {}).get("successful_runs", 0))
    return 0 if n_ok > 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
