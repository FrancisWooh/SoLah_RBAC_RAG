from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import require_roles
from app.core.db import get_db
from app.models.user import User
from app.schemas.dashboard import DashboardStatsOut, VolumePointOut, ViolationItemOut
from app.services.dashboard import get_dashboard_stats

router = APIRouter()


@router.get("/stats", response_model=DashboardStatsOut)
def get_stats(
    days: int = Query(14, ge=1, le=90),
    db: Session = Depends(get_db),
    _current_user: User = Depends(require_roles("platform_admin")),
):
    stats = get_dashboard_stats(db, days=days)
    return DashboardStatsOut(
        total_queries=stats.total_queries,
        allow_count=stats.allow_count,
        deny_count=stats.deny_count,
        deny_rate=stats.deny_rate,
        recent_violations=[
            ViolationItemOut(
                id=v.id,
                user_id=v.user_id,
                username=v.username,
                query_text=v.query_text,
                deny_reason=v.deny_reason,
                created_at=v.created_at,
            )
            for v in stats.recent_violations
        ],
        query_volume_by_day=[
            VolumePointOut(date=p.date, count=p.count) for p in stats.query_volume_by_day
        ],
        sync_status_counts=stats.sync_status_counts,
    )
