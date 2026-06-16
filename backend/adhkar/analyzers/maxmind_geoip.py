"""MaxMind GeoIP analyzer.

Resolves an IP observable to country + ASN using local MaxMind databases.
Pure read against the filesystem so it runs offline and can sit inside
the Docker sandbox safely. The `maxminddb` package is intentionally
optional — when missing, the analyzer returns a structured error rather
than crashing the runner."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from adhkar.analyzers.base import Analyzer, AnalyzerResult

_log = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class MaxMindGeoIpConfig:
    city_db_path: str | None = None
    asn_db_path: str | None = None


class MaxMindGeoIpAnalyzer(Analyzer):
    name = "MaxMind_GeoIP_0_1"
    description = "Resolve IP observables to country + city + ASN via MaxMind databases."
    supported_types = frozenset({"ip"})

    def __init__(self, config: MaxMindGeoIpConfig) -> None:
        self.config = config

    async def run(self, data_type: str, data: str) -> AnalyzerResult:
        if data_type not in self.supported_types:
            return AnalyzerResult(
                summary={"errorMessage": f"unsupported_dataType:{data_type}"},
                full={},
            )
        try:
            import maxminddb  # type: ignore[import-not-found]
        except ImportError:
            return AnalyzerResult(
                summary={"errorMessage": "maxminddb_package_not_installed"},
                full={"install_hint": "uv add maxminddb"},
            )
        full: dict[str, Any] = {}
        country: str | None = None
        city: str | None = None
        asn: int | None = None
        asn_org: str | None = None
        if self.config.city_db_path:
            try:
                with maxminddb.open_database(self.config.city_db_path) as r:
                    rec = r.get(data) or {}
                full["city"] = rec
                country = (rec.get("country", {}) or {}).get("names", {}).get("en")
                city = (rec.get("city", {}) or {}).get("names", {}).get("en")
            except (FileNotFoundError, ValueError) as e:
                _log.warning("maxmind_city_lookup_failed: %s", e)
                full["city_error"] = str(e)
        if self.config.asn_db_path:
            try:
                with maxminddb.open_database(self.config.asn_db_path) as r:
                    rec = r.get(data) or {}
                full["asn"] = rec
                asn = rec.get("autonomous_system_number")
                asn_org = rec.get("autonomous_system_organization")
            except (FileNotFoundError, ValueError) as e:
                _log.warning("maxmind_asn_lookup_failed: %s", e)
                full["asn_error"] = str(e)
        summary: dict[str, Any] = {
            "ip": data,
            "country": country,
            "city": city,
            "asn": asn,
            "asn_org": asn_org,
        }
        if not any([country, city, asn, asn_org]):
            summary["errorMessage"] = "no_record_found_in_configured_databases"
        return AnalyzerResult(summary=summary, full=full)
