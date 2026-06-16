"""TTP catalog + per-case TTP references (MITRE ATT&CK)."""

from datetime import date as date_cls
from datetime import datetime
from uuid import UUID

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID as PgUUID  # noqa: N811
from sqlalchemy.orm import Mapped, mapped_column

from adhkar.db.base import Base
from adhkar.db.models._common import IdMixin


class TtpCatalogEntry(Base, IdMixin):
    """Global MITRE ATT&CK technique catalog. Seeded from STIX bundles or
    loaded incrementally; lookup key is technique_id (e.g. T1059, T1059.001)."""

    __tablename__ = "ttp_catalog"

    technique_id: Mapped[str] = mapped_column(String(20), nullable=False, unique=True, index=True)
    name: Mapped[str] = mapped_column(String(300), nullable=False)
    tactic: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(String, nullable=True)
    url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    is_subtechnique: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class CaseTtp(Base, IdMixin):
    """Mapping of a case to one MITRE ATT&CK technique with procedure notes."""

    __tablename__ = "case_ttps"
    __table_args__ = (
        UniqueConstraint("case_id", "technique_id", name="uq_case_ttps_case_technique"),
    )

    organization_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False, index=True
    )
    case_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("cases.id"), nullable=False, index=True
    )
    technique_id: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    tactic: Mapped[str] = mapped_column(String(80), nullable=False)
    occurrence_date: Mapped[date_cls | None] = mapped_column(Date, nullable=True)
    procedure_note: Mapped[str | None] = mapped_column(String, nullable=True)
    created_by: Mapped[UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
