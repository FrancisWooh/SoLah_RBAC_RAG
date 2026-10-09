import uuid
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class AuditLog(Base):
    """Append-only. Rows must never be updated or deleted by application code."""

    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    event_type: Mapped[str] = mapped_column(String(32), nullable=False)
    user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    session_id: Mapped[str | None] = mapped_column(String(64))
    effective_roles: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)
    role_sources: Mapped[dict | None] = mapped_column(JSONB)
    input_type: Mapped[str | None] = mapped_column(String(16))
    raw_input_ref: Mapped[str | None] = mapped_column(Text)
    recognized_text: Mapped[str | None] = mapped_column(Text)
    normalized_text: Mapped[str | None] = mapped_column(Text)
    query_text: Mapped[str | None] = mapped_column(Text)
    filter_applied: Mapped[dict | None] = mapped_column(JSONB)
    retrieved_doc_ids: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)
    # Documents the user was *blocked* from: on a deny, the most relevant
    # restricted document (id only). Audit/admin-facing; never returned to the
    # asking user. Covered by the hash chain whenever non-empty.
    blocked_doc_ids: Mapped[list[str] | None] = mapped_column(ARRAY(String))
    decision: Mapped[str | None] = mapped_column(String(16))
    deny_reason: Mapped[str | None] = mapped_column(Text)
    model_id: Mapped[str | None] = mapped_column(String(64))
    latency_ms: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    # Tamper-evident hash chain, see app/services/audit.py. Nullable because
    # rows written before this feature existed have none (see
    # backfill_audit_hash_chain.py for bringing them into the chain).
    prev_hash: Mapped[str | None] = mapped_column(String(64))
    record_hash: Mapped[str | None] = mapped_column(String(64))
