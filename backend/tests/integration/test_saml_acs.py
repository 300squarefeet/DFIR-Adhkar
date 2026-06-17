"""End-to-end: POST a signed SAML fixture against the live /acs endpoint.

Mounts a pre-built SamlVerifier into app.state so we don't need to
hit a real IdP metadata URL during the test. Overrides get_db with a
no-op session and get_redis with a fakeredis instance so we don't
need a live Postgres or Redis. The valid-response 200 test is
deferred to the testcontainers integration suite (separate plan)
since it needs a live DB to mint tokens."""

from __future__ import annotations

import base64
import json
import pathlib
from datetime import UTC, datetime

import fakeredis.aioredis
import pytest
import pytest_asyncio
from adhkar.api.deps import get_db, get_redis
from adhkar.auth.saml import SamlProviderConfig
from adhkar.auth.saml_verifier import build_verifier_from_metadata_xml
from adhkar.core.settings import Settings, get_settings
from adhkar.main import create_app
from freezegun import freeze_time
from httpx import ASGITransport, AsyncClient

FIXTURES = pathlib.Path(__file__).parent.parent / "unit" / "fixtures" / "saml"
FROZEN_NOW = datetime(2026, 6, 17, 12, 0, 0, tzinfo=UTC)


class _NoopSession:
    """Stub AsyncSession that satisfies the few methods the ACS path calls.

    The ACS handler under test will reach this only when an exception
    branch invokes _audit_failed -> audit_and_emit. We swallow .add and
    .flush so the audit path doesn't crash; we DON'T need to verify the
    audit row was written here (that's unit-test territory)."""

    async def execute(self, *_args, **_kwargs):
        class _R:
            def scalar_one_or_none(self):
                return None

        return _R()

    def add(self, _obj) -> None:
        return None

    async def flush(self) -> None:
        return None


async def _override_db():
    yield _NoopSession()


@pytest_asyncio.fixture
async def fake_redis():
    r = fakeredis.aioredis.FakeRedis()
    try:
        yield r
    finally:
        await r.aclose()


@pytest.fixture
def saml_env(monkeypatch) -> None:
    monkeypatch.setenv("ADHKAR_SECRET_KEY", "x" * 32)
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://u:p@h/db")
    monkeypatch.setenv("REDIS_URL", "redis://h:6379/0")
    monkeypatch.setenv(
        "ADHKAR_SAML_PROVIDERS_JSON",
        json.dumps(
            {
                "test": {
                    "idp_entity_id": "https://idp.test/saml/metadata",
                    "idp_sso_url": "https://idp.test/saml/sso",
                    "sp_entity_id": "https://adhkar.test/api/v1/auth/saml/test/metadata",
                    "acs_url": "https://adhkar.test/v1/auth/saml/test/acs",
                    "metadata_url": "https://idp.test/metadata",
                }
            }
        ),
    )
    get_settings.cache_clear()


def _b64(name: str) -> str:
    return base64.b64encode((FIXTURES / name).read_bytes()).decode()


def _build_app(saml_env, fake_redis, *, with_verifier: bool):
    app = create_app(Settings())
    if with_verifier:
        cfg = SamlProviderConfig(
            name="test",
            idp_entity_id="https://idp.test/saml/metadata",
            idp_sso_url="https://idp.test/saml/sso",
            sp_entity_id="https://adhkar.test/api/v1/auth/saml/test/metadata",
            acs_url="https://adhkar.test/v1/auth/saml/test/acs",
            metadata_url="https://idp.test/metadata",
            wanted_attributes={"email": "mail", "display_name": "displayName"},
        )
        metadata_xml = (FIXTURES / "valid_idp_metadata.xml").read_text()
        app.state.saml_verifiers = {"test": build_verifier_from_metadata_xml(cfg, metadata_xml)}
    else:
        app.state.saml_verifiers = {}

    app.dependency_overrides[get_db] = _override_db

    async def _override_redis():
        yield fake_redis

    app.dependency_overrides[get_redis] = _override_redis
    return app


@pytest.mark.asyncio
@freeze_time(FROZEN_NOW)
async def test_acs_with_wrong_signer_returns_401(saml_env, fake_redis) -> None:
    app = _build_app(saml_env, fake_redis, with_verifier=True)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://t") as c:
        r = await c.post(
            "/v1/auth/saml/test/acs",
            data={"SAMLResponse": _b64("wrong_signer_response.xml"), "RelayState": ""},
        )
    assert r.status_code == 401
    assert r.json()["detail"] == "signature_invalid"


@pytest.mark.asyncio
@freeze_time(FROZEN_NOW)
async def test_acs_without_verifier_returns_503(saml_env, fake_redis) -> None:
    app = _build_app(saml_env, fake_redis, with_verifier=False)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://t") as c:
        r = await c.post(
            "/v1/auth/saml/test/acs",
            data={"SAMLResponse": _b64("valid_response.xml"), "RelayState": ""},
        )
    assert r.status_code == 503
    assert r.json()["detail"] == "saml_metadata_unavailable"
