"""Attachment + CaseShare (Phase 9)."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID as PgUUID  # noqa: N811
from sqlalchemy.orm import Mapped, mapped_column

from adhkar.db.base import Base
from adhkar.db.models._common import IdMixin


class Attachment(Base, IdMixin):
    """File attached to a case or task. Storage: object key in S3/MinIO."""

    __tablename__ = "attachments"

    organization_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False, index=True
    )
    case_id: Mapped[UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("cases.id"), nullable=True, index=True
    )
    task_id: Mapped[UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("tasks.id"), nullable=True, index=True
    )
    filename: Mapped[str] = mapped_column(String(500), nullable=False)
    content_type: Mapped[str] = mapped_column(String(200), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    storage_key: Mapped[str] = mapped_column(String(500), nullable=False)
    is_quarantined: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    # password-protected ZIPs of malware → quarantined until AV scan completes
    av_scan_status: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default="pending"
    )
    # pending | clean | infected | skipped
    uploaded_by: Mapped[UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class CaseShare(Base, IdMixin):
    """Per-case external grant — Portal user can view + optionally comment."""

    __tablename__ = "case_shares"
    __table_args__ = (UniqueConstraint("case_id", "user_id", name="uq_case_shares_case_user"),)

    organization_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False, index=True
    )
    case_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("cases.id"), nullable=False, index=True
    )
    user_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    can_comment: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    can_upload: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    granted_by: Mapped[UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
