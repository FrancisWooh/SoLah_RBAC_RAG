from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.audit_log import AuditLog
from app.models.data_source import DataSource
from app.models.user import User


@dataclass
class ViolationItem:
    id: int
    user_id: str | None
    username: str | None
    query_text: str | None
    deny_reason: str | None
    created_at: datetime


@dataclass
class VolumePoint:
    date: str
    count: int


@dataclass
class DashboardStats:
    total_queries: int
    allow_count: int
    deny_count: int
    deny_rate: float
    recent_violations: list[ViolationItem]
    query_volume_by_day: list[VolumePoint]
    sync_status_counts: dict[str, int]


def get_dashboard_stats(
    db: Session, *, days: int = 14, violation_limit: int = 10
) -> DashboardStats:
    since = datetime.utcnow() - timedelta(days=days)

    query_filter = AuditLog.event_type == "query"

    total_queries = db.scalar(select(func.count()).select_from(AuditLog).where(query_filter)) or 0
    allow_count = (
        db.scalar(
            select(func.count())
            .select_from(AuditLog)
            .where(query_filter, AuditLog.decision == "allow")
        )
        or 0
    )
    deny_count = (
        db.scalar(
            select(func.count())
            .select_from(AuditLog)
            .where(query_filter, AuditLog.decision == "deny")
        )
        or 0
    )
    deny_rate = (deny_count / total_queries) if total_queries else 0.0

    violation_rows = db.execute(
        select(AuditLog, User.username)
        .outerjoin(User, User.id == AuditLog.user_id)
        .where(query_filter, AuditLog.decision == "deny")
        .order_by(AuditLog.id.desc())
        .limit(violation_limit)
    ).all()
    recent_violations = [
        ViolationItem(
            id=row.AuditLog.id,
            user_id=str(row.AuditLog.user_id) if row.AuditLog.user_id else None,
            username=row.username,
            query_text=row.AuditLog.query_text,
            deny_reason=row.AuditLog.deny_reason,
            created_at=row.AuditLog.created_at,
        )
        for row in violation_rows
    ]

    volume_rows = db.execute(
        select(func.date(AuditLog.created_at).label("day"), func.count().label("cnt"))
        .where(query_filter, AuditLog.created_at >= since)
        .group_by("day")
        .order_by("day")
    ).all()
    query_volume_by_day = [VolumePoint(date=str(row.day), count=row.cnt) for row in volume_rows]

    # data_sources is a Phase-2-scope table (real CDC/NAS sync is explicitly
    # out of scope, see readme.txt) — this honestly reports whatever rows
    # actually exist rather than fabricating "all healthy" numbers. Empty
    # until something (a demo seed script, or real Phase-2 work) populates it.
    sync_rows = db.execute(select(DataSource.sync_status, func.count()).group_by(DataSource.sync_status)).all()
    sync_status_counts = {(row[0] or "unknown"): row[1] for row in sync_rows}

    return DashboardStats(
        total_queries=total_queries,
        allow_count=allow_count,
        deny_count=deny_count,
        deny_rate=deny_rate,
        recent_violations=recent_violations,
        query_volume_by_day=query_volume_by_day,
        sync_status_counts=sync_status_counts,
    )
