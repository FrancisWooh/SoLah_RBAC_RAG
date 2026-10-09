import csv
import io
import json
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.orm import Session

from app.api.deps import require_roles
from app.core.db import get_db
from app.models.audit_log import AuditLog
from app.models.user import User
from app.schemas.audit import AuditLogOut, ChainVerificationOut
from app.services.audit import query_audit_logs, verify_audit_chain

router = APIRouter()

_EXPORT_FIELDS = [
    "id",
    "event_type",
    "user_id",
    "session_id",
    "input_type",
    "query_text",
    "decision",
    "deny_reason",
    "retrieved_doc_ids",
    "model_id",
    "latency_ms",
    "created_at",
    "record_hash",
]


def _to_out(row: AuditLog) -> AuditLogOut:
    return AuditLogOut(
        id=row.id,
        event_type=row.event_type,
        user_id=str(row.user_id) if row.user_id else None,
        session_id=row.session_id,
        effective_roles=row.effective_roles or [],
        role_sources=row.role_sources,
        input_type=row.input_type,
        query_text=row.query_text,
        normalized_text=row.normalized_text,
        filter_applied=row.filter_applied,
        retrieved_doc_ids=row.retrieved_doc_ids or [],
        blocked_doc_ids=row.blocked_doc_ids or [],
        decision=row.decision,
        deny_reason=row.deny_reason,
        model_id=row.model_id,
        latency_ms=row.latency_ms,
        created_at=row.created_at,
        prev_hash=row.prev_hash,
        record_hash=row.record_hash,
    )


def _parse_user_id(value: str | None) -> uuid.UUID | None:
    if value is None:
        return None
    try:
        return uuid.UUID(value)
    except ValueError:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"无效的用户ID：{value}")


@router.get("/logs", response_model=list[AuditLogOut])
def get_audit_logs(
    user_id: str | None = Query(None),
    event_type: str | None = Query(None),
    decision: str | None = Query(None),
    start_time: datetime | None = Query(None),
    end_time: datetime | None = Query(None),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    _current_user: User = Depends(require_roles("platform_admin")),
):
    rows = query_audit_logs(
        db,
        user_id=_parse_user_id(user_id),
        event_type=event_type,
        decision=decision,
        start_time=start_time,
        end_time=end_time,
        limit=limit,
        offset=offset,
    )
    return [_to_out(r) for r in rows]


@router.get("/logs/{log_id}", response_model=AuditLogOut)
def get_audit_log_detail(
    log_id: int,
    db: Session = Depends(get_db),
    _current_user: User = Depends(require_roles("platform_admin")),
):
    row = db.get(AuditLog, log_id)
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "审计日志不存在")
    return _to_out(row)


@router.get("/verify", response_model=ChainVerificationOut)
def get_verify_chain(
    db: Session = Depends(get_db),
    _current_user: User = Depends(require_roles("platform_admin")),
):
    result = verify_audit_chain(db)
    return ChainVerificationOut(
        ok=result.ok,
        rows_checked=result.rows_checked,
        broken_at_id=result.broken_at_id,
        reason=result.reason,
    )


@router.get("/export")
def get_audit_export(
    format: str = Query("csv", pattern="^(csv|json)$"),
    user_id: str | None = Query(None),
    event_type: str | None = Query(None),
    decision: str | None = Query(None),
    start_time: datetime | None = Query(None),
    end_time: datetime | None = Query(None),
    limit: int = Query(500, ge=1, le=500),
    db: Session = Depends(get_db),
    _current_user: User = Depends(require_roles("platform_admin")),
):
    rows = query_audit_logs(
        db,
        user_id=_parse_user_id(user_id),
        event_type=event_type,
        decision=decision,
        start_time=start_time,
        end_time=end_time,
        limit=limit,
    )
    records = [_to_out(r).model_dump() for r in rows]

    if format == "json":
        body = json.dumps(records, ensure_ascii=False, default=str, indent=2)
        return Response(
            content=body,
            media_type="application/json",
            headers={"Content-Disposition": "attachment; filename=audit_logs.json"},
        )

    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=_EXPORT_FIELDS, extrasaction="ignore")
    writer.writeheader()
    for record in records:
        writer.writerow(record)

    return Response(
        content=buffer.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=audit_logs.csv"},
    )
