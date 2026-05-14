from __future__ import annotations

import logging
import os
from typing import List, Optional, TYPE_CHECKING, Tuple

if TYPE_CHECKING:
    from app.services.retrieval_service import RetrievalResultItem

logger = logging.getLogger(__name__)

_cross_encoder = None
_cross_encoder_key: Optional[Tuple[str, str]] = None


def is_reranker_enabled() -> bool:
    return os.environ.get("LAWGIC_RERANKER_ENABLED", "true").lower() in ("1", "true", "yes")


def get_reranker_model_id() -> str:
    return os.environ.get("LAWGIC_RERANKER_MODEL", "BAAI/bge-reranker-v2-m3")


def max_rerank_candidates() -> int:
    return max(1, int(os.environ.get("LAWGIC_MAX_RERANK_CANDIDATES", "25")))


def _device() -> str:
    d = (os.environ.get("LAWGIC_RERANKER_DEVICE") or "").strip().lower()
    if d in ("cuda", "cpu"):
        return d
    import torch

    return "cuda" if torch.cuda.is_available() else "cpu"


def _get_cross_encoder():
    global _cross_encoder, _cross_encoder_key
    mid = get_reranker_model_id()
    device = _device()
    key = (mid, device)
    if _cross_encoder is None or _cross_encoder_key != key:
        from sentence_transformers import CrossEncoder

        _cross_encoder = CrossEncoder(mid, device=device)
        _cross_encoder_key = key
    return _cross_encoder


def warm_reranker_if_enabled() -> None:
    """Load cross-encoder at startup so the first /rag/ask does not hold a DB session during multi-GB download."""
    if not is_reranker_enabled():
        return
    try:
        logger.info(
            "Lawgic reranker: loading %s (first run may download ~2GB; see LAWGIC_RERANKER_ENABLED to skip)",
            get_reranker_model_id(),
        )
        _get_cross_encoder()
        logger.info("Lawgic reranker: model loaded.")
    except Exception:
        logger.exception(
            "Lawgic reranker warmup failed; disable with LAWGIC_RERANKER_ENABLED=false or fix network/cache"
        )


def _rerank_passage_text(c: "RetrievalResultItem", max_doc: int) -> str:
    """Structured document for cross-encoder: citation line + body (not body alone)."""
    act = (c.act_name or "").strip()
    sec = (c.section_number or "").strip()
    title = (c.section_title or "").strip()
    head_parts: List[str] = []
    if act:
        head_parts.append(f"Act: {act}")
    if sec or title:
        if sec and sec.lower() != "-":
            head_parts.append(f"Section: {sec}" + (f" — {title}" if title else ""))
        elif title:
            head_parts.append(f"Section title: {title}")
    header = "\n".join(head_parts)
    body = (c.text or "").strip() or (c.summary or "").strip()
    doc = f"{header}\n\n{body}" if header else body
    if len(doc) > max_doc:
        doc = doc[:max_doc]
    return doc


def rerank_candidates(query: str, candidates: List[RetrievalResultItem]) -> List[RetrievalResultItem]:
    """
    Second-stage cross-encoder scores; sorts by rerank_score descending.
    """
    from app.services.retrieval_service import RetrievalResultItem as RRI

    if not candidates:
        return candidates
    if not is_reranker_enabled():
        return list(candidates)

    model = _get_cross_encoder()
    max_doc = int(os.environ.get("LAWGIC_RERANK_MAX_DOC_CHARS", "8000"))
    batch_size = max(1, int(os.environ.get("LAWGIC_RERANKER_BATCH_SIZE", "8")))

    texts: List[str] = [_rerank_passage_text(c, max_doc) for c in candidates]

    pairs = [[query, t] for t in texts]
    scores = model.predict(pairs, batch_size=batch_size, show_progress_bar=False)

    out: List[RRI] = []
    for c, s in zip(candidates, scores):
        out.append(c.model_copy(update={"rerank_score": float(s)}))
    out.sort(key=lambda x: -float(x.rerank_score or 0.0))

    if os.environ.get("LAWGIC_RERANKER_DEBUG", "").lower() in ("1", "true", "yes"):
        for i, c in enumerate(out[:10]):
            logger.info(
                "rerank debug [%s] section_number=%s section_title=%s original_score=%s rerank_score=%s",
                i + 1,
                c.section_number,
                (c.section_title or "")[:120],
                c.score,
                c.rerank_score,
            )
    return out
