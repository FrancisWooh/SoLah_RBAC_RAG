import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class ProjectMember(Base):
    __tablename__ = "project_members"

    project_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), primary_key=True
    )
    project_role: Mapped[str | None] = mapped_column(String(64))
    joined_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    left_at: Mapped[datetime | None] = mapped_column(DateTime)
    project_end_at: Mapped[datetime | None] = mapped_column(DateTime)
