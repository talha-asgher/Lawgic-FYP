# app/routers/ai_qa.py
import uuid
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app import models, schemas
from app.deps import get_db
from app.routers.auth import get_current_user
from app.services.ollama_service import OllamaServiceError
from app.services.rag_service import finalize_rag_ask, retrieve_for_rag_ask
from app.services.language_output import normalize_output_language

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
    out_lang = normalize_output_language(req.language)

    qa = models.QAInteraction(
        user_id=current_user.user_id,
        question=req.question,
        language=out_lang,
        status="pending",
        session_id=session_id,
    )
    db.add(qa)
    db.flush()
    qa_id = qa.qa_id

    rag_req = schemas.RagAskRequest(
        query=req.question,
        top_k_retrieval=15,
        top_k_context=6,
        output_language=out_lang,
        query_language=req.query_language,
    )
    try:
        retrieval = retrieve_for_rag_ask(db, rag_req)
    except Exception:
        qa.status = "failed"
        db.commit()
        raise HTTPException(status_code=503, detail="AI service is currently unavailable") from None

    # Release DB connection before rerank / SLM
    db.commit()

    try:
        rag_resp = finalize_rag_ask(rag_req, retrieval)
    except OllamaServiceError as e:
        qa_u = db.get(models.QAInteraction, qa_id)
        if qa_u:
            qa_u.status = "failed"
            db.commit()
        raise HTTPException(status_code=503, detail=str(e)) from e
    except Exception:
        qa_u = db.get(models.QAInteraction, qa_id)
        if qa_u:
            qa_u.status = "failed"
            db.commit()
        raise HTTPException(status_code=503, detail="AI service is currently unavailable") from None

    qa_u = db.get(models.QAInteraction, qa_id)
    if not qa_u:
        raise HTTPException(status_code=500, detail="QA record missing after RAG")
    qa_u.answer = rag_resp.answer
    qa_u.language = rag_resp.output_language
    qa_u.status = "answered"

    citation_outs: List[schemas.CitationOut] = []
    persist_sources = rag_resp.sources or rag_resp.retrieved_sources
    for s in persist_sources:
        snippet = s.excerpt_text or (s.full_source_text or "")[:600] or None
        qc = models.QACitation(
            qa_id=qa_id,
            source_title=s.act_name,
            citation_ref=s.source_reference,
            snippet_text=snippet,
        )
        db.add(qc)
        citation_outs.append(
            schemas.CitationOut(
                source_title=s.act_name,
                citation_ref=s.source_reference,
                snippet_text=snippet,
            )
        )

    db.commit()
    db.refresh(qa_u)

    return schemas.AskAIResponse(
        qa_id=qa_u.qa_id,
        question=qa_u.question,
        answer=qa_u.answer,
        language=qa_u.language,
        status=qa_u.status,
        session_id=qa_u.session_id,
        citations=citation_outs,
        created_at=qa_u.created_at,
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

    return sorted(seen.values(), key=lambda x: x["created_at"], reverse=True)
