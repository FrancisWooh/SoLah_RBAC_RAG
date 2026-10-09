from datetime import datetime

from pydantic import BaseModel


class SubmitRoleRequestIn(BaseModel):
    role_id: str
    reason: str
    source_ref: str | None = None
    requested_duration_hours: float | None = None


class RoleRequestOut(BaseModel):
    id: int
    requester_id: str
    role_id: str
    source_ref: str | None
    reason: str
    requested_duration_hours: float | None
    status: str
    approver_id: str | None
    approved_at: datetime | None
    start_at: datetime | None
    end_at: datetime | None
    created_at: datetime
