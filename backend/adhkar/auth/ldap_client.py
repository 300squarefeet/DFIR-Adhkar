"""Thin wrapper over ldap3.Connection.

Knows nothing about the database. Two methods: bind_and_search (service-bind)
and user_bind (per-user password verify). Always unbinds; never leaks the
password into exception strings."""

from __future__ import annotations

from dataclasses import dataclass

from ldap3 import ALL, Connection, Server, Tls
from ldap3.core.exceptions import LDAPBindError, LDAPException, LDAPSocketOpenError

from adhkar.auth.ldap_errors import LdapConnectionError, LdapInvalidCredentials


def _build_connection(
    uri: str,
    bind_dn: str,
    bind_password: str,
    tls_required: bool,
    allow_insecure: bool,
    timeout: int,
) -> Connection:
    use_ssl = uri.startswith("ldaps://")
    tls = Tls() if (tls_required and not allow_insecure) else None
    server = Server(uri, use_ssl=use_ssl, tls=tls, get_info=ALL, connect_timeout=timeout)
    return Connection(
        server,
        user=bind_dn,
        password=bind_password,
        auto_bind=False,
        receive_timeout=timeout,
    )


@dataclass(slots=True)
class LdapClient:
    server_uris: list[str]
    tls_required: bool
    allow_insecure: bool
    timeout_seconds: int = 5

    def bind_and_search(
        self,
        *,
        bind_dn: str,
        bind_password: str,
        base_dn: str,
        search_filter: str,
        attributes: list[str],
    ) -> list[dict[str, object]]:
        last_exc: Exception | None = None
        for uri in self.server_uris:
            conn = _build_connection(
                uri,
                bind_dn,
                bind_password,
                self.tls_required,
                self.allow_insecure,
                self.timeout_seconds,
            )
            try:
                if not conn.bind():
                    raise LdapConnectionError(f"service-bind failed at {uri}")
                conn.search(
                    search_base=base_dn,
                    search_filter=search_filter,
                    attributes=attributes,
                )
                return [
                    {
                        "dn": entry.entry_dn,
                        "attrs": {k: list(v) for k, v in entry.entry_attributes_as_dict.items()},
                    }
                    for entry in conn.entries
                ]
            except (LDAPSocketOpenError, LDAPException) as exc:
                last_exc = exc
                continue
            finally:
                try:
                    conn.unbind()
                except Exception:  # noqa: S110 — cleanup, swallow
                    pass
        raise LdapConnectionError(f"all server URIs unreachable: {self.server_uris}") from last_exc

    def user_bind(self, user_dn: str, password: str) -> bool:
        if not password:
            raise LdapInvalidCredentials("empty password rejected")
        last_exc: Exception | None = None
        for uri in self.server_uris:
            conn = _build_connection(
                uri,
                user_dn,
                password,
                self.tls_required,
                self.allow_insecure,
                self.timeout_seconds,
            )
            try:
                bound = conn.bind()
                if bound:
                    return True
                # ldap3 sets result.description = 'invalidCredentials' on wrong pw
                if conn.result and conn.result.get("description") == "invalidCredentials":
                    return False
                raise LdapConnectionError(f"user-bind unexpected failure at {uri}")
            except LDAPBindError:
                return False
            except (LDAPSocketOpenError, LDAPException) as exc:
                last_exc = exc
                continue
            finally:
                try:
                    conn.unbind()
                except Exception:  # noqa: S110 — cleanup, swallow
                    pass
        raise LdapConnectionError(f"all server URIs unreachable: {self.server_uris}") from last_exc
