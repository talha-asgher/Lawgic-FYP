from __future__ import annotations

import os
import re
from collections import defaultdict
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, Sequence, Set, Tuple

from pydantic import BaseModel, Field
from rank_bm25 import BM25Okapi
from sqlalchemy import MetaData, Table, Column, String, Text, Integer, select, and_, or_, true, func
from sqlalchemy.dialects.postgresql import ARRAY, UUID, JSONB
from sqlalchemy.orm import Session
from pgvector.sqlalchemy import Vector

VECTOR_DIM = int(os.environ.get("LAWGIC_VECTOR_DIM", "1024"))
DEFAULT_EMBED_MODEL = os.environ.get("LAWGIC_EMBED_MODEL", "bge-m3")

_WS_RE = re.compile(r"\s+")
_TOKEN_RE = re.compile(r"[A-Za-z0-9\u0600-\u06FF]+", re.UNICODE)

_TABLE_ROUTE_KEYWORDS = ("table", "rate", "list", "schedule")
_FORM_ROUTE_KEYWORDS = ("form", "application", "schedule")
_SECTION_RES = (
    re.compile(r"(?i)section\s+(\d+[A-Za-z]?(?:\s*\(\d+[A-Za-z]?\))?)"),
    re.compile(r"(?i)sec\.?\s*(\d+[A-Za-z]?)"),
    re.compile(r"(?i)\bs\.?\s*(\d+[A-Za-z]?)"),
    re.compile(r"(?i)article\s+(\d+[A-Za-z]?)"),
)

ACT_ALIASES: Dict[str, List[str]] = {
    "ppc": ["pakistan penal code", "penal code, 1860", "penal code 1860"],
    "cpc": ["code of civil procedure", "civil procedure code", "c.p.c"],
    "crpc": ["code of criminal procedure", "criminal procedure code", "cr.p.c"],
}

# Longest-first phrases for fuzzy act filter (substring match in DB act_name).
_ACT_SUBSTRING_HINTS: Tuple[str, ...] = (
    "child marriage restraint",
    "child marriage restriction",
    "child marriage",
)

_CATEGORY_QUERY_PATTERNS: Tuple[Tuple[re.Pattern, str], ...] = (
    (
        re.compile(
            r"\b(child marriage|nikah|divorce|dower|dowry|custody|guardianship|maintenance|iddat|haq mehr|family)\b",
            re.IGNORECASE,
        ),
        "family",
    ),
    (
        re.compile(
            r"\b(murder|theft|robbery|fraud|bail|fir|offence|offense|penal code|ppc|criminal|qatl|zina)\b",
            re.IGNORECASE,
        ),
        "criminal",
    ),
    (
        re.compile(
            r"\b(contract|specific relief|limitation act|suit|civil procedure|cpc|civil)\b",
            re.IGNORECASE,
        ),
        "civil",
    ),
)


def normalize_query(q: str) -> str:
    if not q:
        return ""
    t = q.replace("\u00a0", " ").strip()
    t = _WS_RE.sub(" ", t)
    return t


def tokenize_for_bm25(text: str) -> List[str]:
    if not text:
        return []
    return [x.lower() for x in _TOKEN_RE.findall(text)]


def normalize_section_for_match(s: Optional[str]) -> str:
    if not s:
        return ""
    t = str(s).strip().lower()
    t = re.sub(r"\s+", "", t)
    t = t.replace("–", "-").replace("—", "-")
    t = re.sub(r"(\d)-([a-z])", r"\1\2", t)
    t = re.sub(r"\(\s*", "(", t)
    t = re.sub(r"\s*\)", ")", t)
    return t


def section_references_equivalent(a: Optional[str], b: Optional[str]) -> bool:
    na = normalize_section_for_match(a)
    nb = normalize_section_for_match(b)
    return bool(na and nb and na == nb)


def expand_section_filter_values(section: Optional[str]) -> List[str]:
    if not section:
        return []
    raw = str(section).strip()
    if not raw:
        return []
    norm = normalize_section_for_match(raw)
    variants: Set[str] = {raw, raw.lower(), norm}
    m = re.match(r"^(\d+)([a-z])$", norm)
    if m:
        variants.add(f"{m.group(1)}-{m.group(2)}")
        variants.add(f"{m.group(1)} {m.group(2)}")
        variants.add(f"{m.group(1).upper()}-{m.group(2).upper()}")
    return [v for v in variants if v]


def normalize_act_filter_token(act: Optional[str]) -> str:
    if not act:
        return ""
    return re.sub(r"\s+", " ", str(act).strip()).lower()


def act_filter_sql_condition(m: Table, act_name: str):
    al = normalize_act_filter_token(act_name)
    if not al:
        return true()
    key = re.sub(r"[\s.]+", "", al)
    if al in ACT_ALIASES:
        return or_(*[m.c.act_name.ilike(f"%{n}%") for n in ACT_ALIASES[al]])
    if key in ACT_ALIASES:
        return or_(*[m.c.act_name.ilike(f"%{n}%") for n in ACT_ALIASES[key]])
    return func.lower(func.trim(m.c.act_name)) == al


def extract_section_numbers_from_query(q: str) -> List[str]:
    out: List[str] = []
    for rx in _SECTION_RES:
        for m in rx.finditer(q or ""):
            if m.lastindex:
                s = m.group(1).strip()
                if s and s not in out:
                    out.append(s)
    return out


def extract_normalized_sections_from_query(q: str) -> List[str]:
    seen: Set[str] = set()
    out: List[str] = []
    for raw in extract_section_numbers_from_query(q):
        n = normalize_section_for_match(raw)
        if n and n not in seen:
            seen.add(n)
            out.append(n)
    return out


def infer_category_from_query(q: str) -> Optional[str]:
    if not q:
        return None
    for rx, cat in _CATEGORY_QUERY_PATTERNS:
        if rx.search(q):
            return cat
    return None


def infer_act_fuzzy_phrase_from_query(q: str) -> Optional[str]:
    """Substring to use with act_name ILIKE when the API did not pass act_name."""
    if not q:
        return None
    ql = q.lower().strip()
    best: Optional[str] = None
    best_len = 0
    for phrase in sorted(_ACT_SUBSTRING_HINTS, key=len, reverse=True):
        if phrase in ql and len(phrase) > best_len:
            best = phrase
            best_len = len(phrase)
    if best:
        return best
    compact = re.sub(r"\s+", "", ql)
    for key, aliases in ACT_ALIASES.items():
        if key in ql.split() or key in compact:
            return aliases[0]
        for al in aliases:
            if al in ql:
                return al
    return None


def post_filter_by_inferred_metadata(
    hits: List[ScoredHit],
    inferred_category: Optional[str],
    act_phrase: Optional[str],
) -> List[ScoredHit]:
    """Drop obvious mismatches when inference was used (restore if list becomes too small)."""
    if not hits:
        return hits
    out = list(hits)
    if inferred_category:
        ic = inferred_category.strip().lower()
        narrowed = [h for h in out if safe_str(h.category).strip().lower() == ic]
        if len(narrowed) >= max(2, len(out) // 4):
            out = narrowed
    if act_phrase:
        ap = act_phrase.strip().lower()
        if ap:
            narrowed = [h for h in out if ap in safe_str(h.act_name).lower()]
            if len(narrowed) >= max(2, len(out) // 4):
                out = narrowed
    return out if out else hits


def _query_has_keyword(q: str, words: Tuple[str, ...]) -> bool:
    if not q:
        return False
    for w in words:
        if re.search(rf"\b{re.escape(w)}\b", q, re.IGNORECASE):
            return True
    return False


def heuristic_needs_table(q: str) -> bool:
    return _query_has_keyword(q or "", _TABLE_ROUTE_KEYWORDS)


def heuristic_needs_form(q: str) -> bool:
    return _query_has_keyword(q or "", _FORM_ROUTE_KEYWORDS)


def resolve_needs_table(q: str, explicit: Optional[bool]) -> bool:
    if explicit is True:
        return True
    if explicit is False:
        return False
    return heuristic_needs_table(q)


def resolve_needs_form(q: str, explicit: Optional[bool]) -> bool:
    if explicit is True:
        return True
    if explicit is False:
        return False
    return heuristic_needs_form(q)


def min_max_normalize(scores: Dict[str, float]) -> Dict[str, float]:
    if not scores:
        return {}
    vals = list(scores.values())
    lo, hi = min(vals), max(vals)
    if hi <= lo + 1e-12:
        return {k: 1.0 for k in scores}
    return {k: (v - lo) / (hi - lo) for k, v in scores.items()}


def safe_str(x: Any) -> str:
    if x is None:
        return ""
    return str(x).strip()


def bm25_document_child(
    section_title: Any,
    text: Any,
    act_name: Any,
    section_number: Any,
    category: Any,
) -> str:
    """Body text first so BM25 is driven by substance; metadata appended as a light tail."""
    body = safe_str(text)
    meta_bits = [
        safe_str(act_name),
        safe_str(section_number),
        safe_str(section_title),
        safe_str(category),
    ]
    meta = " ".join(x for x in meta_bits if x)
    if body and meta:
        return f"{body}\n{meta}"
    return body or meta


def bm25_document_table_embed_aligned(
    table_local_id: Any,
    act_name: Any,
    section_number: Any,
    section_title: Any,
    category: Any,
    summary: Any,
) -> str:
    parts: List[str] = []
    act = safe_str(act_name)
    if act:
        parts.append(f"Act: {act}")
    sec = safe_str(section_number)
    title = safe_str(section_title)
    if sec and sec.lower() != "-":
        parts.append(f"Section: {sec}" + (f" — {title}" if title else ""))
    elif title:
        parts.append(f"Section title: {title}")
    cat = safe_str(category)
    if cat:
        parts.append(f"Category: {cat}")
    tid = safe_str(table_local_id)
    if tid:
        parts.append(f"Table: {tid}")
    summ = safe_str(summary)
    if summ:
        parts.append(summ)
    return "\n".join(parts)


def bm25_document_form_embed_aligned(
    form_local_id: Any,
    act_name: Any,
    section_number: Any,
    section_title: Any,
    category: Any,
    summary: Any,
) -> str:
    parts: List[str] = []
    act = safe_str(act_name)
    if act:
        parts.append(f"Act: {act}")
    sec = safe_str(section_number)
    title = safe_str(section_title)
    if sec and sec.lower() != "-":
        parts.append(f"Section: {sec}" + (f" — {title}" if title else ""))
    elif title:
        parts.append(f"Section title: {title}")
    cat = safe_str(category)
    if cat:
        parts.append(f"Category: {cat}")
    fid = safe_str(form_local_id)
    if fid:
        parts.append(f"Form: {fid}")
    summ = safe_str(summary)
    if summ:
        parts.append(summ)
    return "\n".join(parts)


def act_names_align(filter_act: Optional[str], row_act: Any) -> bool:
    if not filter_act:
        return False
    ra = safe_str(row_act)
    if not ra:
        return False
    al = normalize_act_filter_token(filter_act)
    key = re.sub(r"[\s.]+", "", al)
    rl = ra.lower()
    needles: List[str] = []
    if al in ACT_ALIASES:
        needles = ACT_ALIASES[al]
    elif key in ACT_ALIASES:
        needles = ACT_ALIASES[key]
    if needles:
        return any(n.lower() in rl for n in needles)
    return rl == al


def section_title_keyword_overlap(query_tokens: Set[str], section_title: str) -> float:
    if not section_title or not query_tokens:
        return 0.0
    st = set(tokenize_for_bm25(section_title))
    if not st:
        return 0.0
    inter = len(query_tokens & st)
    return min(1.0, inter / max(1, len(query_tokens)))



_SUBSTANTIVE_QUERY_RE = re.compile(
    r"\b(what can|what should|what may|how can|remedy|relief|punishment|penalt|offen[sc]e|liability|"
    r"sue|claim|right|divorce|dissolution|custody|maintenance|inherit|talaq|khul|dower|dowry)\b",
    re.IGNORECASE,
)
_PROCEDURAL_EVIDENCE_TITLE_RE = re.compile(
    r"\b(competent|competence|evidence|witness|costs?\b|rules?\b|power to make rules|interpretation|"
    r"definitions?\b|preamble|extent of|short title|commencement)\b",
    re.IGNORECASE,
)


def _substantive_rights_query(qn: str) -> bool:
    return bool(qn and _SUBSTANTIVE_QUERY_RE.search(qn))


def _procedural_noise_title(title: str) -> bool:
    return bool(title and _PROCEDURAL_EVIDENCE_TITLE_RE.search(title))


def metadata_boost_score(
    query_norm: str,
    query_tokens: Set[str],
    filter_act: Optional[str],
    filter_category: Optional[str],
    filter_section: Optional[str],
    extracted_sections_norm: Sequence[str],
    act_name: Any,
    category: Any,
    section_number: Any,
    section_title: Any,
    act_substring_boost: Optional[str] = None,
) -> float:
    parts: List[float] = []
    an = safe_str(act_name)
    cat = safe_str(category)
    sn = safe_str(section_number)
    stitle = safe_str(section_title)

    if filter_act:
        parts.append(
            1.0
            if act_names_align(filter_act, an)
            else (
                0.4
                if normalize_act_filter_token(filter_act) in query_norm.lower()
                and normalize_act_filter_token(filter_act) in an.lower()
                else 0.0
            )
        )
    elif act_substring_boost:
        ah = act_substring_boost.strip().lower()
        if ah and ah in an.lower():
            parts.append(0.88)
        else:
            parts.append(0.0)
    else:
        if an and an.lower() in query_norm.lower():
            parts.append(0.5)

    if filter_section:
        parts.append(1.0 if section_references_equivalent(filter_section, sn) else 0.0)
    else:
        matched = False
        for es in extracted_sections_norm:
            if section_references_equivalent(es, sn):
                parts.append(1.0)
                matched = True
                break
        if not matched and extracted_sections_norm and sn:
            parts.append(0.2)

    if filter_category:
        parts.append(1.0 if cat.lower() == filter_category.strip().lower() else 0.0)

    title_ov = section_title_keyword_overlap(query_tokens, stitle)
    tw = float(os.environ.get("LAWGIC_TITLE_OVERLAP_METADATA_WEIGHT", "0.45"))
    parts.append(tw * title_ov)

    if not parts:
        return 0.0
    return min(1.0, sum(parts) / max(1, len(parts)))


def structure_boost_value(
    chunk_type: str,
    needs_table: bool,
    needs_form: bool,
) -> float:
    if chunk_type == "table" and needs_table:
        return 1.0
    if chunk_type == "form" and needs_form:
        return 1.0
    if chunk_type == "child":
        return 0.85
    if chunk_type == "table" and not needs_table:
        return 0.35
    if chunk_type == "form" and not needs_form:
        return 0.35
    return 0.5


def final_hybrid_score(
    dense_n: float,
    bm25_n: float,
    meta_b: float,
    struct_b: float,
    w_d: float = 0.50,
    w_b: float = 0.25,
    w_m: float = 0.15,
    w_s: float = 0.10,
) -> float:
    return w_d * dense_n + w_b * bm25_n + w_m * meta_b + w_s * struct_b


def merge_dense_bm25_candidates(
    dense_scores: Dict[str, float],
    bm25_scores: Dict[str, float],
    dense_top_n: int,
    bm25_top_n: int,
) -> Set[str]:
    ids: Set[str] = set()
    for k, _ in sorted(dense_scores.items(), key=lambda x: -x[1])[:dense_top_n]:
        ids.add(k)
    for k, _ in sorted(bm25_scores.items(), key=lambda x: -x[1])[:bm25_top_n]:
        ids.add(k)
    return ids


def diversify_results(
    ranked: List["ScoredHit"],
    max_per_section: int,
    score_ratio_keep: float,
) -> List["ScoredHit"]:
    counts: Dict[Tuple[str, str], int] = {}
    out: List[ScoredHit] = []
    top_score = ranked[0].final_score if ranked else 0.0
    for h in ranked:
        key = (h.parent_id or "", safe_str(h.section_number))
        c = counts.get(key, 0)
        if c >= max_per_section and h.final_score < top_score * score_ratio_keep:
            continue
        counts[key] = c + 1
        out.append(h)
    return out


def confidence_from_results(
    hits: List["ScoredHit"],
    filter_act: Optional[str],
    filter_category: Optional[str],
    filter_section: Optional[str],
    extracted_sections_norm: Sequence[str],
    act_fuzzy_phrase: Optional[str] = None,
) -> Tuple[float, str]:
    if not hits:
        return 0.0, "low"
    h0 = hits[0]
    h1 = hits[1] if len(hits) > 1 else None
    gap = (h0.final_score - h1.final_score) if h1 else h0.final_score

    sig = 0.0
    if filter_act and act_names_align(filter_act, h0.act_name):
        sig += 0.2
    elif act_fuzzy_phrase:
        af = act_fuzzy_phrase.strip().lower()
        if af and af in safe_str(h0.act_name).lower():
            sig += 0.18
    if filter_category and safe_str(h0.category).lower() == filter_category.strip().lower():
        sig += 0.15
    if filter_section and section_references_equivalent(filter_section, h0.section_number):
        sig += 0.2
    for es in extracted_sections_norm:
        if section_references_equivalent(es, h0.section_number):
            sig += 0.15
            break
    sig += 0.30 * min(1.0, h0.final_score)
    sig += 0.18 * min(1.0, h0.dense_norm)
    sig += 0.10 * min(1.0, h0.bm25_norm)
    sig += 0.22 * min(1.0, gap * 3.0)

    top_act_sec = [
        (safe_str(x.act_name).lower(), safe_str(x.section_number).lower())
        for x in hits[:5]
    ]
    if len(set(top_act_sec)) <= 2 and len(top_act_sec) >= 3:
        sig += 0.1

    top5 = hits[:5]
    pid0 = h0.parent_id
    if pid0 and sum(1 for x in top5 if x.parent_id == pid0) >= 2:
        sig += 0.12

    score = min(1.0, max(0.0, sig))
    if score >= 0.72:
        label = "high"
    elif score >= 0.42:
        label = "medium"
    else:
        label = "low"
    return score, label


@dataclass
class ScoredHit:
    chunk_type: str
    object_id: str
    parent_id: Optional[str]
    text: str
    summary: Optional[str]
    act_name: Optional[str]
    category: Optional[str]
    section_number: Optional[str]
    section_title: Optional[str]
    page_numbers: Any
    dense_norm: float
    bm25_norm: float
    metadata_boost: float
    structure_boost: float
    final_score: float
    row_extra: Dict[str, Any]


def _law_tables(meta: MetaData) -> Tuple[Table, Table, Table, Table, Table, Table, Table]:
    law_parent_metadata = Table(
        "law_parent_metadata",
        meta,
        Column("parent_id", String(512), primary_key=True),
        Column("act_name", Text),
        Column("category", String(128)),
        Column("section_number", String(256)),
        Column("section_title", Text),
        Column("page_numbers", ARRAY(Integer)),
        Column("text", Text),
    )
    law_child_metadata = Table(
        "law_child_metadata",
        meta,
        Column("child_id", String(512), primary_key=True),
        Column("parent_id", String(512)),
        Column("act_name", Text),
        Column("category", String(128)),
        Column("section_number", String(256)),
        Column("section_title", Text),
        Column("page_numbers", ARRAY(Integer)),
        Column("start_pos_raw", Integer),
        Column("end_pos_raw", Integer),
        Column("text", Text),
        Column("footnotes", JSONB),
    )
    law_child_embeddings = Table(
        "law_child_embeddings",
        meta,
        Column("child_id", String(512), primary_key=True),
        Column("model_name", String(128), primary_key=True),
        Column("embedding", Vector(VECTOR_DIM)),
    )
    law_table_metadata = Table(
        "law_table_metadata",
        meta,
        Column("table_uid", UUID(as_uuid=True), primary_key=True),
        Column("table_local_id", String(512)),
        Column("parent_id", String(512)),
        Column("act_name", Text),
        Column("category", String(128)),
        Column("section_number", String(256)),
        Column("section_title", Text),
        Column("table_index_in_section", Integer),
        Column("page_numbers", ARRAY(Integer)),
        Column("page", Integer),
        Column("text", Text),
        Column("summary", Text),
        Column("pdf_path", Text),
    )
    law_table_embeddings = Table(
        "law_table_embeddings",
        meta,
        Column("table_uid", UUID(as_uuid=True), primary_key=True),
        Column("model_name", String(128), primary_key=True),
        Column("embedding", Vector(VECTOR_DIM)),
    )
    law_form_metadata = Table(
        "law_form_metadata",
        meta,
        Column("form_uid", UUID(as_uuid=True), primary_key=True),
        Column("form_local_id", String(512)),
        Column("parent_id", String(512)),
        Column("act_name", Text),
        Column("category", String(128)),
        Column("section_number", String(256)),
        Column("section_title", Text),
        Column("form_index_in_section", Integer),
        Column("page_numbers", ARRAY(Integer)),
        Column("page", Integer),
        Column("text", Text),
        Column("summary", Text),
        Column("pdf_path", Text),
    )
    law_form_embeddings = Table(
        "law_form_embeddings",
        meta,
        Column("form_uid", UUID(as_uuid=True), primary_key=True),
        Column("model_name", String(128), primary_key=True),
        Column("embedding", Vector(VECTOR_DIM)),
    )
    return (
        law_parent_metadata,
        law_child_metadata,
        law_child_embeddings,
        law_table_metadata,
        law_table_embeddings,
        law_form_metadata,
        law_form_embeddings,
    )


def _filter_conditions_child(
    m: Table,
    act_name: Optional[str],
    category: Optional[str],
    section_number: Optional[str],
    act_fuzzy_phrase: Optional[str] = None,
):
    conds = []
    if act_name:
        conds.append(act_filter_sql_condition(m, act_name))
    elif act_fuzzy_phrase and act_fuzzy_phrase.strip():
        conds.append(m.c.act_name.ilike(f"%{act_fuzzy_phrase.strip()}%"))
    if category:
        conds.append(func.lower(m.c.category) == category.strip().lower())
    if section_number:
        vars_sec = expand_section_filter_values(section_number)
        if vars_sec:
            conds.append(or_(*[m.c.section_number == v for v in vars_sec]))
    return and_(*conds) if conds else true()


def _filter_conditions_table_form(
    m: Table,
    act_name: Optional[str],
    category: Optional[str],
    section_number: Optional[str],
    act_fuzzy_phrase: Optional[str] = None,
):
    return _filter_conditions_child(m, act_name, category, section_number, act_fuzzy_phrase)


def bm25_candidates_from_pool(
    doc_texts: List[str],
    ids: List[str],
    query_tokens: List[str],
) -> Dict[str, float]:
    if not doc_texts or not ids or len(doc_texts) != len(ids):
        return {}
    tokenized_corpus = [tokenize_for_bm25(t) for t in doc_texts]
    if not any(tokenized_corpus):
        return {}
    bm25 = BM25Okapi(tokenized_corpus)
    scores = bm25.get_scores(query_tokens)
    return {ids[i]: float(scores[i]) for i in range(len(ids))}


class RetrievalResultItem(BaseModel):
    chunk_type: str
    object_id: str
    parent_id: Optional[str] = None
    text: str = ""
    summary: Optional[str] = None
    act_name: Optional[str] = None
    category: Optional[str] = None
    section_number: Optional[str] = None
    section_title: Optional[str] = None
    page_numbers: Optional[List[Any]] = Field(default=None)
    score: float = 0.0
    dense_norm: Optional[float] = None
    bm25_norm: Optional[float] = None
    metadata_boost: Optional[float] = None
    rerank_score: Optional[float] = None
    parent_text: Optional[str] = None
    parent_act_name: Optional[str] = None
    parent_category: Optional[str] = None
    parent_section_number: Optional[str] = None
    parent_section_title: Optional[str] = None
    parent_page_numbers: Optional[List[Any]] = Field(default=None)
    neighboring_children: Optional[List[Dict[str, Any]]] = None


class RetrievalResponse(BaseModel):
    query: str
    applied_filters: Dict[str, Any]
    needs_table: bool
    needs_form: bool
    fallback_used: bool = False
    confidence_score: float
    confidence_label: str
    results: List[RetrievalResultItem]


class RetrievalService:
    def __init__(
        self,
        model_name: Optional[str] = None,
        max_bm25_pool: int = 12000,
        dense_candidate_limit_child: int = 120,
        dense_candidate_limit_table: int = 72,
        dense_candidate_limit_form: int = 72,
        bm25_merge_top_child: int = 220,
        bm25_merge_top_table: int = 72,
        bm25_merge_top_form: int = 72,
        fallback_expand_top_score_threshold: Optional[float] = None,
        embed_query: Optional[Callable[[str], List[float]]] = None,
    ):
        self.model_name = model_name or DEFAULT_EMBED_MODEL
        self.max_bm25_pool = max_bm25_pool
        self.dense_candidate_limit_child = dense_candidate_limit_child
        self.dense_candidate_limit_table = dense_candidate_limit_table
        self.dense_candidate_limit_form = dense_candidate_limit_form
        self.bm25_merge_top_child = bm25_merge_top_child
        self.bm25_merge_top_table = bm25_merge_top_table
        self.bm25_merge_top_form = bm25_merge_top_form
        _ft = fallback_expand_top_score_threshold
        if _ft is None:
            _ft = float(os.environ.get("LAWGIC_FALLBACK_EXPAND_TOP_SCORE", "0.52"))
        self.fallback_expand_top_score_threshold = _ft
        self.embed_query = embed_query
        self._meta = MetaData()
        (
            self.law_parent_metadata,
            self.law_child_metadata,
            self.law_child_embeddings,
            self.law_table_metadata,
            self.law_table_embeddings,
            self.law_form_metadata,
            self.law_form_embeddings,
        ) = _law_tables(self._meta)

    def _require_embedding(
        self,
        query: str,
        query_embedding: Optional[Sequence[float]],
    ) -> List[float]:
        if query_embedding is not None:
            return list(query_embedding)
        if self.embed_query is None:
            raise ValueError("query_embedding is required when embed_query is not configured")
        return list(self.embed_query(query))

    def dense_search_children(
        self,
        db: Session,
        query_embedding: Sequence[float],
        act_name: Optional[str],
        category: Optional[str],
        section_number: Optional[str],
        limit: int,
        act_fuzzy_phrase: Optional[str] = None,
    ) -> List[Tuple[str, float, Dict[str, Any]]]:
        m = self.law_child_metadata
        e = self.law_child_embeddings
        dist = e.c.embedding.cosine_distance(list(query_embedding))
        stmt = (
            select(
                m.c.child_id,
                m.c.parent_id,
                m.c.act_name,
                m.c.category,
                m.c.section_number,
                m.c.section_title,
                m.c.page_numbers,
                m.c.start_pos_raw,
                m.c.end_pos_raw,
                m.c.text,
                dist.label("distance"),
            )
            .select_from(m.join(e, m.c.child_id == e.c.child_id))
            .where(
                and_(
                    e.c.model_name == self.model_name,
                    _filter_conditions_child(m, act_name, category, section_number, act_fuzzy_phrase),
                )
            )
            .order_by(dist)
            .limit(limit)
        )
        rows = db.execute(stmt).all()
        out: List[Tuple[str, float, Dict[str, Any]]] = []
        for r in rows:
            d = float(r.distance or 0.0)
            sim = max(0.0, min(1.0, 1.0 - d))
            rid = str(r.child_id)
            out.append(
                (
                    rid,
                    sim,
                    {
                        "child_id": rid,
                        "parent_id": r.parent_id,
                        "act_name": r.act_name,
                        "category": r.category,
                        "section_number": r.section_number,
                        "section_title": r.section_title,
                        "page_numbers": list(r.page_numbers) if r.page_numbers is not None else None,
                        "start_pos_raw": r.start_pos_raw,
                        "end_pos_raw": r.end_pos_raw,
                        "text": r.text or "",
                    },
                )
            )
        return out

    def dense_search_tables(
        self,
        db: Session,
        query_embedding: Sequence[float],
        act_name: Optional[str],
        category: Optional[str],
        section_number: Optional[str],
        limit: int,
        act_fuzzy_phrase: Optional[str] = None,
    ) -> List[Tuple[str, float, Dict[str, Any]]]:
        m = self.law_table_metadata
        e = self.law_table_embeddings
        dist = e.c.embedding.cosine_distance(list(query_embedding))
        stmt = (
            select(
                m.c.table_uid,
                m.c.parent_id,
                m.c.act_name,
                m.c.category,
                m.c.section_number,
                m.c.section_title,
                m.c.page_numbers,
                m.c.text,
                m.c.summary,
                dist.label("distance"),
            )
            .select_from(m.join(e, m.c.table_uid == e.c.table_uid))
            .where(
                and_(
                    e.c.model_name == self.model_name,
                    _filter_conditions_table_form(m, act_name, category, section_number, act_fuzzy_phrase),
                )
            )
            .order_by(dist)
            .limit(limit)
        )
        rows = db.execute(stmt).all()
        out: List[Tuple[str, float, Dict[str, Any]]] = []
        for r in rows:
            d = float(r.distance or 0.0)
            sim = max(0.0, min(1.0, 1.0 - d))
            uid = str(r.table_uid)
            out.append(
                (
                    uid,
                    sim,
                    {
                        "table_uid": uid,
                        "parent_id": r.parent_id,
                        "act_name": r.act_name,
                        "category": r.category,
                        "section_number": r.section_number,
                        "section_title": r.section_title,
                        "page_numbers": list(r.page_numbers) if r.page_numbers is not None else None,
                        "text": r.text or "",
                        "summary": r.summary,
                    },
                )
            )
        return out

    def dense_search_forms(
        self,
        db: Session,
        query_embedding: Sequence[float],
        act_name: Optional[str],
        category: Optional[str],
        section_number: Optional[str],
        limit: int,
        act_fuzzy_phrase: Optional[str] = None,
    ) -> List[Tuple[str, float, Dict[str, Any]]]:
        m = self.law_form_metadata
        e = self.law_form_embeddings
        dist = e.c.embedding.cosine_distance(list(query_embedding))
        stmt = (
            select(
                m.c.form_uid,
                m.c.parent_id,
                m.c.act_name,
                m.c.category,
                m.c.section_number,
                m.c.section_title,
                m.c.page_numbers,
                m.c.text,
                m.c.summary,
                dist.label("distance"),
            )
            .select_from(m.join(e, m.c.form_uid == e.c.form_uid))
            .where(
                and_(
                    e.c.model_name == self.model_name,
                    _filter_conditions_table_form(m, act_name, category, section_number, act_fuzzy_phrase),
                )
            )
            .order_by(dist)
            .limit(limit)
        )
        rows = db.execute(stmt).all()
        out: List[Tuple[str, float, Dict[str, Any]]] = []
        for r in rows:
            d = float(r.distance or 0.0)
            sim = max(0.0, min(1.0, 1.0 - d))
            uid = str(r.form_uid)
            out.append(
                (
                    uid,
                    sim,
                    {
                        "form_uid": uid,
                        "parent_id": r.parent_id,
                        "act_name": r.act_name,
                        "category": r.category,
                        "section_number": r.section_number,
                        "section_title": r.section_title,
                        "page_numbers": list(r.page_numbers) if r.page_numbers is not None else None,
                        "text": r.text or "",
                        "summary": r.summary,
                    },
                )
            )
        return out

    def fetch_child_bm25_pool(
        self,
        db: Session,
        act_name: Optional[str],
        category: Optional[str],
        section_number: Optional[str],
        act_fuzzy_phrase: Optional[str] = None,
    ) -> Tuple[List[str], List[str], List[Dict[str, Any]]]:
        m = self.law_child_metadata
        stmt = (
            select(
                m.c.child_id,
                m.c.parent_id,
                m.c.act_name,
                m.c.category,
                m.c.section_number,
                m.c.section_title,
                m.c.page_numbers,
                m.c.start_pos_raw,
                m.c.end_pos_raw,
                m.c.text,
            )
            .where(_filter_conditions_child(m, act_name, category, section_number, act_fuzzy_phrase))
            .limit(self.max_bm25_pool)
        )
        rows = db.execute(stmt).all()
        ids: List[str] = []
        docs: List[str] = []
        metas: List[Dict[str, Any]] = []
        for r in rows:
            rid = str(r.child_id)
            ids.append(rid)
            docs.append(
                bm25_document_child(
                    r.section_title,
                    r.text,
                    r.act_name,
                    r.section_number,
                    r.category,
                )
            )
            metas.append(
                {
                    "child_id": rid,
                    "parent_id": r.parent_id,
                    "act_name": r.act_name,
                    "category": r.category,
                    "section_number": r.section_number,
                    "section_title": r.section_title,
                    "page_numbers": list(r.page_numbers) if r.page_numbers is not None else None,
                    "start_pos_raw": r.start_pos_raw,
                    "end_pos_raw": r.end_pos_raw,
                    "text": r.text or "",
                }
            )
        return ids, docs, metas

    def fetch_table_bm25_pool(
        self,
        db: Session,
        act_name: Optional[str],
        category: Optional[str],
        section_number: Optional[str],
        act_fuzzy_phrase: Optional[str] = None,
    ) -> Tuple[List[str], List[str], List[Dict[str, Any]]]:
        m = self.law_table_metadata
        stmt = (
            select(
                m.c.table_uid,
                m.c.table_local_id,
                m.c.parent_id,
                m.c.act_name,
                m.c.category,
                m.c.section_number,
                m.c.section_title,
                m.c.page_numbers,
                m.c.text,
                m.c.summary,
            )
            .where(_filter_conditions_table_form(m, act_name, category, section_number, act_fuzzy_phrase))
            .limit(self.max_bm25_pool)
        )
        rows = db.execute(stmt).all()
        ids: List[str] = []
        docs: List[str] = []
        metas: List[Dict[str, Any]] = []
        for r in rows:
            uid = str(r.table_uid)
            ids.append(uid)
            docs.append(
                bm25_document_table_embed_aligned(
                    r.table_local_id,
                    r.act_name,
                    r.section_number,
                    r.section_title,
                    r.category,
                    r.summary,
                )
            )
            metas.append(
                {
                    "table_uid": uid,
                    "parent_id": r.parent_id,
                    "act_name": r.act_name,
                    "category": r.category,
                    "section_number": r.section_number,
                    "section_title": r.section_title,
                    "page_numbers": list(r.page_numbers) if r.page_numbers is not None else None,
                    "text": r.text or "",
                    "summary": r.summary,
                }
            )
        return ids, docs, metas

    def fetch_form_bm25_pool(
        self,
        db: Session,
        act_name: Optional[str],
        category: Optional[str],
        section_number: Optional[str],
        act_fuzzy_phrase: Optional[str] = None,
    ) -> Tuple[List[str], List[str], List[Dict[str, Any]]]:
        m = self.law_form_metadata
        stmt = (
            select(
                m.c.form_uid,
                m.c.form_local_id,
                m.c.parent_id,
                m.c.act_name,
                m.c.category,
                m.c.section_number,
                m.c.section_title,
                m.c.page_numbers,
                m.c.text,
                m.c.summary,
            )
            .where(_filter_conditions_table_form(m, act_name, category, section_number, act_fuzzy_phrase))
            .limit(self.max_bm25_pool)
        )
        rows = db.execute(stmt).all()
        ids: List[str] = []
        docs: List[str] = []
        metas: List[Dict[str, Any]] = []
        for r in rows:
            uid = str(r.form_uid)
            ids.append(uid)
            docs.append(
                bm25_document_form_embed_aligned(
                    r.form_local_id,
                    r.act_name,
                    r.section_number,
                    r.section_title,
                    r.category,
                    r.summary,
                )
            )
            metas.append(
                {
                    "form_uid": uid,
                    "parent_id": r.parent_id,
                    "act_name": r.act_name,
                    "category": r.category,
                    "section_number": r.section_number,
                    "section_title": r.section_title,
                    "page_numbers": list(r.page_numbers) if r.page_numbers is not None else None,
                    "text": r.text or "",
                    "summary": r.summary,
                }
            )
        return ids, docs, metas

    def hybrid_chunk_type(
        self,
        db: Session,
        query_norm: str,
        query_tokens: List[str],
        query_embedding: Sequence[float],
        chunk_type: str,
        act_name: Optional[str],
        category: Optional[str],
        section_number: Optional[str],
        act_fuzzy_phrase: Optional[str],
        extracted_sections_norm: Sequence[str],
        needs_table: bool,
        needs_form: bool,
        dense_limit: int,
        bm25_merge_limit: int,
    ) -> List[ScoredHit]:
        if chunk_type == "child":
            dense_rows = self.dense_search_children(
                db,
                query_embedding,
                act_name,
                category,
                section_number,
                dense_limit,
                act_fuzzy_phrase,
            )
            pool_ids, pool_docs, pool_metas = self.fetch_child_bm25_pool(
                db, act_name, category, section_number, act_fuzzy_phrase
            )
        elif chunk_type == "table":
            dense_rows = self.dense_search_tables(
                db,
                query_embedding,
                act_name,
                category,
                section_number,
                dense_limit,
                act_fuzzy_phrase,
            )
            pool_ids, pool_docs, pool_metas = self.fetch_table_bm25_pool(
                db, act_name, category, section_number, act_fuzzy_phrase
            )
        else:
            dense_rows = self.dense_search_forms(
                db,
                query_embedding,
                act_name,
                category,
                section_number,
                dense_limit,
                act_fuzzy_phrase,
            )
            pool_ids, pool_docs, pool_metas = self.fetch_form_bm25_pool(
                db, act_name, category, section_number, act_fuzzy_phrase
            )

        dense_map = {oid: sim for oid, sim, _ in dense_rows}
        dense_norm = min_max_normalize(dense_map)

        bm25_raw = bm25_candidates_from_pool(pool_docs, pool_ids, query_tokens)
        bm25_norm = min_max_normalize(bm25_raw)

        meta_by_id: Dict[str, Dict[str, Any]] = {}
        for oid, _, row in dense_rows:
            meta_by_id[oid] = row
        for i, oid in enumerate(pool_ids):
            if oid not in meta_by_id:
                meta_by_id[oid] = pool_metas[i]

        candidate_ids = merge_dense_bm25_candidates(dense_map, bm25_raw, dense_limit, bm25_merge_limit)
        qtok_set = set(query_tokens)

        hits: List[ScoredHit] = []
        for oid in candidate_ids:
            row = meta_by_id.get(oid)
            if not row:
                continue
            dn = dense_norm.get(oid, 0.0)
            bn = bm25_norm.get(oid, 0.0)
            if chunk_type == "child" and _substantive_rights_query(query_norm):
                if _procedural_noise_title(safe_str(row.get("section_title"))):
                    pen = float(os.environ.get("LAWGIC_BM25_PROCEDURAL_TITLE_PENALTY", "0.14"))
                    bn = max(0.0, bn - pen)
            mb = metadata_boost_score(
                query_norm,
                qtok_set,
                act_name,
                category,
                section_number,
                extracted_sections_norm,
                row.get("act_name"),
                row.get("category"),
                row.get("section_number"),
                row.get("section_title"),
                act_substring_boost=(None if act_name else act_fuzzy_phrase),
            )
            if extracted_sections_norm and safe_str(row.get("section_number")):
                for es in extracted_sections_norm:
                    if section_references_equivalent(es, row.get("section_number")):
                        mb = min(1.0, mb + 0.25)
                        break
            sb = structure_boost_value(chunk_type, needs_table, needs_form)
            fs = final_hybrid_score(dn, bn, mb, sb)
            pid = row.get("parent_id")
            if chunk_type == "child":
                ob_id = str(row.get("child_id"))
                txt = row.get("text") or ""
                summ = None
            elif chunk_type == "table":
                ob_id = str(row.get("table_uid"))
                txt = row.get("text") or ""
                summ = row.get("summary")
            else:
                ob_id = str(row.get("form_uid"))
                txt = row.get("text") or ""
                summ = row.get("summary")
            hits.append(
                ScoredHit(
                    chunk_type=chunk_type,
                    object_id=ob_id,
                    parent_id=str(pid) if pid else None,
                    text=txt,
                    summary=summ,
                    act_name=row.get("act_name"),
                    category=row.get("category"),
                    section_number=row.get("section_number"),
                    section_title=row.get("section_title"),
                    page_numbers=row.get("page_numbers"),
                    dense_norm=dn,
                    bm25_norm=bn,
                    metadata_boost=mb,
                    structure_boost=sb,
                    final_score=fs,
                    row_extra=dict(row),
                )
            )
        hits.sort(key=lambda x: -x.final_score)
        return hits

    def expand_parents(
        self,
        db: Session,
        parent_ids: Set[str],
    ) -> Dict[str, Dict[str, Any]]:
        if not parent_ids:
            return {}
        p = self.law_parent_metadata
        stmt = (
            select(
                p.c.parent_id,
                p.c.text,
                p.c.act_name,
                p.c.category,
                p.c.section_number,
                p.c.section_title,
                p.c.page_numbers,
            )
            .where(p.c.parent_id.in_(list(parent_ids)))
        )
        rows = db.execute(stmt).all()
        return {
            str(r.parent_id): {
                "text": r.text or "",
                "act_name": r.act_name,
                "category": r.category,
                "section_number": r.section_number,
                "section_title": r.section_title,
                "page_numbers": list(r.page_numbers) if r.page_numbers is not None else None,
            }
            for r in rows
        }

    def neighboring_children_batch(
        self,
        db: Session,
        pairs: List[Tuple[str, str]],
    ) -> Dict[Tuple[str, str], List[Dict[str, Any]]]:
        if not pairs:
            return {}
        parents = list({p for p, _ in pairs})
        by_parent: Dict[str, List[Tuple[Any, ...]]] = defaultdict(list)
        m = self.law_child_metadata
        stmt = (
            select(
                m.c.parent_id,
                m.c.child_id,
                m.c.text,
                m.c.section_number,
                m.c.section_title,
                m.c.start_pos_raw,
            )
            .where(m.c.parent_id.in_(parents))
            .order_by(m.c.parent_id.asc(), m.c.start_pos_raw.asc().nulls_last(), m.c.child_id.asc())
        )
        for r in db.execute(stmt).all():
            by_parent[str(r.parent_id)].append(
                (str(r.child_id), r.start_pos_raw, r.text, r.section_number, r.section_title)
            )
        out: Dict[Tuple[str, str], List[Dict[str, Any]]] = {}
        for pid, cid in pairs:
            seq = by_parent.get(pid, [])
            idx = next((i for i, t in enumerate(seq) if t[0] == cid), -1)
            if idx < 0:
                out[(pid, cid)] = []
                continue
            lo = max(0, idx - 1)
            hi = min(len(seq), idx + 2)
            nbrs: List[Dict[str, Any]] = []
            for i in range(lo, hi):
                if i == idx:
                    continue
                t = seq[i]
                nbrs.append(
                    {
                        "child_id": t[0],
                        "text": t[2] or "",
                        "section_number": t[3],
                        "section_title": t[4],
                        "start_pos_raw": t[1],
                    }
                )
            out[(pid, cid)] = nbrs
        return out

    def retrieve(
        self,
        db: Session,
        query: str,
        query_embedding: Optional[Sequence[float]] = None,
        act_name: Optional[str] = None,
        category: Optional[str] = None,
        section_number: Optional[str] = None,
        top_k: int = 20,
        search_tables: Optional[bool] = None,
        search_forms: Optional[bool] = None,
    ) -> RetrievalResponse:
        qn = normalize_query(query)
        q_tokens = tokenize_for_bm25(qn)
        extracted_sections_raw = extract_section_numbers_from_query(qn)
        extracted_sections_norm = extract_normalized_sections_from_query(qn)
        eff_section = section_number
        if not eff_section and extracted_sections_raw:
            eff_section = extracted_sections_raw[0]

        ht = resolve_needs_table(qn, search_tables)
        hf = resolve_needs_form(qn, search_forms)

        inferred_category = infer_category_from_query(qn) if not category else None
        inferred_act_fuzzy = infer_act_fuzzy_phrase_from_query(qn) if not act_name else None
        eff_category = category or inferred_category
        eff_act_fuzzy = inferred_act_fuzzy

        vec = self._require_embedding(qn, query_embedding)

        child_hits = self.hybrid_chunk_type(
            db,
            qn,
            q_tokens,
            vec,
            "child",
            act_name,
            eff_category,
            eff_section,
            eff_act_fuzzy,
            extracted_sections_norm,
            ht,
            hf,
            self.dense_candidate_limit_child,
            self.bm25_merge_top_child,
        )

        child_sorted = sorted(child_hits, key=lambda x: -x.final_score)
        top_child_score = child_sorted[0].final_score if child_sorted else 0.0
        weak_expand_pools = top_child_score < self.fallback_expand_top_score_threshold

        run_table = ht or (weak_expand_pools and search_tables is not False)
        run_form = hf or (weak_expand_pools and search_forms is not False)
        fallback_used = weak_expand_pools and ((run_table and not ht) or (run_form and not hf))

        all_hits: List[ScoredHit] = list(child_hits)

        if run_table:
            all_hits.extend(
                self.hybrid_chunk_type(
                    db,
                    qn,
                    q_tokens,
                    vec,
                    "table",
                    act_name,
                    eff_category,
                    eff_section,
                    eff_act_fuzzy,
                    extracted_sections_norm,
                    True,
                    hf,
                    self.dense_candidate_limit_table,
                    self.bm25_merge_top_table,
                )
            )

        if run_form:
            all_hits.extend(
                self.hybrid_chunk_type(
                    db,
                    qn,
                    q_tokens,
                    vec,
                    "form",
                    act_name,
                    eff_category,
                    eff_section,
                    eff_act_fuzzy,
                    extracted_sections_norm,
                    ht,
                    True,
                    self.dense_candidate_limit_form,
                    self.bm25_merge_top_form,
                )
            )

        seen: Set[Tuple[str, str]] = set()
        deduped: List[ScoredHit] = []
        def _rank_key(h: ScoredHit) -> float:
            bias = 0.018 if h.chunk_type == "child" else 0.0
            return -(h.final_score + bias)

        for h in sorted(all_hits, key=_rank_key):
            key = (h.chunk_type, h.object_id)
            if key in seen:
                continue
            seen.add(key)
            deduped.append(h)

        max_per_sec = max(2, int(os.environ.get("LAWGIC_MAX_CHUNKS_PER_PARENT_SECTION", "4")))
        diversified = diversify_results(deduped, max_per_section=max_per_sec, score_ratio_keep=0.88)
        if inferred_category is not None or inferred_act_fuzzy is not None:
            diversified = post_filter_by_inferred_metadata(
                diversified, inferred_category, inferred_act_fuzzy
            )
        final_list = diversified[: max(top_k, 1)]

        parent_ids: Set[str] = set()
        for h in final_list:
            if h.parent_id:
                parent_ids.add(h.parent_id)
        parent_map = self.expand_parents(db, parent_ids)

        nbr_pairs = [(h.parent_id, h.object_id) for h in final_list if h.chunk_type == "child" and h.parent_id]
        nbr_map = self.neighboring_children_batch(db, nbr_pairs)

        results: List[RetrievalResultItem] = []
        for h in final_list:
            nbr: Optional[List[Dict[str, Any]]] = None
            if h.chunk_type == "child" and h.parent_id:
                nbr = nbr_map.get((h.parent_id, h.object_id))
            pinfo = parent_map.get(h.parent_id) if h.parent_id else None
            results.append(
                RetrievalResultItem(
                    chunk_type=h.chunk_type,
                    object_id=h.object_id,
                    parent_id=h.parent_id,
                    text=h.text,
                    summary=h.summary,
                    act_name=h.act_name,
                    category=h.category,
                    section_number=h.section_number,
                    section_title=h.section_title,
                    page_numbers=list(h.page_numbers) if h.page_numbers is not None else None,
                    score=h.final_score,
                    dense_norm=h.dense_norm,
                    bm25_norm=h.bm25_norm,
                    metadata_boost=h.metadata_boost,
                    parent_text=(pinfo or {}).get("text") if pinfo else None,
                    parent_act_name=(pinfo or {}).get("act_name") if pinfo else None,
                    parent_category=(pinfo or {}).get("category") if pinfo else None,
                    parent_section_number=(pinfo or {}).get("section_number") if pinfo else None,
                    parent_section_title=(pinfo or {}).get("section_title") if pinfo else None,
                    parent_page_numbers=(pinfo or {}).get("page_numbers") if pinfo else None,
                    neighboring_children=nbr,
                )
            )

        conf_score, conf_label = confidence_from_results(
            final_list,
            act_name,
            eff_category,
            eff_section,
            extracted_sections_norm,
            act_fuzzy_phrase=eff_act_fuzzy,
        )

        return RetrievalResponse(
            query=query,
            applied_filters={
                "act_name": act_name,
                "category": eff_category,
                "section_number": eff_section,
                "act_fuzzy_phrase_applied": eff_act_fuzzy,
                "category_inferred": inferred_category is not None,
                "act_phrase_inferred": inferred_act_fuzzy is not None,
                "extracted_section_numbers": list(extracted_sections_raw),
                "extracted_section_numbers_normalized": list(extracted_sections_norm),
            },
            needs_table=run_table,
            needs_form=run_form,
            fallback_used=fallback_used,
            confidence_score=conf_score,
            confidence_label=conf_label,
            results=results,
        )
