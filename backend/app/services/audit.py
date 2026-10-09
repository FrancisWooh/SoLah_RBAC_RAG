"""Append-only, tamper-evident audit log.

Every row's record_hash = sha256(prev_row.record_hash + canonical_json(this
row's fields)). Changing, reordering, or deleting any past row breaks the
chain from that point forward, and verify_audit_chain() will say exactly
where. The genesis row (nothing before it) chains from GENESIS_HASH.

All writes go through append_audit_log() — nothing else should construct
AuditLog() directly, or it won't be part of the chain.
"""

import json
import uuid
from dataclasses import dataclass
from datetime import datetime
from hashlib import sha256

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.audit_log import AuditLog

DEFAULT_PAGE_SIZE = 50
MAX_PAGE_SIZE = 500

GENESIS_HASH = "0" * 64

_HASHED_FIELDS = (
    "event_type",
    "user_id",
    "session_id",
    "effective_roles",
    "role_sources",
    "input_type",
    "raw_input_ref",
    "recognized_text",
    "normalized_text",
    "query_text",
    "filter_applied",
    "retrieved_doc_ids",
    "decision",
    "deny_reason",
    "model_id",
    "latency_ms",
    "created_at",
)


# Hashed only when non-empty, so rows written before this field existed keep
# verifying; once a row has it, changing or emptying it breaks the chain.
_OPTIONAL_HASHED_FIELDS = ("blocked_doc_ids",)


def hashed_fields_of(row) -> dict:
    """The field values of an AuditLog row that feed its hash."""
    return {k: getattr(row, k) for k in (*_HASHED_FIELDS, *_OPTIONAL_HASHED_FIELDS)}


def _canonical_payload(fields: dict) -> str:
    normalized = {k: (str(v) if isinstance(v, (uuid.UUID, datetime)) else v) for k, v in fields.items()}
    return json.dumps(normalized, sort_keys=True, ensure_ascii=False, default=str)


def _compute_record_hash(prev_hash: str, row_fields: dict) -> str:
    hashed = {k: row_fields.get(k) for k in _HASHED_FIELDS}
    for k in _OPTIONAL_HASHED_FIELDS:
        if row_fields.get(k):
            hashed[k] = row_fields[k]
    payload = _canonical_payload(hashed)
    return sha256(f"{prev_hash}|{payload}".encode("utf-8")).hexdigest()


def append_audit_log(db: Session, **fields) -> AuditLog:
    """Builds and adds (not commits) one AuditLog row, correctly chained to
    whatever the latest row in the table currently is. Caller still owns the
    transaction/commit, same as every other write in this codebase.

    Locks the latest row (SELECT ... FOR UPDATE) so concurrent writers can't
    both compute the same prev_hash — audit writes are serialized by design,
    which is the right tradeoff for a tamper-evident chain.

    Fields with a Python-side column default (effective_roles,
    retrieved_doc_ids — both `ARRAY(String), default=list`) must be set
    explicitly here rather than left for SQLAlchemy to fill in at flush
    time: that default is only applied to the ORM object during the INSERT,
    which happens *after* this function computes the hash, so the hash
    would otherwise be taken over None while the stored/verified value is
    actually []. Omitting this is exactly the kind of mismatch
    verify_audit_chain exists to catch.
    """
    fields.setdefault("created_at", datetime.utcnow())
    fields.setdefault("effective_roles", [])
    fields.setdefault("retrieved_doc_ids", [])

    # Rows appended earlier in this same transaction must be visible to the
    # "latest row" lookup below, whatever the session's autoflush setting
    # (SessionLocal has it off): otherwise two appends in one transaction would
    # both chain to the same predecessor and the chain would fork.
    db.flush()

    latest = db.execute(
        select(AuditLog.record_hash).order_by(AuditLog.id.desc()).limit(1).with_for_update()
    ).scalar_one_or_none()
    prev_hash = latest or GENESIS_HASH

    record_hash = _compute_record_hash(prev_hash, fields)

    row = AuditLog(prev_hash=prev_hash, record_hash=record_hash, **fields)
    db.add(row)
    return row


def query_audit_logs(
    db: Session,
    *,
    user_id: uuid.UUID | None = None,
    event_type: str | None = None,
    decision: str | None = None,
    start_time: datetime | None = None,
    end_time: datetime | None = None,
    limit: int = DEFAULT_PAGE_SIZE,
    offset: int = 0,
) -> list[AuditLog]:
    stmt = select(AuditLog)
    if user_id is not None:
        stmt = stmt.where(AuditLog.user_id == user_id)
    if event_type is not None:
        stmt = stmt.where(AuditLog.event_type == event_type)
    if decision is not None:
        stmt = stmt.where(AuditLog.decision == decision)
    if start_time is not None:
        stmt = stmt.where(AuditLog.created_at >= start_time)
    if end_time is not None:
        stmt = stmt.where(AuditLog.created_at <= end_time)

    stmt = stmt.order_by(AuditLog.id.desc()).limit(min(limit, MAX_PAGE_SIZE)).offset(offset)
    return list(db.scalars(stmt))


@dataclass
class ChainVerification:
    ok: bool
    rows_checked: int
    broken_at_id: int | None
    reason: str | None


def verify_audit_chain(db: Session) -> ChainVerification:
    rows = db.scalars(select(AuditLog).order_by(AuditLog.id.asc())).all()

    prev_hash = GENESIS_HASH
    for i, row in enumerate(rows):
        if row.prev_hash is None or row.record_hash is None:
            return ChainVerification(
                ok=False, rows_checked=i, broken_at_id=row.id, reason="该记录缺少哈希字段（早于审计链功能上线）"
            )
        if row.prev_hash != prev_hash:
            return ChainVerification(
                ok=False, rows_checked=i, broken_at_id=row.id, reason="prev_hash 与前一条记录的 record_hash 不匹配"
            )

        row_fields = hashed_fields_of(row)
        expected = _compute_record_hash(prev_hash, row_fields)
        if expected != row.record_hash:
            return ChainVerification(
                ok=False, rows_checked=i, broken_at_id=row.id, reason="record_hash 与记录内容不匹配，内容可能被篡改"
            )

        prev_hash = row.record_hash

    return ChainVerification(ok=True, rows_checked=len(rows), broken_at_id=None, reason=None)
