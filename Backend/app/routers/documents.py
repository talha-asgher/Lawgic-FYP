# app/routers/documents.py
import json
import datetime
from typing import List, Optional, Any

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app import models, schemas
from app.deps import get_db
from app.routers.auth import get_current_user
from app.utils.pdf_generator import generate_document, PDF_GENERATORS

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


class GenerateDocumentRequest(BaseModel):
    template_type: str
    form_data: dict[str, Any]


class GenerateDocumentResponse(BaseModel):
    document_id: int
    template_type: str
    title: str
    message: str
    created_at: str


class DocumentListItem(BaseModel):
    document_id: int
    title: str
    type: str
    created_at: str

    class Config:
        from_attributes = True

@router.post("/generate", response_model=GenerateDocumentResponse)
def generate_document_endpoint(
    request: GenerateDocumentRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    if request.template_type not in PDF_GENERATORS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown template type '{request.template_type}'. "
                   f"Valid: {', '.join(PDF_GENERATORS.keys())}"
        )

    try:
        pdf_bytes = generate_document(request.template_type, request.form_data)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"PDF generation failed: {str(e)}"
        )

    title_map = {
        "fir":          "FIR (First Information Report)",
        "tenancy":      "Tenancy Agreement",
        "divorce":      "Divorce Notice (Talaq)",
        "affidavit":    "Affidavit",
        "poa":          "Power of Attorney",
        "legal_notice": "Legal Notice",
    }
    doc_title = (
        f"{title_map.get(request.template_type, request.template_type)} — "
        f"{datetime.date.today().strftime('%d %b %Y')}"
    )

    db_doc = models.Document(
        user_id=current_user.user_id,
        template_id=None,
        title=doc_title,
        type=request.template_type,
        content=json.dumps(request.form_data),
        pdf_data=pdf_bytes,
    )
    db.add(db_doc)
    db.commit()
    db.refresh(db_doc)

    return GenerateDocumentResponse(
        document_id=db_doc.doc_id,
        template_type=request.template_type,
        title=doc_title,
        message="Document generated and saved successfully",
        created_at=db_doc.created_at.isoformat(),
    )


@router.get("/my-documents", response_model=List[DocumentListItem])
def get_my_documents(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    docs = (
        db.query(models.Document)
        .filter(models.Document.user_id == current_user.user_id)
        .order_by(models.Document.created_at.desc())
        .all()
    )
    return [
        DocumentListItem(
            document_id=d.doc_id,
            title=d.title,
            type=d.type,
            created_at=d.created_at.isoformat(),
        )
        for d in docs
    ]


@router.get("/download/{document_id}")
def download_document(
    document_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    db_doc = db.query(models.Document).filter(
        models.Document.doc_id == document_id
    ).first()

    if not db_doc:
        raise HTTPException(status_code=404, detail="Document not found")

    if db_doc.user_id != current_user.user_id:
        raise HTTPException(status_code=403, detail="Access denied")

    if not db_doc.pdf_data:
        raise HTTPException(status_code=404, detail="PDF data not found")

    filename = f"{db_doc.type}_{db_doc.doc_id}.pdf"

    return Response(
        content=bytes(db_doc.pdf_data),
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
        }
    )


@router.delete("/delete/{document_id}")
def delete_document(
    document_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Delete a document — only the owner can delete."""
    db_doc = db.query(models.Document).filter(
        models.Document.doc_id == document_id
    ).first()

    if not db_doc:
        raise HTTPException(status_code=404, detail="Document not found")

    if db_doc.user_id != current_user.user_id:
        raise HTTPException(status_code=403, detail="Access denied")

    db.delete(db_doc)
    db.commit()

    return {"message": "Document deleted successfully"}


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


# Document Analysis

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

    analysis = models.DocAnalysis(
        user_id=current_user.user_id,
        file_name=file_name,
        file_size=file_size,
        status="done",
        summary=(
        ),
        risks=json.dumps([
        ]),
        key_details=json.dumps({}),
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
