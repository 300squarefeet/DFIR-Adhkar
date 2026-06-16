"""Taxonomy: MISP-flavored namespace:predicate=value vocabulary entries."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID as PgUUID  # noqa: N811
from sqlalchemy.orm import Mapped, mapped_column

from adhkar.db.base import Base
from adhkar.db.models._common import IdMixin


class TaxonomyEntry(Base, IdMixin):
    """One namespace:predicate=value triple. namespace+predicate+value is
    unique per org so MISP imports are idempotent."""

    __tablename__ = "taxonomy_entries"
    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "namespace",
            "predicate",
            "value",
            name="uq_taxonomy_entries_org_ns_pred_val",
        ),
    )

    organization_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False, index=True
    )
    namespace: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    predicate: Mapped[str] = mapped_column(String(100), nullable=False)
    value: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(String, nullable=True)
    color: Mapped[str | None] = mapped_column(String(20), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
