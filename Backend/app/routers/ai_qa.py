# app/routers/ai_qa.py
"""
Ask AI / Legal Q&A endpoint.
Architecture:
  - Endpoint accepts a question + language + optional session_id
  - Persists the QAInteraction record
  - Calls ai_service.get_answer() — currently returns a placeholder
  - Returns the answer + citations in a schema ready for the RAG pipeline

To integrate the RAG pipeline:
  1. Replace the body of ai_service.get_answer() with the actual RAG call
  2. The service returns (answer: str, citations: list[dict])
  3. No changes needed to this router or the response schema
"""
import uuid
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app import models, schemas
from app.deps import get_db
from app.routers.auth import get_current_user
from app.services.ai_service import get_answer  # pluggable interface

router = APIRouter(
    prefix="/ai",
    tags=["ai-qa"],
)


@router.post("/ask", response_model=schemas.AskAIResponse)
def ask_legal_question(
    req: schemas.AskAIRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    session_id = req.session_id or str(uuid.uuid4())

    # Persist the question
    qa = models.QAInteraction(
        user_id=current_user.user_id,
        question=req.question,
        language=req.language,
        status="pending",
        session_id=session_id,
    )
    db.add(qa)
    db.flush()

    # Call the AI service (pluggable — see services/ai_service.py)
    try:
        answer_text, raw_citations = get_answer(req.question, req.language, session_id)
        qa.answer = answer_text
        qa.status = "answered"
    except Exception:
        qa.status = "failed"
        db.commit()
        raise HTTPException(status_code=503, detail="AI service is currently unavailable")

    # Persist citations
    citation_outs: List[schemas.CitationOut] = []
    for c in raw_citations:
        qc = models.QACitation(
            qa_id=qa.qa_id,
            source_title=c.get("source_title"),
            citation_ref=c.get("citation_ref"),
            snippet_text=c.get("snippet_text"),
        )
        db.add(qc)
        citation_outs.append(schemas.CitationOut(
            source_title=c.get("source_title"),
            citation_ref=c.get("citation_ref"),
            snippet_text=c.get("snippet_text"),
        ))

    db.commit()
    db.refresh(qa)

    return schemas.AskAIResponse(
        qa_id=qa.qa_id,
        question=qa.question,
        answer=qa.answer,
        language=qa.language,
        status=qa.status,
        session_id=qa.session_id,
        citations=citation_outs,
        created_at=qa.created_at,
    )


@router.get("/history", response_model=List[schemas.AskAIResponse])
def get_my_qa_history(
    session_id: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    query = (
        db.query(models.QAInteraction)
        .filter(models.QAInteraction.user_id == current_user.user_id)
    )
    if session_id:
        query = query.filter(models.QAInteraction.session_id == session_id)

    interactions = query.order_by(models.QAInteraction.created_at.desc()).all()

    result = []
    for qa in interactions:
        citations = [
            schemas.CitationOut(
                source_title=c.source_title,
                citation_ref=c.citation_ref,
                snippet_text=c.snippet_text,
            )
            for c in qa.citations
        ]
        result.append(schemas.AskAIResponse(
            qa_id=qa.qa_id,
            question=qa.question,
            answer=qa.answer,
            language=qa.language,
            status=qa.status,
            session_id=qa.session_id,
            citations=citations,
            created_at=qa.created_at,
        ))
    return result


@router.get("/sessions")
def list_my_sessions(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Return distinct chat sessions for the sidebar history."""
    # Fetch all interactions ordered by created_at asc so the first question
    # per session becomes the session title. Dedup in Python for DB portability.
    rows = (
        db.query(
            models.QAInteraction.session_id,
            models.QAInteraction.question,
            models.QAInteraction.created_at,
        )
        .filter(models.QAInteraction.user_id == current_user.user_id)
        .order_by(models.QAInteraction.created_at.asc())
        .all()
    )
    seen: dict = {}
    for session_id, question, created_at in rows:
        if session_id not in seen:
            seen[session_id] = {"session_id": session_id, "title": question[:60], "created_at": created_at}
    # Return most recent session first
    return sorted(seen.values(), key=lambda x: x["created_at"], reverse=True)
