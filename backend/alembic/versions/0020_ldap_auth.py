"""ldap auth: providers + group mappings + membership source.

Revision ID: 0020
Revises: 0019
Create Date: 2026-06-18
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0020"
down_revision: str | None = "0019"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "ldap_providers",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("name", sa.String(64), nullable=False),
        sa.Column("server_uris", postgresql.ARRAY(sa.String()), nullable=False),
        sa.Column("bind_dn", sa.String(500), nullable=False),
        sa.Column("bind_password_enc", sa.String(500), nullable=False),
        sa.Column("base_dn", sa.String(500), nullable=False),
        sa.Column("user_search_filter", sa.String(300), nullable=False),
        sa.Column("user_id_attr", sa.String(64), nullable=False, server_default="sAMAccountName"),
        sa.Column("user_email_attr", sa.String(64), nullable=False, server_default="mail"),
        sa.Column(
            "user_display_name_attr", sa.String(64), nullable=False, server_default="displayName"
        ),
        sa.Column(
            "group_membership_attr", sa.String(64), nullable=False, server_default="memberOf"
        ),
        sa.Column("tls_required", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("allow_insecure", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("priority", sa.Integer(), nullable=False, server_default="100"),
        sa.Column("timeout_seconds", sa.Integer(), nullable=False, server_default="5"),
        sa.UniqueConstraint("name", name="uq_ldap_providers_name"),
    )

    op.create_table(
        "ldap_group_mappings",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "ldap_provider_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey(
                "ldap_providers.id",
                ondelete="CASCADE",
                name="fk_ldap_group_mappings_ldap_provider_id_ldap_providers",
            ),
            nullable=False,
        ),
        sa.Column("group_dn", sa.String(500), nullable=False),
        sa.Column(
            "organization_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey(
                "organizations.id",
                name="fk_ldap_group_mappings_organization_id_organizations",
            ),
            nullable=False,
        ),
        sa.Column(
            "profile_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("profiles.id", name="fk_ldap_group_mappings_profile_id_profiles"),
            nullable=False,
        ),
        sa.UniqueConstraint(
            "ldap_provider_id", "group_dn", "organization_id", name="uq_ldap_mapping"
        ),
    )

    op.add_column(
        "user_org_memberships",
        sa.Column("source", sa.String(length=20), server_default="manual", nullable=False),
    )
    op.create_index("ix_memberships_source", "user_org_memberships", ["source"])


def downgrade() -> None:
    op.drop_index("ix_memberships_source", table_name="user_org_memberships")
    op.drop_column("user_org_memberships", "source")
    op.drop_table("ldap_group_mappings")
    op.drop_table("ldap_providers")
