"""Organization (tenant boundary)."""

from sqlalchemy import Boolean, String
from sqlalchemy.orm import Mapped, mapped_column

from adhkar.db.base import Base
from adhkar.db.models._common import IdMixin, SoftDeleteMixin, TimestampMixin


class Organization(Base, IdMixin, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "organizations"

    name: Mapped[str] = mapped_column(String(200), nullable=False, unique=True)
    slug: Mapped[str] = mapped_column(String(63), nullable=False, unique=True)
    description: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    require_mfa: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    locked: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
