"""Observable: typed IOC artifact (ip, domain, url, hash, email, etc.)."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import ARRAY, Boolean, DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import UUID as PgUUID  # noqa: N811
from sqlalchemy.orm import Mapped, mapped_column

from adhkar.db.base import Base
from adhkar.db.models._common import IdMixin


class Observable(Base, IdMixin):
    __tablename__ = "observables"

    organization_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False, index=True
    )
    data_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    data: Mapped[str] = mapped_column(String(2000), nullable=False)
    tlp: Mapped[str] = mapped_column(String(20), nullable=False, server_default="amber")
    pap: Mapped[str] = mapped_column(String(20), nullable=False, server_default="amber")
    tags: Mapped[list[str]] = mapped_column(ARRAY(String), nullable=False, server_default="{}")
    is_ioc: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    sighted: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    ignore_similarity: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    message: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    created_by: Mapped[UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
