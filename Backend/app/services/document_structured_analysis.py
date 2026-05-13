"""Chunked consolidation + structured JSON legal analysis via Ollama."""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from app.services.ollama_service import OllamaServiceError, chat_completion
from app.services.language_output import (
    DOC_DISCLAIMER_BY_LANG,
    OUTPUT_LANG_EN,
    OUTPUT_LANG_UR,
    normalize_output_language,
    structured_schema_hint_footer,
    structured_system_prompt,
)
from app.services.translation_service import translate_text

logger = logging.getLogger(__name__)

# Keep each LLM input bounded; long docs are never sent as one block to the final model.
CHUNK_INPUT_CHARS = 6_000
CHUNK_OVERLAP = 300
MAX_CONSOLIDATED_CHARS = 18_000

CHUNK_EXTRACT_SYS = (
    "You extract legally relevant information from a document excerpt. "
    "Be factual; quote parties, dates, amounts, clause titles, obligations if present. "
    "Output concise bullet notes (no preamble). Pakistan legal context may apply where relevant."
)

CONSOLIDATE_SYS = (
    "You merge fragment notes from one document into one factual brief for downstream summarization. "
    "Remove duplicates; preserve legally important detail (parties, dates, clauses, amounts, obligations). "
    "Use structured prose and bullets as needed. For long sources, the brief may run up to about 3000 words; "
    "do not over-shorten—keep information needed to explain the full document."
)


def _chunk_text(text: str) -> list[str]:
    text = text.strip()
    if len(text) <= CHUNK_INPUT_CHARS:
        return [text]
    chunks: list[str] = []
    start = 0
    n = len(text)
    while start < n:
        end = min(start + CHUNK_INPUT_CHARS, n)
        chunks.append(text[start:end])
        if end >= n:
            break
        start = max(0, end - CHUNK_OVERLAP)
    return chunks


def _summarize(messages: list[dict[str, str]], *, json_format: bool = False) -> str:
    return chat_completion(messages, temperature=0.15, top_p=0.9, json_format=json_format)


def extract_notes_for_chunk(chunk: str, index: int, total: int) -> str:
    user = (
        f"This is excerpt {index + 1} of {total} from the same document.\n\n"
        f"{chunk}\n\nList concise extraction notes as bullets."
    )
    messages = [
        {"role": "system", "content": CHUNK_EXTRACT_SYS},
        {"role": "user", "content": user},
    ]
    return _summarize(messages)


def consolidate_chunk_notes(notes: list[str]) -> str:
    combined = "\n\n---\n\n".join(f"Part {i + 1}:\n{n}" for i, n in enumerate(notes))
    if len(combined) <= MAX_CONSOLIDATED_CHARS:
        messages = [
            {"role": "system", "content": CONSOLIDATE_SYS},
            {
                "role": "user",
                "content": f"Merge these notes into one factual brief for downstream analysis:\n\n{combined}",
            },
        ]
        return _summarize(messages)

    # Brief too long: recursive split (rare)
    mid = len(combined) // 2
    half_a = consolidate_chunk_notes([combined[:mid]])
    half_b = consolidate_chunk_notes([combined[mid:]])
    messages = [
        {"role": "system", "content": CONSOLIDATE_SYS},
        {
            "role": "user",
            "content": f"Merge these two partial briefs into one:\n\nA:\n{half_a}\n\nB:\n{half_b}",
        },
    ]
    return _summarize(messages)


def build_consolidated_brief(full_text: str) -> str:
    full_text = (full_text or "").strip()
    if not full_text:
        raise OllamaServiceError("No text to analyze.")
    chunks = _chunk_text(full_text)
    if len(chunks) == 1:
        notes = [extract_notes_for_chunk(chunks[0], 0, 1)]
    else:
        notes = []
        for i, ch in enumerate(chunks):
            try:
                notes.append(extract_notes_for_chunk(ch, i, len(chunks)))
            except OllamaServiceError:
                logger.warning("Chunk %s extract failed", i)
                notes.append(f"(Excerpt {i + 1} failed.)")
    return consolidate_chunk_notes(notes)


def _strip_json_fence(raw: str) -> str:
    s = raw.strip()
    m = re.match(r"^```(?:json)?\s*([\s\S]*?)\s*```$", s)
    if m:
        return m.group(1).strip()
    return s


def normalize_payload(data: dict[str, Any], default_disclaimer: str) -> dict[str, Any]:
    """Enforce three-field shape and default disclaimer."""
    disclaimer = str(data.get("disclaimer") or "").strip() or default_disclaimer
    return {
        "document_type": str(data.get("document_type") or "").strip() or "Unknown",
        "summary": str(data.get("summary") or "").strip(),
        "disclaimer": disclaimer,
    }


def generate_structured_analysis(
    consolidated_brief: str, output_language: str = "en"
) -> dict[str, Any]:
    lang = normalize_output_language(output_language)
    brief = consolidated_brief.strip()
    if len(brief) > MAX_CONSOLIDATED_CHARS:
        brief = brief[:MAX_CONSOLIDATED_CHARS] + "\n\n[Content truncated for analysis.]"

    # Always generate structured fields in English first; translate to Urdu when output_language is ur
    # (works for English-source and Urdu-source briefs after upstream normalization).
    sys_prompt = structured_system_prompt(OUTPUT_LANG_EN)
    schema_hint = """
Return exactly this JSON shape (no markdown fences):
{
  "document_type": "",
  "summary": "",
  "disclaimer": ""
}
""" + structured_schema_hint_footer(OUTPUT_LANG_EN)
    expected_disc = DOC_DISCLAIMER_BY_LANG[OUTPUT_LANG_EN]

    messages = [
        {"role": "system", "content": sys_prompt},
        {
            "role": "user",
            "content": f"Document brief:\n\n{brief}\n\n{schema_hint}",
        },
    ]
    raw = _summarize(messages, json_format=True)
    try:
        data = json.loads(_strip_json_fence(raw))
    except json.JSONDecodeError as e:
        logger.warning("JSON parse failed, retrying without strict format: %s", e)
        messages_retry = [
            {"role": "system", "content": sys_prompt},
            {
                "role": "user",
                "content": f"Document brief:\n\n{brief}\n\n{schema_hint}\nRespond with raw JSON only.",
            },
        ]
        raw2 = _summarize(messages_retry, json_format=False)
        data = json.loads(_strip_json_fence(raw2))

    if not isinstance(data, dict):
        raise OllamaServiceError("Model returned non-object JSON.")
    payload = normalize_payload(data, expected_disc)
    if lang == OUTPUT_LANG_UR:
        payload["document_type"] = translate_text(
            str(payload.get("document_type") or ""), source="en", target="ur"
        )
        payload["summary"] = translate_text(
            str(payload.get("summary") or ""), source="en", target="ur"
        )
        payload["disclaimer"] = translate_text(
            str(payload.get("disclaimer") or ""), source="en", target="ur"
        )
    return payload
