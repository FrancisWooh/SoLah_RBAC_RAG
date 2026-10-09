"""Parse the document library (data/), chunk it, embed it and push it into the
vector store as RBAC-tagged chunks. Run after seed_data.py.

Usage: python seed_vectorstore.py  (or: docker compose exec backend python seed_vectorstore.py)
Env:   DATA_DIR  library root containing manifest.json (default /data)
Embeddings are cached on disk (see services/embeddings/cache.py), so a re-run
only pays for text that changed.
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
        for document in documents:
            entry = manifest.get(document.id)
            if entry is None:
                print(f"skip {document.id}: not in manifest")
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
    finally:
        db.close()


if __name__ == "__main__":
    seed_vectorstore()
