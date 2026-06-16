"""MISP feeder: pulls published events from a MISP server as Adhkar alerts.

Maps MISP events → AlertPayload:
- type      = "misp.event"
- source    = "<misp_instance_name>"
- source_ref= "<event.uuid>"
- title     = "<event.info>"
- description= MISP event description field
- severity  = MISP threat_level_id (1=High → 4=Critical mapping inverted)
- tlp       = parsed from the Tag list (looks for tlp:white/green/amber/red)

Networking is via httpx. The feeder only emits payloads — the runner
persists them via the upsert path."""

from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any

import httpx

from adhkar.feeders.base import AlertPayload, Feeder

# MISP threat_level_id: 1=High, 2=Medium, 3=Low, 4=Undefined.
# Adhkar severity: 1=Low ... 4=Critical. We invert + cap.
_MISP_THREAT_TO_SEVERITY = {1: 4, 2: 3, 3: 2, 4: 1}


@dataclass(frozen=True, slots=True)
class MispFeederConfig:
    base_url: str
    api_key: str
    instance_name: str = "misp"
    limit: int = 100
    verify_ssl: bool = True


class MispFeeder(Feeder):
    name = "misp.events.v1"
    description = "MISP Published-Events pull (REST /events/restSearch)"

    def __init__(self, config: MispFeederConfig) -> None:
        self.config = config

    async def poll(self) -> AsyncIterator[AlertPayload]:
        url = self.config.base_url.rstrip("/") + "/events/restSearch"
        headers = {
            "Authorization": self.config.api_key,
            "Accept": "application/json",
            "Content-Type": "application/json",
        }
        body = {
            "limit": self.config.limit,
            "published": True,
            "returnFormat": "json",
        }
        async with httpx.AsyncClient(verify=self.config.verify_ssl, timeout=30.0) as client:
            r = await client.post(url, json=body, headers=headers)
            r.raise_for_status()
            data: dict[str, Any] = r.json()
        response_events = data.get("response") or data.get("Event") or []
        for item in response_events:
            event = item.get("Event") if isinstance(item, dict) and "Event" in item else item
            if not isinstance(event, dict):
                continue
            tags = []
            tlp = "amber"
            for tag in event.get("Tag", []) or []:
                tname = str(tag.get("name", "")).lower()
                if tname.startswith("tlp:"):
                    candidate = tname.split(":", 1)[1]
                    if candidate in ("white", "green", "amber", "amber-strict", "red"):
                        tlp = candidate
                else:
                    tags.append(str(tag.get("name", "")))
            try:
                tlid = int(event.get("threat_level_id") or 0)
            except (TypeError, ValueError):
                tlid = 0
            severity = _MISP_THREAT_TO_SEVERITY.get(tlid, 2)
            yield AlertPayload(
                type="misp.event",
                source=self.config.instance_name,
                source_ref=str(event.get("uuid") or event.get("id") or ""),
                title=str(event.get("info") or "(no info)")[:500],
                description=str(event.get("description") or "")[:5000] or None,
                severity=severity,
                tlp=tlp,
                pap="amber",
                tags=tags[:50],
                custom_fields={"orgc": str(event.get("Orgc", {}).get("name", ""))[:200]},
                raw_payload=event,
            )
