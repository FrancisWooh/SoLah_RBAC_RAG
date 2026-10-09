from datetime import datetime

from pydantic import BaseModel, ConfigDict


class AuditLogOut(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    id: int
    event_type: str
    user_id: str | None
    session_id: str | None
    effective_roles: list[str]
    role_sources: dict | None
    input_type: str | None
    query_text: str | None
    normalized_text: str | None
    filter_applied: dict | None
    retrieved_doc_ids: list[str]
    blocked_doc_ids: list[str] = []
    decision: str | None
    deny_reason: str | None
    model_id: str | None
    latency_ms: int | None
    created_at: datetime
    prev_hash: str | None
    record_hash: str | None


class ChainVerificationOut(BaseModel):
    ok: bool
    rows_checked: int
    broken_at_id: int | None
    reason: str | None
