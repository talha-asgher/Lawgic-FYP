"""Normalize API output language codes and build localized RAG / analysis prompts."""

from __future__ import annotations

import os
from typing import Optional

OUTPUT_LANG_EN = "en"
OUTPUT_LANG_UR = "ur"


def normalize_output_language(raw: Optional[str]) -> str:
    if raw is None:
        return OUTPUT_LANG_EN
    s = str(raw).strip().lower().replace("-", "_")
    if not s:
        return OUTPUT_LANG_EN
    aliases = {
        "en": OUTPUT_LANG_EN,
        "english": OUTPUT_LANG_EN,
        "ur": OUTPUT_LANG_UR,
        "urd": OUTPUT_LANG_UR,
        "ur_pk": OUTPUT_LANG_UR,
        "urdu": OUTPUT_LANG_UR,
        # Legacy Roman Urdu codes → standard Urdu (Arabic script) in API/UI
        "ur_latn": OUTPUT_LANG_UR,
        "roman": OUTPUT_LANG_UR,
        "roman_urdu": OUTPUT_LANG_UR,
        "rol": OUTPUT_LANG_UR,
    }
    return aliases.get(s, OUTPUT_LANG_EN)


LOW_CONFIDENCE_DEFAULTS = {
    OUTPUT_LANG_EN: (
        "I could not find sufficiently relevant legal passages in the database for your question, "
        "so a generated answer was not shown. Try rephrasing, adding an Act or section if you know it, "
        "or consult a qualified lawyer for advice tailored to your situation."
    ),
    OUTPUT_LANG_UR: (
        "آپ کے سوال کے لیے ڈیٹابیس میں مکمل طور پر متعلقہ قانونی اقتباسات نہیں ملے، "
        "اس لیے تیار کردہ جواب نہیں دکھایا گیا۔ دوبارہ الفاظ میں پوچھیں، اگر معلوم ہو تو ایکٹ یا دفعہ "
        "بتائیں، یا اپنی صورتحال کے لیے اہل وکیل سے مشورہ کریں۔"
    ),
}

LOW_LABEL_DISCLAIMER_DEFAULTS = {
    OUTPUT_LANG_EN: (
        "The retrieved statutes may only partially match your question. "
        "This is not legal advice; verify everything against the cited sources or a qualified lawyer."
    ),
    OUTPUT_LANG_UR: (
        "حاصل کردہ قوانین آپ کے سوال سے جزوی طور پر مماثلت رکھ سکتے ہیں۔ "
        "یہ قانونی مشورہ نہیں؛ حوالہ دیے گئے ذرائع یا اہل وکیل سے تصدیق کریں۔"
    ),
}


def low_confidence_user_message(lang: str) -> str:
    code = normalize_output_language(lang)
    if code == OUTPUT_LANG_EN:
        custom = os.environ.get("RAG_LOW_CONFIDENCE_USER_MESSAGE", "").strip()
        if custom:
            return custom
    return LOW_CONFIDENCE_DEFAULTS.get(code, LOW_CONFIDENCE_DEFAULTS[OUTPUT_LANG_EN])


def low_label_disclaimer_note(lang: str) -> str:
    code = normalize_output_language(lang)
    if code == OUTPUT_LANG_EN:
        custom = os.environ.get("RAG_LOW_LABEL_DISCLAIMER", "").strip()
        if custom:
            return custom
    return LOW_LABEL_DISCLAIMER_DEFAULTS.get(code, LOW_LABEL_DISCLAIMER_DEFAULTS[OUTPUT_LANG_EN])


DOC_DISCLAIMER_BY_LANG = {
    OUTPUT_LANG_EN: (
        "This is AI-generated legal assistance and not a substitute for professional legal advice."
    ),
    OUTPUT_LANG_UR: (
        "یہ AI سے تیار کردہ قانونی معاونت ہے اور پیشہ ورانہ قانونی مشورے کا متبادل نہیں۔"
    ),
}


GROUNDING_BASE = """You are a legal research assistant for Pakistani law. You must answer ONLY from the numbered passages the user provides ([1], [2], …).

Reading order:
- Do not rely only on the first passage. Carefully consider ALL provided passages before answering.
- If multiple passages are relevant, combine them appropriately while staying within what they actually say.
- Some passages include an "Adjacent excerpts" block under the same [n] — treat that material as supporting context for that passage only, not a separate citation index.
- Some passages include a short "Parent section excerpt" under the same [n] — use it only to interpret backward references or missing conditions in the child text; do not treat it as a separate statute index.

Strict grounding (always):
- Ground every legal statement in those passages. If the passages do not clearly support a point, do not state it as settled law.
- Preserve qualifiers, provisos, exceptions, penalties, conditions, and cross-references exactly as in the passages; do not flatten or soften nuance.
- When the law distinguishes general rules from conditional or special cases, keep that distinction clear; do not overgeneralize a conditional rule as if it always applies.
- If the statutes set out separate remedies, procedures, or grounds, present them as distinct where the text does (do not merge them into one vague remedy).
- Do not invent statutes, sections, penalties, or interpretations not supported by the passages.
- The passage text may be in English; explain it in your OUTPUT language for the user without changing what the law says. Prefer faithful explanation tied to the passages; quote statutory wording only when needed.
"""


def _grounding_output_block(code: str) -> str:
    if code == OUTPUT_LANG_UR:
        return """
Output language (Urdu, Arabic script):
- Write the JSON "answer" string in standard Urdu. Keep passage markers like [1], [2].
- If insufficient_context is true, explain briefly in Urdu what is missing (still only as JSON).
- When context is sufficient, use about 2–4 short sentences: first = direct legal answer; then brief plain explanation in practice, strictly from the passages.
- Do not become verbose.

Plain-language style when context is sufficient:
- Write for a common person in Urdu (Arabic script); avoid dense legalese unless the passage requires quoting it.
"""
    return """
Plain-language style when context is sufficient:
- Write in simple, everyday English for a common person (avoid dense legalese unless the passage requires quoting it).
- Usually use about 2–4 short sentences: the first sentence states the direct legal answer to the question; the next sentence(s) give a brief plain-language explanation of what that means in practice, strictly based on the passages.
- Do not become verbose: no long essays, repetition, or extra background not supported by the passages.

Insufficient context:
- If the passages are insufficient to answer safely, set "insufficient_context" to true and explain briefly in simple English what is missing (still only as JSON).
"""


GROUNDING_TAIL = """
Source attribution:
- In "used_source_indexes", include EVERY passage index you relied on for any part of the answer—including passages you only partially used for context or supporting detail. Do not omit an index to keep the list short.
- Use the integer passage numbers exactly as labeled (1 for [1], 2 for [2], …). If no passage applies at all, use [] and set "used_source_ids" to [].

Output:
- Respond with a single JSON object ONLY (no markdown fences), with exactly these keys:
  "answer": string (you may mention passage numbers like [1] where helpful),
  "insufficient_context": boolean,
  "used_source_indexes": array of integers,
  "used_source_ids": array of strings (optional; object_id values from passage headers when used, else [])
"""


def build_grounding_system(output_lang: str) -> str:
    code = normalize_output_language(output_lang)
    return GROUNDING_BASE + _grounding_output_block(code) + GROUNDING_TAIL


def build_grounding_system_english_pipeline() -> str:
    """English-only SLM instructions (retrieval may still use translated user question)."""
    return GROUNDING_BASE + _grounding_output_block(OUTPUT_LANG_EN) + GROUNDING_TAIL


STRUCTURED_SYS_EN = (
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
    "Set disclaimer to exactly the sentence provided in the user message for the disclaimer field."
)


def structured_system_prompt(output_lang: str) -> str:
    code = normalize_output_language(output_lang)
    if code == OUTPUT_LANG_EN:
        return STRUCTURED_SYS_EN
    if code == OUTPUT_LANG_UR:
        return (
            STRUCTURED_SYS_EN
            + " All user-visible string values (document_type, summary, disclaimer) must be in standard Urdu "
            "(Arabic script). The summary must follow the same depth and completeness requirements as in English."
        )
    return STRUCTURED_SYS_EN


def structured_schema_hint_footer(output_lang: str) -> str:
    code = normalize_output_language(output_lang)
    disc = DOC_DISCLAIMER_BY_LANG.get(code, DOC_DISCLAIMER_BY_LANG[OUTPUT_LANG_EN])
    return (
        f'The summary must be a long, complete narrative that explains the entire document (as represented in the brief).\n'
        f'Cover all major themes, clauses, and facts you can infer from the brief; integrate risks, gaps, and suggestions '
        f'within that narrative. Prefer depth and completeness over brevity.\n'
        f'Set "disclaimer" to exactly: {disc}'
    )
