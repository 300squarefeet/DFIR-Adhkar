"""LdapAuthService: orchestrate provider iteration, group resolution, upsert.

Flow:
  1. Load enabled providers ordered by priority ASC.
  2. For each provider:
     - Check circuit breaker (Redis key ldap:open:{name}:{id}); skip if open.
     - Build LdapClient + LdapProviderConfig from the row.
     - Service-bind + search by rendered filter (email -> {input}).
     - On 0 hits OR user-bind False  -> raise LdapInvalidCredentials (no skip).
     - On LdapConnectionError / LdapServiceBindError -> bump fail counter, audit, continue.
     - On success: fetch memberOf, resolve_memberships, fail-closed check, return BindResult.
  3. If every provider raised connection-class errors, raise LdapAllProvidersFailed.

Circuit breaker math: INCR `ldap:fail:{name}:{id}` (TTL 60s) on every
connection-class failure. When the post-INCR count crosses 50, SET
`ldap:open:{name}:{id}` TTL 300s. The next call sees
`exists ldap:open:{name}:{id}` and skips that provider until the key expires.
The `{name}` prefix exists so operators can grep Redis by human-readable
provider name; `{id}` keeps keys unique."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, cast
from uuid import UUID

from sqlalchemy import select

from adhkar.auth.ldap_client import LdapClient
from adhkar.auth.ldap_errors import (
    LdapAllProvidersFailed,
    LdapConnectionError,
    LdapInvalidCredentials,
    LdapNoAuthorizedGroup,
    LdapServiceBindError,
)
from adhkar.auth.ldap_provider import LdapProviderConfig
from adhkar.db.models import (
    LdapGroupMapping,
    LdapProvider,
    Organization,
    User,
    UserOrgMembership,
)

if TYPE_CHECKING:
    from redis.asyncio import Redis as RedisType
    from sqlalchemy.ext.asyncio import AsyncSession

CIRCUIT_FAIL_THRESHOLD = 50
CIRCUIT_FAIL_WINDOW_SECONDS = 60
CIRCUIT_OPEN_TTL_SECONDS = 300


@dataclass(frozen=True, slots=True)
class BindResult:
    provider_id: UUID
    user_dn: str
    email: str
    display_name: str
    matched_group_dns: list[str]
    resolved_memberships: list[tuple[UUID, UUID]]


class LdapAuthService:
    def __init__(self, *, secret_key: str, redis: RedisType[Any] | None) -> None:
        self._secret_key = secret_key
        self._redis = redis

    def _build_client(self, cfg: LdapProviderConfig) -> LdapClient:
        return LdapClient(
            server_uris=cfg.server_uris,
            tls_required=cfg.tls_required,
            allow_insecure=cfg.allow_insecure,
            timeout_seconds=cfg.timeout_seconds,
        )

    async def _load_enabled_providers(self, db: AsyncSession) -> list[LdapProviderConfig]:
        rows = (
            (
                await db.execute(
                    select(LdapProvider)
                    .where(LdapProvider.enabled.is_(True), LdapProvider.deleted_at.is_(None))
                    .order_by(LdapProvider.priority.asc())
                )
            )
            .scalars()
            .all()
        )
        return [LdapProviderConfig.from_row(r, self._secret_key) for r in rows]

    async def _circuit_open(self, provider_id: UUID, provider_name: str) -> bool:
        if self._redis is None:
            return False
        return bool(await self._redis.exists(f"ldap:open:{provider_name}:{provider_id}"))

    async def _bump_failure(self, provider_id: UUID, provider_name: str) -> None:
        if self._redis is None:
            return
        count = await self._redis.incr(f"ldap:fail:{provider_name}:{provider_id}")
        if count == 1:
            await self._redis.expire(
                f"ldap:fail:{provider_name}:{provider_id}", CIRCUIT_FAIL_WINDOW_SECONDS
            )
        if count > CIRCUIT_FAIL_THRESHOLD:
            await self._redis.set(
                f"ldap:open:{provider_name}:{provider_id}", "1", ex=CIRCUIT_OPEN_TTL_SECONDS
            )

    async def _resolve_memberships(
        self,
        db: AsyncSession,
        provider_id: UUID,
        group_dns: list[str],
    ) -> list[tuple[UUID, UUID]]:
        if not group_dns:
            return []
        rows = (
            await db.execute(
                select(LdapGroupMapping.organization_id, LdapGroupMapping.profile_id)
                .join(Organization, Organization.id == LdapGroupMapping.organization_id)
                .where(
                    LdapGroupMapping.ldap_provider_id == provider_id,
                    LdapGroupMapping.group_dn.in_(group_dns),
                    Organization.deleted_at.is_(None),
                )
            )
        ).all()
        return [(row[0], row[1]) for row in rows]

    async def _count_manual_memberships(self, db: AsyncSession, email: str) -> int:
        result = await db.execute(
            select(UserOrgMembership)
            .join(User, User.id == UserOrgMembership.user_id)
            .where(User.email == email, UserOrgMembership.source == "manual")
        )
        return len(result.scalars().all())

    async def try_bind(
        self,
        db: AsyncSession,
        *,
        email: str,
        password: str,
    ) -> BindResult:
        providers = await self._load_enabled_providers(db)
        attempted = 0
        connection_failures = 0
        for cfg in providers:
            if await self._circuit_open(cfg.id, cfg.name):
                continue
            attempted += 1
            client = self._build_client(cfg)
            try:
                entries = client.bind_and_search(
                    bind_dn=cfg.bind_dn,
                    bind_password=cfg.bind_password,
                    base_dn=cfg.base_dn,
                    search_filter=cfg.render_filter(email),
                    attributes=[
                        cfg.user_id_attr,
                        cfg.user_email_attr,
                        cfg.user_display_name_attr,
                        cfg.group_membership_attr,
                    ],
                )
            except (LdapConnectionError, LdapServiceBindError):
                await self._bump_failure(cfg.id, cfg.name)
                connection_failures += 1
                continue
            if not entries:
                # User not found on this provider — continue to next provider.
                # Anti-enumeration: final error is LdapInvalidCredentials regardless.
                continue

            entry = entries[0]
            user_dn = cast(str, entry["dn"])
            if not client.user_bind(user_dn, password):
                raise LdapInvalidCredentials("user-bind rejected")

            attrs = cast(dict[str, list[str]], entry["attrs"])
            display_name = (attrs.get(cfg.user_display_name_attr) or [email])[0]
            resolved_email = (attrs.get(cfg.user_email_attr) or [email])[0]
            groups = list(attrs.get(cfg.group_membership_attr) or [])

            resolved = await self._resolve_memberships(db, cfg.id, groups)
            if not resolved:
                manual = await self._count_manual_memberships(db, resolved_email)
                if manual == 0:
                    raise LdapNoAuthorizedGroup(
                        f"no group mapping matched and no manual membership for {resolved_email}"
                    )

            return BindResult(
                provider_id=cfg.id,
                user_dn=user_dn,
                email=resolved_email,
                display_name=display_name,
                matched_group_dns=groups,
                resolved_memberships=resolved,
            )

        if attempted > 0 and connection_failures == attempted:
            raise LdapAllProvidersFailed("every provider failed to connect")
        raise LdapInvalidCredentials("no provider available")

    async def upsert_user_and_memberships(
        self,
        db: AsyncSession,
        result: BindResult,
        *,
        request_ip: str | None,
    ) -> User:
        from adhkar.audit import audit_and_emit
        from adhkar.db.models import User

        existing = (
            await db.execute(select(User).where(User.email == result.email))
        ).scalar_one_or_none()

        first_time = existing is None
        if existing is None:
            existing = User(
                email=result.email,
                display_name=result.display_name,
                password_hash=None,
                status="active",
                default_org_id=(
                    result.resolved_memberships[0][0] if result.resolved_memberships else None
                ),
            )
            db.add(existing)
            await db.flush()
        else:
            existing.display_name = result.display_name
            if existing.default_org_id is None and result.resolved_memberships:
                existing.default_org_id = result.resolved_memberships[0][0]

        existing_ldap = (
            (
                await db.execute(
                    select(UserOrgMembership).where(
                        UserOrgMembership.user_id == existing.id,
                        UserOrgMembership.source == "ldap",
                    )
                )
            )
            .scalars()
            .all()
        )
        existing_pairs = {(m.organization_id, m.profile_id) for m in existing_ldap}
        resolved_pairs = set(result.resolved_memberships)
        to_add = resolved_pairs - existing_pairs
        to_remove = existing_pairs - resolved_pairs

        for m in existing_ldap:
            if (m.organization_id, m.profile_id) in to_remove:
                await db.delete(m)
        for org_id, profile_id in to_add:
            db.add(
                UserOrgMembership(
                    user_id=existing.id,
                    organization_id=org_id,
                    profile_id=profile_id,
                    source="ldap",
                )
            )

        action = "ldap_user_provisioned" if first_time else "ldap_membership_sync"
        await audit_and_emit(
            db,
            actor_user_id=existing.id,
            organization_id=existing.default_org_id,
            action=action,
            entity_type="user",
            entity_id=existing.id,
            diff={
                "provider_id": str(result.provider_id),
                "added": [[str(a), str(b)] for a, b in to_add],
                "removed": [[str(a), str(b)] for a, b in to_remove],
                "groups": result.matched_group_dns,
            },
            ip=request_ip,
        )
        await db.flush()
        return existing
