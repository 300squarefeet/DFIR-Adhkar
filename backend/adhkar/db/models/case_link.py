"""CaseLink: typed relationship between two Cases (same org)."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID as PgUUID  # noqa: N811
from sqlalchemy.orm import Mapped, mapped_column

from adhkar.db.base import Base
from adhkar.db.models._common import IdMixin


class CaseLink(Base, IdMixin):
    __tablename__ = "case_links"
    __table_args__ = (
        UniqueConstraint("source_case_id", "target_case_id", name="uq_case_links_source_target"),
        CheckConstraint("source_case_id <> target_case_id", name="ck_case_links_no_self_link"),
    )

    organization_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False, index=True
    )
    source_case_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("cases.id"), nullable=False, index=True
    )
    target_case_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("cases.id"), nullable=False, index=True
    )
    relation: Mapped[str] = mapped_column(String(40), nullable=False, server_default="related")
    # related | duplicate | child_of | caused_by | references
    note: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    created_by: Mapped[UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
