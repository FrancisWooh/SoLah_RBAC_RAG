"""Keep the knowledge base in step with the department databases.

Every row in `data_sources` (type "postgresql") describes one database to read:

  connection_config  host/port/dbname/user/password, table, id_column,
                     title_column, content_columns [, category_column, schema]
  permission_mapping attach_roles (the department's role, the default for every
                     record), clearance_column, compartment_column,
                     roles_column, default_clearance [, department]

One pass (run_db_sync) reads the rows of each source and brings the `documents`
table and the vector store in line, the same way library_sync does for files:

  new row      -> registered + indexed
  changed row  -> chunks replaced (content OR access control changed)
  removed row  -> marked deleted and its chunks dropped

Access control of a record (see requirement/db_source_demo.md):

  allowed_roles       roles_column if the row has one, else the source's attach_roles
  required_clearance  clearance_column (default_clearance when NULL), must be 1..4
  compartments        compartment_column; NULL/empty = normal record, otherwise a
                      partitioned record (comma separated for several)

Fail closed: a record with an unknown role, an invalid clearance or no role at
all is NOT indexed (and is dropped from the index if it was before) and an ERROR
is logged once. An unreachable database or an empty result never wipes the index.
Runs in the background (start_db_watcher) and on demand (POST
/api/admin/library/db-sync, sync_databases.py).
"""

import hashlib
import json
import logging
import re
import threading
import time
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import column, create_engine, select, table
from sqlalchemy.engine import URL
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.db import SessionLocal
from app.models.data_source import DataSource
from app.models.document import Document
from app.models.role import Role
from app.services.embeddings.factory import get_embedder
from app.services.ingestion import build_chunks_from_lines
from app.services.library_sync import SyncReport
from app.services.vectorstore.factory import get_vector_store

logger = logging.getLogger(__name__)

SOURCE_PREFIX = "db://"
SUPPORTED_TYPES = {"postgresql"}
MAX_CLEARANCE = 4

_lock = threading.Lock()
_alerted: dict[str, str] = {}  # doc id -> last alarm text, so a bad row alarms once, not every pass


@dataclass
class Record:
    pk: str
    doc_id: str
    source_ref: str
    title: str
    category: str
    text: str
    allowed_roles: list[str]
    clearance: int
    compartments: list[str]
    content_hash: str


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")


def source_key(source: DataSource) -> str:
    return _slug(source.name or "") or f"source_{source.id}"


def _department(source: DataSource) -> str:
    mapping = source.permission_mapping or {}
    return mapping.get("department") or (source.name or "").removesuffix(" Database").strip()


def _as_list(value) -> list[str]:
    """NULL / '' / 'a, b' / ['a', 'b'] -> clean list of strings."""
    if value is None:
        return []
    items = re.split(r"[,;]", value) if isinstance(value, str) else list(value)
    return [str(i).strip() for i in items if str(i).strip()]


def fetch_rows(source: DataSource) -> list[dict]:
    """Read every row of the configured table (read-only), as column -> value dicts."""
    cfg, mapping = source.connection_config or {}, source.permission_mapping or {}
    names = [cfg["id_column"], cfg["title_column"], *cfg["content_columns"]]
    names += [c for c in (cfg.get("category_column"), mapping.get("clearance_column"),
                          mapping.get("compartment_column"), mapping.get("roles_column")) if c]
    names = list(dict.fromkeys(names))
    query = select(*[column(n) for n in names]).select_from(table(cfg["table"], schema=cfg.get("schema"))).order_by(column(cfg["id_column"]))
    url = URL.create("postgresql+psycopg2", username=cfg.get("user"), password=cfg.get("password"),
                     host=cfg.get("host"), port=cfg.get("port", 5432), database=cfg["dbname"])
    engine = create_engine(url, connect_args={"connect_timeout": 5})
    try:
        with engine.connect() as conn:
            return [dict(r) for r in conn.execute(query).mappings()]
    finally:
        engine.dispose()


def _resolve(source: DataSource, key: str, row: dict, known_roles: set[str]) -> tuple[Record | None, str, str]:
    """Row -> (record, pk, reason). record is None (with a reason) if it must not be indexed."""
    cfg, mapping = source.connection_config, source.permission_mapping or {}
    raw_pk = row.get(cfg["id_column"])
    pk = str(raw_pk).strip() if raw_pk is not None else ""
    if not pk:
        return None, pk, "row has no id"

    title = str(row.get(cfg["title_column"]) or pk).strip()
    cols = cfg["content_columns"]
    parts = [(c, str(row.get(c)).strip()) for c in cols if row.get(c) is not None and str(row.get(c)).strip()]
    text = "\n".join(v if len(cols) == 1 else f"{c}: {v}" for c, v in parts)
    if not text:
        return None, pk, "empty content"
    category = str(row.get(cfg.get("category_column")) or "").strip() if cfg.get("category_column") else ""

    clr_col = mapping.get("clearance_column")
    raw_clr = row.get(clr_col) if clr_col else None
    if raw_clr is None:
        raw_clr = mapping.get("default_clearance", 1)
    try:
        clearance = int(raw_clr)
    except (TypeError, ValueError):
        return None, pk, f"invalid clearance {raw_clr!r}"
    if not 1 <= clearance <= MAX_CLEARANCE:
        return None, pk, f"clearance {clearance} out of range 1-{MAX_CLEARANCE}"

    comp_col = mapping.get("compartment_column")
    compartments = [c.lower() for c in _as_list(row.get(comp_col))] if comp_col else []

    roles_col = mapping.get("roles_column")
    roles = _as_list(row.get(roles_col)) if roles_col else []
    roles = roles or _as_list(mapping.get("attach_roles"))
    if not roles:
        return None, pk, "no allowed roles (no roles on the record and no attach role on the source)"
    unknown = [r for r in roles if r not in known_roles]
    if unknown:
        return None, pk, f"unknown role(s): {', '.join(unknown)}"

    digest = hashlib.sha256(json.dumps(
        [title, category, text, clearance, sorted(compartments), sorted(roles)], ensure_ascii=False).encode()
    ).hexdigest()
    return Record(
        pk=pk, doc_id=f"db_{key}_{_slug(pk)}",
        source_ref=f"{SOURCE_PREFIX}{key}/{cfg['table']}/{_slug(pk)}/{_slug(title) or _slug(pk)}",
        title=title, category=category, text=text, allowed_roles=roles, clearance=clearance,
        compartments=compartments, content_hash=digest,
    ), pk, ""


def _index(doc: Document, rec: Record, department: str, embedder, store) -> None:
    lines = [(ln, rec.category) for ln in rec.text.splitlines() if ln.strip()]
    chunks = build_chunks_from_lines(doc, lines, embedder, title=rec.title, department=department)
    for c in chunks:  # the doc row may still say deleted while it is being (re)activated
        c.status = "active"
    store.delete_doc(doc.id)  # drop stale chunks (e.g. the record got shorter)
    store.upsert(chunks)


def _drop(doc: Document, store, report: SyncReport, label: str) -> None:
    store.delete_doc(doc.id)
    doc.status = "deleted"
    report.removed.append(label)


def apply_rows(db: Session, source: DataSource, rows: list[dict], embedder, store) -> SyncReport:
    """Bring documents + vector store in line with `rows` (the current content of the source)."""
    report = SyncReport()
    key, department = source_key(source), _department(source)
    docs = {d.id: d for d in db.query(Document).filter(
        Document.source_type == "db", Document.source_ref.like(f"{SOURCE_PREFIX}{key}/%"))}

    if not rows and any(d.status == "active" for d in docs.values()):
        report.errors.append(f"{key}: source returned no records; nothing changed")
        return report

    known_roles = {r for (r,) in db.query(Role.id)}
    wanted: dict[str, Record] = {}
    for row in rows:
        rec, pk, reason = _resolve(source, key, row, known_roles)
        doc_id = rec.doc_id if rec else f"db_{key}_{_slug(pk)}"
        if rec and doc_id in wanted:
            rec, reason = None, "duplicate id after normalisation"
        if rec is None:
            msg = f"{key}/{pk}: {reason}; not indexed"
            report.skipped.append(msg)
            if _alerted.get(doc_id) != msg:
                _alerted[doc_id] = msg
                logger.error("ACCESS-CONTROL ALARM - %s", msg)
            continue
        _alerted.pop(doc_id, None)
        wanted[doc_id] = rec

    # removed rows, and rows that stopped being valid (fail closed)
    for doc_id, doc in docs.items():
        if doc_id not in wanted and doc.status == "active":
            _drop(doc, store, report, f"{key}/{doc_id.removeprefix(f'db_{key}_')}")
    db.commit()

    for doc_id, rec in wanted.items():
        doc, label = docs.get(doc_id), f"{key}/{rec.pk}"
        if doc and doc.status == "active" and doc.content_hash == rec.content_hash:
            continue
        try:
            was_active = bool(doc and doc.status == "active")
            if doc is None:
                doc = Document(id=doc_id, source_type="db", version="v1.0")
            doc.source_ref, doc.content_hash, doc.status = rec.source_ref, rec.content_hash, "active"
            doc.allowed_roles, doc.required_clearance, doc.compartments = rec.allowed_roles, rec.clearance, rec.compartments
            _index(doc, rec, department, embedder, store)
            db.add(doc)
            db.commit()
            (report.updated if was_active or doc_id in docs else report.added).append(label)
        except Exception as e:
            db.rollback()
            logger.warning("db sync: failed to index %s", label, exc_info=True)
            report.errors.append(f"{label}: {e}")
    return report


def _drop_orphans(db: Session, keys: set[str], store) -> SyncReport:
    """Records of a source that was removed from data_sources leave the index."""
    report = SyncReport()
    for d in db.query(Document).filter(Document.source_type == "db", Document.status == "active"):
        k = (d.source_ref or "")[len(SOURCE_PREFIX):].split("/", 1)[0]
        if k not in keys:
            _drop(d, store, report, d.source_ref or d.id)
    db.commit()
    return report


def run_db_sync(source_id: int | None = None) -> dict[str, SyncReport]:
    """Sync every registered database (or just `source_id`). Returns reports by source name."""
    results: dict[str, SyncReport] = {}
    db = SessionLocal()
    try:
        with _lock:
            embedder, store = get_embedder(), get_vector_store()
            sources = db.query(DataSource).order_by(DataSource.id).all()
            for source in sources:
                if source_id is not None and source.id != source_id:
                    continue
                name = source.name or f"source_{source.id}"
                if source.type not in SUPPORTED_TYPES:
                    report = SyncReport(errors=[f"unsupported data source type {source.type!r}"])
                else:
                    try:
                        report = apply_rows(db, source, fetch_rows(source), embedder, store)
                    except Exception as e:  # unreachable database, bad config...: leave the index as it is
                        db.rollback()
                        logger.warning("db sync: source %s failed", name, exc_info=True)
                        report = SyncReport(errors=[f"{name}: {e}"])
                source.last_sync_at = datetime.utcnow()
                source.sync_status = "error" if report.errors else "warning" if report.skipped else "ok"
                db.commit()
                results[name] = report
                if report.changed:
                    logger.info("db sync %s: +%d new, %d updated, %d removed",
                                name, len(report.added), len(report.updated), len(report.removed))
            if source_id is None:
                orphans = _drop_orphans(db, {source_key(s) for s in sources}, store)
                if orphans.removed:
                    results["(removed sources)"] = orphans
    finally:
        db.close()
    return results


def start_db_watcher() -> None:
    interval = settings.db_sync_interval
    if interval <= 0:
        return

    def loop():
        time.sleep(10)  # let the app / embedder warm up first
        while True:
            try:
                run_db_sync()
            except Exception:
                logger.warning("db sync pass failed", exc_info=True)
            time.sleep(interval)

    threading.Thread(target=loop, name="db-sync", daemon=True).start()
