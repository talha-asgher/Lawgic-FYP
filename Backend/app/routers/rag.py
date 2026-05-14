import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app import models, schemas
from app.deps import get_db
from app.routers.auth import get_current_user
from app.services.language_output import normalize_output_language
from app.services.ollama_service import OllamaServiceError
from app.services.rag_service import finalize_rag_ask, retrieve_for_rag_ask

router = APIRouter(prefix="/rag", tags=["rag"])


@router.post("/ask", response_model=schemas.RagAskResponse)
def rag_ask(
    req: schemas.RagAskRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    session_id = req.session_id or str(uuid.uuid4())
    out_lang = normalize_output_language(req.output_language)

    qa = models.QAInteraction(
        user_id=current_user.user_id,
        question=req.query,
        language=out_lang,
        status="pending",
        session_id=session_id,
    )
    db.add(qa)
    db.flush()
    qa_id = qa.qa_id

    try:
        retrieval = retrieve_for_rag_ask(db, req)
    except Exception:
        qa.status = "failed"
        db.commit()
        raise HTTPException(
            status_code=503, detail="AI service is currently unavailable"
        ) from None

    db.commit()

    try:
        rag_resp = finalize_rag_ask(req, retrieval)
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
        raise HTTPException(
            status_code=503, detail="AI service is currently unavailable"
        ) from None

    qa_u = db.get(models.QAInteraction, qa_id)
    if not qa_u:
        raise HTTPException(status_code=500, detail="QA record missing after RAG")
    qa_u.answer = rag_resp.answer
    qa_u.language = rag_resp.output_language
    qa_u.status = "answered"

    persist_sources = rag_resp.sources or rag_resp.retrieved_sources
    for s in persist_sources:
        snippet = s.excerpt_text or (s.full_source_text or "")[:600] or None
        db.add(
            models.QACitation(
                qa_id=qa_id,
                source_title=s.act_name,
                citation_ref=s.source_reference,
                snippet_text=snippet,
            )
        )

    db.commit()

    return rag_resp
