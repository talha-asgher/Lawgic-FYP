#!/usr/bin/env python3
"""
Qwen-based SLM summarizer for legal TABLE and FORM chunks.

- CPU only.
- English-only summaries.
- Uses the model chat template when available.
- Produces short retrieval-oriented 3-line summaries (Title / Type / Contains).
"""

from typing import Dict, Literal, Any
import re
import torch
from transformers import AutoTokenizer, AutoModelForCausalLM

MODEL_NAME = "Qwen/Qwen1.5-1.8B-Chat"
MAX_TABLE_PROMPT_CHARS = 8000

_SYSTEM_PROMPT = (
    "You are a legal text assistant for retrieval indexing. "
    "Reply with only the three requested lines. "
    "Do not repeat instructions, do not quote BEGIN/END markers, "
    "and do not use angle brackets or placeholder text in your answer."
)


class TableFormSummarizer:
    def __init__(
        self,
        model_name: str = MODEL_NAME,
        max_new_tokens: int = 160,
        temperature: float = 0.0,
        top_p: float = 0.8,
    ):
        self.model_name = model_name
        self.max_new_tokens = max_new_tokens
        self.temperature = temperature
        self.top_p = top_p
        self.device = "cpu"

        self.tokenizer = AutoTokenizer.from_pretrained(model_name)
        self.model = AutoModelForCausalLM.from_pretrained(
            model_name,
            torch_dtype=torch.float32,
        ).to(self.device)
        self.model.eval()

    def _normalize(self, text: str) -> str:
        return re.sub(r"\s+", " ", text or "").strip()

    def _build_user_prompt(
        self,
        text: str,
        kind: Literal["table", "form"],
        metadata: Dict[str, Any],
    ) -> str:
        act_name = self._normalize(str(metadata.get("act_name", "")))
        section_number = self._normalize(str(metadata.get("section_number", "")))
        section_title = self._normalize(str(metadata.get("section_title", "")))
        chunk_id = metadata.get("table_id") if kind == "table" else metadata.get("form_id")
        content_type_hint = self._normalize(str(metadata.get("content_type_hint", "")))
        instructions = self._normalize(str(metadata.get("instructions", "")))

        title_value = section_title or "Untitled"

        context_lines = []
        if act_name:
            context_lines.append(f"Act: {act_name}")
        if section_number and section_number != "-":
            context_lines.append(f"Section number: {section_number}")
        if section_title:
            context_lines.append(f"Section title: {section_title}")
        if chunk_id:
            context_lines.append(f"{kind.capitalize()} ID: {chunk_id}")
        if content_type_hint:
            context_lines.append(f"Detected type hint: {content_type_hint}")

        header = "\n".join(context_lines).strip()
        if header:
            header += "\n\n"

        hint_lower = content_type_hint.lower()
        membership_note = ""
        if kind == "table" and ("membership" in hint_lower or "composition" in hint_lower):
            membership_note = (
                "This table lists who sits on the body: summarize roles in the Contains line "
                "using short phrases from the text (chair, ministries, ex officio members, etc.); "
                "do not copy every row and do not state legal effect beyond the wording shown.\n"
            )

        if kind == "table":
            task = (
                f"{membership_note}"
                "Summarize the legal table for retrieval.\n"
                "Write only facts visible in the table text.\n"
                "Do not explain legal effect, purpose, fees, eligibility, or background unless explicitly stated.\n"
                "Do not copy numbering tokens like (i), (ii), 1, 2 unless essential.\n"
                "Use short phrases on the Contains line, separated by semicolons.\n"
                f"The first line must be exactly: Title: {title_value}\n"
                "The second line must start with Type: followed by one short factual label (examples: "
                "contents/index table, membership/composition table, fees/costs table).\n"
                "The third line must start with Contains: then 5–10 short items separated by semicolons.\n"
                "Output exactly three lines and nothing else (no markdown fences, no preamble).\n"
            )
        else:
            task = (
                "Summarize the legal form for retrieval.\n"
                "Write only facts visible in the form text.\n"
                "Do not infer legal consequences, who fills it, attachments, financial details, or case history unless explicitly stated.\n"
                "Use short field-style phrases on the Contains line, separated by commas or semicolons.\n"
                f"The first line must be exactly: Title: {title_value}\n"
                "The second line must start with Type: followed by one short factual label describing the form.\n"
                "The third line must start with Contains: then 5–10 short items.\n"
                "Output exactly three lines and nothing else (no markdown fences, no preamble).\n"
            )

        if instructions:
            task += f"Extra rule: {instructions}\n"

        body = text.strip()
        if kind == "table" and len(body) > MAX_TABLE_PROMPT_CHARS:
            body = body[:MAX_TABLE_PROMPT_CHARS] + "\n[Truncated visible portion only.]"

        return (
            f"{task}\n"
            f"{header}"
            f"--- BEGIN {kind.upper()} TEXT ---\n"
            f"{body}\n"
            f"--- END {kind.upper()} TEXT ---\n"
        )

    @staticmethod
    def _postprocess_three_lines(raw: str, expected_title: str) -> str:
        """Keep the first Title/Type/Contains lines in order; drop trailing ramble."""
        title_prefix = "title:"
        type_prefix = "type:"
        contains_prefix = "contains:"
        title_line: str | None = None
        type_line: str | None = None
        contains_line: str | None = None
        for line in (raw or "").splitlines():
            s = line.strip()
            if not s:
                continue
            low = s.lower()
            if low.startswith(title_prefix) and title_line is None:
                title_line = s
            elif low.startswith(type_prefix) and title_line is not None and type_line is None:
                type_line = s
            elif low.startswith(contains_prefix) and type_line is not None and contains_line is None:
                contains_line = s
                break
        if title_line and type_line and contains_line:
            if expected_title:
                title_line = f"Title: {expected_title}"
            return f"{title_line}\n{type_line}\n{contains_line}"
        return (raw or "").strip()

    def _encode_chat(self, user_content: str) -> dict[str, Any]:
        messages = [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": user_content},
        ]
        tpl = getattr(self.tokenizer, "chat_template", None)
        if tpl:
            prompt = self.tokenizer.apply_chat_template(
                messages,
                tokenize=False,
                add_generation_prompt=True,
            )
        else:
            prompt = _SYSTEM_PROMPT + "\n\n" + user_content
        return self.tokenizer(prompt, return_tensors="pt")

    def _generate(
        self,
        user_prompt: str,
        temperature: float | None = None,
        top_p: float | None = None,
        max_new_tokens: int | None = None,
        expected_title: str = "",
    ) -> str:
        inputs = self._encode_chat(user_prompt).to(self.device)
        temperature = self.temperature if temperature is None else temperature
        top_p = self.top_p if top_p is None else top_p
        max_new_tokens = self.max_new_tokens if max_new_tokens is None else max_new_tokens

        generate_kwargs: dict[str, Any] = {
            "max_new_tokens": max_new_tokens,
            "pad_token_id": self.tokenizer.eos_token_id,
        }
        if temperature and temperature > 0:
            generate_kwargs.update({"do_sample": True, "temperature": temperature, "top_p": top_p})
        else:
            generate_kwargs.update({"do_sample": False})

        with torch.no_grad():
            output_ids = self.model.generate(**inputs, **generate_kwargs)

        generated_ids = output_ids[0][inputs["input_ids"].shape[1]:]
        raw = self.tokenizer.decode(generated_ids, skip_special_tokens=True).strip()
        return self._postprocess_three_lines(raw, expected_title)

    def summarize_table(
        self,
        text: str,
        metadata: Dict[str, Any],
        temperature: float | None = None,
        top_p: float | None = None,
        max_new_tokens: int | None = None,
    ) -> str:
        meta = metadata or {}
        user_prompt = self._build_user_prompt(text=text, kind="table", metadata=meta)
        title_value = self._normalize(str(meta.get("section_title", ""))) or "Untitled"
        return self._generate(
            user_prompt,
            temperature=temperature,
            top_p=top_p,
            max_new_tokens=max_new_tokens,
            expected_title=title_value,
        )

    def summarize_form(
        self,
        text: str,
        metadata: Dict[str, Any],
        temperature: float | None = None,
        top_p: float | None = None,
        max_new_tokens: int | None = None,
    ) -> str:
        meta = metadata or {}
        user_prompt = self._build_user_prompt(text=text, kind="form", metadata=meta)
        title_value = self._normalize(str(meta.get("section_title", ""))) or "Untitled"
        return self._generate(
            user_prompt,
            temperature=temperature,
            top_p=top_p,
            max_new_tokens=max_new_tokens,
            expected_title=title_value,
        )
