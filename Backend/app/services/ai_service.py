# app/services/ai_service.py
"""
AI Service Interface — Pluggable RAG adapter.

This module defines the interface between the AI Q&A router and the underlying
AI/RAG pipeline. The current implementation returns a placeholder response.

TO INTEGRATE THE RAG PIPELINE:
  1. Replace the body of get_answer() with your RAG pipeline call.
  2. Return (answer_text: str, citations: list[dict]) in the same format.
  3. Each citation dict should have keys: source_title, citation_ref, snippet_text.
  4. No changes needed to ai_qa.py router or the database models.

Example RAG integration sketch:
  from your_rag_module import RagPipeline
  pipeline = RagPipeline(...)

  def get_answer(question, language, session_id):
      result = pipeline.query(question, lang=language)
      return result.answer, result.citations
"""
from typing import List, Tuple, Dict, Any


def get_answer(
    question: str,
    language: str = "en",
    session_id: str = None,
) -> Tuple[str, List[Dict[str, Any]]]:
    """
    Placeholder implementation.
    Returns a mock answer with sample citations.

    Replace this function body with the actual RAG pipeline call.
    """
    # TODO: Replace with actual RAG pipeline
    placeholder_answer = (
        "Based on Pakistani law, this is a placeholder answer. "
        "The actual AI-powered response will be provided once the RAG pipeline is integrated. "
        f"Your question was: \"{question}\""
    )

    placeholder_citations = [
        {
            "source_title": "Constitution of Pakistan 1973",
            "citation_ref": "Art. 10-A",
            "snippet_text": "Right to fair trial — every person shall be entitled to a fair trial.",
        },
        {
            "source_title": "Pakistan Penal Code 1860",
            "citation_ref": "Section 506",
            "snippet_text": "Punishment for criminal intimidation.",
        },
    ]

    return placeholder_answer, placeholder_citations
