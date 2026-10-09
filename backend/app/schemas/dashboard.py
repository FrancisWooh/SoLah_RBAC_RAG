from datetime import datetime

from pydantic import BaseModel


class ViolationItemOut(BaseModel):
    id: int
    user_id: str | None
    username: str | None
    query_text: str | None
    deny_reason: str | None
    created_at: datetime


class VolumePointOut(BaseModel):
    date: str
    count: int


class DashboardStatsOut(BaseModel):
    total_queries: int
    allow_count: int
    deny_count: int
    deny_rate: float
    recent_violations: list[ViolationItemOut]
    query_volume_by_day: list[VolumePointOut]
    sync_status_counts: dict[str, int]
