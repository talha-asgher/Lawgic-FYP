"""Background processing for structured document analysis."""

from __future__ import annotations

import json
import logging

from app import models
from app.database import SessionLocal
from app.services.document_structured_analysis import (
    build_consolidated_brief,
    generate_structured_analysis,
)
from app.services.document_text_extraction import extract_document_text
from app.services.translation_service import prepare_document_body_for_english_pipeline
from app.services.ollama_service import OllamaServiceError

logger = logging.getLogger(__name__)

STAGE_EXTRACT = "extracting_text"
STAGE_CLAUSES = "analyzing_clauses"
STAGE_RISKS = "checking_risks"
STAGE_SUGGEST = "generating_suggestions"


def _progress(db, analysis_id: int, stage: str) -> None:
    row = db.get(models.DocAnalysis, analysis_id)
    if row:
        row.progress_stage = stage
        db.commit()


def run_doc_analysis_job(
    analysis_id: int,
    file_bytes: bytes,
    file_name: str,
    content_type: str | None,
    output_language: str = "en",
) -> None:
    db = SessionLocal()
    try:
        row = db.get(models.DocAnalysis, analysis_id)
        if not row:
            logger.warning("DocAnalysis id=%s not found", analysis_id)
            return

        row.status = "processing"
        row.progress_stage = STAGE_EXTRACT
        db.commit()

        text = extract_document_text(file_bytes, file_name, content_type)
        if not text.strip():
            raise ValueError(
                "No readable text was extracted. The file may be empty, scanned-only, or corrupted."
            )

        text_body, _doc_tr_meta = prepare_document_body_for_english_pipeline(text)
        _progress(db, analysis_id, STAGE_CLAUSES)
        brief = build_consolidated_brief(text_body)

        _progress(db, analysis_id, STAGE_RISKS)
        payload = generate_structured_analysis(brief, output_language)

        _progress(db, analysis_id, STAGE_SUGGEST)

        row = db.get(models.DocAnalysis, analysis_id)
        if not row:
            return

        row.status = "done"
        row.analysis_json = json.dumps(payload, ensure_ascii=False)
        row.summary = payload.get("summary") or ""
        row.risks = json.dumps([])
        row.key_details = None
        row.progress_stage = None
        db.commit()
    except OllamaServiceError as e:
        logger.warning("Ollama error for analysis %s: %s", analysis_id, e)
        _fail(db, analysis_id, str(e))
    except ValueError as e:
        logger.info("Validation/extraction error for analysis %s: %s", analysis_id, e)
        _fail(db, analysis_id, str(e))
    except Exception as e:
        logger.exception("Unexpected error for analysis %s", analysis_id)
        _fail(db, analysis_id, str(e))
    finally:
        db.close()


def _fail(db, analysis_id: int, message: str) -> None:
    try:
        row = db.get(models.DocAnalysis, analysis_id)
        if not row:
            return
        row.status = "failed"
        row.analysis_json = None
        row.summary = None
        row.risks = None
        row.progress_stage = None
        row.key_details = json.dumps({"error": message[:4000]})
        db.commit()
    except Exception:
        logger.exception("Failed to persist error for analysis %s", analysis_id)
