"""Keep the knowledge base in step with the document library directory.

One pass (sync_library) compares the files under settings.data_dir with the
`documents` table and brings the DB and the vector store in line:

  new file         -> registered + indexed. Its access control comes from
                      manifest.json if the file is listed there; otherwise it
                      is inherited from the earlier version of the same
                      document ("X -v 2.0.docx" after "X.docx"); otherwise it is
                      read from the access-control block at the top of the file
                      (doc_header.py; Allowed Roles defaults from the department) and appended to manifest.json. A file with
                      none of these - or an incomplete/unknown header - is NOT
                      indexed (fail closed) and an ERROR is logged once.
  new version      -> the previous version is archived and dropped from the
                      index, so answers come from the latest version only.
  changed file     -> re-parsed and its chunks replaced (content hash differs).
  removed file     -> marked deleted and its chunks dropped; if it was the newest
                      version, the previous version is restored and re-indexed.

Runs in the background (start_library_watcher) and on demand
(sync_library.py, POST /api/admin/library/sync). manifest.json stays the
authority: existing entries are never edited, only new ones are appended (so the
library mount must be writable). The DB is the live source of truth at runtime.
"""

import hashlib
import json
import logging
import re
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.db import SessionLocal
from app.models.document import Document
from app.models.role import Role
from app.services.doc_header import default_roles, read_header_acl
from app.services.doc_parser import is_table_format, parse_structured
from app.services.embeddings.factory import get_embedder
from app.services.ingestion import build_chunks_from_lines
from app.services.vectorstore.factory import get_vector_store

logger = logging.getLogger(__name__)

SOURCE_PREFIX = "/company_share/"
SUPPORTED = {".pdf", ".docx", ".xlsx", ".pptx", ".md"}
SETTLE_SECONDS = 2  # ignore files modified this recently (still being copied)
_VERSION_RE = re.compile(r"^(?P<base>.*?)[\s_-]*v\s*(?P<ver>\d+(?:\.\d+)*)$", re.IGNORECASE)

_lock = threading.Lock()
_hash_cache: dict[str, tuple[int, int, str]] = {}  # rel path -> (size, mtime_ns, sha256)
_alerted: dict[str, str] = {}  # rel path -> last alarm text, so a bad file alarms once, not every pass


@dataclass
class SyncReport:
    added: list[str] = field(default_factory=list)
    updated: list[str] = field(default_factory=list)
    archived: list[str] = field(default_factory=list)
    removed: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)  # (file, reason)
    errors: list[str] = field(default_factory=list)

    @property
    def changed(self) -> bool:
        return bool(self.added or self.updated or self.archived or self.removed)


def _split_version(stem: str) -> tuple[str, tuple[int, ...] | None]:
    m = _VERSION_RE.match(stem)
    if not m or not m["base"].strip():
        return stem.strip(), None
    return m["base"].strip(), tuple(int(x) for x in m["ver"].split("."))


def _fmt_version(ver: tuple[int, ...] | None) -> str:
    if not ver:
        return "v1.0"
    return "v" + ".".join(map(str, ver if len(ver) > 1 else (*ver, 0)))


def _parse_version(text: str | None) -> tuple[int, ...]:
    nums = re.findall(r"\d+", text or "")
    return tuple(int(n) for n in nums) or (1, 0)


def _sha256(path: Path, rel: str) -> str:
    st = path.stat()
    cached = _hash_cache.get(rel)
    if cached and cached[:2] == (st.st_size, st.st_mtime_ns):
        return cached[2]
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    _hash_cache[rel] = (st.st_size, st.st_mtime_ns, digest)
    return digest


def _scan(root: Path) -> dict[str, Path]:
    now = time.time()
    return {
        p.relative_to(root).as_posix(): p
        for p in root.rglob("*")
        if p.is_file() and p.suffix.lower() in SUPPORTED and now - p.stat().st_mtime >= SETTLE_SECONDS
    }


def _rel(document: Document) -> str | None:
    ref = document.source_ref or ""
    return ref[len(SOURCE_PREFIX):] if ref.startswith(SOURCE_PREFIX) else None


def _load_manifest(root: Path) -> list[dict]:
    f = root / "manifest.json"
    return json.loads(f.read_text()) if f.exists() else []


def _alarm(report: SyncReport, rel: str, reason: str) -> None:
    """File has no usable access control: not indexed. Reported on every pass,
    logged at ERROR only when the reason is new."""
    msg = f"{rel}: {reason}; not indexed"
    report.skipped.append(msg)
    if _alerted.get(rel) != msg:
        _alerted[rel] = msg
        logger.error("ACCESS-CONTROL ALARM - %s", msg)


def _entry_from_header(db: Session, rel: str, path: Path, root: Path, manifest: dict) -> tuple[dict | None, str]:
    """Build a manifest entry from the file's own header. (None, reason) if unusable."""
    try:
        acl = read_header_acl(path)
    except Exception as e:
        return None, f"cannot read header ({e})"
    errors = list(acl.errors)
    if not acl.allowed_roles:  # no Allowed Roles line: fall back to the department's owner role
        acl.allowed_roles, why = default_roles(acl.department, rel.split("/")[0])
        if why:
            errors.append(why)
    unknown = [r for r in acl.allowed_roles if db.get(Role, r) is None]
    if unknown:
        errors.append(f"unknown role(s) in Allowed Roles: {', '.join(unknown)}")
    if errors:
        return None, "no valid access-control header: " + "; ".join(errors)

    taken = {m["id"] for m in manifest.values()}
    entry_id = acl.doc_id if acl.doc_id and acl.doc_id not in taken else "N" + hashlib.sha1(rel.encode()).hexdigest()[:6].upper()
    return {
        "id": entry_id,
        "path": rel,
        "filename": path.name,
        "format": path.suffix.lower().lstrip("."),
        "department": acl.department or rel.split("/")[0],
        "project": "",
        "allowed_roles": acl.allowed_roles,
        "required_clearance": acl.required_clearance,
        "classification": acl.classification,
        "compartments": acl.compartments,
        "version": acl.version or "v1.0",
        "status": "active",
        "source_type": "nas",
        "source_ref": SOURCE_PREFIX + rel,
        "size_bytes": path.stat().st_size,
        "content_hash": _sha256(path, rel),
    }, ""


def _append_manifest(root: Path, entry: dict) -> None:
    """Append one entry to manifest.json (atomic replace). Raises if the library is read-only."""
    f = root / "manifest.json"
    entries = json.loads(f.read_text()) if f.exists() else []
    entries.append(entry)
    tmp = f.with_name(f.name + ".tmp")
    tmp.write_text(json.dumps(entries, indent=2, ensure_ascii=False) + "\n")
    tmp.replace(f)


def _slug(stem: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", stem.lower()).strip("_")


def _index(db_doc: Document, path: Path, title: str, department: str, embedder, store) -> int:
    chunks = build_chunks_from_lines(
        db_doc, parse_structured(path), embedder, title=title, department=department, table=is_table_format(path)
    )
    for c in chunks:  # the doc row may still say archived/deleted while it is being (re)activated
        c.status = "active"
    store.delete_doc(db_doc.id)  # drop stale chunks (e.g. the document got shorter)
    store.upsert(chunks)
    return len(chunks)


def sync_library(db: Session) -> SyncReport:
    report = SyncReport()
    root = Path(settings.data_dir)
    if not root.is_dir():
        report.errors.append(f"library directory not found: {root}")
        return report
    with _lock:
        files = _scan(root)
        if not files:  # an empty/unmounted library must never wipe the index
            report.errors.append("no documents found in library; nothing changed")
            return report
        embedder, store = get_embedder(), get_vector_store()
        manifest = {m["path"]: m for m in _load_manifest(root)}
        dept_by_dir = {m["path"].split("/")[0]: m["department"] for m in manifest.values() if "/" in m["path"]}
        docs = db.query(Document).all()
        by_rel = {r: d for d in docs if (r := _rel(d))}

        # 1. files that disappeared
        for rel, d in by_rel.items():
            if rel not in files and d.status == "active":
                store.delete_doc(d.id)
                d.status = "deleted"
                report.removed.append(rel)
        # also heals a family left with only archived versions by an earlier removal
        for rel, d in by_rel.items():
            if rel not in files and d.status == "deleted":
                _restore_previous(db, rel, docs, files, dept_by_dir, embedder, store, report)
        db.commit()

        # 2. changed files
        for rel, d in by_rel.items():
            if rel not in files:
                continue
            digest = _sha256(files[rel], rel)
            if digest == d.content_hash and d.status == "active":
                continue
            if d.status == "archived":
                continue  # superseded versions stay out of the index
            try:
                base, _ = _split_version(Path(rel).stem)
                _index(d, files[rel], base.replace("_", " "), dept_by_dir.get(rel.split("/")[0], ""), embedder, store)
                d.content_hash, d.status = digest, "active"
                db.commit()
                report.updated.append(rel)
            except Exception as e:
                db.rollback()
                logger.warning("sync: failed to re-index %s", rel, exc_info=True)
                report.errors.append(f"{rel}: {e}")

        # 3. new files
        for rel, path in sorted(files.items()):
            if rel in by_rel:
                continue
            try:
                _add_new(db, rel, path, manifest.get(rel), docs, dept_by_dir, embedder, store, report, root, manifest)
            except Exception as e:
                db.rollback()
                logger.warning("sync: failed to add %s", rel, exc_info=True)
                report.errors.append(f"{rel}: {e}")

        # one active version per document: a returning newer version supersedes the restored older one
        families: dict[tuple[str, str], list[Document]] = {}
        for d in docs:
            if (r := _rel(d)) and d.status == "active":
                families.setdefault((str(Path(r).parent), _split_version(Path(r).stem)[0].lower()), []).append(d)
        for members in families.values():
            for old in sorted(members, key=lambda d: _parse_version(d.version))[:-1]:
                store.delete_doc(old.id)
                old.status = "archived"
                report.archived.append(_rel(old))
        db.commit()

    if report.changed:
        logger.info(
            "library sync: +%d new, %d updated, %d archived, %d removed",
            len(report.added), len(report.updated), len(report.archived), len(report.removed),
        )
    return report


def _restore_previous(db, removed_rel, docs, files, dept_by_dir, embedder, store, report) -> None:
    """The newest version of a document was deleted: bring back the latest
    earlier version that is still on disk, unless another version is active."""
    base = _split_version(Path(removed_rel).stem)[0].lower()
    family = [
        d for d in docs
        if (r := _rel(d)) and str(Path(r).parent) == str(Path(removed_rel).parent)
        and _split_version(Path(r).stem)[0].lower() == base
    ]
    if any(d.status == "active" for d in family):
        return
    candidates = [d for d in family if d.status == "archived" and _rel(d) in files]
    if not candidates:
        return
    prev = max(candidates, key=lambda d: _parse_version(d.version))
    rel = _rel(prev)
    try:
        _index(prev, files[rel], base.replace("_", " "), dept_by_dir.get(rel.split("/")[0], ""), embedder, store)
        prev.content_hash, prev.status = _sha256(files[rel], rel), "active"
        report.updated.append(f"{rel} (restored: newer version removed)")
    except Exception as e:
        logger.warning("sync: failed to restore %s", rel, exc_info=True)
        report.errors.append(f"{rel}: {e}")


def _add_new(db, rel, path, entry, docs, dept_by_dir, embedder, store, report, root, manifest) -> None:
    stem = Path(rel).stem
    base, ver = _split_version(stem)
    directory = str(Path(rel).parent)

    # earlier versions of the same document: same folder, same base name
    siblings = [
        d for d in docs
        if (r := _rel(d)) and str(Path(r).parent) == directory
        and _split_version(Path(r).stem)[0].lower() == base.lower() and d.status != "deleted"
    ]
    latest = max(siblings, key=lambda d: _parse_version(d.version), default=None)

    if entry:  # manifest.json is authoritative
        acl = {k: entry[k] for k in ("allowed_roles", "required_clearance", "compartments")}
        version, department = entry["version"], entry["department"]
    elif latest:  # new version inherits the previous version's access control
        acl = dict(allowed_roles=list(latest.allowed_roles), required_clearance=latest.required_clearance,
                   compartments=list(latest.compartments))
        version, department = _fmt_version(ver), dept_by_dir.get(rel.split("/")[0], "")
    else:  # last resort: the file's own header, written back to manifest.json
        entry, reason = _entry_from_header(db, rel, path, root, manifest)
        if entry is None:
            _alarm(report, rel, reason)
            return
        try:
            _append_manifest(root, entry)
        except OSError as e:  # e.g. read-only mount: do not index something the manifest cannot record
            _alarm(report, rel, f"cannot write manifest.json ({e})")
            return
        manifest[rel] = entry
        _alerted.pop(rel, None)
        acl = {k: entry[k] for k in ("allowed_roles", "required_clearance", "compartments")}
        version, department = entry["version"], entry["department"]

    is_newest = latest is None or _parse_version(version) > _parse_version(latest.version)
    doc_id = f"doc_{_slug(stem)}"
    if any(d.id == doc_id for d in docs):
        doc_id += "_" + hashlib.sha1(rel.encode()).hexdigest()[:6]
    doc = Document(
        id=doc_id, source_type="nas", source_ref=SOURCE_PREFIX + rel, version=version,
        status="active" if is_newest else "archived", content_hash=_sha256(path, rel), **acl,
    )
    if is_newest:
        _index(doc, path, base.replace("_", " "), department, embedder, store)
    db.add(doc)
    docs.append(doc)
    report.added.append(rel)
    if is_newest:
        for old in siblings:
            if old.status == "active":
                store.delete_doc(old.id)
                old.status = "archived"
                report.archived.append(_rel(old))
    db.commit()


def run_sync() -> SyncReport:
    db = SessionLocal()
    try:
        return sync_library(db)
    finally:
        db.close()


def start_library_watcher() -> None:
    interval = settings.library_sync_interval
    if interval <= 0:
        return

    def loop():
        time.sleep(5)  # let the app / embedder warm up first
        while True:
            try:
                run_sync()
            except Exception:
                logger.warning("library sync pass failed", exc_info=True)
            time.sleep(interval)

    threading.Thread(target=loop, name="library-sync", daemon=True).start()
