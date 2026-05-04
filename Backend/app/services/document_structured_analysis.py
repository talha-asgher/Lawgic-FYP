"""Chunked consolidation + structured JSON legal analysis via Ollama."""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from app.services.ollama_service import OllamaServiceError, chat_completion

logger = logging.getLogger(__name__)

# Keep each LLM input bounded; long docs are never sent as one block to the final model.
CHUNK_INPUT_CHARS = 6_000
CHUNK_OVERLAP = 300
MAX_CONSOLIDATED_CHARS = 18_000

DEFAULT_DISCLAIMER = (
    "This is AI-generated legal assistance and not a substitute for professional legal advice."
)

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

STRUCTURED_SYS = (
    "You are a legal document analyst for readers in Pakistan where applicable. "
    "Output MUST be a single JSON object with exactly three string fields: document_type, summary, disclaimer. "
    "The summary field must be a comprehensive explanation of the COMPLETE document as reflected in the brief—"
    "not a short blurb. Write in plain language but be thorough: multiple substantial paragraphs (and bullet "
    "lines inside the string where helpful). Cover what the document is; parties and roles; main purpose; "
    "important definitions and obligations; timelines, payments, or penalties if present; termination and "
    "dispute handling where stated; important risks, red flags, gaps or missing information; and practical "
    "suggestions. Aim for substantial length when the source material is rich—typically on the order of "
    "800–2000 words for complex agreements, shorter only when the brief itself is very short. "
    "Do not invent facts; use only information supported by the brief. "
    "Set disclaimer to: This is AI-generated legal assistance and not a substitute for professional legal advice."
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


def normalize_payload(data: dict[str, Any]) -> dict[str, Any]:
    """Enforce three-field shape and default disclaimer."""
    disclaimer = str(data.get("disclaimer") or "").strip() or DEFAULT_DISCLAIMER
    return {
        "document_type": str(data.get("document_type") or "").strip() or "Unknown",
        "summary": str(data.get("summary") or "").strip(),
        "disclaimer": disclaimer,
    }


def generate_structured_analysis(consolidated_brief: str) -> dict[str, Any]:
    brief = consolidated_brief.strip()
    if len(brief) > MAX_CONSOLIDATED_CHARS:
        brief = brief[:MAX_CONSOLIDATED_CHARS] + "\n\n[Content truncated for analysis.]"

    schema_hint = """
Return exactly this JSON shape (no markdown fences):
{
  "document_type": "",
  "summary": "",
  "disclaimer": "This is AI-generated legal assistance and not a substitute for professional legal advice."
}
The summary must be a long, complete narrative that explains the entire document (as represented in the brief).
Cover all major themes, clauses, and facts you can infer from the brief; integrate risks, gaps, and suggestions
within that narrative. Prefer depth and completeness over brevity.
"""
    messages = [
        {"role": "system", "content": STRUCTURED_SYS},
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
            {"role": "system", "content": STRUCTURED_SYS},
            {
                "role": "user",
                "content": f"Document brief:\n\n{brief}\n\n{schema_hint}\nRespond with raw JSON only.",
            },
        ]
        raw2 = _summarize(messages_retry, json_format=False)
        data = json.loads(_strip_json_fence(raw2))

    if not isinstance(data, dict):
        raise OllamaServiceError("Model returned non-object JSON.")
    return normalize_payload(data)
