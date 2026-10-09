from sqlalchemy import Boolean, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class Role(Base):
    __tablename__ = "roles"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    is_permanent: Mapped[bool] = mapped_column(Boolean, default=True)
    approver_role: Mapped[str | None] = mapped_column(String(64))
