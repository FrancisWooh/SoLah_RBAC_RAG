from datetime import datetime

from sqlalchemy import BigInteger, DateTime, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class DataSource(Base):
    __tablename__ = "data_sources"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    name: Mapped[str | None] = mapped_column(String(128))
    type: Mapped[str | None] = mapped_column(String(32))
    connection_config: Mapped[dict | None] = mapped_column(JSONB)
    permission_mapping: Mapped[dict | None] = mapped_column(JSONB)
    last_sync_at: Mapped[datetime | None] = mapped_column(DateTime)
    sync_status: Mapped[str | None] = mapped_column(String(16))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
