"""Parse the document library (data/), chunk it, embed it and push it into the
vector store as RBAC-tagged chunks. Run after seed_data.py.

Usage: python seed_vectorstore.py  (or: docker compose exec backend python seed_vectorstore.py)
Env:   DATA_DIR  library root containing manifest.json (default /data)
Embeddings are cached on disk (see services/embeddings/cache.py), so a re-run
only pays for text that changed.

The collection is rebuilt from scratch, but documents the background syncers registered at
runtime are NOT in manifest.json (a newer file version such as "X -v 2.0.docx", or records of a
registered department database). Those would be wiped and, because their stored hash still
matches, never re-indexed. So after the manifest pass this script clears their hash and runs the
same syncs, which index them again.
"""

import json
import time
from pathlib import Path

from app.core.config import settings
from app.core.db import SessionLocal
from app.models.document import Document
from app.services.doc_parser import is_table_format, parse_structured
from app.services.embeddings.factory import get_embedder
from app.services.ingestion import build_chunks_from_lines
from app.services.vectorstore.factory import get_vector_store
from seed_data import manifest_doc_id


def reindex_unlisted(db, unlisted) -> None:
    """Bring back active documents that are not in manifest.json (see module docstring)."""
    files = [d for d in unlisted if d.source_type == "nas" and d.status == "active"]
    records = [d for d in unlisted if d.source_type == "db" and d.status == "active"]
    for d in files + records:
        d.content_hash = None  # forces the syncers to treat them as changed
    db.commit()

    if files:
        from app.services.library_sync import sync_library

        report = sync_library(db)
        print(f"library sync: {len(files)} file document(s) outside the manifest, updated={len(report.updated)} errors={report.errors}")
    if records:
        from app.services.db_sync import run_db_sync

        try:
            results = run_db_sync()
            print(f"database sync: {len(records)} record(s) outside the manifest, " + ", ".join(
                f"{n}: updated={len(r.updated)} errors={len(r.errors)}" for n, r in results.items()))
        except Exception as e:  # e.g. the department databases are unreachable from where this runs
            print(f"WARNING: database sync failed ({e}); the backend retries it every DB_SYNC_INTERVAL seconds")


def seed_vectorstore():
    data_dir = Path(settings.data_dir)
    manifest = {manifest_doc_id(m["id"]): m for m in json.loads((data_dir / "manifest.json").read_text())}
    db = SessionLocal()
    embedder = get_embedder()
    store = get_vector_store()
    if hasattr(store, "reset"):
        store.reset()
    try:
        documents = db.query(Document).order_by(Document.id).all()
        total_chunks = 0
        started = time.time()
        unlisted = []
        for document in documents:
            entry = manifest.get(document.id)
            if entry is None:
                print(f"skip {document.id}: not in manifest (re-indexed by the syncers below if active)")
                unlisted.append(document)
                continue
            path = data_dir / entry["path"]
            title = Path(entry["filename"]).stem.replace("_", " ")
            chunks = build_chunks_from_lines(
                document,
                parse_structured(path),
                embedder,
                title=title,
                department=entry["department"],
                table=is_table_format(path),
            )
            store.upsert(chunks)
            total_chunks += len(chunks)
            print(f"upserted {len(chunks):3d} chunk(s) for {document.id} [{document.status}]")

        print(f"Done: {len(documents)} document(s), {total_chunks} chunk(s) total in {time.time() - started:.0f}s.")
        reindex_unlisted(db, unlisted)
    finally:
        db.close()


if __name__ == "__main__":
    seed_vectorstore()
