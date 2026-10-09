from datetime import datetime

from sqlalchemy import DateTime, Integer, String, func
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class Document(Base):
    """Metadata mirror of a knowledge chunk also stored in the vector DB payload."""

    __tablename__ = "documents"

    id: Mapped[str] = mapped_column(String(128), primary_key=True)
    source_type: Mapped[str | None] = mapped_column(String(32))
    source_ref: Mapped[str | None] = mapped_column(String)
    version: Mapped[str | None] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(16), default="active")
    allowed_roles: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)
    required_clearance: Mapped[int] = mapped_column(Integer, default=1)
    compartments: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)
    content_hash: Mapped[str | None] = mapped_column(String(64))
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
