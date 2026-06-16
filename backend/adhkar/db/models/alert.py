"""Alert: inbound signal that may be promoted to a Case."""

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import ARRAY, DateTime, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PgUUID  # noqa: N811
from sqlalchemy.orm import Mapped, mapped_column

from adhkar.db.base import Base
from adhkar.db.models._common import IdMixin


class Alert(Base, IdMixin):
    __tablename__ = "alerts"
    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "type",
            "source",
            "source_ref",
            name="uq_alerts_org_type_source_ref",
        ),
    )

    organization_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False, index=True
    )
    type: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    source: Mapped[str] = mapped_column(String(100), nullable=False)
    source_ref: Mapped[str] = mapped_column(String(255), nullable=False)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str | None] = mapped_column(String, nullable=True)
    severity: Mapped[int] = mapped_column(Integer, nullable=False, server_default="2")
    tlp: Mapped[str] = mapped_column(String(20), nullable=False, server_default="amber")
    pap: Mapped[str] = mapped_column(String(20), nullable=False, server_default="amber")
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default="New")
    # New | Updated | Ignored | Imported
    date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    tags: Mapped[list[str]] = mapped_column(ARRAY(String), nullable=False, server_default="{}")
    custom_fields: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default="{}"
    )
    raw_payload: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    case_id: Mapped[UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("cases.id"), nullable=True, index=True
    )
    imported_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_by: Mapped[UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
