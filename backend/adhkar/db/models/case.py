"""Case: the core investigation entity."""

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import ARRAY, Boolean, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PgUUID  # noqa: N811
from sqlalchemy.orm import Mapped, mapped_column

from adhkar.db.base import Base
from adhkar.db.models._common import IdMixin


class Case(Base, IdMixin):
    __tablename__ = "cases"

    organization_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False, index=True
    )
    # Auto-incrementing per-org number via app-level counter (assigned at create time).
    number: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str | None] = mapped_column(String, nullable=True)
    severity: Mapped[int] = mapped_column(Integer, nullable=False, server_default="2")
    # 1=Low 2=Medium 3=High 4=Critical
    tlp: Mapped[str] = mapped_column(String(20), nullable=False, server_default="amber")
    pap: Mapped[str] = mapped_column(String(20), nullable=False, server_default="amber")
    status: Mapped[str] = mapped_column(String(50), nullable=False, server_default="Open")
    stage: Mapped[str] = mapped_column(String(20), nullable=False, server_default="open")
    # open | in_progress | closed
    resolution: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    impact_summary: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    assignee_id: Mapped[UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    start_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    end_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    tags: Mapped[list[str]] = mapped_column(ARRAY(String), nullable=False, server_default="{}")
    custom_fields: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default="{}"
    )
    flagged: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
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
