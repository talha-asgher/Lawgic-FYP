#!/usr/bin/env python3
"""Retrieval-only evaluation for Lawgic RAG.

Run:
  python evaluation/evaluate_retrieval.py --dataset evaluation/datasets/new_dataset.jsonl --top-k 10

This script calls the existing backend retrieval components through the
evaluation-only `retrieve_for_rag_evaluation` helper. It does not evaluate LLM
answers and does not modify database schema, embeddings, frontend, or chatbot
logic.

Tracks three ranked lists per question (see summary ``metric_note``):
  * before — fused hybrid retrieval order (depth ``retrieve_k`` from the backend).
  * after — reranked **pool only** (first ``pool_n`` fused hits), matching production.
  * context — top ``max_ctx`` of that pool after rerank, then the same dedupe step as
    ``finalize_rag_ask`` (length usually <= ``RAG_CONTEXT_MAX_CHUNKS``).

Default ``--candidate-k`` / implicit ``--context-k`` match ``RagAskRequest`` and
``app/routers/ai_qa.py`` (``top_k_retrieval=15``, ``top_k_context=6``). No LLM —
retrieval, rerank, and context slicing only.
"""

from __future__ import annotations

import argparse
import csv
import json
import logging
import math
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple


REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = REPO_ROOT / "Backend"
DEFAULT_DATASET = REPO_ROOT / "evaluation" / "datasets" / "new_dataset.jsonl"
DEFAULT_OUTPUT_DIR = REPO_ROOT / "evaluation" / "results"
K_VALUES = (1, 3, 5, 10)
META_MATCH_AT = (1, 5, 10)

if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

# Same as Backend/app/schemas.py RagAskRequest and app/routers/ai_qa.py rag_req.
CHATBOT_TOP_K_RETRIEVAL = 15
CHATBOT_TOP_K_CONTEXT = 6


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate Lawgic retrieval against a JSONL dataset.")
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--top-k", type=int, default=10)
    parser.add_argument(
        "--candidate-k",
        type=int,
        default=CHATBOT_TOP_K_RETRIEVAL,
        help=(
            "RagAskRequest.top_k_retrieval (first-stage depth); default matches AI QA chatbot (15). "
            "With rerank on, backend fetches max(candidate_k, pool_n)."
        ),
    )
    parser.add_argument(
        "--context-k",
        type=int,
        default=None,
        help=(
            "RagAskRequest.top_k_context; same as chatbot (default 6). "
            "Effective context is min(RAG_CONTEXT_MAX_CHUNKS, top_k_context), as in finalize_rag_ask."
        ),
    )
    parser.add_argument("--mrr-cutoff", type=int, default=10)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--language", choices=("en", "ur", "all"), default="all")
    parser.add_argument("--question-type", default=None)
    parser.add_argument("--verbose", action="store_true")
    return parser.parse_args()


def configure_logging(verbose: bool) -> None:
    if verbose:
        return
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.pool").setLevel(logging.WARNING)


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


def progress_iter(rows: List[Dict[str, Any]], verbose: bool) -> Iterable[Tuple[int, Dict[str, Any]]]:
    try:
        from tqdm import tqdm

        yield from enumerate(tqdm(rows, desc="Evaluating retrieval"), start=1)
        return
    except Exception:
        pass

    total = len(rows)
    for idx, row in enumerate(rows, start=1):
        if verbose or idx == 1 or idx == total or idx % 25 == 0:
            print(f"Evaluating {idx}/{total}")
        yield idx, row


def import_retrieval_dependencies(verbose: bool):
    try:
        from sqlalchemy import text
        from app.database import SessionLocal, engine
        from app.schemas import RagAskRequest
        from app.services.rag_service import retrieve_for_rag_evaluation
        from app.services.query_embedder import get_bge_query_model_id
        from app.services.reranker_service import (
            get_reranker_model_id,
            is_reranker_enabled,
            max_rerank_candidates,
        )
    except Exception as exc:
        raise RuntimeError(
            "Could not import Lawgic backend retrieval dependencies. "
            "Run this from the project root with backend requirements installed and DB config available."
        ) from exc
    if not verbose:
        engine.echo = False
    return {
        "SessionLocal": SessionLocal,
        "RagAskRequest": RagAskRequest,
        "retrieve_for_rag_evaluation": retrieve_for_rag_evaluation,
        "text": text,
        "get_bge_query_model_id": get_bge_query_model_id,
        "get_reranker_model_id": get_reranker_model_id,
        "is_reranker_enabled": is_reranker_enabled,
        "max_rerank_candidates": max_rerank_candidates,
    }


def preflight_database(SessionLocal: Any, text: Any) -> None:
    db = SessionLocal()
    try:
        db.execute(text("SELECT 1"))
    finally:
        db.close()


def effective_context_k(arg_value: Optional[int]) -> int:
    if arg_value is not None:
        return int(arg_value)
    return CHATBOT_TOP_K_CONTEXT


def retrieve_question(
    question: str,
    candidate_k: int,
    context_k: int,
    SessionLocal: Any,
    RagAskRequest: Any,
    retrieve_for_rag_evaluation: Any,
) -> Any:
    # Same shape as app/routers/ai_qa.py: RagAskRequest(query=..., top_k_retrieval=..., top_k_context=...)
    req = RagAskRequest(
        query=question,
        top_k_retrieval=max(candidate_k, 1),
        top_k_context=max(context_k, 1),
    )
    db = SessionLocal()
    try:
        return retrieve_for_rag_evaluation(db, req, candidate_k=max(candidate_k, 1))
    finally:
        db.close()


def result_to_dict(item: Any, rank: int) -> Dict[str, Any]:
    chunk_type = safe_str(getattr(item, "chunk_type", ""))
    object_id = safe_str(getattr(item, "object_id", ""))
    return {
        "rank": rank,
        "chunk_type": chunk_type,
        "object_id": object_id,
        "child_id": object_id if chunk_type == "child" else "",
        "parent_id": safe_str(getattr(item, "parent_id", "")),
        "act_name": safe_str(getattr(item, "act_name", "")),
        "section_number": safe_str(getattr(item, "section_number", "")),
        "section_title": safe_str(getattr(item, "section_title", "")),
        "category": safe_str(getattr(item, "category", "")),
        "page_numbers": getattr(item, "page_numbers", None) or [],
        "score": getattr(item, "score", None),
        "dense_norm": getattr(item, "dense_norm", None),
        "bm25_norm": getattr(item, "bm25_norm", None),
        "metadata_boost": getattr(item, "metadata_boost", None),
        "rerank_score": getattr(item, "rerank_score", None),
    }


def results_to_dicts(items: List[Any], limit: int) -> List[Dict[str, Any]]:
    return [result_to_dict(item, rank) for rank, item in enumerate(items[:limit], start=1)]


def expected_gold_id(row: Dict[str, Any]) -> str:
    return safe_str(row.get("expected_child_id") or row.get("expected_object_id"))


def rank_of_expected(gold_id: str, retrieved: List[Dict[str, Any]]) -> Optional[int]:
    if not gold_id:
        return None
    gold = safe_str(gold_id)
    for item in retrieved:
        if safe_str(item.get("child_id")) == gold or safe_str(item.get("object_id")) == gold:
            return int(item["rank"])
    return None


def rank_of_expected_raw(gold_id: str, raw_items: List[Any]) -> Optional[int]:
    if not gold_id:
        return None
    gold = safe_str(gold_id)
    for i, item in enumerate(raw_items, start=1):
        chunk_type = safe_str(getattr(item, "chunk_type", ""))
        oid = safe_str(getattr(item, "object_id", ""))
        child_id = oid if chunk_type == "child" else ""
        if child_id == gold or oid == gold:
            return i
    return None


def metadata_match(row: Dict[str, Any], retrieved: List[Dict[str, Any]], field: str, k: int) -> bool:
    expected_key = f"expected_{field}"
    expected = row.get(expected_key)
    if expected is None or safe_str(expected) == "":
        return False
    if field == "section_number":
        exp = norm_section(expected)
        return any(norm_section(item.get(field)) == exp for item in retrieved[:k])
    if field in ("act_name", "category"):
        exp = norm_text(expected)
        return any(norm_text(item.get(field)) == exp for item in retrieved[:k])
    if field == "parent_id":
        exp = safe_str(expected)
        return any(safe_str(item.get(field)) == exp for item in retrieved[:k])
    return False


def f1_score(precision: float, recall: float) -> float:
    if precision + recall == 0:
        return 0.0
    return 2 * precision * recall / (precision + recall)


def list_metrics(
    row: Dict[str, Any],
    retrieved: List[Dict[str, Any]],
    top_k: int,
    mrr_cutoff: int,
    prefix: str,
) -> Tuple[Dict[str, Any], Optional[int]]:
    gold = expected_gold_id(row)
    rank = rank_of_expected(gold, retrieved)
    reciprocal_rank = 1.0 / rank if rank and rank <= mrr_cutoff else 0.0
    out: Dict[str, Any] = {
        f"{prefix}_rank_of_expected": rank,
        f"{prefix}_reciprocal_rank": reciprocal_rank,
        f"{prefix}_ndcg_at_10": 1.0 / math.log2(rank + 1) if rank and rank <= 10 else 0.0,
    }
    nret = max(1, len(retrieved))
    for md in META_MATCH_AT:
        cap = min(md, top_k, nret)
        out[f"{prefix}_act_match_at_{md}"] = metadata_match(row, retrieved, "act_name", cap)
        out[f"{prefix}_section_match_at_{md}"] = metadata_match(
            row, retrieved, "section_number", cap
        )
        out[f"{prefix}_category_match_at_{md}"] = metadata_match(
            row, retrieved, "category", cap
        )
        out[f"{prefix}_parent_match_at_{md}"] = metadata_match(
            row, retrieved, "parent_id", cap
        )
    for k in K_VALUES:
        kk = min(k, top_k)
        hit = bool(rank and rank <= kk)
        precision = (1.0 / k) if hit else 0.0
        recall = 1.0 if hit else 0.0
        out[f"{prefix}_hit_at_{k}"] = hit
        out[f"{prefix}_accuracy_at_{k}"] = hit
        out[f"{prefix}_precision_at_{k}"] = precision
        out[f"{prefix}_recall_at_{k}"] = recall
        out[f"{prefix}_f1_at_{k}"] = f1_score(precision, recall)
    out[f"{prefix}_map_at_{mrr_cutoff}"] = reciprocal_rank
    return out, rank


def infer_failure_reason(row: Dict[str, Any], retrieved: List[Dict[str, Any]]) -> str:
    act = metadata_match(row, retrieved, "act_name", 10)
    section = metadata_match(row, retrieved, "section_number", 10)
    category = metadata_match(row, retrieved, "category", 10)
    parent = metadata_match(row, retrieved, "parent_id", 10)
    if parent:
        return "correct_parent_wrong_child"
    if act and section:
        return "correct_act_and_section_wrong_chunk"
    if act and not section:
        return "correct_act_wrong_section"
    if section and not act:
        return "correct_section_wrong_act"
    if category and not act:
        return "correct_category_wrong_act"
    return "wrong_act_or_no_close_metadata_match"


def rank_effect(before_rank: Optional[int], after_rank: Optional[int]) -> str:
    if before_rank is None and after_rank is None:
        return "still_missing"
    if before_rank is None and after_rank is not None:
        return "improved"
    if before_rank is not None and after_rank is None:
        return "worsened"
    if after_rank < before_rank:
        return "improved"
    if after_rank > before_rank:
        return "worsened"
    return "unchanged"


def order_ids(items: List[Dict[str, Any]], k: int) -> List[str]:
    return [safe_str(item.get("object_id")) for item in items[:k]]


def evaluate_row(
    row: Dict[str, Any],
    before: List[Dict[str, Any]],
    after: List[Dict[str, Any]],
    context: List[Dict[str, Any]],
    top_k: int,
    mrr_cutoff: int,
    gold_rank_at_retrieve_k: Optional[int],
    gold_rank_in_rerank_pool: Optional[int],
    gold_in_rerank_pool: bool,
    confidence_score: Optional[float],
    confidence_label: Optional[str],
) -> Dict[str, Any]:
    gold = expected_gold_id(row)
    before_metrics, before_rank = list_metrics(row, before, top_k, mrr_cutoff, "before")
    after_metrics, after_rank = list_metrics(row, after, top_k, mrr_cutoff, "after")
    context_metrics, context_rank = list_metrics(row, context, top_k, mrr_cutoff, "context")

    detail: Dict[str, Any] = {
        "eval_id": safe_str(row.get("id")),
        "question": safe_str(row.get("question")),
        "language": safe_str(row.get("language")),
        "question_type": safe_str(row.get("question_type")),
        "expected_child_id": gold,
        "expected_object_id": safe_str(row.get("expected_object_id")),
        "expected_gold_id": gold,
        "expected_act_name": safe_str(row.get("expected_act_name")),
        "expected_section_number": safe_str(row.get("expected_section_number")),
        "expected_category": safe_str(row.get("expected_category")),
        "expected_parent_id": safe_str(row.get("expected_parent_id")),
        "gold_rank_at_retrieve_k": gold_rank_at_retrieve_k,
        "gold_rank_in_rerank_pool": gold_rank_in_rerank_pool,
        "gold_in_rerank_pool": gold_in_rerank_pool,
        "retrieval_confidence_score": confidence_score,
        "retrieval_confidence_label": confidence_label,
        "before_retrieved_top_k": before[:top_k],
        "after_retrieved_top_k": after[:top_k],
        "context_retrieved_top_k": context[:top_k],
    }
    detail.update(before_metrics)
    detail.update(after_metrics)
    detail.update(context_metrics)
    detail.update(
        {
            "rerank_changed_order": order_ids(before, top_k) != order_ids(after, top_k),
            "expected_moved_from_rank": before_rank,
            "expected_moved_to_rank": after_rank,
            "expected_rank_delta": (
                None if before_rank is None or after_rank is None else before_rank - after_rank
            ),
            "rerank_effect": rank_effect(before_rank, after_rank),
            "context_rank_delta_vs_after": (
                None if context_rank is None or after_rank is None else after_rank - context_rank
            ),
        }
    )
    return detail


def selected_env_metadata() -> Dict[str, str]:
    keys = (
        "LAWGIC_EMBED_MODEL",
        "BGE_QUERY_MODEL",
        "OLLAMA_MODEL",
        "LAWGIC_MAX_RERANK_CANDIDATES",
        "LAWGIC_RERANKER_ENABLED",
        "LAWGIC_RERANKER_MODEL",
        "RAG_CONTEXT_MAX_CHUNKS",
    )
    return {key: os.environ[key] for key in keys if os.environ.get(key)}


def bool_mean(details: List[Dict[str, Any]], key: str) -> float:
    return sum(1.0 for d in details if d.get(key)) / len(details)


def prefixed_metrics(details: List[Dict[str, Any]], prefix: str, mrr_cutoff: int) -> Dict[str, float]:
    out: Dict[str, float] = {}
    for k in K_VALUES:
        out[f"{prefix}_Hit@{k}"] = bool_mean(details, f"{prefix}_hit_at_{k}")
        out[f"{prefix}_Accuracy@{k}"] = out[f"{prefix}_Hit@{k}"]
        out[f"{prefix}_Precision@{k}"] = (
            sum(float(d.get(f"{prefix}_precision_at_{k}") or 0.0) for d in details) / len(details)
        )
        out[f"{prefix}_Recall@{k}"] = (
            sum(float(d.get(f"{prefix}_recall_at_{k}") or 0.0) for d in details) / len(details)
        )
        out[f"{prefix}_F1@{k}"] = (
            sum(float(d.get(f"{prefix}_f1_at_{k}") or 0.0) for d in details) / len(details)
        )
    out[f"{prefix}_MRR@{mrr_cutoff}"] = (
        sum(float(d.get(f"{prefix}_reciprocal_rank") or 0.0) for d in details) / len(details)
    )
    out[f"{prefix}_nDCG@10"] = (
        sum(float(d.get(f"{prefix}_ndcg_at_10") or 0.0) for d in details) / len(details)
    )
    out[f"{prefix}_MAP@{mrr_cutoff}"] = (
        sum(float(d.get(f"{prefix}_map_at_{mrr_cutoff}") or 0.0) for d in details) / len(details)
    )
    for md in META_MATCH_AT:
        out[f"{prefix}_Act Match@{md}"] = bool_mean(details, f"{prefix}_act_match_at_{md}")
        out[f"{prefix}_Section Match@{md}"] = bool_mean(
            details, f"{prefix}_section_match_at_{md}"
        )
        out[f"{prefix}_Category Match@{md}"] = bool_mean(
            details, f"{prefix}_category_match_at_{md}"
        )
        out[f"{prefix}_Parent Match@{md}"] = bool_mean(
            details, f"{prefix}_parent_match_at_{md}"
        )
    return out


def aggregate_metrics(
    details: List[Dict[str, Any]],
    args: argparse.Namespace,
    attempted_count: int,
    retrieval_error_count: int,
    retrieval_meta: Dict[str, Any],
) -> Dict[str, Any]:
    n = len(details)
    if n == 0:
        raise ValueError("No rows were evaluated")

    rerank_on = bool(retrieval_meta.get("reranker_enabled"))
    metric_note = (
        "Means are over successfully evaluated rows only. "
        "'before' = fused hybrid order (retrieve_k deep). "
        "'after' = cross-encoder rerank of the first pool_n fused hits only (production-aligned); "
        "gold beyond pool_n cannot appear in 'after'. "
        "'context' = top max_ctx of that reranked head, then dedupe_chunks_by_act_section (prompt path); "
        "Hit@k here measures inclusion in that short deduped list, not the full 10-passage window. "
        f"Hit@{{1,3,5,10}} and MRR use reporting cutoff top_k={args.top_k}. "
        "Metadata match @1/@5/@10 scans only up to min(k, top_k, list length). "
        f"context_k (summary field) is RagAskRequest.top_k_context (chat default {CHATBOT_TOP_K_CONTEXT}); "
        f"max_ctx=min(RAG_CONTEXT_MAX_CHUNKS, context_k)."
    )

    summary: Dict[str, Any] = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "dataset": str(args.dataset),
        "dataset_path": str(args.dataset),
        "output_dir": str(args.output_dir),
        "evaluated_count": n,
        "attempted_count": attempted_count,
        "retrieval_error_count": retrieval_error_count,
        "top_k": args.top_k,
        "candidate_k": args.candidate_k,
        "context_k": retrieval_meta.get("context_k"),
        "pool_n": retrieval_meta.get("pool_n"),
        "retrieve_k": retrieval_meta.get("retrieve_k"),
        "max_ctx_used": retrieval_meta.get("max_ctx_used"),
        "mrr_cutoff": args.mrr_cutoff,
        "language_filter": args.language,
        "question_type_filter": args.question_type or "all",
        "reranker_enabled": retrieval_meta.get("reranker_enabled"),
        "rerank_skipped_identical_after_track": not rerank_on,
        "reranker_model": retrieval_meta.get("reranker_model"),
        "rerank_pool_size": retrieval_meta.get("rerank_pool_size"),
        "configured_max_rerank_candidates": retrieval_meta.get("configured_max_rerank_candidates"),
        "embedding_model": retrieval_meta.get("embedding_model"),
        "bge_query_model": retrieval_meta.get("bge_query_model"),
        "retrieval_mode": "hybrid_dense_bm25_metadata_boost",
        "metric_note": metric_note,
        "environment": selected_env_metadata(),
    }
    summary.update(prefixed_metrics(details, "before", args.mrr_cutoff))
    summary.update(prefixed_metrics(details, "after", args.mrr_cutoff))
    summary.update(prefixed_metrics(details, "context", args.mrr_cutoff))
    for metric in ("Hit@1", "Hit@5", "Hit@10", f"MRR@{args.mrr_cutoff}", "nDCG@10"):
        summary[f"delta_{metric}"] = summary[f"after_{metric}"] - summary[f"before_{metric}"]
    for md in META_MATCH_AT:
        for label_base in ("Act Match", "Section Match", "Category Match", "Parent Match"):
            label = f"{label_base}@{md}"
            summary[f"delta_{label}"] = summary[f"after_{label}"] - summary[f"before_{label}"]
    summary["delta_context_hit10_vs_after"] = (
        summary["context_Hit@10"] - summary["after_Hit@10"]
    )
    summary["before_failures_at_10"] = sum(1 for d in details if not d.get("before_hit_at_10"))
    summary["after_failures_at_10"] = sum(1 for d in details if not d.get("after_hit_at_10"))
    summary["context_failures_at_10"] = sum(1 for d in details if not d.get("context_hit_at_10"))
    summary["rerank_changed_order_count"] = sum(1 for d in details if d.get("rerank_changed_order"))
    summary["rerank_improved_count"] = sum(1 for d in details if d.get("rerank_effect") == "improved")
    summary["rerank_worsened_count"] = sum(1 for d in details if d.get("rerank_effect") == "worsened")
    summary["rerank_unchanged_count"] = sum(1 for d in details if d.get("rerank_effect") == "unchanged")
    summary["rerank_still_missing_count"] = sum(
        1 for d in details if d.get("rerank_effect") == "still_missing"
    )
    summary["mean_gold_in_rerank_pool"] = bool_mean(details, "gold_in_rerank_pool")
    pool_sizes = [int(d.get("rerank_pool_actual_len") or 0) for d in details]
    ctx_sizes = [int(d.get("context_deduped_len") or 0) for d in details]
    if pool_sizes:
        summary["mean_rerank_pool_size"] = sum(pool_sizes) / n
        summary["min_rerank_pool_size"] = min(pool_sizes)
        summary["max_rerank_pool_size"] = max(pool_sizes)
    if ctx_sizes:
        summary["mean_context_size"] = sum(ctx_sizes) / n
        summary["min_context_size"] = min(ctx_sizes)
        summary["max_context_size"] = max(ctx_sizes)
    return summary


def write_json(path: Path, data: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: Iterable[Dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def write_summary_csv(path: Path, summary: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["metric", "value"])
        for key, value in summary.items():
            writer.writerow([key, value])


def failure_row(detail: Dict[str, Any], prefix: str) -> Dict[str, Any]:
    top10 = detail.get(f"{prefix}_retrieved_top_k", [])[:10]
    expected = {
        "expected_child_id": detail.get("expected_child_id"),
        "expected_object_id": detail.get("expected_object_id"),
        "expected_gold_id": detail.get("expected_gold_id"),
        "expected_act_name": detail.get("expected_act_name"),
        "expected_section_number": detail.get("expected_section_number"),
        "expected_category": detail.get("expected_category"),
        "expected_parent_id": detail.get("expected_parent_id"),
    }
    synthetic_row = {
        "expected_act_name": detail.get("expected_act_name"),
        "expected_section_number": detail.get("expected_section_number"),
        "expected_category": detail.get("expected_category"),
        "expected_parent_id": detail.get("expected_parent_id"),
    }
    return {
        "eval_id": detail.get("eval_id"),
        "question": detail.get("question"),
        "language": detail.get("language"),
        "expected_metadata": expected,
        "top_10_retrieved_chunks": top10,
        "act_matched": metadata_match(synthetic_row, top10, "act_name", 10),
        "section_matched": metadata_match(synthetic_row, top10, "section_number", 10),
        "category_matched": metadata_match(synthetic_row, top10, "category", 10),
        "parent_matched": metadata_match(synthetic_row, top10, "parent_id", 10),
        "reason": infer_failure_reason(synthetic_row, top10),
    }


def rerank_change_row(detail: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "eval_id": detail.get("eval_id"),
        "question": detail.get("question"),
        "language": detail.get("language"),
        "question_type": detail.get("question_type"),
        "expected_metadata": {
            "expected_gold_id": detail.get("expected_gold_id"),
            "expected_object_id": detail.get("expected_object_id"),
            "expected_act_name": detail.get("expected_act_name"),
            "expected_section_number": detail.get("expected_section_number"),
            "expected_category": detail.get("expected_category"),
            "expected_parent_id": detail.get("expected_parent_id"),
        },
        "before_rank": detail.get("before_rank_of_expected"),
        "after_rank": detail.get("after_rank_of_expected"),
        "context_rank": detail.get("context_rank_of_expected"),
        "rank_delta": detail.get("expected_rank_delta"),
        "before_top_5": detail.get("before_retrieved_top_k", [])[:5],
        "after_top_5": detail.get("after_retrieved_top_k", [])[:5],
        "context_chunks": detail.get("context_retrieved_top_k", []),
        "gold_in_rerank_pool": detail.get("gold_in_rerank_pool"),
        "rerank_effect": detail.get("rerank_effect"),
    }


def main() -> int:
    args = parse_args()
    configure_logging(args.verbose)
    if args.top_k < 1:
        print("[ERROR] --top-k must be greater than zero", file=sys.stderr)
        return 2
    if args.top_k < 10:
        print("[ERROR] --top-k must be at least 10 for the required @10 metrics", file=sys.stderr)
        return 2
    if args.candidate_k < args.top_k:
        print("[ERROR] --candidate-k must be greater than or equal to --top-k", file=sys.stderr)
        return 2
    if args.mrr_cutoff < 1:
        print("[ERROR] --mrr-cutoff must be greater than zero", file=sys.stderr)
        return 2
    if args.limit is not None and args.limit < 1:
        print("[ERROR] --limit must be greater than zero when provided", file=sys.stderr)
        return 2
    if args.context_k is not None and args.context_k < 1:
        print("[ERROR] --context-k must be at least one when provided", file=sys.stderr)
        return 2
    context_k = effective_context_k(args.context_k)
    if not args.dataset.is_file():
        print(f"[ERROR] dataset not found: {args.dataset}", file=sys.stderr)
        return 1

    rows = filter_rows(load_jsonl(args.dataset), args)
    if not rows:
        print("[ERROR] no dataset rows matched the provided filters", file=sys.stderr)
        return 1

    try:
        deps = import_retrieval_dependencies(args.verbose)
        preflight_database(deps["SessionLocal"], deps["text"])
    except Exception as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 1

    details: List[Dict[str, Any]] = []
    errors: List[Dict[str, Any]] = []
    retrieval_meta: Dict[str, Any] = {
        "reranker_enabled": deps["is_reranker_enabled"](),
        "reranker_model": deps["get_reranker_model_id"](),
        "configured_max_rerank_candidates": deps["max_rerank_candidates"](),
        "embedding_model": os.environ.get("LAWGIC_EMBED_MODEL", "BAAI/bge-m3"),
        "bge_query_model": deps["get_bge_query_model_id"](),
        "rerank_pool_size": 0,
        "pool_n": deps["max_rerank_candidates"](),
        "retrieve_k": 0,
        "max_ctx_used": 0,
        "context_k": context_k,
    }
    pool_n_cfg = deps["max_rerank_candidates"]()
    if deps["is_reranker_enabled"]() and args.candidate_k < pool_n_cfg:
        print(
            f"[WARN] candidate_k ({args.candidate_k}) < pool_n ({pool_n_cfg}): "
            "retrieve_k will be pool_n; see summary retrieve_k.",
            file=sys.stderr,
        )
        total_rows = len(rows)

    for idx, row in progress_iter(rows, args.verbose):
        print(
            f"\nStarting query {idx}/{total_rows} | Success: {len(details)} | Errors: {len(errors)}",
            flush=True,
        )

        question = safe_str(row.get("question"))
        if not question:
            errors.append({"eval_id": row.get("id"), "error": "missing_question"})
            print(
                f"Completed row {idx}/{total_rows} | Success: {len(details)} | Errors: {len(errors)}",
                flush=True,
            )
            continue
        try:
            eval_retrieval = retrieve_question(
                question,
                args.candidate_k,
                context_k,
                deps["SessionLocal"],
                deps["RagAskRequest"],
                deps["retrieve_for_rag_evaluation"],
            )
            retrieval_meta["reranker_enabled"] = eval_retrieval.reranker_enabled
            retrieval_meta["rerank_pool_size"] = eval_retrieval.rerank_pool_size
            retrieval_meta["candidate_k"] = eval_retrieval.candidate_k
            retrieval_meta["pool_n"] = eval_retrieval.pool_n
            retrieval_meta["retrieve_k"] = eval_retrieval.retrieve_k
            retrieval_meta["max_ctx_used"] = eval_retrieval.max_ctx_used

            fused_for_diag = list(eval_retrieval.retrieval.results[: eval_retrieval.retrieve_k])
            pool_slice = list(eval_retrieval.retrieval.results[: eval_retrieval.pool_n])
            gold = expected_gold_id(row)
            gold_rank_at_retrieve_k = rank_of_expected_raw(gold, fused_for_diag)
            gold_rank_in_rerank_pool = rank_of_expected_raw(gold, pool_slice)
            gold_in_rerank_pool = gold_rank_in_rerank_pool is not None

            n_before = len(eval_retrieval.pre_rerank_results)
            n_after = len(eval_retrieval.post_rerank_results)
            n_ctx = len(eval_retrieval.post_context_deduped)
            before = results_to_dicts(eval_retrieval.pre_rerank_results, n_before)
            after = results_to_dicts(eval_retrieval.post_rerank_results, n_after)
            context = results_to_dicts(eval_retrieval.post_context_deduped, n_ctx)

            rec = evaluate_row(
                row,
                before,
                after,
                context,
                args.top_k,
                args.mrr_cutoff,
                gold_rank_at_retrieve_k,
                gold_rank_in_rerank_pool,
                gold_in_rerank_pool,
                getattr(eval_retrieval.retrieval, "confidence_score", None),
                getattr(eval_retrieval.retrieval, "confidence_label", None),
            )
            rec["rerank_pool_actual_len"] = (
                min(eval_retrieval.pool_n, len(eval_retrieval.retrieval.results))
                if eval_retrieval.reranker_enabled
                else 0
            )
            rec["post_rerank_results_len"] = n_after
            rec["context_deduped_len"] = n_ctx
            details.append(rec)
            print(
                f"Completed row {idx}/{total_rows} | Success: {len(details)} | Errors: {len(errors)}",
                flush=True,
            )
        except Exception as exc:
            errors.append(
                {
                    "eval_id": row.get("id"),
                    "question": question,
                    "error": str(exc),
                }
            )
            print(
                f"Completed row {idx}/{total_rows} | Success: {len(details)} | Errors: {len(errors)}",
                flush=True,
            )
            if args.verbose:
                print(f"[WARN] retrieval failed for {row.get('id')}: {exc}", file=sys.stderr)

    if not details:
        print("[ERROR] retrieval failed for every evaluated row", file=sys.stderr)
        if errors:
            print(f"[ERROR] first error: {errors[0].get('error')}", file=sys.stderr)
        return 1

    summary = aggregate_metrics(
        details,
        args,
        attempted_count=len(rows),
        retrieval_error_count=len(errors),
        retrieval_meta=retrieval_meta,
    )
    if errors:
        summary["retrieval_errors_sample"] = errors[:5]

    before_failures = [failure_row(d, "before") for d in details if not d.get("before_hit_at_10")]
    after_failures = [failure_row(d, "after") for d in details if not d.get("after_hit_at_10")]
    context_failures = [
        failure_row(d, "context") for d in details if not d.get("context_hit_at_10")
    ]
    rerank_changes = [
        rerank_change_row(d)
        for d in details
        if d.get("rerank_changed_order")
        or d.get("expected_moved_from_rank") != d.get("expected_moved_to_rank")
    ]

    args.output_dir.mkdir(parents=True, exist_ok=True)
    summary_json = args.output_dir / "retrieval_eval_summary.json"
    details_jsonl = args.output_dir / "retrieval_eval_details.jsonl"
    before_failures_jsonl = args.output_dir / "retrieval_eval_failures_before_rerank.jsonl"
    after_failures_jsonl = args.output_dir / "retrieval_eval_failures_after_rerank.jsonl"
    context_failures_jsonl = args.output_dir / "retrieval_eval_failures_context_deduped.jsonl"
    rerank_changes_jsonl = args.output_dir / "retrieval_eval_rerank_changes.jsonl"
    errors_jsonl = args.output_dir / "retrieval_eval_errors.jsonl"
    summary_csv = args.output_dir / "retrieval_eval_summary.csv"

    write_json(summary_json, summary)
    write_jsonl(details_jsonl, details)
    write_jsonl(before_failures_jsonl, before_failures)
    write_jsonl(after_failures_jsonl, after_failures)
    write_jsonl(context_failures_jsonl, context_failures)
    write_jsonl(rerank_changes_jsonl, rerank_changes)
    write_jsonl(errors_jsonl, errors)
    write_summary_csv(summary_csv, summary)

    print("Retrieval evaluation complete")
    print(f"  evaluated: {summary['evaluated_count']}")
    print(f"  before_Hit@10: {summary['before_Hit@10']:.4f}")
    print(f"  after_Hit@10: {summary['after_Hit@10']:.4f}")
    print(f"  delta_Hit@10: {summary['delta_Hit@10']:.4f}")
    print(f"  before_MRR@{args.mrr_cutoff}: {summary[f'before_MRR@{args.mrr_cutoff}']:.4f}")
    print(f"  after_MRR@{args.mrr_cutoff}: {summary[f'after_MRR@{args.mrr_cutoff}']:.4f}")
    print(f"  delta_MRR@{args.mrr_cutoff}: {summary[f'delta_MRR@{args.mrr_cutoff}']:.4f}")
    print(f"  before failures@10: {summary['before_failures_at_10']}")
    print(f"  context_Hit@10 (deduped prompt path): {summary['context_Hit@10']:.4f}")
    print(f"  context failures@10: {summary['context_failures_at_10']}")
    print(f"  mean gold in rerank pool: {summary['mean_gold_in_rerank_pool']:.4f}")
    print(f"  details: {details_jsonl}")
    print(f"  before failures: {before_failures_jsonl}")
    print(f"  context failures: {context_failures_jsonl}")
    print(f"  errors: {errors_jsonl}")
    print(f"  summary csv: {summary_csv}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
