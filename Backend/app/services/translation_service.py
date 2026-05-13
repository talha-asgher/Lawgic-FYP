"""English ⟷ Urdu via AI4Bharat IndicTrans2 on GPU, with Helsinki-NLP OPUS-MT Marian
models on CPU (and as GPU fallback when IndicTrans2 fails).

Gated HF models: log in (`huggingface-cli login` or set `HF_TOKEN`) and accept the
model license on Hugging Face before first download (ai4bharat/indictrans2-*-1B).

Legacy HTTP translators were removed; see `translation_service_legacy_google_azure.py`.
"""

from __future__ import annotations

import logging
import os
import threading
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

MODEL_EN_INDIC = "ai4bharat/indictrans2-en-indic-1B"
MODEL_INDIC_EN = "ai4bharat/indictrans2-indic-en-1B"
MODEL_OPUS_EN_UR = os.environ.get("LAWGIC_OPUS_MT_EN_UR", "Helsinki-NLP/opus-mt-en-ur")
MODEL_OPUS_UR_EN = os.environ.get("LAWGIC_OPUS_MT_UR_EN", "Helsinki-NLP/opus-mt-ur-en")
LANG_EN = "eng_Latn"
LANG_UR = "urd_Arab"

_MAX_SEG_LEN = int(os.environ.get("LAWGIC_TRANSLATE_MAX_SEGMENT_CHARS", "4500"))
_OPUS_MAX_SEG_LEN = int(os.environ.get("LAWGIC_OPUS_MAX_SEGMENT_CHARS", "450"))
_MAX_NEW_TOKENS = int(os.environ.get("LAWGIC_INDICTRANS_MAX_NEW_TOKENS", "256"))
_OPUS_MAX_NEW_TOKENS = int(os.environ.get("LAWGIC_OPUS_MAX_NEW_TOKENS", "256"))
_NUM_BEAMS = int(os.environ.get("LAWGIC_INDICTRANS_NUM_BEAMS", "5"))
_OPUS_NUM_BEAMS = int(os.environ.get("LAWGIC_OPUS_NUM_BEAMS", "4"))

_load_lock = threading.Lock()
_infer_lock = threading.Lock()
_processor = None
_en_indic: Optional[Tuple[Any, Any]] = None
_indic_en: Optional[Tuple[Any, Any]] = None
_opus_en_ur: Optional[Tuple[Any, Any]] = None
_opus_ur_en: Optional[Tuple[Any, Any]] = None


def urdu_arabic_script_ratio(text: str, sample_chars: int = 8000) -> float:
    if not text or not text.strip():
        return 0.0
    s = text[:sample_chars]
    letters = sum(1 for c in s if not c.isspace() and c.isprintable() and ord(c) > 127)
    if letters == 0:
        return 0.0
    arabic = sum(
        1 for c in s if "\u0600" <= c <= "\u06FF" or "\u0750" <= c <= "\u077F" or "\u08A0" <= c <= "\u08FF"
    )
    return arabic / max(letters, 1)


def looks_like_urdu_script_query(text: str) -> bool:
    if not text or not text.strip():
        return False
    ratio = urdu_arabic_script_ratio(text, sample_chars=min(4000, len(text)))
    thr = float(os.environ.get("LAWGIC_URDU_SCRIPT_RATIO_THRESHOLD", "0.12"))
    return ratio >= thr


def _split_segments(text: str, max_len: Optional[int] = None) -> List[str]:
    text = text.strip()
    if not text:
        return []
    limit = max_len if max_len is not None else _MAX_SEG_LEN
    if len(text) <= limit:
        return [text]
    parts: List[str] = []
    start = 0
    n = len(text)
    while start < n:
        end = min(start + limit, n)
        if end < n:
            cut = text.rfind("\n\n", start, end)
            if cut == -1 or cut < start + limit // 2:
                cut = text.rfind(" ", start, end)
            if cut > start:
                end = cut + 1
        chunk = text[start:end].strip()
        if chunk:
            parts.append(chunk)
        start = end
    return parts


def _device() -> str:
    import torch

    return "cuda" if torch.cuda.is_available() else "cpu"


def _hf_token() -> Optional[str]:
    t = (os.environ.get("HF_TOKEN") or os.environ.get("HUGGING_FACE_HUB_TOKEN") or "").strip()
    return t or None


def _get_processor():
    global _processor
    if _processor is not None:
        return _processor
    with _load_lock:
        if _processor is None:
            from IndicTransToolkit.processor import IndicProcessor

            _processor = IndicProcessor(inference=True)
    return _processor


def _load_pair(model_id: str) -> Tuple[Any, Any]:
    from transformers import AutoModelForSeq2SeqLM, AutoTokenizer

    import torch

    global _en_indic, _indic_en
    tok = AutoTokenizer.from_pretrained(
        model_id,
        trust_remote_code=True,
        token=_hf_token(),
    )
    device = _device()
    kwargs: Dict[str, Any] = {
        "trust_remote_code": True,
        "token": _hf_token(),
    }
    if device == "cuda":
        kwargs["torch_dtype"] = torch.float16
    else:
        kwargs["torch_dtype"] = torch.float32
    model = AutoModelForSeq2SeqLM.from_pretrained(model_id, **kwargs).to(device)
    model.eval()
    return tok, model


def _get_en_indic() -> Tuple[Any, Any]:
    global _en_indic
    if _en_indic is not None:
        return _en_indic
    with _load_lock:
        if _en_indic is None:
            _en_indic = _load_pair(MODEL_EN_INDIC)
    return _en_indic


def _get_indic_en() -> Tuple[Any, Any]:
    global _indic_en
    if _indic_en is not None:
        return _indic_en
    with _load_lock:
        if _indic_en is None:
            _indic_en = _load_pair(MODEL_INDIC_EN)
    return _indic_en


def _translate_batch(
    sentences: List[str],
    *,
    direction: str,
) -> List[str]:
    if not sentences:
        return []
    ip = _get_processor()
    if direction == "en2ur":
        tok, model = _get_en_indic()
        src, tgt = LANG_EN, LANG_UR
    elif direction == "ur2en":
        tok, model = _get_indic_en()
        src, tgt = LANG_UR, LANG_EN
    else:
        raise ValueError(f"unknown direction {direction!r}")

    import torch

    device = _device()
    batch = ip.preprocess_batch(sentences, src_lang=src, tgt_lang=tgt)
    with _infer_lock:
        inputs = tok(
            batch,
            truncation=True,
            padding="longest",
            return_tensors="pt",
            return_attention_mask=True,
        ).to(device)
        with torch.no_grad():
            gen = model.generate(
                **inputs,
                use_cache=True,
                min_length=0,
                max_new_tokens=_MAX_NEW_TOKENS,
                num_beams=_NUM_BEAMS,
                num_return_sequences=1,
            )
        decoded = tok.batch_decode(
            gen,
            skip_special_tokens=True,
            clean_up_tokenization_spaces=True,
        )
    return ip.postprocess_batch(decoded, lang=tgt)


def _load_opus_pair(model_id: str) -> Tuple[Any, Any]:
    from transformers import MarianMTModel, MarianTokenizer

    tok = MarianTokenizer.from_pretrained(model_id, token=_hf_token())
    device = _device()
    model = MarianMTModel.from_pretrained(model_id, token=_hf_token()).to(device)
    model.eval()
    return tok, model


def _get_opus_en_ur() -> Tuple[Any, Any]:
    global _opus_en_ur
    if _opus_en_ur is not None:
        return _opus_en_ur
    with _load_lock:
        if _opus_en_ur is None:
            _opus_en_ur = _load_opus_pair(MODEL_OPUS_EN_UR)
    return _opus_en_ur


def _get_opus_ur_en() -> Tuple[Any, Any]:
    global _opus_ur_en
    if _opus_ur_en is not None:
        return _opus_ur_en
    with _load_lock:
        if _opus_ur_en is None:
            _opus_ur_en = _load_opus_pair(MODEL_OPUS_UR_EN)
    return _opus_ur_en


def _translate_opus_batch(
    sentences: List[str],
    *,
    direction: str,
) -> List[str]:
    if not sentences:
        return []
    if direction == "en2ur":
        tok, model = _get_opus_en_ur()
    elif direction == "ur2en":
        tok, model = _get_opus_ur_en()
    else:
        raise ValueError(f"unknown direction {direction!r}")

    import torch

    device = _device()
    with _infer_lock:
        inputs = tok(
            sentences,
            return_tensors="pt",
            padding=True,
            truncation=True,
        ).to(device)
        with torch.no_grad():
            gen = model.generate(
                **inputs,
                max_new_tokens=_OPUS_MAX_NEW_TOKENS,
                num_beams=_OPUS_NUM_BEAMS,
                num_return_sequences=1,
            )
        return tok.batch_decode(gen, skip_special_tokens=True)


def _translate_opus_segments(text: str, direction: str) -> str:
    out: List[str] = []
    for seg in _split_segments(text, _OPUS_MAX_SEG_LEN):
        out.extend(_translate_opus_batch([seg], direction=direction))
    return "\n\n".join(part.strip() for part in out if part and part.strip()).strip()


def _translate_by_segments(text: str, direction: str) -> str:
    text = (text or "").strip()
    if not text:
        return text

    if _device() == "cuda":
        try:
            out: List[str] = []
            for seg in _split_segments(text):
                out.extend(_translate_batch([seg], direction=direction))
            joined = "\n\n".join(part.strip() for part in out if part and part.strip()).strip()
            if joined:
                return joined
        except Exception as e:
            logger.warning("IndicTrans2 %s failed: %s", direction, e)

    try:
        joined = _translate_opus_segments(text, direction)
        if joined:
            return joined
    except Exception as e:
        logger.warning("OPUS-MT %s failed: %s", direction, e)

    return text


def translate_en_to_ur(text: str) -> str:
    return _translate_by_segments(text, "en2ur")


def translate_ur_to_en(text: str) -> str:
    return _translate_by_segments(text, "ur2en")


def translate_text_lang(text: str, src_lang: str, tgt_lang: str) -> str:
    s = (src_lang or "").strip().lower().split("-")[0]
    t = (tgt_lang or "").strip().lower().split("-")[0]
    if s == t:
        return (text or "").strip()
    if s == "en" and t == "ur":
        return translate_en_to_ur(text)
    if s == "ur" and t == "en":
        return translate_ur_to_en(text)
    logger.warning("translate_text_lang: unsupported pair %s→%s", s, t)
    return (text or "").strip()


def translate_text(
    text: str,
    *,
    source: Optional[str],
    target: str,
    allow_empty_provider: bool = True,
) -> str:
    _ = allow_empty_provider
    text = (text or "").strip()
    if not text:
        return text
    tgt = target.lower().replace("_", "-")
    tgt_lang = tgt.split("-")[0] if tgt else ""
    src_lang = ""
    if source:
        src_lang = source.strip().lower().replace("_", "-").split("-")[0]
    if not tgt_lang or tgt_lang in ("und", "auto"):
        return text
    if src_lang and src_lang == tgt_lang:
        return text

    if tgt_lang == "en":
        if src_lang == "ur" or (not src_lang and looks_like_urdu_script_query(text)):
            try:
                return translate_ur_to_en(text)
            except Exception as e:
                logger.warning("translate_text ur→en: %s", e)
                return text
        return text
    if tgt_lang == "ur":
        if src_lang == "en" or not src_lang:
            try:
                return translate_en_to_ur(text)
            except Exception as e:
                logger.warning("translate_text en→ur: %s", e)
                return text
        return text
    return text


def translate_doc_analysis_payload(
    data: Dict[str, Any],
    *,
    source_lang: str,
    target_lang: str,
) -> Dict[str, Any]:
    from app.services.language_output import normalize_output_language

    s = normalize_output_language(source_lang)
    t = normalize_output_language(target_lang)
    out = dict(data)
    if s == t:
        return out
    src_api = "en" if s == "en" else "ur"
    tgt_api = "en" if t == "en" else "ur"
    if src_api == tgt_api:
        return out
    for key in ("document_type", "summary", "disclaimer"):
        raw = str(out.get(key) or "")
        if not raw.strip():
            continue
        try:
            out[key] = translate_text(raw, source=src_api, target=tgt_api)
        except Exception as e:
            logger.warning("translate_doc_analysis_payload field %s: %s", key, e)
    return out


def translate_rag_query_to_english(
    raw_query: str,
    *,
    query_language_hint: str = "auto",
) -> tuple[str, Dict[str, Any]]:
    raw_query = (raw_query or "").strip()
    meta: Dict[str, Any] = {
        "original_query": raw_query,
        "retrieval_query_translated": False,
        "query_language_requested": query_language_hint,
    }
    if not raw_query:
        return raw_query, meta

    hint = (query_language_hint or "auto").strip().lower()

    want_translate = False
    use_source: Optional[str] = None

    if hint == "en":
        return raw_query, meta
    if hint == "ur":
        want_translate = True
        use_source = "ur"
    elif hint == "auto":
        if looks_like_urdu_script_query(raw_query):
            want_translate = True
            use_source = "ur"

    if not want_translate:
        meta["detected_query_style"] = (
            "urdu_script" if looks_like_urdu_script_query(raw_query) else "latin_or_mixed"
        )
        return raw_query, meta

    try:
        translated = translate_text(raw_query, source=use_source, target="en")
    except Exception as e:
        logger.warning("translate_rag_query_to_english: %s", e)
        return raw_query, meta
    if translated and translated != raw_query:
        meta["retrieval_query_translated"] = True
        meta["retrieval_query_english"] = translated
        return translated.strip(), meta
    return raw_query, meta


def prepare_document_body_for_english_pipeline(
    full_text: str,
    *,
    force_translate: bool = False,
) -> tuple[str, Dict[str, Any]]:
    full_text = (full_text or "").strip()
    meta: Dict[str, Any] = {"document_body_translated": False}
    if not full_text:
        return full_text, meta

    ratio = urdu_arabic_script_ratio(full_text, sample_chars=min(16_000, len(full_text)))
    meta["urdu_script_ratio_sample"] = round(ratio, 4)

    thr = float(os.environ.get("LAWGIC_DOC_TRANSLATE_RATIO_THRESHOLD", "0.22"))
    if not force_translate and ratio < thr:
        return full_text, meta

    max_chars = int(os.environ.get("LAWGIC_DOC_TRANSLATE_MAX_INPUT_CHARS", "120000"))
    to_translate = full_text[:max_chars] if len(full_text) > max_chars else full_text

    try:
        translated = translate_text(to_translate, source="ur", target="en")
    except Exception as e:
        logger.warning("prepare_document_body_for_english_pipeline: %s", e)
        translated = to_translate
    meta["document_body_translated"] = translated != to_translate.strip()
    if len(full_text) > max_chars:
        translated += "\n\n[Additional pages omitted from translation; raw text continues in original language.]"
    return translated if translated else full_text, meta
