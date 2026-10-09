from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.document import Document


def doc_filenames(db: Session, doc_ids) -> dict[str, str]:
    """doc_id -> real file name (basename of the document's source_ref)."""
    ids = set(doc_ids)
    if not ids:
        return {}
    rows = db.execute(select(Document.id, Document.source_ref).where(Document.id.in_(ids))).all()
    return {i: ref.rsplit("/", 1)[-1] for i, ref in rows if ref}


def cite(db: Session, citations) -> list[dict]:
    """Citation dicts (doc_id + snippet) enriched with `filename`; accepts
    Citation objects or stored dicts."""
    items = [c if isinstance(c, dict) else {"doc_id": c.doc_id, "snippet": c.snippet} for c in citations or []]
    names = doc_filenames(db, (c["doc_id"] for c in items))
    return [{**c, "filename": names.get(c["doc_id"])} for c in items]
