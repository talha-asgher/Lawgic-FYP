from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import os
import re
from typing import Any, Dict, List, Optional, Set, Tuple

from sqlalchemy.orm import Session

from app.schemas import (
    RagAskRequest,
    RagAskResponse,
    RagSourceOut,
    RetrievedChunkOut,
)
from app.services.ollama_service import (
    chat_completion,
    get_ollama_temperature,
    get_ollama_top_p,
)
from app.services.query_embedder import embed_query_text
from app.services.reranker_service import is_reranker_enabled, max_rerank_candidates, rerank_candidates
from app.services.retrieval_service import RetrievalResponse, RetrievalResultItem, RetrievalService
from app.services.language_output import (
    OUTPUT_LANG_EN,
    OUTPUT_LANG_UR,
    build_grounding_system_english_pipeline,
    low_confidence_user_message,
    low_label_disclaimer_note,
)
from app.services.translation_service import (
    looks_like_urdu_script_query,
    translate_rag_query_to_english,
    translate_text,
)


def _low_confidence_threshold() -> float:
    raw = os.environ.get("RAG_LOW_CONFIDENCE_THRESHOLD", "0.42").strip()
    try:
        return float(raw)
    except ValueError:
        return 0.42


def _context_min_top_score_allow_llm() -> float:
    """If best in-context chunk score meets this floor, still call the LLM when confidence_score is below RAG_LOW_CONFIDENCE_THRESHOLD (retrieval had signal but heuristic confidence stayed low)."""
    raw = os.environ.get("RAG_CONTEXT_MIN_TOP_SCORE_ALLOW_LLM", "0.25").strip()
    try:
        return max(0.0, min(1.0, float(raw)))
    except ValueError:
        return 0.25


def _best_context_fused_score(items: List[RetrievalResultItem]) -> float:
    """Max hybrid fused score on context chunks (same scale as retrieval `final_score`; not reranker logits)."""
    if not items:
        return 0.0
    return max(float(c.score or 0.0) for c in items)


def _append_low_label_disclaimer(
    answer: str, retrieval: RetrievalResponse, output_lang: str
) -> str:
    """When label is still 'low' but score cleared the block threshold, warn in the reply text."""
    if (retrieval.confidence_label or "").strip().lower() != "low":
        return answer
    note = low_label_disclaimer_note(output_lang)
    if not note:
        return answer
    return f"{answer.rstrip()}\n\n---\n{note}"


@dataclass
class RagEvaluationRetrieval:
    pre_rerank_results: List[RetrievalResultItem]
    post_rerank_results: List[RetrievalResultItem]
    post_context_deduped: List[RetrievalResultItem]
    retrieval: RetrievalResponse
    reranker_enabled: bool
    rerank_pool_size: int
    candidate_k: int
    pool_n: int
    retrieve_k: int
    max_ctx_used: int


def _retrieval_sort_score(c: RetrievalResultItem) -> float:
    if c.rerank_score is not None:
        return float(c.rerank_score)
    return float(c.score or 0.0)


def _safe_str(x: Any) -> str:
    if x is None:
        return ""
    return str(x).strip()


def _pages_str(pages: Optional[List[Any]]) -> str:
    if not pages:
        return ""
    try:
        return ", ".join(str(p) for p in pages[:20])
    except Exception:
        return ""


def _dedupe_key(c: RetrievalResultItem) -> Tuple[str, ...]:
    """Non-child: one row per (type, act, section, object_id)."""
    ct = (_safe_str(c.chunk_type) or "child").lower()
    oid = _safe_str(c.object_id)
    act = _safe_str(c.act_name).lower()
    sec = _safe_str(c.section_number).strip().lower()
    return (ct, act, sec, oid)


def _norm_body_for_dedupe(text: str) -> str:
    return " ".join(text.lower().split())


_CROSS_REF_NEED_PARENT_RE = re.compile(
    r"(?i)\b(?:grounds?\s+aforesaid|as\s+(?:mentioned|stated)\s+above|subject\s+to\s+the\s+following|"
    r"aforementioned|hereinafter|referred\s+to\s+(?:above|in)|in\s+the\s+manner\s+hereinafter|"
    r"notwithstanding\s+anything|provided\s+further\s+that)\b"
)
_PROC_TITLE_NEED_PARENT_RE = re.compile(
    r"(?i)\b(?:procedure|petition|application\s+to\s+the\s+court|power\s+of\s+the\s+court|"
    r"relief\s+in\s+case)\b",
)


def dedupe_chunks_by_act_section(chunks: List[RetrievalResultItem]) -> List[RetrievalResultItem]:
    """
    Child chunks: never collapse by (act, section) alone — each object_id is kept.
    Drop only (a) repeated object_id in the list, or (b) same act+section+identical body (retrieval glitch).
    """
    ranked = sorted(chunks, key=lambda x: -_retrieval_sort_score(x))
    seen_child_oid: Set[str] = set()
    seen_child_body_sig: Set[Tuple[str, str, str]] = set()
    seen_other: Set[Tuple[str, ...]] = set()
    out: List[RetrievalResultItem] = []
    for c in ranked:
        ct = (_safe_str(c.chunk_type) or "child").lower()
        if ct == "child":
            oid = _safe_str(c.object_id)
            if oid in seen_child_oid:
                continue
            act = _safe_str(c.act_name).lower()
            sec = _safe_str(c.section_number).strip().lower()
            body = _chunk_body_for_context(c)
            fp = hashlib.sha256(
                _norm_body_for_dedupe(body).encode("utf-8", errors="ignore")
            ).hexdigest()
            sig = (act, sec, fp)
            if sig in seen_child_body_sig:
                continue
            seen_child_oid.add(oid)
            seen_child_body_sig.add(sig)
            out.append(c)
        else:
            dk = _dedupe_key(c)
            if dk in seen_other:
                continue
            seen_other.add(dk)
            out.append(c)
    return out


def _child_needs_parent_excerpt(c: RetrievalResultItem) -> bool:
    if (_safe_str(c.chunk_type) or "child").lower() != "child":
        return False
    if not _safe_str(c.parent_text):
        return False
    body = _chunk_body_for_context(c)
    if not body:
        return True
    short = int(os.environ.get("RAG_PARENT_EXPAND_SHORT_CHARS", "380"))
    proc_cap = int(os.environ.get("RAG_PARENT_EXPAND_PROCEDURAL_MAX_CHARS", "650"))
    if len(body) < short:
        return True
    if _CROSS_REF_NEED_PARENT_RE.search(body):
        return True
    if _PROC_TITLE_NEED_PARENT_RE.search(_safe_str(c.section_title)) and len(body) < proc_cap:
        return True
    return False


def _parent_excerpt_addon(c: RetrievalResultItem, max_chars: int) -> str:
    pt = _safe_str(c.parent_text)
    if not pt or max_chars < 200:
        return ""
    return (
        "\n\n[Parent section excerpt — same statutory unit; use only to resolve references in the child passage above]\n"
        + _truncate(pt, max_chars)
    )


def _chunk_body_for_context(c: RetrievalResultItem) -> str:
    ct = (_safe_str(c.chunk_type) or "child").lower()
    if ct in ("table", "form"):
        if c.summary and _safe_str(c.summary):
            return _safe_str(c.summary)
        return _safe_str(c.text)
    if _safe_str(c.text):
        return _safe_str(c.text)
    return _safe_str(c.summary)


def _chunk_full_display_text(c: RetrievalResultItem) -> str:
    return _chunk_body_for_context(c)


def _truncate(s: str, max_len: int) -> str:
    if max_len <= 0 or len(s) <= max_len:
        return s
    return s[: max_len - 3] + "..."


def _neighbor_context_addon(c: RetrievalResultItem, max_chars: int) -> str:
    """Adjacent child snippets from retrieval (same parent section); not separate [n] passages."""
    if max_chars <= 0:
        return ""
    nbrs = c.neighboring_children
    if not nbrs:
        return ""
    parts: List[str] = []
    used = 0
    for nb in nbrs:
        txt = _safe_str(nb.get("text"))
        if not txt:
            continue
        sn = _safe_str(nb.get("section_number"))
        st = _safe_str(nb.get("section_title"))
        if sn or st:
            label = f"(Adjacent — Sec. {sn}" + (f" — {st}" if st else "") + ")"
        else:
            label = "(Adjacent excerpt)"
        chunk = label + "\n" + txt
        if used + len(chunk) > max_chars:
            chunk = _truncate(chunk, max_chars - used)
        if not chunk.strip():
            break
        parts.append(chunk)
        used += len(chunk) + 2
        if used >= max_chars:
            break
    if not parts:
        return ""
    return "\n\n[Adjacent excerpts from the same statutory block — use with the main passage above]\n" + "\n\n".join(
        parts
    )


def build_grounded_context(
    chunks: List[RetrievalResultItem],
    max_chars_per_chunk: int,
) -> str:
    include_nbr = os.environ.get("RAG_INCLUDE_NEIGHBOR_CONTEXT", "true").lower() in (
        "1",
        "true",
        "yes",
    )
    parent_on = os.environ.get("RAG_PARENT_EXPAND_ENABLED", "true").lower() in ("1", "true", "yes")
    nbr_budget = max(
        0,
        min(
            int(os.environ.get("RAG_NEIGHBOR_MAX_CHARS", "900")),
            max_chars_per_chunk // 3,
        ),
    )
    parent_cap_env = int(os.environ.get("RAG_PARENT_EXPAND_MAX_CHARS", "1000"))
    parent_cap = max(0, min(parent_cap_env, max_chars_per_chunk // 4))
    deduped = dedupe_chunks_by_act_section(chunks)
    blocks: List[str] = []
    for i, c in enumerate(deduped, start=1):
        pages = _pages_str(c.page_numbers)
        header = (
            f"[{i}] chunk_type={c.chunk_type} object_id={c.object_id} "
            f"act_name={c.act_name or ''} section_number={c.section_number or ''} "
            f"section_title={c.section_title or ''} page_numbers={pages}"
        )
        reserve_nbr = nbr_budget if (include_nbr and (_safe_str(c.chunk_type).lower() == "child")) else 0
        main_cap = max_chars_per_chunk - reserve_nbr
        body = _truncate(_chunk_body_for_context(c), max(200, main_cap))
        if include_nbr and (_safe_str(c.chunk_type).lower() == "child") and nbr_budget > 0:
            addon = _neighbor_context_addon(c, nbr_budget)
            if addon:
                body = body + addon
        if parent_on and _child_needs_parent_excerpt(c):
            room = max(0, max_chars_per_chunk - len(body))
            pcap = min(parent_cap, room)
            body = body + _parent_excerpt_addon(c, pcap)
        if len(body) > max_chars_per_chunk:
            body = _truncate(body, max_chars_per_chunk)
        blocks.append(header + "\n" + body)
    return "\n\n---\n\n".join(blocks) if blocks else "(no retrieved passages)"


def chunks_to_sources(
    chunks: List[RetrievalResultItem],
    full_max: int = 12000,
) -> List[RagSourceOut]:
    deduped = dedupe_chunks_by_act_section(chunks)
    out: List[RagSourceOut] = []
    for i, c in enumerate(deduped, start=1):
        ref_parts: List[str] = []
        if c.section_number:
            ref_parts.append(f"Section {c.section_number}")
        if c.section_title:
            ref_parts.append(str(c.section_title))
        source_reference = " — ".join(ref_parts) if ref_parts else None
        full_txt = _chunk_full_display_text(c)
        out.append(
            RagSourceOut(
                source_index=i,
                act_name=c.act_name,
                section_number=c.section_number,
                section_title=c.section_title,
                page_numbers=c.page_numbers,
                chunk_type=c.chunk_type,
                object_id=c.object_id,
                source_reference=source_reference,
                excerpt_text=None,
                full_source_text=_truncate(full_txt, full_max) if full_txt else None,
            )
        )
    return out


def chunks_to_retrieved_out(
    chunks: List[RetrievalResultItem],
    max_text_len: int,
) -> List[RetrievedChunkOut]:
    out: List[RetrievedChunkOut] = []
    for c in chunks:
        out.append(
            RetrievedChunkOut(
                chunk_type=c.chunk_type,
                object_id=c.object_id,
                parent_id=c.parent_id,
                act_name=c.act_name,
                category=c.category,
                section_number=c.section_number,
                section_title=c.section_title,
                page_numbers=c.page_numbers,
                score=c.score,
                rerank_score=c.rerank_score,
                summary=c.summary,
                text=_truncate(c.text or "", max_text_len),
            )
        )
    return out


_FENCE_RE = re.compile(r"^```(?:json)?\s*", re.IGNORECASE)
_FENCE_END_RE = re.compile(r"\s*```\s*$", re.IGNORECASE)


def parse_legal_model_json(raw: str) -> Tuple[str, bool, List[int], List[str]]:
    t = (raw or "").strip()
    if not t:
        return "", True, [], []
    t = _FENCE_RE.sub("", t)
    t = _FENCE_END_RE.sub("", t).strip()
    try:
        data = json.loads(t)
        if not isinstance(data, dict):
            return raw.strip(), False, [], []
        ans = data.get("answer")
        answer = _safe_str(ans) if ans is not None else ""
        ins = data.get("insufficient_context")
        insufficient = bool(ins) if isinstance(ins, bool) else str(ins).lower() in ("true", "1", "yes")
        idx_raw = data.get("used_source_indexes") or data.get("used_sources") or []
        ids_raw = data.get("used_source_ids") or []
        indexes: List[int] = []
        if isinstance(idx_raw, list):
            for x in idx_raw:
                try:
                    indexes.append(int(x))
                except (TypeError, ValueError):
                    pass
        ids: List[str] = []
        if isinstance(ids_raw, list):
            ids = [_safe_str(x) for x in ids_raw if _safe_str(x)]
        return answer, insufficient, indexes, ids
    except json.JSONDecodeError:
        return raw.strip(), False, [], []


def partition_sources_by_model_usage(
    all_sources: List[RagSourceOut],
    used_indexes: List[int],
    used_ids: List[str],
) -> Tuple[List[RagSourceOut], List[RagSourceOut]]:
    """sources_used = model-attributed passages; retrieved_only = full list when model gave no ids/indexes."""
    if used_indexes:
        want = set(used_indexes)
        return ([s for s in all_sources if s.source_index in want], [])
    if used_ids:
        idset = {_safe_str(x) for x in used_ids if _safe_str(x)}
        return ([s for s in all_sources if _safe_str(s.object_id) in idset], [])
    return ([], list(all_sources))


def _rag_query_hint(req: RagAskRequest) -> str:
    h = getattr(req, "query_language", None)
    if h is None or not str(h).strip():
        return "auto"
    return str(h).strip().lower()


def _respond_in_urdu_for_query(req: RagAskRequest, q_trans_meta: Dict[str, Any]) -> bool:
    """Match assistant reply script to query language (not output_language preference)."""
    hint = _rag_query_hint(req)
    if hint == "en":
        return False
    if hint == "ur":
        return True
    raw = (req.query or "").strip()
    if looks_like_urdu_script_query(raw):
        return True
    if q_trans_meta.get("retrieval_query_translated"):
        return True
    return False


def retrieve_for_rag_ask(db: Session, req: RagAskRequest) -> RetrievalResponse:
    """DB-bound hybrid/dense retrieval only. Callers should close the session before rerank/LLM."""
    q_hint = _rag_query_hint(req)
    q_en, q_meta = translate_rag_query_to_english(req.query or "", query_language_hint=q_hint)
    q_for_retrieval = q_en.strip() if q_en.strip() else (req.query or "").strip()
    qvec = embed_query_text(q_for_retrieval)
    retriever = RetrievalService()
    pool_n = max_rerank_candidates()
    use_rerank = is_reranker_enabled()
    retrieve_k = (
        max(max(1, req.top_k_retrieval), pool_n) if use_rerank else max(1, req.top_k_retrieval)
    )
    out = retriever.retrieve(
        db=db,
        query=q_for_retrieval,
        query_embedding=qvec,
        act_name=req.act_name,
        category=req.category,
        section_number=req.section_number,
        top_k=retrieve_k,
        search_tables=req.search_tables,
        search_forms=req.search_forms,
    )
    meta = dict(q_meta)
    if meta.get("retrieval_query_translated"):
        meta["retrieval_query_english"] = q_for_retrieval
    return out.model_copy(update={"translation_meta": meta})


def retrieve_for_rag_evaluation(
    db: Session,
    req: RagAskRequest,
    candidate_k: int,
) -> RagEvaluationRetrieval:
    """Evaluation-only retrieval aligned with production `finalize_rag_ask` rerank/dedupe.

    One pass per call (no duplicate work):
    - Single `embed_query_text` for the question.
    - Single `RetrievalService.retrieve` (first-stage hybrid/dense/BM25) with shared
      `query_embedding=qvec`; `pre_rerank_results` and the rerank pool are slices of
      `retrieval.results` from that call.
    - Single `rerank_candidates` when the reranker is enabled; `post_rerank_results` is
      the reranked pool only.

    - DB retrieval depth matches `retrieve_for_rag_ask` when rerank is on:
      max(candidate_k, pool_n).
    - Reranking runs on the first pool_n fused hits only (same as production).
    - `post_rerank_results` is that reranked pool only (length <= pool_n); there is no
      tail appended — chunks beyond pool_n are never reranked in production.
    - `post_context_deduped` mirrors the prompt path: top `max_ctx` of the reranked pool
      (or fused list if rerank off), then `dedupe_chunks_by_act_section`.
    """
    effective_candidate_k = max(1, int(candidate_k))
    pool_n = max_rerank_candidates()
    use_rerank = is_reranker_enabled()
    retrieve_k = (
        max(effective_candidate_k, pool_n) if use_rerank else effective_candidate_k
    )
    max_ctx = int(os.environ.get("RAG_CONTEXT_MAX_CHUNKS", "6"))
    max_ctx = min(max_ctx, max(1, req.top_k_context))

    q_hint = _rag_query_hint(req)
    q_en, eval_q_meta = translate_rag_query_to_english(req.query or "", query_language_hint=q_hint)
    q_for_retrieval = q_en.strip() if q_en.strip() else (req.query or "").strip()
    qvec = embed_query_text(q_for_retrieval)
    retriever = RetrievalService()
    raw_retrieval = retriever.retrieve(
        db=db,
        query=q_for_retrieval,
        query_embedding=qvec,
        act_name=req.act_name,
        category=req.category,
        section_number=req.section_number,
        top_k=retrieve_k,
        search_tables=req.search_tables,
        search_forms=req.search_forms,
    )
    meta_eval = dict(eval_q_meta)
    if meta_eval.get("retrieval_query_translated"):
        meta_eval["retrieval_query_english"] = q_for_retrieval
    retrieval = raw_retrieval.model_copy(update={"translation_meta": meta_eval})
    pre = list(retrieval.results[:retrieve_k])
    pool = list(retrieval.results[:pool_n])

    if use_rerank:
        post = rerank_candidates(q_for_retrieval, pool)
        rerank_pool_size = len(pool)
        top_for_dedupe = post[:max_ctx]
    else:
        post = list(pre)
        rerank_pool_size = 0
        top_for_dedupe = pre[:max_ctx]

    post_context_deduped = dedupe_chunks_by_act_section(top_for_dedupe)

    return RagEvaluationRetrieval(
        pre_rerank_results=pre,
        post_rerank_results=post,
        post_context_deduped=post_context_deduped,
        retrieval=retrieval,
        reranker_enabled=use_rerank,
        rerank_pool_size=rerank_pool_size,
        candidate_k=effective_candidate_k,
        pool_n=pool_n,
        retrieve_k=retrieve_k,
        max_ctx_used=max_ctx,
    )


def finalize_rag_ask(req: RagAskRequest, retrieval: RetrievalResponse) -> RagAskResponse:
    """Rerank, build context, call SLM. No DB — safe for long-running work after session is closed.

    Reply language follows the user's question: Urdu when query_language is "ur", or when
    query_language is auto/unset and the question has Urdu (Arabic) script or was translated
    for retrieval; English when query_language is "en" or otherwise. Request output_language
    is ignored for this choice.
    """
    q_sl = (retrieval.query or "").strip() or (req.query or "").strip()
    q_trans_meta = retrieval.translation_meta if retrieval.translation_meta else {}
    answer_in_urdu = _respond_in_urdu_for_query(req, q_trans_meta)
    response_out_lang = OUTPUT_LANG_UR if answer_in_urdu else OUTPUT_LANG_EN
    max_ctx = int(os.environ.get("RAG_CONTEXT_MAX_CHUNKS", "6"))
    max_ctx = min(max_ctx, max(1, req.top_k_context))
    max_chars = int(os.environ.get("RAG_CONTEXT_MAX_CHARS_PER_CHUNK", "2500"))
    max_resp_text = int(os.environ.get("RAG_RESPONSE_MAX_CHUNK_CHARS", "4000"))

    pool_n = max_rerank_candidates()
    use_rerank = is_reranker_enabled()

    if use_rerank:
        pool = retrieval.results[:pool_n]
        reranked = rerank_candidates(q_sl, pool)
        top = reranked[:max_ctx]
    else:
        top = retrieval.results[:max_ctx]
    deduped_top = dedupe_chunks_by_act_section(top)

    conf_threshold = _low_confidence_threshold()
    min_ctx_top = _context_min_top_score_allow_llm()
    best_ctx_score = _best_context_fused_score(deduped_top)
    low_conf_heuristic = (
        conf_threshold > 0 and retrieval.confidence_score < conf_threshold
    )
    context_score_override = bool(deduped_top) and best_ctx_score >= min_ctx_top
    block_low_conf = low_conf_heuristic and not context_score_override
    if block_low_conf:
        all_sources = chunks_to_sources(deduped_top)
        retrieved = chunks_to_retrieved_out(deduped_top, max_text_len=max_resp_text)
        meta: Dict[str, Any] = {
            "needs_table": retrieval.needs_table,
            "needs_form": retrieval.needs_form,
            "fallback_used": retrieval.fallback_used,
            "applied_filters": retrieval.applied_filters,
            "sources_used_count": 0,
            "retrieved_sources_fallback": True,
            "reranker_enabled": use_rerank,
            "rerank_pool_size": pool_n if use_rerank else 0,
            "context_chunks_selected": max_ctx,
            "context_chunks_after_dedupe": len(deduped_top),
            "low_confidence_blocked": True,
        }
        if q_trans_meta:
            meta["query_translation"] = q_trans_meta
        return RagAskResponse(
            answer=low_confidence_user_message(response_out_lang),
            insufficient_context=False,
            low_retrieval_confidence=True,
            output_language=response_out_lang,
            used_source_indexes=[],
            used_source_ids=[],
            confidence_score=retrieval.confidence_score,
            confidence_label=retrieval.confidence_label,
            sources=[],
            retrieved_sources=all_sources,
            retrieved_chunks=retrieved,
            retrieval_meta=meta,
        )

    context_block = build_grounded_context(deduped_top, max_chars_per_chunk=max_chars)
    user_msg = (
        f"Retrieved passages (sole authority; use only these):\n\n{context_block}\n\n"
        f"User question: {q_sl}\n\n"
        "Return only the JSON object described in your instructions."
    )

    system_grounding = build_grounding_system_english_pipeline()

    raw = chat_completion(
        [
            {"role": "system", "content": system_grounding},
            {"role": "user", "content": user_msg},
        ],
        temperature=get_ollama_temperature(),
        top_p=get_ollama_top_p(),
        json_format=True,
    )

    answer, insufficient, used_idx, used_ids = parse_legal_model_json(raw)
    if not answer:
        answer = raw if raw else "No answer was returned by the model."
    if answer_in_urdu:
        answer = _append_low_label_disclaimer(answer, retrieval, OUTPUT_LANG_EN)
        answer = translate_text(answer, source="en", target="ur")
    else:
        answer = _append_low_label_disclaimer(answer, retrieval, OUTPUT_LANG_EN)

    all_sources = chunks_to_sources(deduped_top)
    # Frontend "sources" = only passages the model listed; "retrieved_sources" = full list if lists empty
    sources_used, retrieved_sources = partition_sources_by_model_usage(
        all_sources, used_idx, used_ids
    )
    retrieved = chunks_to_retrieved_out(deduped_top, max_text_len=max_resp_text)
    meta: Dict[str, Any] = {
        "needs_table": retrieval.needs_table,
        "needs_form": retrieval.needs_form,
        "fallback_used": retrieval.fallback_used,
        "applied_filters": retrieval.applied_filters,
        "sources_used_count": len(sources_used),
        "retrieved_sources_fallback": bool(retrieved_sources),
        "reranker_enabled": use_rerank,
        "rerank_pool_size": pool_n if use_rerank else 0,
        "context_chunks_selected": max_ctx,
        "context_chunks_after_dedupe": len(deduped_top),
    }
    if low_conf_heuristic and context_score_override:
        meta["low_confidence_overridden_by_context_score"] = True
    if q_trans_meta:
        meta["query_translation"] = q_trans_meta

    return RagAskResponse(
        answer=answer,
        insufficient_context=insufficient,
        low_retrieval_confidence=False,
        output_language=response_out_lang,
        used_source_indexes=used_idx,
        used_source_ids=used_ids,
        confidence_score=retrieval.confidence_score,
        confidence_label=retrieval.confidence_label,
        sources=sources_used,
        retrieved_sources=retrieved_sources,
        retrieved_chunks=retrieved,
        retrieval_meta=meta,
    )


def run_rag_ask(db: Session, req: RagAskRequest) -> RagAskResponse:
    retrieval = retrieve_for_rag_ask(db, req)
    return finalize_rag_ask(req, retrieval)
