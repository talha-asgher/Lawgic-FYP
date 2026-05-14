# app/routers/documents.py
import hashlib
import json
import datetime
import time
from typing import List, Optional, Any

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.responses import Response, StreamingResponse
from pydantic import BaseModel
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app import models, schemas
from app.deps import get_db
from app.database import SessionLocal
from app.routers.auth import get_current_user
from app.utils.pdf_generator import generate_document, PDF_GENERATORS
from app.services.document_text_extraction import detect_kind
from app.services.doc_analysis_tasks import run_doc_analysis_job
from app.services.language_output import OUTPUT_LANG_EN, OUTPUT_LANG_UR, normalize_output_language
from app.services.translation_service import (
    translate_doc_analysis_payload,
    urdu_arabic_script_ratio,
)

MAX_ANALYSIS_FILE_BYTES = 20 * 1024 * 1024

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


def serialize_doc_analysis(row: models.DocAnalysis) -> schemas.DocAnalysisOut:
    result = None
    if row.analysis_json:
        try:
            parsed = json.loads(row.analysis_json)
            if isinstance(parsed, dict):
                result = schemas.document_analysis_from_stored_dict(parsed)
            else:
                result = None
        except Exception:
            result = None
    summary_text = row.summary
    if result is not None and result.summary:
        summary_text = result.summary
    return schemas.DocAnalysisOut(
        analysis_id=row.analysis_id,
        user_id=row.user_id,
        file_name=row.file_name,
        file_size=row.file_size,
        file_hash=row.file_hash,
        output_language=getattr(row, "output_language", None) or "en",
        status=row.status,
        progress_stage=row.progress_stage,
        summary=summary_text,
        risks=row.risks,
        key_details=row.key_details,
        result=result,
        created_at=row.created_at,
    )


def serialize_doc_analysis_created(
    row: models.DocAnalysis, from_cache: bool
) -> schemas.DocAnalysisCreatedOut:
    base = serialize_doc_analysis(row)
    return schemas.DocAnalysisCreatedOut(**base.model_dump(), from_cache=from_cache)


def _stored_doc_analysis_dict(row: models.DocAnalysis) -> dict:
    if row.analysis_json:
        try:
            parsed = json.loads(row.analysis_json)
            if isinstance(parsed, dict):
                return parsed
        except Exception:
            pass
    return {"summary": str(row.summary or "").strip()}


def _cache_row_language(row: models.DocAnalysis, payload: dict) -> str:
    lang = normalize_output_language(getattr(row, "output_language", None))
    summary = str(payload.get("summary") or row.summary or "")
    if lang == OUTPUT_LANG_UR and summary and urdu_arabic_script_ratio(summary) < 0.12:
        return OUTPUT_LANG_EN
    return lang


def _materialize_cached_analysis(
    db: Session,
    row: models.DocAnalysis,
    *,
    target_lang: str,
    file_name: str,
    file_size: int,
) -> models.DocAnalysis:
    payload = _stored_doc_analysis_dict(row)
    source_lang = _cache_row_language(row, payload)
    if source_lang == target_lang:
        return row

    translated = translate_doc_analysis_payload(
        payload,
        source_lang=source_lang,
        target_lang=target_lang,
    )
    translated_summary = str(translated.get("summary") or "").strip()
    if (
        source_lang == OUTPUT_LANG_EN
        and target_lang == OUTPUT_LANG_UR
        and translated_summary
        and urdu_arabic_script_ratio(translated_summary) < 0.12
    ):
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Cached summary translation to Urdu failed. Try again when the translation service is available.",
        )
    translated_row = models.DocAnalysis(
        user_id=row.user_id,
        file_name=file_name,
        file_size=file_size,
        file_hash=row.file_hash,
        output_language=target_lang,
        status="done",
        progress_stage=None,
        summary=translated_summary or None,
        risks=json.dumps([]),
        key_details=None,
        analysis_json=json.dumps(translated, ensure_ascii=False),
    )
    db.add(translated_row)
    db.commit()
    db.refresh(translated_row)
    return translated_row


# ── Document Analysis ─────────────────────────────────────────────────────────

analysis_router = APIRouter(
    prefix="/doc-analysis",
    tags=["doc-analysis"],
)


@analysis_router.post("/", response_model=schemas.DocAnalysisCreatedOut)
async def create_analysis_job(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    output_language: str = Form("en"),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """
    Upload a PDF, DOCX, TXT, or image. Structured analysis runs in the background.
    Same file bytes + same output_language (per user, SHA-256 + language) may return a cached result.
    If the file was already analyzed in the other supported language (English vs Urdu), the stored
    result/summary is translated so the user does not wait for a full re-analysis.
    Poll GET /doc-analysis/{id} for `progress_stage` and `result`.
    """
    raw = await file.read()
    if len(raw) > MAX_ANALYSIS_FILE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File too large. Maximum size is {MAX_ANALYSIS_FILE_BYTES // (1024 * 1024)} MB.",
        )
    if len(raw) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Empty file.",
        )

    name = file.filename or "document"
    ct = file.content_type
    if detect_kind(name, ct) is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unsupported file type. Upload a PDF, DOCX, TXT, or image (PNG, JPEG, WebP).",
        )

    file_hash = hashlib.sha256(raw).hexdigest()
    out_lang = normalize_output_language(output_language)
    cached = (
        db.query(models.DocAnalysis)
        .filter(
            models.DocAnalysis.user_id == current_user.user_id,
            models.DocAnalysis.file_hash == file_hash,
            models.DocAnalysis.output_language == out_lang,
            models.DocAnalysis.status == "done",
            or_(
                models.DocAnalysis.analysis_json.isnot(None),
                models.DocAnalysis.summary.isnot(None),
            ),
        )
        .order_by(models.DocAnalysis.created_at.desc())
        .first()
    )
    if cached:
        try:
            cached = _materialize_cached_analysis(
                db,
                cached,
                target_lang=out_lang,
                file_name=name,
                file_size=len(raw),
            )
        except HTTPException:
            db.rollback()
            raise
        except Exception:
            db.rollback()
        return serialize_doc_analysis_created(cached, from_cache=True)

    sibling_lang = OUTPUT_LANG_UR if out_lang == OUTPUT_LANG_EN else OUTPUT_LANG_EN
    sibling = (
        db.query(models.DocAnalysis)
        .filter(
            models.DocAnalysis.user_id == current_user.user_id,
            models.DocAnalysis.file_hash == file_hash,
            models.DocAnalysis.output_language == sibling_lang,
            models.DocAnalysis.status == "done",
            or_(
                models.DocAnalysis.analysis_json.isnot(None),
                models.DocAnalysis.summary.isnot(None),
            ),
        )
        .order_by(models.DocAnalysis.created_at.desc())
        .first()
    )
    if sibling:
        try:
            translated_row = _materialize_cached_analysis(
                db,
                sibling,
                target_lang=out_lang,
                file_name=name,
                file_size=len(raw),
            )
            return serialize_doc_analysis_created(translated_row, from_cache=True)
        except HTTPException:
            db.rollback()
            raise
        except Exception:
            db.rollback()

    analysis = models.DocAnalysis(
        user_id=current_user.user_id,
        file_name=name,
        file_size=len(raw),
        file_hash=file_hash,
        output_language=out_lang,
        status="pending",
        progress_stage="pending",
        summary=None,
        risks=None,
        key_details=None,
        analysis_json=None,
    )
    db.add(analysis)
    db.commit()
    db.refresh(analysis)

    background_tasks.add_task(
        run_doc_analysis_job,
        analysis.analysis_id,
        raw,
        name,
        ct,
        out_lang,
    )
    return serialize_doc_analysis_created(analysis, from_cache=False)


@analysis_router.get("/my", response_model=List[schemas.DocAnalysisOut])
def list_my_analyses(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    rows = (
        db.query(models.DocAnalysis)
        .filter(models.DocAnalysis.user_id == current_user.user_id)
        .order_by(models.DocAnalysis.created_at.desc())
        .all()
    )
    return [serialize_doc_analysis(r) for r in rows]


@analysis_router.get("/{analysis_id}/stream")
def stream_analysis_progress(
    analysis_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """
    Server-Sent Events: emits `status` and `progress_stage` about once per second until
    `done` or `failed`. Optional alternative to polling GET /doc-analysis/{id}.
    """
    a = db.get(models.DocAnalysis, analysis_id)
    if not a:
        raise HTTPException(status_code=404, detail="Analysis not found")
    if a.user_id != current_user.user_id:
        raise HTTPException(status_code=403, detail="Access denied")

    def event_generator():
        while True:
            s = SessionLocal()
            try:
                row = s.get(models.DocAnalysis, analysis_id)
                if not row:
                    yield f"data: {json.dumps({'status': 'gone', 'progress_stage': None})}\n\n"
                    break
                payload = {"status": row.status, "progress_stage": row.progress_stage}
                yield f"data: {json.dumps(payload)}\n\n"
                if row.status in ("done", "failed"):
                    break
            finally:
                s.close()
            time.sleep(1.0)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
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
    return serialize_doc_analysis(a)
