"""LDAP / Active Directory authentication provider config."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import Boolean, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.dialects.postgresql import UUID as PgUUID  # noqa: N811
from sqlalchemy.orm import Mapped, mapped_column

from adhkar.db.base import Base
from adhkar.db.models._common import IdMixin, SoftDeleteMixin, TimestampMixin


class LdapProvider(Base, IdMixin, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "ldap_providers"

    name: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    server_uris: Mapped[list[str]] = mapped_column(ARRAY(String), nullable=False, default=list)
    bind_dn: Mapped[str] = mapped_column(String(500), nullable=False)
    bind_password_enc: Mapped[str] = mapped_column(String(500), nullable=False)
    base_dn: Mapped[str] = mapped_column(String(500), nullable=False)
    user_search_filter: Mapped[str] = mapped_column(String(300), nullable=False)
    user_id_attr: Mapped[str] = mapped_column(String(64), nullable=False, default="sAMAccountName")
    user_email_attr: Mapped[str] = mapped_column(String(64), nullable=False, default="mail")
    user_display_name_attr: Mapped[str] = mapped_column(
        String(64), nullable=False, default="displayName"
    )
    group_membership_attr: Mapped[str] = mapped_column(
        String(64), nullable=False, default="memberOf"
    )
    tls_required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    allow_insecure: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=100)
    timeout_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=5)


class LdapGroupMapping(Base, IdMixin, TimestampMixin):
    __tablename__ = "ldap_group_mappings"
    __table_args__ = (
        UniqueConstraint("ldap_provider_id", "group_dn", "organization_id", name="uq_ldap_mapping"),
    )

    ldap_provider_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("ldap_providers.id", ondelete="CASCADE"),
        nullable=False,
    )
    group_dn: Mapped[str] = mapped_column(String(500), nullable=False)
    organization_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False
    )
    profile_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("profiles.id"), nullable=False
    )
