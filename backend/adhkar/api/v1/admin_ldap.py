"""Admin endpoints for LDAP provider + group mapping management."""

from __future__ import annotations

import time
from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID

from cryptography.fernet import InvalidToken
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from adhkar.api.deps import CurrentUser, get_db, get_settings, require_permission
from adhkar.audit import audit_and_emit
from adhkar.auth.crypto import encrypt
from adhkar.auth.ldap_client import LdapClient
from adhkar.auth.ldap_errors import LdapConnectionError, LdapServiceBindError
from adhkar.auth.ldap_provider import LdapProviderConfig
from adhkar.core.settings import Settings
from adhkar.db.models import LdapGroupMapping, LdapProvider

router = APIRouter(prefix="/v1/admin/ldap-providers", tags=["admin-ldap"])


# ---------------------------------------------------------------------------
# Request / response schemas
# ---------------------------------------------------------------------------


class LdapProviderIn(BaseModel):
    name: str
    server_uris: list[str]
    bind_dn: str
    bind_password: str
    base_dn: str
    user_search_filter: str = "(mail={input})"
    user_id_attr: str = "sAMAccountName"
    user_email_attr: str = "mail"
    user_display_name_attr: str = "displayName"
    group_membership_attr: str = "memberOf"
    tls_required: bool = True
    allow_insecure: bool = False
    enabled: bool = True
    priority: int = 100
    timeout_seconds: int = 5


class LdapProviderPatch(BaseModel):
    name: str | None = None
    server_uris: list[str] | None = None
    bind_dn: str | None = None
    bind_password: str | None = None  # plain text; encrypted before write
    base_dn: str | None = None
    user_search_filter: str | None = None
    user_id_attr: str | None = None
    user_email_attr: str | None = None
    user_display_name_attr: str | None = None
    group_membership_attr: str | None = None
    tls_required: bool | None = None
    allow_insecure: bool | None = None
    enabled: bool | None = None
    priority: int | None = None
    timeout_seconds: int | None = None


class LdapProviderOut(BaseModel):
    """bind_password / bind_password_enc are intentionally absent (write-only)."""

    id: UUID
    name: str
    server_uris: list[str]
    bind_dn: str
    base_dn: str
    user_search_filter: str
    user_id_attr: str
    user_email_attr: str
    user_display_name_attr: str
    group_membership_attr: str
    tls_required: bool
    allow_insecure: bool
    enabled: bool
    priority: int
    timeout_seconds: int


class LdapGroupMappingIn(BaseModel):
    group_dn: str
    organization_id: UUID
    profile_id: UUID


class LdapGroupMappingOut(BaseModel):
    id: UUID
    ldap_provider_id: UUID
    group_dn: str
    organization_id: UUID
    profile_id: UUID


class TestConnectionResult(BaseModel):
    ok: bool
    server_uri_used: str | None = None
    error: str | None = None
    duration_ms: int


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _to_out(row: LdapProvider) -> LdapProviderOut:
    return LdapProviderOut(
        id=row.id,
        name=row.name,
        server_uris=list(row.server_uris),
        bind_dn=row.bind_dn,
        base_dn=row.base_dn,
        user_search_filter=row.user_search_filter,
        user_id_attr=row.user_id_attr,
        user_email_attr=row.user_email_attr,
        user_display_name_attr=row.user_display_name_attr,
        group_membership_attr=row.group_membership_attr,
        tls_required=row.tls_required,
        allow_insecure=row.allow_insecure,
        enabled=row.enabled,
        priority=row.priority,
        timeout_seconds=row.timeout_seconds,
    )


def _mapping_to_out(r: LdapGroupMapping) -> LdapGroupMappingOut:
    return LdapGroupMappingOut(
        id=r.id,
        ldap_provider_id=r.ldap_provider_id,
        group_dn=r.group_dn,
        organization_id=r.organization_id,
        profile_id=r.profile_id,
    )


# ---------------------------------------------------------------------------
# Provider endpoints
# ---------------------------------------------------------------------------


@router.get("", response_model=list[LdapProviderOut])
async def list_providers(
    _user: Annotated[CurrentUser, Depends(require_permission("manageConfig"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[LdapProviderOut]:
    rows = (
        (
            await db.execute(
                select(LdapProvider)
                .where(LdapProvider.deleted_at.is_(None))
                .order_by(LdapProvider.priority.asc())
            )
        )
        .scalars()
        .all()
    )
    return [_to_out(r) for r in rows]


@router.post("", response_model=LdapProviderOut, status_code=status.HTTP_201_CREATED)
async def create_provider(
    body: LdapProviderIn,
    user: Annotated[CurrentUser, Depends(require_permission("manageConfig"))],
    db: Annotated[AsyncSession, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> LdapProviderOut:
    enc = encrypt(body.bind_password.encode(), settings.secret_key).decode()
    row = LdapProvider(
        name=body.name,
        server_uris=body.server_uris,
        bind_dn=body.bind_dn,
        bind_password_enc=enc,
        base_dn=body.base_dn,
        user_search_filter=body.user_search_filter,
        user_id_attr=body.user_id_attr,
        user_email_attr=body.user_email_attr,
        user_display_name_attr=body.user_display_name_attr,
        group_membership_attr=body.group_membership_attr,
        tls_required=body.tls_required,
        allow_insecure=body.allow_insecure,
        enabled=body.enabled,
        priority=body.priority,
        timeout_seconds=body.timeout_seconds,
    )
    db.add(row)
    try:
        await db.flush()
    except IntegrityError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, "name_already_exists") from exc

    await audit_and_emit(
        db,
        actor_user_id=user.user_id,
        organization_id=user.org_id,
        action="ldap_provider_created",
        entity_type="ldap_provider",
        entity_id=row.id,
        diff={"name": row.name, "enabled": row.enabled},
        emit_outbox=True,
    )
    return _to_out(row)


@router.get("/{provider_id}", response_model=LdapProviderOut)
async def get_provider(
    provider_id: UUID,
    _user: Annotated[CurrentUser, Depends(require_permission("manageConfig"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> LdapProviderOut:
    row = await db.get(LdapProvider, provider_id)
    if row is None or row.deleted_at is not None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "not_found")
    return _to_out(row)


@router.patch("/{provider_id}", response_model=LdapProviderOut)
async def patch_provider(
    provider_id: UUID,
    body: LdapProviderPatch,
    user: Annotated[CurrentUser, Depends(require_permission("manageConfig"))],
    db: Annotated[AsyncSession, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> LdapProviderOut:
    row = await db.get(LdapProvider, provider_id)
    if row is None or row.deleted_at is not None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "not_found")
    payload = body.model_dump(exclude_unset=True)
    audit_fields = sorted(payload.keys())
    if "bind_password" in payload:
        payload["bind_password_enc"] = encrypt(
            payload.pop("bind_password").encode(), settings.secret_key
        ).decode()
    for k, v in payload.items():
        setattr(row, k, v)
    await db.flush()
    await audit_and_emit(
        db,
        actor_user_id=user.user_id,
        organization_id=user.org_id,
        action="ldap_provider_updated",
        entity_type="ldap_provider",
        entity_id=row.id,
        diff={"updated_fields": audit_fields},
        emit_outbox=True,
    )
    return _to_out(row)


@router.delete("/{provider_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_provider(
    provider_id: UUID,
    user: Annotated[CurrentUser, Depends(require_permission("manageConfig"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    row = await db.get(LdapProvider, provider_id)
    if row is None or row.deleted_at is not None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "not_found")
    row.deleted_at = datetime.now(tz=UTC)
    await audit_and_emit(
        db,
        actor_user_id=user.user_id,
        organization_id=user.org_id,
        action="ldap_provider_deleted",
        entity_type="ldap_provider",
        entity_id=row.id,
        emit_outbox=True,
    )
    await db.flush()


# ---------------------------------------------------------------------------
# Test-connection endpoint
# ---------------------------------------------------------------------------


@router.post("/{provider_id}/test-connection", response_model=TestConnectionResult)
async def test_connection(
    provider_id: UUID,
    user: Annotated[CurrentUser, Depends(require_permission("manageConfig"))],
    db: Annotated[AsyncSession, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> TestConnectionResult:
    row = await db.get(LdapProvider, provider_id)
    if row is None or row.deleted_at is not None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "not_found")

    try:
        cfg = LdapProviderConfig.from_row(row, settings.secret_key)
    except InvalidToken:
        await audit_and_emit(
            db,
            actor_user_id=user.user_id,
            organization_id=user.org_id,
            action="ldap_test_connection",
            entity_type="ldap_provider",
            entity_id=row.id,
            diff={"ok": False, "error": "bind_password_decrypt_failed", "duration_ms": 0},
        )
        return TestConnectionResult(
            ok=False,
            server_uri_used=None,
            error="bind_password_decrypt_failed",
            duration_ms=0,
        )

    client = LdapClient(
        server_uris=cfg.server_uris,
        tls_required=cfg.tls_required,
        allow_insecure=cfg.allow_insecure,
        timeout_seconds=cfg.timeout_seconds,
    )
    started = time.monotonic()
    ok: bool
    err: str | None
    uri: str | None
    try:
        client.bind_and_search(
            bind_dn=cfg.bind_dn,
            bind_password=cfg.bind_password,
            base_dn=cfg.base_dn,
            search_filter="(objectClass=*)",
            attributes=[],
        )
        ok = True
        err = None
        uri = cfg.server_uris[0] if cfg.server_uris else None
    except (LdapConnectionError, LdapServiceBindError) as exc:
        ok = False
        err = str(exc)
        uri = None
    duration_ms = int((time.monotonic() - started) * 1000)

    await audit_and_emit(
        db,
        actor_user_id=user.user_id,
        organization_id=user.org_id,
        action="ldap_test_connection",
        entity_type="ldap_provider",
        entity_id=row.id,
        diff={"ok": ok, "error": err, "duration_ms": duration_ms},
        emit_outbox=True,
    )
    return TestConnectionResult(ok=ok, server_uri_used=uri, error=err, duration_ms=duration_ms)


# ---------------------------------------------------------------------------
# Group mapping endpoints
# ---------------------------------------------------------------------------


@router.get("/{provider_id}/mappings", response_model=list[LdapGroupMappingOut])
async def list_mappings(
    provider_id: UUID,
    _user: Annotated[CurrentUser, Depends(require_permission("manageConfig"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[LdapGroupMappingOut]:
    parent = await db.get(LdapProvider, provider_id)
    if parent is None or parent.deleted_at is not None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "not_found")
    rows = (
        (
            await db.execute(
                select(LdapGroupMapping).where(LdapGroupMapping.ldap_provider_id == provider_id)
            )
        )
        .scalars()
        .all()
    )
    return [_mapping_to_out(r) for r in rows]


@router.post(
    "/{provider_id}/mappings",
    response_model=LdapGroupMappingOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_mapping(
    provider_id: UUID,
    body: LdapGroupMappingIn,
    user: Annotated[CurrentUser, Depends(require_permission("manageConfig"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> LdapGroupMappingOut:
    parent = await db.get(LdapProvider, provider_id)
    if parent is None or parent.deleted_at is not None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "not_found")
    row = LdapGroupMapping(
        ldap_provider_id=provider_id,
        group_dn=body.group_dn,
        organization_id=body.organization_id,
        profile_id=body.profile_id,
    )
    db.add(row)
    try:
        await db.flush()
    except IntegrityError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, "mapping_already_exists") from exc

    await audit_and_emit(
        db,
        actor_user_id=user.user_id,
        organization_id=user.org_id,
        action="ldap_mapping_created",
        entity_type="ldap_provider",
        entity_id=provider_id,
        diff={
            "group_dn": body.group_dn,
            "organization_id": str(body.organization_id),
            "profile_id": str(body.profile_id),
        },
        emit_outbox=True,
    )
    return _mapping_to_out(row)


@router.delete(
    "/{provider_id}/mappings/{mapping_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_mapping(
    provider_id: UUID,
    mapping_id: UUID,
    user: Annotated[CurrentUser, Depends(require_permission("manageConfig"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    row = await db.get(LdapGroupMapping, mapping_id)
    if row is None or row.ldap_provider_id != provider_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "not_found")
    await db.delete(row)
    await audit_and_emit(
        db,
        actor_user_id=user.user_id,
        organization_id=user.org_id,
        action="ldap_mapping_deleted",
        entity_type="ldap_provider",
        entity_id=provider_id,
        diff={"mapping_id": str(mapping_id)},
        emit_outbox=True,
    )
    await db.flush()
