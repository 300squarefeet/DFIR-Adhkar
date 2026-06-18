"""Resolve the real client IP for a request.

Order:
  1. left-most non-private, non-loopback entry in X-Forwarded-For
  2. X-Real-IP header
  3. request.client.host
  4. None

The caller MUST sit behind a sanitizing reverse proxy in production —
we trust forwarded headers unconditionally."""

from __future__ import annotations

import ipaddress

from starlette.requests import Request

# Explicit RFC1918 / loopback / link-local ranges. We deliberately do NOT
# use ipaddress.is_private because that also flags documentation ranges
# (RFC 5737 TEST-NET-1/2/3, RFC 3849 2001:db8::/32) which downstream
# operators may legitimately route as public for testing.
_SKIP_NETS_V4 = (
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("169.254.0.0/16"),
)
_SKIP_NETS_V6 = (
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("fc00::/7"),
    ipaddress.ip_network("fe80::/10"),
)


def _is_private_or_loopback(ip: str) -> bool:
    try:
        parsed = ipaddress.ip_address(ip.strip())
    except ValueError:
        # Malformed -> treat as private so the next entry gets considered.
        return True
    nets: tuple[ipaddress.IPv4Network | ipaddress.IPv6Network, ...] = (
        _SKIP_NETS_V4 if isinstance(parsed, ipaddress.IPv4Address) else _SKIP_NETS_V6
    )
    return any(parsed in net for net in nets)


def source_ip(request: Request) -> str | None:
    xff = request.headers.get("x-forwarded-for")
    if xff:
        for raw in xff.split(","):
            candidate = raw.strip()
            if candidate and not _is_private_or_loopback(candidate):
                return candidate
    xri = request.headers.get("x-real-ip")
    if xri:
        stripped = xri.strip()
        if stripped:
            return stripped
    if request.client is not None:
        return request.client.host
    return None
