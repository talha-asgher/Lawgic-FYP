# app/routers/documents.py
"""
Document Templates and Document Generation.
Templates are seeded; generation creates a Document record.
Full AI-powered generation can be plugged in via the service layer later.
"""
import json
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app import models, schemas
from app.deps import get_db
from app.routers.auth import get_current_user

router = APIRouter(
    prefix="/documents",
    tags=["documents"],
)


@router.get("/templates", response_model=List[schemas.DocumentTemplateOut])
def list_templates(
    language: Optional[str] = None,
    doc_type: Optional[str] = None,
    db: Session = Depends(get_db),
):
    query = db.query(models.DocumentTemplate)
    if language:
        query = query.filter(models.DocumentTemplate.language == language)
    if doc_type:
        query = query.filter(models.DocumentTemplate.type.ilike(f"%{doc_type}%"))
    return query.all()


@router.get("/templates/{template_id}", response_model=schemas.DocumentTemplateOut)
def get_template(template_id: int, db: Session = Depends(get_db)):
    t = db.get(models.DocumentTemplate, template_id)
    if not t:
        raise HTTPException(status_code=404, detail="Template not found")
    return t


@router.post("/generate", response_model=schemas.DocumentOut)
def generate_document(
    req: schemas.DocumentGenerateRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """
    Generate a document from a template.
    Currently: merges input_data into the sample_content as a placeholder.
    Future: plug in AI generation service here.
    """
    template = db.get(models.DocumentTemplate, req.template_id)
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")

    # Placeholder content generation: substitute {{field}} placeholders
    content = template.sample_content or f"[{template.title or template.type} — content pending]"
    if req.input_data:
        for key, value in req.input_data.items():
            content = content.replace(f"{{{{{key}}}}}", str(value))

    doc = models.Document(
        user_id=current_user.user_id,
        template_id=req.template_id,
        title=req.title,
        type=template.type,
        content=content,
        input_data=json.dumps(req.input_data) if req.input_data else None,
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)
    return doc


@router.get("/my", response_model=List[schemas.DocumentOut])
def list_my_documents(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    return (
        db.query(models.Document)
        .filter(models.Document.user_id == current_user.user_id)
        .order_by(models.Document.created_at.desc())
        .all()
    )


@router.get("/{doc_id}", response_model=schemas.DocumentOut)
def get_document(
    doc_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    doc = db.get(models.Document, doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    if doc.user_id != current_user.user_id:
        raise HTTPException(status_code=403, detail="Access denied")
    return doc


# ── Document Analysis ─────────────────────────────────────────────────────────

analysis_router = APIRouter(
    prefix="/doc-analysis",
    tags=["doc-analysis"],
)


@analysis_router.post("/", response_model=schemas.DocAnalysisOut)
def create_analysis_job(
    file_name: str,
    file_size: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """
    Create an analysis job record.
    Actual file upload + AI analysis is a future integration point.
    Returns a mock/placeholder analysis result for now.
    """
    analysis = models.DocAnalysis(
        user_id=current_user.user_id,
        file_name=file_name,
        file_size=file_size,
        status="done",  # placeholder: immediately returns mock result
        summary=(
            "This document appears to be a standard legal agreement. "
            "Key obligations are outlined in sections 2, 4, and 7."
        ),
        risks=json.dumps([
            "Clause 5.2 contains a broad indemnification clause that may expose you to unlimited liability.",
            "No dispute resolution mechanism specified — defaults to local court jurisdiction.",
            "Termination clause (Section 8) allows termination without cause with only 7 days notice.",
        ]),
        key_details=json.dumps({
            "document_type": "Contract / Agreement",
            "parties": "Identified in Section 1",
            "effective_date": "Upon signing",
            "governing_law": "Laws of Pakistan",
        }),
    )
    db.add(analysis)
    db.commit()
    db.refresh(analysis)
    return analysis


@analysis_router.get("/my", response_model=List[schemas.DocAnalysisOut])
def list_my_analyses(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    return (
        db.query(models.DocAnalysis)
        .filter(models.DocAnalysis.user_id == current_user.user_id)
        .order_by(models.DocAnalysis.created_at.desc())
        .all()
    )


@analysis_router.get("/{analysis_id}", response_model=schemas.DocAnalysisOut)
def get_analysis(
    analysis_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    a = db.get(models.DocAnalysis, analysis_id)
    if not a:
        raise HTTPException(status_code=404, detail="Analysis not found")
    if a.user_id != current_user.user_id:
        raise HTTPException(status_code=403, detail="Access denied")
    return a
