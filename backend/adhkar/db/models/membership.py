"""UserOrgMembership: M:N user-org with profile binding."""

from uuid import UUID

from sqlalchemy import ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PgUUID  # noqa: N811
from sqlalchemy.orm import Mapped, mapped_column

from adhkar.db.base import Base
from adhkar.db.models._common import IdMixin, TimestampMixin


class UserOrgMembership(Base, IdMixin, TimestampMixin):
    __tablename__ = "user_org_memberships"
    __table_args__ = (
        UniqueConstraint("user_id", "organization_id"),
        Index("ix_memberships_source", "source"),
    )

    user_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    organization_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False
    )
    profile_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("profiles.id"), nullable=False
    )
    source: Mapped[str] = mapped_column(String(20), nullable=False, server_default="manual")
