"""Register the built-in starter analyzers."""

from adhkar.analyzers.dns_resolver import DnsResolver
from adhkar.analyzers.mock_reputation import MockReputation
from adhkar.analyzers.registry import get_registry


def register_builtins() -> None:
    reg = get_registry()
    if reg.get("DNS_Resolver_1_0") is None:
        reg.register(DnsResolver())
    if reg.get("Mock_Reputation_0_1") is None:
        reg.register(MockReputation())
