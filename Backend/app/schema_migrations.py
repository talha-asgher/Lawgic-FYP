"""Lightweight ALTERs for existing DBs (PostgreSQL)."""

from __future__ import annotations

import logging

from sqlalchemy import inspect, text

logger = logging.getLogger(__name__)


def ensure_doc_analysis_columns(engine) -> None:
    if engine.dialect.name != "postgresql":
        return
    with engine.begin() as conn:
        insp = inspect(conn)
        cols = {c["name"] for c in insp.get_columns("doc_analysis")}
        if "file_hash" not in cols:
            logger.info("Adding column doc_analysis.file_hash")
            conn.execute(text("ALTER TABLE doc_analysis ADD COLUMN file_hash VARCHAR(64)"))
        if "progress_stage" not in cols:
            logger.info("Adding column doc_analysis.progress_stage")
            conn.execute(text("ALTER TABLE doc_analysis ADD COLUMN progress_stage TEXT"))
        if "analysis_json" not in cols:
            logger.info("Adding column doc_analysis.analysis_json")
            conn.execute(text("ALTER TABLE doc_analysis ADD COLUMN analysis_json TEXT"))

        insp = inspect(conn)
        cols = {c["name"] for c in insp.get_columns("doc_analysis")}
        if "output_language" not in cols:
            logger.info("Adding column doc_analysis.output_language")
            conn.execute(
                text(
                    "ALTER TABLE doc_analysis ADD COLUMN output_language TEXT NOT NULL DEFAULT 'en'"
                )
            )

        insp = inspect(conn)
        idx_names = {ix["name"] for ix in insp.get_indexes("doc_analysis")}
        if "ix_doc_analysis_user_file_hash" not in idx_names:
            logger.info("Creating index ix_doc_analysis_user_file_hash")
            conn.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS ix_doc_analysis_user_file_hash "
                    "ON doc_analysis (user_id, file_hash)"
                )
            )
        if "ix_doc_analysis_user_hash_lang" not in idx_names:
            logger.info("Creating index ix_doc_analysis_user_hash_lang")
            conn.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS ix_doc_analysis_user_hash_lang "
                    "ON doc_analysis (user_id, file_hash, output_language)"
                )
            )
