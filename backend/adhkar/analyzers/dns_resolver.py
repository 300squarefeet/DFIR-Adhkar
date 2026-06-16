"""DNS resolver analyzer: A/AAAA/PTR lookup."""

from __future__ import annotations

import asyncio
import socket

from adhkar.analyzers.base import Analyzer, AnalyzerResult


class DnsResolver(Analyzer):
    name = "DNS_Resolver_1_0"
    supported_types = frozenset({"ip", "domain"})
    description = "Reverse and forward DNS lookups via system resolver."

    async def run(self, data_type: str, data: str) -> AnalyzerResult:
        if data_type == "domain":
            try:
                infos = await asyncio.get_event_loop().getaddrinfo(data, None)
                addrs = sorted({i[4][0] for i in infos})
                return AnalyzerResult(
                    summary={"resolved": True, "count": len(addrs)},
                    full={"addresses": addrs},
                )
            except socket.gaierror as e:
                return AnalyzerResult(
                    summary={"resolved": False, "error": str(e)},
                    full={"error": str(e)},
                )
        # data_type == ip
        try:
            host, _, _ = await asyncio.get_event_loop().run_in_executor(
                None, socket.gethostbyaddr, data
            )
            return AnalyzerResult(
                summary={"reverse": host},
                full={"hostname": host},
            )
        except socket.herror as e:
            return AnalyzerResult(
                summary={"reverse": None, "error": str(e)},
                full={"error": str(e)},
            )
