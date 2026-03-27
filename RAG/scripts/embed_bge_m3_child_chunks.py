#!/usr/bin/env python3
"""
Embed child chunks and/or table & form summaries using BGE-M3.

Child chunks (default --mode child):
  data/chunking/{civil,criminal,family}/child_chunks/*_child_chunks.json
  -> data/chunking/<category>/embeddings-bgem3/<stem>_bge_m3_dense.json

Table summaries (--mode table or summaries):
  data/chunking/<category>/table_summaries/*_table_chunks.json
  -> data/chunking/<category>/table_embeddings/<stem>_bge_m3_dense.json

Form summaries (--mode form or summaries):
  data/chunking/<category>/form_summaries/*_form_chunks.json
  -> data/chunking/<category>/form_embeddings/<stem>_bge_m3_dense.json

Features:
- --mode child: If --file is set, process one child file; else scan child_chunks with resume marker.
- --mode table / form / summaries: scan corresponding summary folders with separate resume markers.
- Embedded text for summaries = Act/Section header lines + the summary field (for better retrieval).

Example usages (run from RAG project root):

    python scripts/embed_bge_m3_child_chunks.py \
        --file data/chunking/civil/child_chunks/ISLAMABAD_CONSUMERS_PROTECTION_ACT,_1995_child_chunks.json

    python scripts/embed_bge_m3_child_chunks.py

    python scripts/embed_bge_m3_child_chunks.py --mode table
    python scripts/embed_bge_m3_child_chunks.py --mode form
    python scripts/embed_bge_m3_child_chunks.py --mode summaries
"""

import argparse
import json
import sys
from pathlib import Path
from typing import List, Dict, Any, Optional

import torch
from FlagEmbedding import BGEM3FlagModel


# -------------------- PATHS & CONSTANTS --------------------

# This script lives in Lawgic-1/scripts/, so project root is one level up
SCRIPTS_DIR = Path(__file__).parent.resolve()
PROJECT_ROOT = SCRIPTS_DIR.parent

# Chunked JSON layout: data/chunking/<category>/...
CHUNKING_ROOT = PROJECT_ROOT / "data" / "chunking"
BASE_CHUNKS_DIR = CHUNKING_ROOT
CATEGORIES = ["civil", "criminal", "family"]

# Resume markers (shared across categories)
EMBED_ROOT = CHUNKING_ROOT / "embeddings-bgem3"
LAST_PROCESSED_MARKER = EMBED_ROOT / "last_processed_child_file.txt"
LAST_PROCESSED_TABLE_MARKER = EMBED_ROOT / "last_processed_table_summary_file.txt"
LAST_PROCESSED_FORM_MARKER = EMBED_ROOT / "last_processed_form_summary_file.txt"


# -------------------- MODEL WRAPPER --------------------

class BgeM3Embedder:
    def __init__(self, model_name: str = "BAAI/bge-m3", device: Optional[str] = None):
        if device is None:
            device = "cuda" if torch.cuda.is_available() else "cpu"

        self.device = device
        self.model = BGEM3FlagModel(
            model_name,
            use_fp16=(device == "cuda"),
            device=device,
        )

    def embed_texts(self, texts: List[str], batch_size: int = 32) -> List[List[float]]:
        """
        Compute dense embeddings for a list of texts.
        Returns: list of 1024-dim vectors (as Python lists of floats).
        """
        outputs = self.model.encode(
            texts,
            batch_size=batch_size,
            max_length=2048,      # your chunks are not huge; 2048 is enough
            return_dense=True,
            return_sparse=False,
            return_colbert_vecs=False,
        )
        dense_vecs = outputs["dense_vecs"]
        return [vec.tolist() for vec in dense_vecs]


# -------------------- UTILS: FILE DISCOVERY & MARKER --------------------

def find_all_child_chunk_files() -> List[Path]:
    """
    Find all *_child_chunks.json under:
        data/chunking/{civil,criminal,family}/child_chunks

    Returns a list of RELATIVE paths (relative to PROJECT_ROOT), sorted.
    """
    files: List[Path] = []

    for cat in CATEGORIES:
        child_dir = BASE_CHUNKS_DIR / cat / "child_chunks"
        if not child_dir.exists():
            continue
        for path in sorted(child_dir.glob("*_child_chunks.json")):
            files.append(path.relative_to(PROJECT_ROOT))

    # Sort once more in case categories influence order
    files = sorted(files, key=lambda p: str(p))
    return files


def find_all_table_summary_files() -> List[Path]:
    files: List[Path] = []
    for cat in CATEGORIES:
        d = BASE_CHUNKS_DIR / cat / "table_summaries"
        if not d.is_dir():
            continue
        for path in sorted(d.glob("*_table_chunks.json")):
            files.append(path.relative_to(PROJECT_ROOT))
    return sorted(files, key=lambda p: str(p))


def find_all_form_summary_files() -> List[Path]:
    files: List[Path] = []
    for cat in CATEGORIES:
        d = BASE_CHUNKS_DIR / cat / "form_summaries"
        if not d.is_dir():
            continue
        for path in sorted(d.glob("*_form_chunks.json")):
            files.append(path.relative_to(PROJECT_ROOT))
    return sorted(files, key=lambda p: str(p))


def load_last_processed_rel() -> Optional[Path]:
    """
    Read the last processed file path (relative to PROJECT_ROOT) from marker.
    Returns None if marker does not exist or is empty.
    """
    if not LAST_PROCESSED_MARKER.exists():
        return None
    content = LAST_PROCESSED_MARKER.read_text(encoding="utf-8").strip()
    if not content:
        return None
    return Path(content)


def save_last_processed_rel(rel_path: Path) -> None:
    """
    Save the last processed file path (relative to PROJECT_ROOT) to the marker.
    """
    EMBED_ROOT.mkdir(parents=True, exist_ok=True)
    LAST_PROCESSED_MARKER.write_text(str(rel_path), encoding="utf-8")


def load_marker(marker_path: Path) -> Optional[Path]:
    if not marker_path.exists():
        return None
    content = marker_path.read_text(encoding="utf-8").strip()
    if not content:
        return None
    return Path(content)


def save_marker(marker_path: Path, rel_path: Path) -> None:
    EMBED_ROOT.mkdir(parents=True, exist_ok=True)
    marker_path.write_text(str(rel_path), encoding="utf-8")


# -------------------- CORE: LOAD, EMBED, SAVE --------------------

def load_child_chunks(child_chunks_path: Path) -> List[Dict[str, Any]]:
    if not child_chunks_path.exists():
        print(f"[ERROR] Child chunks file not found: {child_chunks_path}")
        sys.exit(1)
    with child_chunks_path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, list):
        print(f"[ERROR] Child chunks file does not contain a list: {child_chunks_path}")
        sys.exit(1)
    return data


def infer_category_from_chunks(child_chunks: List[Dict[str, Any]]) -> str:
    """
    Use metadata.category from the first non-empty chunk, fallback to 'unknown'.
    """
    for chunk in child_chunks:
        meta = chunk.get("metadata") or {}
        cat = meta.get("category")
        if cat:
            return str(cat).lower()
    return "unknown"


def build_output_records(
    child_chunks: List[Dict[str, Any]],
    embeddings: List[Optional[List[float]]],
) -> List[Dict[str, Any]]:
    """
    Combine child chunk text + metadata + embedding into a list of records.

    Uses metadata keys seen in your sample JSON:
      - child_id, parent_id, act_name, section_number, section_title, category,
        page_numbers, start_pos_raw, end_pos_raw
    """
    records: List[Dict[str, Any]] = []

    for chunk, emb in zip(child_chunks, embeddings):
        if emb is None:
            # Skip chunks that had no text / no embedding
            continue

        text = (chunk.get("text") or "").strip()
        if not text:
            continue

        metadata = chunk.get("metadata", {}) or {}

        record = {
            "id": metadata.get("child_id"),
            "parent_id": metadata.get("parent_id"),
            "act_name": metadata.get("act_name"),
            "section_number": metadata.get("section_number"),
            "section_title": metadata.get("section_title") or metadata.get("section_name"),
            "category": metadata.get("category"),
            "page_numbers": metadata.get("page_numbers"),
            "start_pos_raw": metadata.get("start_pos_raw"),
            "end_pos_raw": metadata.get("end_pos_raw"),
            "text": text,
            "embedding": emb,
        }
        records.append(record)

    return records


def build_summary_embed_text(item: Dict[str, Any], kind: str) -> str:
    """
    Text to embed for a table/form summary row: metadata header + summary body.
    """
    meta = item.get("metadata") or {}
    parts: List[str] = []
    act = str(meta.get("act_name") or "").strip()
    if act:
        parts.append(f"Act: {act}")
    sec = str(meta.get("section_number") or "").strip()
    title = str(meta.get("section_title") or "").strip()
    if sec and sec != "-":
        parts.append(f"Section: {sec}" + (f" — {title}" if title else ""))
    elif title:
        parts.append(f"Section title: {title}")
    cat = str(meta.get("category") or "").strip()
    if cat:
        parts.append(f"Category: {cat}")
    if kind == "table":
        tid = str(meta.get("table_id") or "").strip()
        if tid:
            parts.append(f"Table: {tid}")
    else:
        fid = str(meta.get("form_id") or "").strip()
        if fid:
            parts.append(f"Form: {fid}")
    summary = (item.get("summary") or "").strip()
    if not summary:
        return ""
    parts.append(summary)
    return "\n".join(parts)


def build_table_form_records(
    items: List[Dict[str, Any]],
    embeddings: List[Optional[List[float]]],
    kind: str,
    source_rel: Path,
) -> List[Dict[str, Any]]:
    """Records for table_embeddings / form_embeddings JSON output."""
    file_stem = source_rel.stem
    records: List[Dict[str, Any]] = []

    for idx, (item, emb) in enumerate(zip(items, embeddings)):
        if emb is None:
            continue
        summary = (item.get("summary") or "").strip()
        if not summary:
            continue
        meta = item.get("metadata") or {}
        tid = meta.get("table_id") if kind == "table" else None
        fid = meta.get("form_id") if kind == "form" else None
        slot = tid or fid or f"idx{idx}"
        record_id = f"{file_stem}__{slot}"

        record: Dict[str, Any] = {
            "id": record_id,
            "kind": kind,
            "source_file": str(source_rel).replace("\\", "/"),
            "parent_id": meta.get("parent_id"),
            "act_name": meta.get("act_name"),
            "section_number": meta.get("section_number"),
            "section_title": meta.get("section_title") or meta.get("section_name"),
            "category": meta.get("category"),
            "page_numbers": meta.get("page_numbers"),
            "summary": summary,
            "embed_text": build_summary_embed_text(item, kind),
            "embedding": emb,
        }
        if kind == "table":
            record["table_id"] = tid
        else:
            record["form_id"] = fid
        records.append(record)

    return records


def embed_single_summary_file(
    rel_path: Path,
    embedder: BgeM3Embedder,
    kind: str,
    overwrite: bool = False,
) -> None:
    """
    Embed one table_summaries or form_summaries JSON file.
    kind: 'table' | 'form'
    """
    abs_path = PROJECT_ROOT / rel_path
    print(f"\n[INFO] Processing ({kind} summaries): {abs_path}")

    items = load_child_chunks(abs_path)  # same list-of-dicts shape
    if not items:
        print("[WARN] No items; skipping.")
        return

    category = infer_category_from_chunks(items)
    if category not in CATEGORIES:
        print(f"[WARN] Unknown category '{category}', storing under that folder name.")

    subdir = "table_embeddings" if kind == "table" else "form_embeddings"
    out_dir = CHUNKING_ROOT / category / subdir
    out_dir.mkdir(parents=True, exist_ok=True)
    out_name = f"{abs_path.stem}_bge_m3_dense.json"
    out_path = out_dir / out_name

    if out_path.exists() and not overwrite:
        print(f"[INFO] Output exists, skipping (use --overwrite): {out_path}")
        marker = LAST_PROCESSED_TABLE_MARKER if kind == "table" else LAST_PROCESSED_FORM_MARKER
        save_marker(marker, rel_path)
        return

    texts: List[str] = []
    valid_indices: List[int] = []
    for idx, item in enumerate(items):
        t = build_summary_embed_text(item, kind)
        if not t.strip():
            continue
        texts.append(t)
        valid_indices.append(idx)

    if not texts:
        print("[WARN] No non-empty summaries to embed; skipping.")
        marker = LAST_PROCESSED_TABLE_MARKER if kind == "table" else LAST_PROCESSED_FORM_MARKER
        save_marker(marker, rel_path)
        return

    print(f"[INFO] Computing embeddings for {len(texts)} summary rows...")
    dense_vecs = embedder.embed_texts(texts, batch_size=32)

    embeddings: List[Optional[List[float]]] = [None] * len(items)
    for emb, vidx in zip(dense_vecs, valid_indices):
        embeddings[vidx] = emb

    records = build_table_form_records(items, embeddings, kind, rel_path)
    print(f"[INFO] Saving {len(records)} records to: {out_path}")
    with out_path.open("w", encoding="utf-8") as f:
        json.dump(records, f, ensure_ascii=False, indent=2)

    marker = LAST_PROCESSED_TABLE_MARKER if kind == "table" else LAST_PROCESSED_FORM_MARKER
    save_marker(marker, rel_path)
    print(f"[INFO] Updated marker: {marker.name} -> {rel_path}")


def run_summary_embedding_loop(
    embedder: BgeM3Embedder,
    kind: str,
    overwrite: bool,
    single_file: Optional[str],
) -> None:
    marker = LAST_PROCESSED_TABLE_MARKER if kind == "table" else LAST_PROCESSED_FORM_MARKER
    find_fn = find_all_table_summary_files if kind == "table" else find_all_form_summary_files

    if single_file:
        input_path = Path(single_file)
        if not input_path.is_absolute():
            input_path = PROJECT_ROOT / input_path
        if not input_path.exists():
            print(f"[ERROR] File not found: {input_path}")
            sys.exit(1)
        rel = input_path.relative_to(PROJECT_ROOT)
        embed_single_summary_file(rel, embedder, kind, overwrite=overwrite)
        return

    all_files = find_fn()
    if not all_files:
        print(f"[ERROR] No {'table' if kind == 'table' else 'form'} summary files found.")
        sys.exit(1)

    last_rel = load_marker(marker)
    start_index = 0
    if last_rel is not None:
        print(f"[INFO] Last processed ({kind}): {last_rel}")
        if last_rel in all_files:
            start_index = all_files.index(last_rel) + 1
        else:
            print("[WARN] Marker path not in file list; starting from beginning.")

    if start_index >= len(all_files):
        print(f"[INFO] All {kind} summary files already processed.")
        return

    print(f"[INFO] {kind} summaries: {len(all_files) - start_index} file(s) to process.")
    for rel_path in all_files[start_index:]:
        embed_single_summary_file(rel_path, embedder, kind, overwrite=overwrite)
    print(f"[INFO] Finished {kind} summary embedding.")


def embed_single_child_file(
    rel_child_file: Path,
    embedder: BgeM3Embedder,
    overwrite: bool = False,
) -> None:
    """
    Process ONE child_chunks JSON file (path relative to PROJECT_ROOT).

    Steps:
    - Load child chunks
    - Infer category from metadata
    - Build output path
    - Compute BGE-M3 embeddings for each chunk's text
    - Save result as JSON with text + metadata + embedding
    """
    abs_child_path = PROJECT_ROOT / rel_child_file
    print(f"\n[INFO] Processing: {abs_child_path}")

    child_chunks = load_child_chunks(abs_child_path)
    if not child_chunks:
        print("[WARN] No chunks in this file; skipping.")
        return

    category = infer_category_from_chunks(child_chunks)
    if category not in CATEGORIES:
        print(f"[WARN] Unknown category '{category}', will still embed and store under that folder.")

    # Output dir + file
    out_dir = CHUNKING_ROOT / category / "embeddings-bgem3"
    out_dir.mkdir(parents=True, exist_ok=True)

    out_name = f"{abs_child_path.stem}_bge_m3_dense.json"
    out_path = out_dir / out_name

    if out_path.exists() and not overwrite:
        print(f"[INFO] Output already exists, skipping (use --overwrite to force): {out_path}")
        # Still update marker so resume jumps after this file
        save_last_processed_rel(rel_child_file)
        print(f"[INFO] Updated last processed marker to: {rel_child_file}")
        return

    # Collect texts & maintain alignment
    texts: List[str] = []
    valid_indices: List[int] = []
    for idx, chunk in enumerate(child_chunks):
        text = (chunk.get("text") or "").strip()
        if not text:
            continue
        texts.append(text)
        valid_indices.append(idx)

    if not texts:
        print("[WARN] All chunks have empty text; nothing to embed.")
        save_last_processed_rel(rel_child_file)
        return

    print(f"[INFO] Computing embeddings for {len(texts)} non-empty child chunks...")
    dense_vecs = embedder.embed_texts(texts, batch_size=32)

    # Build full embedding list aligned with original list
    embeddings: List[Optional[List[float]]] = [None] * len(child_chunks)
    for emb, idx in zip(dense_vecs, valid_indices):
        embeddings[idx] = emb

    records = build_output_records(child_chunks, embeddings)

    print(f"[INFO] Saving {len(records)} embedded records to: {out_path}")
    with out_path.open("w", encoding="utf-8") as f:
        json.dump(records, f, ensure_ascii=False, indent=2)

    # Update marker
    save_last_processed_rel(rel_child_file)
    print(f"[INFO] Updated last processed marker to: {rel_child_file}")


# -------------------- MAIN / CLI --------------------

def main():
    parser = argparse.ArgumentParser(
        description="Embed child chunks and/or table & form summaries with BGE-M3."
    )
    parser.add_argument(
        "--mode",
        type=str,
        choices=["child", "table", "form", "summaries"],
        default="child",
        help=(
            "child: embed child_chunks (default). "
            "table: embed data/chunking/*/table_summaries/*_table_chunks.json -> table_embeddings. "
            "form: embed data/chunking/*/form_summaries/*_form_chunks.json -> form_embeddings. "
            "summaries: run table then form."
        ),
    )
    parser.add_argument(
        "--file",
        type=str,
        default=None,
        help=(
            "For --mode child: one *_child_chunks.json path. "
            "For --mode table|form|summaries: one summary JSON under table_summaries or form_summaries "
            "(summaries mode uses this only for the first pass that matches the path)."
        ),
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="If set, overwrite existing embedding JSON files.",
    )

    args = parser.parse_args()

    # Initialize model once
    print("[INFO] Loading BGE-M3 model...")
    embedder = BgeM3Embedder()
    print("[INFO] Model ready.")

    if args.mode == "table":
        run_summary_embedding_loop(embedder, "table", args.overwrite, args.file)
        return
    if args.mode == "form":
        run_summary_embedding_loop(embedder, "form", args.overwrite, args.file)
        return
    if args.mode == "summaries":
        # Optional single file: route to table or form by path substring
        if args.file:
            fp = args.file.replace("\\", "/").lower()
            if "table_summaries" in fp:
                run_summary_embedding_loop(embedder, "table", args.overwrite, args.file)
                run_summary_embedding_loop(embedder, "form", args.overwrite, None)
            elif "form_summaries" in fp:
                run_summary_embedding_loop(embedder, "form", args.overwrite, args.file)
            else:
                print(
                    "[ERROR] With --mode summaries and --file, path must contain "
                    "table_summaries or form_summaries."
                )
                sys.exit(1)
        else:
            run_summary_embedding_loop(embedder, "table", args.overwrite, None)
            run_summary_embedding_loop(embedder, "form", args.overwrite, None)
        return

    if args.file:
        # Process only this file
        input_path = Path(args.file)
        if not input_path.is_absolute():
            input_path = PROJECT_ROOT / input_path
        if not input_path.exists():
            print(f"[ERROR] Specified file does not exist: {input_path}")
            sys.exit(1)

        rel_input = input_path.relative_to(PROJECT_ROOT)
        embed_single_child_file(rel_input, embedder, overwrite=args.overwrite)
    else:
        # Process all files with resume
        all_files = find_all_child_chunk_files()
        if not all_files:
            print("[ERROR] No child_chunks files found.")
            sys.exit(1)

        last_rel = load_last_processed_rel()
        start_index = 0

        if last_rel is not None:
            print(f"[INFO] Last processed file from marker: {last_rel}")
            if last_rel in all_files:
                start_index = all_files.index(last_rel) + 1
            else:
                print(
                    "[WARN] Marker file refers to a path not in the current file list. "
                    "Will start from the beginning."
                )

        if start_index >= len(all_files):
            print("[INFO] Nothing to process; all files appear to be done.")
            return

        print(f"[INFO] Total files found: {len(all_files)}")
        print(f"[INFO] Starting from index {start_index} "
              f"({len(all_files) - start_index} files to process).")

        for rel_path in all_files[start_index:]:
            embed_single_child_file(rel_path, embedder, overwrite=args.overwrite)

        print("[INFO] Finished processing all remaining files.")


if __name__ == "__main__":
    main()
