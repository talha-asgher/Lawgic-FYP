#!/usr/bin/env python3
"""
Load Lawgic `data/chunking/` JSON exports into Postgres tables:

  law_parent_metadata
  law_child_metadata
  law_child_embeddings
  law_table_metadata
  law_table_embeddings
  law_form_metadata
  law_form_embeddings

Expects DATABASE_URL in .env (same as lawgic_retrieve.py).
Requires: psycopg >= 3, pgvector, python-dotenv

Layout scanned (per category in civil / criminal / family):

  data/chunking/<cat>/parent_chunks/*_parent_chunks.json
  data/chunking/<cat>/child_chunks/*_child_chunks.json
  data/chunking/<cat>/embeddings-bgem3/*_child_chunks_bge_m3_dense.json
  data/chunking/<cat>/table_chunks/*_table_chunks.json          (body text)
  data/chunking/<cat>/table_summaries/*_table_chunks.json       (summary overlay, same stem)
  data/chunking/<cat>/table_embeddings/*_bge_m3_dense.json
  data/chunking/<cat>/form_chunks/*_form_chunks.json
  data/chunking/<cat>/form_summaries/*_form_chunks.json
  data/chunking/<cat>/form_embeddings/*_bge_m3_dense.json

Rows with empty parent_id on tables/forms get a synthetic parent row:
  __orphan__<category>__<slug(act_name)>

Upserts (ON CONFLICT):
  Metadata tables and law_child_embeddings use INSERT ... ON CONFLICT DO UPDATE so
  you can re-run loads safely. law_table_embeddings and law_form_embeddings do the
  same on (table_uid, model_name) and (form_uid, model_name) — you must add the
  UNIQUE constraints in sql/law_schema_notes.sql or equivalent DDL, otherwise
  Postgres will reject those statements.

  Purpose: avoid duplicate embedding rows when re-embedding or re-importing JSON;
  the existing row is updated (e.g. new vector) instead of inserting a second row.

Usage (from RAG project root):

  python scripts/load_data_to_db.py --dry-run
  python scripts/load_data_to_db.py --step all
  python scripts/load_data_to_db.py --step parents,children
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from dotenv import load_dotenv
import psycopg
from pgvector.psycopg import register_vector

SCRIPTS_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPTS_DIR.parent
CHUNKING_ROOT = PROJECT_ROOT / "data" / "chunking"
CATEGORIES = ("civil", "criminal", "family")
DEFAULT_MODEL_NAME = os.environ.get("LAWGIC_EMBED_MODEL", "bge-m3")

load_dotenv(PROJECT_ROOT / ".env")
DB_URL = os.environ.get("DATABASE_URL")
if not DB_URL:
    print("[ERROR] DATABASE_URL not set in .env", file=sys.stderr)
    sys.exit(1)


def slug_act(act_name: str, max_len: int = 120) -> str:
    s = re.sub(r"[^a-zA-Z0-9]+", "_", (act_name or "unknown").strip()).strip("_")
    return (s or "unknown")[:max_len]


def orphan_parent_id(category: str, act_name: str) -> str:
    return f"__orphan__{category}__{slug_act(act_name)}"


def as_int_list(pages: Any) -> List[int]:
    if not pages:
        return []
    out: List[int] = []
    for p in pages:
        try:
            out.append(int(p))
        except (TypeError, ValueError):
            continue
    return out


def as_str_list(xs: Any) -> List[str]:
    if not xs:
        return []
    return [str(x) for x in xs]


def load_json_list(path: Path) -> List[Dict[str, Any]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError(f"Expected JSON list in {path}")
    return data


def iter_json_files(root: Path, pattern: str) -> List[Path]:
    if not root.is_dir():
        return []
    return sorted(root.glob(pattern))


def summary_overlay_map(summary_path: Path) -> Dict[Tuple[str, str], str]:
    """
    Map (parent_id, table_id|form_id) -> summary string from a summaries file.
    """
    out: Dict[Tuple[str, str], str] = {}
    try:
        rows = load_json_list(summary_path)
    except FileNotFoundError:
        return out
    for row in rows:
        meta = row.get("metadata") or {}
        pid = str(meta.get("parent_id") or "").strip()
        tid = str(meta.get("table_id") or meta.get("form_id") or "").strip()
        summ = (row.get("summary") or "").strip()
        if tid and summ:
            out[(pid, tid)] = summ
    return out


def parent_id_overlay_map(summary_path: Path, id_key: str) -> Dict[str, str]:
    """Map table_id / form_id -> parent_id from summaries when chunk JSON omitted parent_id."""
    out: Dict[str, str] = {}
    if not summary_path.is_file():
        return out
    for row in load_json_list(summary_path):
        meta = row.get("metadata") or {}
        tid = str(meta.get(id_key) or "").strip()
        pid = str(meta.get("parent_id") or "").strip()
        if tid and pid:
            out[tid] = pid
    return out


def parse_embedding_suffix(record_id: str) -> Optional[str]:
    """e.g. ACT_table_chunks__TABLE_1 -> TABLE_1"""
    if "__" not in record_id:
        return None
    return record_id.rsplit("__", 1)[-1].strip() or None


class LawTempLoader:
    def __init__(self, chunking_root: Path, dry_run: bool):
        self.chunking_root = chunking_root
        self.dry_run = dry_run
        self._stub_parents_written: Set[str] = set()

    def connect(self):
        conn = psycopg.connect(DB_URL)
        register_vector(conn)
        return conn

    def ensure_stub_parent(
        self,
        cur,
        *,
        synthetic_parent_id: str,
        act_name: str,
        category: str,
    ) -> None:
        if synthetic_parent_id in self._stub_parents_written:
            return
        self._stub_parents_written.add(synthetic_parent_id)
        if self.dry_run:
            print(f"  [dry-run] stub parent {synthetic_parent_id}")
            return
        cur.execute(
            """
            INSERT INTO law_parent_metadata (
                parent_id, act_name, category, section_number, section_title,
                page_numbers, start_pos_raw, end_pos_raw, text,
                table_numbers, form_numbers
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (parent_id) DO NOTHING;
            """,
            (
                synthetic_parent_id,
                act_name,
                category,
                "-",
                "Document root (synthetic)",
                [],
                None,
                None,
                "[Synthetic parent for tables/forms missing parent_id in source JSON.]",
                [],
                [],
            ),
        )

    def load_parents(self, cur) -> int:
        n = 0
        for cat in CATEGORIES:
            d = self.chunking_root / cat / "parent_chunks"
            for path in iter_json_files(d, "*_parent_chunks.json"):
                rows = load_json_list(path)
                for row in rows:
                    meta = row.get("metadata") or {}
                    pid = meta.get("parent_id")
                    if not pid:
                        continue
                    text = (row.get("text") or "").strip()
                    if not text and not self.dry_run:
                        text = "[empty]"
                    rec = (
                        str(pid),
                        str(meta.get("act_name") or ""),
                        str(meta.get("category") or cat),
                        meta.get("section_number"),
                        meta.get("section_title"),
                        as_int_list(meta.get("page_numbers")),
                        meta.get("start_pos_raw"),
                        meta.get("end_pos_raw"),
                        text,
                        as_str_list(meta.get("table_numbers")),
                        as_str_list(meta.get("form_numbers")),
                    )
                    if self.dry_run:
                        n += 1
                        continue
                    cur.execute(
                        """
                        INSERT INTO law_parent_metadata (
                            parent_id, act_name, category, section_number, section_title,
                            page_numbers, start_pos_raw, end_pos_raw, text,
                            table_numbers, form_numbers
                        )
                        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                        ON CONFLICT (parent_id) DO UPDATE SET
                            act_name = EXCLUDED.act_name,
                            category = EXCLUDED.category,
                            section_number = EXCLUDED.section_number,
                            section_title = EXCLUDED.section_title,
                            page_numbers = EXCLUDED.page_numbers,
                            start_pos_raw = EXCLUDED.start_pos_raw,
                            end_pos_raw = EXCLUDED.end_pos_raw,
                            text = EXCLUDED.text,
                            table_numbers = EXCLUDED.table_numbers,
                            form_numbers = EXCLUDED.form_numbers;
                        """,
                        rec,
                    )
                    n += 1
                print(f"  parents <- {path.relative_to(PROJECT_ROOT)} ({len(rows)} rows)")
        return n

    def load_children(self, cur) -> int:
        n = 0
        for cat in CATEGORIES:
            d = self.chunking_root / cat / "child_chunks"
            for path in iter_json_files(d, "*_child_chunks.json"):
                rows = load_json_list(path)
                for row in rows:
                    meta = row.get("metadata") or {}
                    cid = meta.get("child_id")
                    pid = meta.get("parent_id")
                    if not cid or not pid:
                        continue
                    text = (row.get("text") or "").strip()
                    if not text and not self.dry_run:
                        text = "[empty]"
                    footnotes = row.get("footnotes")
                    if footnotes is None:
                        footnotes = []
                    if self.dry_run:
                        n += 1
                        continue
                    cur.execute(
                        """
                        INSERT INTO law_child_metadata (
                            child_id, parent_id, act_name, category,
                            section_number, section_title, page_numbers,
                            start_pos_raw, end_pos_raw, text, footnotes
                        )
                        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb)
                        ON CONFLICT (child_id) DO UPDATE SET
                            parent_id = EXCLUDED.parent_id,
                            act_name = EXCLUDED.act_name,
                            category = EXCLUDED.category,
                            section_number = EXCLUDED.section_number,
                            section_title = EXCLUDED.section_title,
                            page_numbers = EXCLUDED.page_numbers,
                            start_pos_raw = EXCLUDED.start_pos_raw,
                            end_pos_raw = EXCLUDED.end_pos_raw,
                            text = EXCLUDED.text,
                            footnotes = EXCLUDED.footnotes;
                        """,
                        (
                            str(cid),
                            str(pid),
                            str(meta.get("act_name") or ""),
                            str(meta.get("category") or cat),
                            meta.get("section_number"),
                            meta.get("section_title"),
                            as_int_list(meta.get("page_numbers")),
                            meta.get("start_pos_raw"),
                            meta.get("end_pos_raw"),
                            text,
                            json.dumps(footnotes),
                        ),
                    )
                    n += 1
                print(f"  children <- {path.relative_to(PROJECT_ROOT)} ({len(rows)} rows)")
        return n

    def load_child_embeddings(self, cur) -> int:
        n = 0
        for cat in CATEGORIES:
            d = self.chunking_root / cat / "embeddings-bgem3"
            for path in iter_json_files(d, "*_child_chunks_bge_m3_dense.json"):
                rows = load_json_list(path)
                for row in rows:
                    cid = row.get("id")
                    emb = row.get("embedding")
                    if not cid or not emb:
                        continue
                    if self.dry_run:
                        n += 1
                        continue
                    cur.execute(
                        """
                        INSERT INTO law_child_embeddings (child_id, model_name, embedding)
                        VALUES (%s, %s, %s)
                        ON CONFLICT (child_id, model_name) DO UPDATE SET
                            embedding = EXCLUDED.embedding;
                        """,
                        (str(cid), DEFAULT_MODEL_NAME, emb),
                    )
                    n += 1
                print(f"  child_embeddings <- {path.relative_to(PROJECT_ROOT)} ({len(rows)} rows)")
        return n

    def load_tables(self, cur) -> Tuple[int, Dict[Tuple[str, str], Any]]:
        """
        Returns count and map (parent_id, table_local_id) -> table_uid (UUID from DB).
        """
        n = 0
        uid_map: Dict[Tuple[str, str], Any] = {}
        for cat in CATEGORIES:
            tc = self.chunking_root / cat / "table_chunks"
            ts = self.chunking_root / cat / "table_summaries"
            for path in iter_json_files(tc, "*_table_chunks.json"):
                summ_path = ts / path.name
                overlay = summary_overlay_map(summ_path)
                pid_by_table = parent_id_overlay_map(summ_path, "table_id")
                rows = load_json_list(path)
                for row in rows:
                    meta = row.get("metadata") or {}
                    local_id = str(meta.get("table_id") or "").strip()
                    if not local_id:
                        continue
                    act_name = str(meta.get("act_name") or "")
                    pid = str(meta.get("parent_id") or "").strip()
                    if not pid:
                        pid = str(pid_by_table.get(local_id) or "").strip()
                    if not pid:
                        pid = orphan_parent_id(cat, act_name)
                        self.ensure_stub_parent(cur, synthetic_parent_id=pid, act_name=act_name, category=cat)
                    summary = (row.get("summary") or "").strip()
                    if not summary:
                        orig_pid = str(meta.get("parent_id") or "").strip()
                        for okey in ((orig_pid, local_id), ("", local_id), (pid, local_id)):
                            summary = overlay.get(okey, "")
                            if summary:
                                break
                    text = (row.get("text") or "").strip()
                    if not text and not self.dry_run:
                        text = "[empty]"
                    key = (pid, local_id)
                    if self.dry_run:
                        n += 1
                        uid_map[key] = None
                        continue
                    cur.execute(
                        """
                        INSERT INTO law_table_metadata (
                            table_local_id, parent_id, act_name, category,
                            section_number, section_title, table_index_in_section,
                            page_numbers, page, text, summary, pdf_path
                        )
                        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                        ON CONFLICT (parent_id, table_local_id) DO UPDATE SET
                            act_name = EXCLUDED.act_name,
                            category = EXCLUDED.category,
                            section_number = EXCLUDED.section_number,
                            section_title = EXCLUDED.section_title,
                            table_index_in_section = EXCLUDED.table_index_in_section,
                            page_numbers = EXCLUDED.page_numbers,
                            page = EXCLUDED.page,
                            text = EXCLUDED.text,
                            summary = EXCLUDED.summary,
                            pdf_path = EXCLUDED.pdf_path
                        RETURNING table_uid;
                        """,
                        (
                            local_id,
                            pid,
                            act_name,
                            str(meta.get("category") or cat),
                            meta.get("section_number"),
                            meta.get("section_title"),
                            meta.get("table_index_in_section"),
                            as_int_list(meta.get("page_numbers")),
                            meta.get("page"),
                            text,
                            summary or None,
                            meta.get("pdf_path"),
                        ),
                    )
                    uid = cur.fetchone()[0]
                    uid_map[key] = uid
                    n += 1
                print(f"  tables <- {path.relative_to(PROJECT_ROOT)} ({len(rows)} rows)")
        return n, uid_map

    def load_table_embeddings(self, cur, uid_map: Dict[Tuple[str, str], Any]) -> int:
        n = 0
        for cat in CATEGORIES:
            d = self.chunking_root / cat / "table_embeddings"
            for path in iter_json_files(d, "*_bge_m3_dense.json"):
                rows = load_json_list(path)
                for row in rows:
                    emb = row.get("embedding")
                    if not emb:
                        continue
                    pid = str(row.get("parent_id") or "").strip()
                    local = parse_embedding_suffix(str(row.get("id") or ""))
                    if not local:
                        local = str(row.get("table_id") or "").strip()
                    if not pid:
                        act_name = str(row.get("act_name") or "")
                        pid = orphan_parent_id(cat, act_name)
                    key = (pid, local)
                    table_uid = uid_map.get(key)
                    if table_uid is None and not self.dry_run:
                        cur.execute(
                            "SELECT table_uid FROM law_table_metadata WHERE parent_id = %s AND table_local_id = %s",
                            (pid, local),
                        )
                        r = cur.fetchone()
                        table_uid = r[0] if r else None
                    if not table_uid and not self.dry_run:
                        print(f"    [WARN] skip table embedding (no row): parent_id={pid!r} table_local_id={local!r}")
                        continue
                    if self.dry_run:
                        n += 1
                        continue
                    cur.execute(
                        """
                        INSERT INTO law_table_embeddings (table_uid, model_name, embedding)
                        VALUES (%s, %s, %s)
                        ON CONFLICT (table_uid, model_name) DO UPDATE SET
                            embedding = EXCLUDED.embedding;
                        """,
                        (table_uid, DEFAULT_MODEL_NAME, emb),
                    )
                    n += 1
                print(f"  table_embeddings <- {path.relative_to(PROJECT_ROOT)} ({len(rows)} rows)")
        return n

    def load_forms(self, cur) -> Tuple[int, Dict[Tuple[str, str], Any]]:
        n = 0
        uid_map: Dict[Tuple[str, str], Any] = {}
        for cat in CATEGORIES:
            fc = self.chunking_root / cat / "form_chunks"
            fs = self.chunking_root / cat / "form_summaries"
            for path in iter_json_files(fc, "*_form_chunks.json"):
                summ_path = fs / path.name
                overlay = summary_overlay_map(summ_path)
                pid_by_form = parent_id_overlay_map(summ_path, "form_id")
                rows = load_json_list(path)
                for row in rows:
                    meta = row.get("metadata") or {}
                    local_id = str(meta.get("form_id") or "").strip()
                    if not local_id:
                        continue
                    act_name = str(meta.get("act_name") or "")
                    pid = str(meta.get("parent_id") or "").strip()
                    if not pid:
                        pid = str(pid_by_form.get(local_id) or "").strip()
                    if not pid:
                        pid = orphan_parent_id(cat, act_name)
                        self.ensure_stub_parent(cur, synthetic_parent_id=pid, act_name=act_name, category=cat)
                    summary = (row.get("summary") or "").strip()
                    if not summary:
                        orig_pid = str(meta.get("parent_id") or "").strip()
                        for okey in ((orig_pid, local_id), ("", local_id), (pid, local_id)):
                            summary = overlay.get(okey, "")
                            if summary:
                                break
                    text = (row.get("text") or "").strip()
                    if not text and not self.dry_run:
                        text = "[empty]"
                    key = (pid, local_id)
                    if self.dry_run:
                        n += 1
                        uid_map[key] = None
                        continue
                    cur.execute(
                        """
                        INSERT INTO law_form_metadata (
                            form_local_id, parent_id, act_name, category,
                            section_number, section_title, form_index_in_section,
                            page_numbers, page, text, summary, pdf_path
                        )
                        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                        ON CONFLICT (parent_id, form_local_id) DO UPDATE SET
                            act_name = EXCLUDED.act_name,
                            category = EXCLUDED.category,
                            section_number = EXCLUDED.section_number,
                            section_title = EXCLUDED.section_title,
                            form_index_in_section = EXCLUDED.form_index_in_section,
                            page_numbers = EXCLUDED.page_numbers,
                            page = EXCLUDED.page,
                            text = EXCLUDED.text,
                            summary = EXCLUDED.summary,
                            pdf_path = EXCLUDED.pdf_path
                        RETURNING form_uid;
                        """,
                        (
                            local_id,
                            pid,
                            act_name,
                            str(meta.get("category") or cat),
                            meta.get("section_number"),
                            meta.get("section_title"),
                            meta.get("form_index_in_section"),
                            as_int_list(meta.get("page_numbers")),
                            meta.get("page"),
                            text,
                            summary or None,
                            meta.get("pdf_path"),
                        ),
                    )
                    uid = cur.fetchone()[0]
                    uid_map[key] = uid
                    n += 1
                print(f"  forms <- {path.relative_to(PROJECT_ROOT)} ({len(rows)} rows)")
        return n, uid_map

    def load_form_embeddings(self, cur, uid_map: Dict[Tuple[str, str], Any]) -> int:
        n = 0
        for cat in CATEGORIES:
            d = self.chunking_root / cat / "form_embeddings"
            for path in iter_json_files(d, "*_bge_m3_dense.json"):
                rows = load_json_list(path)
                for row in rows:
                    emb = row.get("embedding")
                    if not emb:
                        continue
                    pid = str(row.get("parent_id") or "").strip()
                    local = parse_embedding_suffix(str(row.get("id") or ""))
                    if not local:
                        local = str(row.get("form_id") or "").strip()
                    if not pid:
                        act_name = str(row.get("act_name") or "")
                        pid = orphan_parent_id(cat, act_name)
                    key = (pid, local)
                    form_uid = uid_map.get(key)
                    if form_uid is None and not self.dry_run:
                        cur.execute(
                            "SELECT form_uid FROM law_form_metadata WHERE parent_id = %s AND form_local_id = %s",
                            (pid, local),
                        )
                        r = cur.fetchone()
                        form_uid = r[0] if r else None
                    if not form_uid and not self.dry_run:
                        print(f"    [WARN] skip form embedding (no row): parent_id={pid!r} form_local_id={local!r}")
                        continue
                    if self.dry_run:
                        n += 1
                        continue
                    cur.execute(
                        """
                        INSERT INTO law_form_embeddings (form_uid, model_name, embedding)
                        VALUES (%s, %s, %s)
                        ON CONFLICT (form_uid, model_name) DO UPDATE SET
                            embedding = EXCLUDED.embedding;
                        """,
                        (form_uid, DEFAULT_MODEL_NAME, emb),
                    )
                    n += 1
                print(f"  form_embeddings <- {path.relative_to(PROJECT_ROOT)} ({len(rows)} rows)")
        return n


def parse_steps(s: str) -> Set[str]:
    allowed = {
        "all",
        "parents",
        "children",
        "child_embeddings",
        "tables",
        "table_embeddings",
        "forms",
        "form_embeddings",
    }
    parts = {p.strip() for p in s.split(",") if p.strip()}
    if "all" in parts:
        return {
            "parents",
            "children",
            "child_embeddings",
            "tables",
            "table_embeddings",
            "forms",
            "form_embeddings",
        }
    bad = parts - allowed
    if bad:
        raise SystemExit(f"Unknown --step value(s): {bad}")
    return parts


def main() -> None:
    parser = argparse.ArgumentParser(description="Load data/chunking JSON into law_* Postgres tables.")
    parser.add_argument(
        "--chunking-root",
        type=Path,
        default=None,
        help="Root folder with civil/criminal/family subdirs (default: RAG/data/chunking)",
    )
    parser.add_argument(
        "--temp-root",
        type=Path,
        default=None,
        help="Deprecated: same as --chunking-root (legacy name)",
    )
    parser.add_argument("--dry-run", action="store_true", help="Parse files only; no DB writes.")
    parser.add_argument(
        "--step",
        type=str,
        default="all",
        help="Comma list: parents,children,child_embeddings,tables,table_embeddings,forms,form_embeddings,all",
    )
    args = parser.parse_args()

    steps = parse_steps(args.step)
    chunking_root = args.chunking_root or args.temp_root or CHUNKING_ROOT
    loader = LawTempLoader(chunking_root.resolve(), dry_run=args.dry_run)

    print(f"[INFO] chunking root: {loader.chunking_root}")
    print(f"[INFO] steps: {sorted(steps)}")
    print(f"[INFO] model_name: {DEFAULT_MODEL_NAME}")
    if args.dry_run:
        print("[INFO] dry-run: no database connection")

    table_uid_map: Dict[Tuple[str, str], Any] = {}
    form_uid_map: Dict[Tuple[str, str], Any] = {}

    def run():
        nonlocal table_uid_map, form_uid_map
        if "parents" in steps:
            print("\n== law_parent_metadata ==")
            loader.load_parents(cur)
        if "children" in steps:
            print("\n== law_child_metadata ==")
            loader.load_children(cur)
        if "child_embeddings" in steps:
            print("\n== law_child_embeddings ==")
            loader.load_child_embeddings(cur)
        if "tables" in steps:
            print("\n== law_table_metadata ==")
            _, table_uid_map = loader.load_tables(cur)
        if "table_embeddings" in steps:
            print("\n== law_table_embeddings ==")
            if not table_uid_map and "tables" not in steps:
                print("  (loading table_uid map from DB for FK resolution)")
                if not args.dry_run:
                    cur.execute(
                        "SELECT parent_id, table_local_id, table_uid FROM law_table_metadata"
                    )
                    for r in cur.fetchall():
                        table_uid_map[(r[0], r[1])] = r[2]
            loader.load_table_embeddings(cur, table_uid_map)
        if "forms" in steps:
            print("\n== law_form_metadata ==")
            _, form_uid_map = loader.load_forms(cur)
        if "form_embeddings" in steps:
            print("\n== law_form_embeddings ==")
            if not form_uid_map and "forms" not in steps:
                if not args.dry_run:
                    cur.execute(
                        "SELECT parent_id, form_local_id, form_uid FROM law_form_metadata"
                    )
                    for r in cur.fetchall():
                        form_uid_map[(r[0], r[1])] = r[2]
            loader.load_form_embeddings(cur, form_uid_map)

    if args.dry_run:
        class Dummy:
            def execute(self, *a, **k):
                pass

            def fetchone(self):
                return [None]

            def fetchall(self):
                return []

        cur = Dummy()
        run()
        print("\n[dry-run] finished.")
        return

    with loader.connect() as conn:
        conn.autocommit = False
        with conn.cursor() as cur:
            try:
                run()
                conn.commit()
            except Exception:
                conn.rollback()
                raise
        print("\n[INFO] committed.")

    print("[INFO] done.")


if __name__ == "__main__":
    main()
