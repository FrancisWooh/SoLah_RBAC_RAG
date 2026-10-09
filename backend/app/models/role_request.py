import uuid
from datetime import datetime, timedelta

from sqlalchemy import BigInteger, DateTime, ForeignKey, Interval, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class RoleRequest(Base):
    __tablename__ = "role_requests"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    requester_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    role_id: Mapped[str] = mapped_column(String(64), ForeignKey("roles.id"))
    source_ref: Mapped[str | None] = mapped_column(String(128))
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    requested_duration: Mapped[timedelta | None] = mapped_column(Interval)
    status: Mapped[str] = mapped_column(String(16), default="pending")
    approver_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    approved_at: Mapped[datetime | None] = mapped_column(DateTime)
    start_at: Mapped[datetime | None] = mapped_column(DateTime)
    end_at: Mapped[datetime | None] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
