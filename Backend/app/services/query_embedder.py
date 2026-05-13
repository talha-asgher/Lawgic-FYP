from __future__ import annotations

import os
from typing import Any, List, Optional, Tuple

_model: Any = None
_model_cache_key: Optional[Tuple[str, str, bool]] = None


def get_bge_query_model_id() -> str:
    return os.environ.get("BGE_QUERY_MODEL", "BAAI/bge-m3")


def _query_device() -> str:
    explicit = (os.environ.get("BGE_QUERY_DEVICE") or "").strip().lower()
    if explicit in ("cuda", "cpu"):
        return explicit
    import torch

    return "cuda" if torch.cuda.is_available() else "cpu"


def embed_query_text(text: str) -> List[float]:
    """
    Dense query embedding aligned with RAG/scripts/embed_bge_m3_child_chunks.py (BGEM3FlagModel.encode).
    """
    global _model, _model_cache_key
    mid = get_bge_query_model_id()
    device = _query_device()
    use_fp16 = device == "cuda"
    key = (mid, device, use_fp16)
    if _model is None or _model_cache_key != key:
        from FlagEmbedding import BGEM3FlagModel

        _model = BGEM3FlagModel(mid, use_fp16=use_fp16, device=device)
        _model_cache_key = key

    outputs = _model.encode(
        [text],
        batch_size=1,
        max_length=2048,
        return_dense=True,
        return_sparse=False,
        return_colbert_vecs=False,
    )
    vec = outputs["dense_vecs"][0]
    if hasattr(vec, "tolist"):
        return vec.tolist()
    return list(vec)
