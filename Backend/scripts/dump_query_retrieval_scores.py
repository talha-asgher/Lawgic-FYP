"""
Run retrieval for a fixed query and write TSV with score breakdown.
Usage (from repo root):  python Backend/scripts/dump_query_retrieval_scores.py
"""
from __future__ import annotations

import csv
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]
_BACKEND = _REPO / "Backend"
sys.path.insert(0, str(_BACKEND))

QUERY = "If a man marries a minor girl, what punishment can he face?"
OUT_PATH = _BACKEND / "query_retrieval_minor_marriage_scores.tsv"
TOP_K = 25


def main() -> None:
    from app.database import SessionLocal
    from app.services.query_embedder import embed_query_text
    from app.services.retrieval_service import RetrievalService

    db = SessionLocal()
    try:
        vec = embed_query_text(QUERY)
        svc = RetrievalService()
        resp = svc.retrieve(db=db, query=QUERY, query_embedding=vec, top_k=TOP_K)
        rows = []
        for r in resp.results:
            rows.append(
                {
                    "section_number": r.section_number or "",
                    "section_title": (r.section_title or "").replace("\t", " ").replace("\n", " "),
                    "final_score": round(float(r.score), 6),
                    "dense_norm": round(float(r.dense_norm or 0.0), 6),
                    "bm25_norm": round(float(r.bm25_norm or 0.0), 6),
                    "metadata_boost": round(float(r.metadata_boost or 0.0), 6),
                }
            )
        OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
        with OUT_PATH.open("w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(
                f,
                fieldnames=[
                    "section_number",
                    "section_title",
                    "final_score",
                    "dense_norm",
                    "bm25_norm",
                    "metadata_boost",
                ],
                delimiter="\t",
            )
            w.writeheader()
            w.writerows(rows)
        print(f"Wrote {len(rows)} rows to {OUT_PATH}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
