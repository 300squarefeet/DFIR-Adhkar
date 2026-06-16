"""MISP feeder unit tests with mocked httpx transport."""

from __future__ import annotations

import httpx
import pytest
from adhkar.feeders.misp import MispFeeder, MispFeederConfig


@pytest.mark.asyncio
async def test_maps_misp_event_to_alert_payload(monkeypatch) -> None:
    captured = {}

    async def fake_post(self, url, json, headers):
        captured["url"] = url
        captured["json"] = json
        return httpx.Response(
            200,
            json={
                "response": [
                    {
                        "Event": {
                            "uuid": "abc-123",
                            "info": "Phishing wave from acme.com",
                            "description": "user reported",
                            "threat_level_id": "2",
                            "Tag": [
                                {"name": "tlp:amber"},
                                {"name": "campaign:acme"},
                            ],
                            "Orgc": {"name": "CIRCL"},
                        }
                    }
                ]
            },
            request=httpx.Request("POST", url),
        )

    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)

    cfg = MispFeederConfig(base_url="https://misp.example", api_key="key", instance_name="ci-misp")
    feeder = MispFeeder(cfg)

    out = []
    async for p in feeder.poll():
        out.append(p)

    assert len(out) == 1
    p = out[0]
    assert p.type == "misp.event"
    assert p.source == "ci-misp"
    assert p.source_ref == "abc-123"
    assert p.title == "Phishing wave from acme.com"
    assert p.severity == 3  # threat_level_id=2 → severity 3 (High)
    assert p.tlp == "amber"
    assert "campaign:acme" in p.tags
    assert p.custom_fields["orgc"] == "CIRCL"


@pytest.mark.asyncio
async def test_handles_empty_response(monkeypatch) -> None:
    async def fake_post(self, url, json, headers):
        return httpx.Response(200, json={"response": []}, request=httpx.Request("POST", url))

    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)
    feeder = MispFeeder(
        MispFeederConfig(base_url="https://m.example", api_key="k", instance_name="m")
    )
    out = [p async for p in feeder.poll()]
    assert out == []
