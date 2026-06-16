"""Presigned PUT URL builder unit tests (deterministic via fixed `now`)."""

from __future__ import annotations

import datetime as dt
from urllib.parse import parse_qs, urlparse

from adhkar.storage.presigned import S3Config, presigned_put_url


def _cfg() -> S3Config:
    return S3Config(
        region="us-east-1",
        bucket="adhkar-attachments",
        endpoint="http://minio.local:9000",
        access_key_id="AKIAIOSFODNN7EXAMPLE",
        secret_access_key="wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
        path_style=True,
    )


def _fixed_now() -> dt.datetime:
    return dt.datetime(2026, 6, 17, 12, 0, 0, tzinfo=dt.UTC)


def test_presigned_url_is_stable_for_fixed_inputs() -> None:
    url1 = presigned_put_url(_cfg(), "k/abc.bin", "application/octet-stream", 600, _fixed_now())
    url2 = presigned_put_url(_cfg(), "k/abc.bin", "application/octet-stream", 600, _fixed_now())
    assert url1 == url2


def test_presigned_url_path_style_includes_bucket_in_path() -> None:
    url = presigned_put_url(_cfg(), "k/abc.bin", "application/octet-stream", 600, _fixed_now())
    p = urlparse(url)
    assert p.path == "/adhkar-attachments/k/abc.bin"
    assert p.scheme == "http"
    assert p.netloc == "minio.local:9000"


def test_presigned_url_has_required_query_params() -> None:
    url = presigned_put_url(_cfg(), "k/abc.bin", "application/octet-stream", 600, _fixed_now())
    q = parse_qs(urlparse(url).query)
    for key in (
        "X-Amz-Algorithm",
        "X-Amz-Credential",
        "X-Amz-Date",
        "X-Amz-Expires",
        "X-Amz-SignedHeaders",
        "X-Amz-Signature",
    ):
        assert key in q, f"missing query param: {key}"
    assert q["X-Amz-Algorithm"] == ["AWS4-HMAC-SHA256"]
    assert q["X-Amz-Expires"] == ["600"]


def test_presigned_url_different_keys_have_different_signatures() -> None:
    a = presigned_put_url(_cfg(), "k/one.bin", "application/octet-stream", 600, _fixed_now())
    b = presigned_put_url(_cfg(), "k/two.bin", "application/octet-stream", 600, _fixed_now())
    sig_a = parse_qs(urlparse(a).query)["X-Amz-Signature"][0]
    sig_b = parse_qs(urlparse(b).query)["X-Amz-Signature"][0]
    assert sig_a != sig_b
