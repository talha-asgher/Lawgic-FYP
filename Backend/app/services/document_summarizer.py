"""Map-reduce style summarization via Ollama for long documents."""

from __future__ import annotations

import logging

from app.services.ollama_service import OllamaServiceError, chat_completion

logger = logging.getLogger(__name__)

CHUNK_CHARS = 12_000
CHUNK_OVERLAP = 400

SYSTEM = (
    "You summarize legal and general documents for non-experts. "
    "Use clear, simple language. Do not invent facts. "
    "If the excerpt is unclear or empty, say so briefly."
)

PARTIAL_USER = (
    "Below is an excerpt from one document. Summarize only this part in 3–6 short bullet points.\n\n"
    "{chunk}"
)

FINAL_USER = (
    "The following bullet summaries describe different parts of the same document. "
    "Write one short, cohesive summary (under 220 words) in plain language for the reader. "
    "Prefer a short paragraph; you may add up to 4 bullets if it helps clarity.\n\n"
    "{combined}"
)


def _summarize(messages: list[dict[str, str]], *, temperature: float = 0.2) -> str:
    return chat_completion(messages, temperature=temperature, top_p=0.9)


def _chunk_text(text: str) -> list[str]:
    text = text.strip()
    if len(text) <= CHUNK_CHARS:
        return [text]
    chunks: list[str] = []
    start = 0
    n = len(text)
    while start < n:
        end = min(start + CHUNK_CHARS, n)
        chunks.append(text[start:end])
        if end >= n:
            break
        start = max(0, end - CHUNK_OVERLAP)
    return chunks


def summarize_document_text(text: str) -> str:
    text = (text or "").strip()
    if not text:
        raise OllamaServiceError("No text to summarize.")

    chunks = _chunk_text(text)
    if len(chunks) == 1:
        messages = [
            {"role": "system", "content": SYSTEM},
            {
                "role": "user",
                "content": (
                    "Summarize this document in simple language for a general reader. "
                    "Use a short opening paragraph and up to 6 bullet points if useful.\n\n"
                    + chunks[0]
                ),
            },
        ]
        return _summarize(messages)

    partials: list[str] = []
    for i, ch in enumerate(chunks):
        messages = [
            {"role": "system", "content": SYSTEM},
            {
                "role": "user",
                "content": PARTIAL_USER.format(chunk=ch),
            },
        ]
        try:
            partials.append(_summarize(messages, temperature=0.15))
        except OllamaServiceError:
            logger.warning("Chunk %s summarization failed; skipping", i)
            partials.append(f"(Part {i + 1} could not be summarized.)")

    combined = "\n\n".join(
        f"--- Part {i + 1} ---\n{p}" for i, p in enumerate(partials)
    )
    messages = [
        {"role": "system", "content": SYSTEM},
        {"role": "user", "content": FINAL_USER.format(combined=combined)},
    ]
    return _summarize(messages, temperature=0.2)
