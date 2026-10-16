import re

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.data_source import DataSource
from app.models.document import Document

DB_PREFIX = "db://"


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")  # same rule as db_sync.source_key


def _db_label(ref: str, source_names: dict[str, str]) -> str:
    """'db://hr_database/knowledge_records/hr_l01/annual_leave_entitlement' ->
    'HR Database · HR-L01 · Annual Leave Entitlement' (data source, record code, title)."""
    parts = ref[len(DB_PREFIX):].split("/")
    key = parts[0]
    source = source_names.get(key) or key.replace("_", " ").title()
    if len(parts) < 4:
        return source
    code = parts[2].upper().replace("_", "-")
    title = parts[3].replace("_", " ").title()
    return f"{source} \u00b7 {code} \u00b7 {title}"


def doc_sources(db: Session, doc_ids) -> dict[str, tuple[str, str]]:
    """doc_id -> (display name, 'file' | 'db'). Files show their real file name (basename of the
    source_ref); records of a registered department database show data source, record code and title."""
    ids = set(doc_ids)
    if not ids:
        return {}
    rows = db.execute(select(Document.id, Document.source_ref).where(Document.id.in_(ids))).all()
    source_names = None
    out: dict[str, tuple[str, str]] = {}
    for i, ref in rows:
        if not ref:
            continue
        if ref.startswith(DB_PREFIX):
            if source_names is None:
                source_names = {_slug(s.name or ""): s.name for s in db.scalars(select(DataSource)) if s.name}
            out[i] = (_db_label(ref, source_names), "db")
        else:
            out[i] = (ref.rsplit("/", 1)[-1], "file")
    return out


def doc_filenames(db: Session, doc_ids) -> dict[str, str]:
    """doc_id -> display name (see doc_sources)."""
    return {i: name for i, (name, _) in doc_sources(db, doc_ids).items()}


def cite(db: Session, citations) -> list[dict]:
    """Citation dicts (doc_id + snippet) enriched with `filename` (display name) and
    `source_type` ('file' | 'db'); accepts Citation objects or stored dicts."""
    items = [c if isinstance(c, dict) else {"doc_id": c.doc_id, "snippet": c.snippet} for c in citations or []]
    info = doc_sources(db, (c["doc_id"] for c in items))
    return [
        {**c, "filename": info.get(c["doc_id"], (None, None))[0], "source_type": info.get(c["doc_id"], (None, None))[1]}
        for c in items
    ]
