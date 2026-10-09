import uuid
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class UserRole(Base):
    """A user's role grant. One row per (user, role, source) assignment.

    source: 'permanent' | 'project' | 'temporary'
    status: 'active' | 'revoked' | 'expired'
    """

    __tablename__ = "user_roles"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    role_id: Mapped[str] = mapped_column(String(64), ForeignKey("roles.id"))
    source: Mapped[str] = mapped_column(String(32), nullable=False)
    source_ref: Mapped[str | None] = mapped_column(String(128))
    start_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    end_at: Mapped[datetime | None] = mapped_column(DateTime)
    status: Mapped[str] = mapped_column(String(16), default="active")
    created_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
