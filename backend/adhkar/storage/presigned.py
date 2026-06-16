"""Pure-Python AWS S3 SigV4 presigned-PUT URL generator.

Works against any S3-compatible endpoint (MinIO, Backblaze, etc.) without
adding boto3/aioboto3 as a runtime dependency. We only need the presigned
URL; the actual upload happens in the browser via fetch(PUT).

Reference: AWS Sig v4 presigned URL spec.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import hmac
from dataclasses import dataclass
from urllib.parse import quote


@dataclass(frozen=True, slots=True)
class S3Config:
    region: str
    bucket: str
    endpoint: str
    # e.g. "https://s3.amazonaws.com" or "http://minio.local:9000"
    access_key_id: str
    secret_access_key: str
    path_style: bool = True
    # MinIO + most self-hosted compat needs path-style addressing


def _sign(key: bytes, msg: str) -> bytes:
    return hmac.new(key, msg.encode("utf-8"), hashlib.sha256).digest()


def _signing_key(secret: str, date_stamp: str, region: str, service: str) -> bytes:
    k = ("AWS4" + secret).encode("utf-8")
    k = _sign(k, date_stamp)
    k = _sign(k, region)
    k = _sign(k, service)
    return _sign(k, "aws4_request")


def presigned_put_url(
    cfg: S3Config,
    object_key: str,
    content_type: str,
    expires_seconds: int = 3600,
    now: dt.datetime | None = None,
) -> str:
    """Build a SigV4 presigned URL the browser can PUT to."""
    now = now or dt.datetime.now(tz=dt.UTC)
    amz_date = now.strftime("%Y%m%dT%H%M%SZ")
    date_stamp = now.strftime("%Y%m%d")
    service = "s3"
    algorithm = "AWS4-HMAC-SHA256"
    credential_scope = f"{date_stamp}/{cfg.region}/{service}/aws4_request"

    if cfg.path_style:
        host = cfg.endpoint.replace("https://", "").replace("http://", "").rstrip("/")
        canonical_uri = f"/{cfg.bucket}/{quote(object_key, safe='/')}"
        url_base = f"{cfg.endpoint.rstrip('/')}/{cfg.bucket}/{quote(object_key, safe='/')}"
    else:
        bare = cfg.endpoint.replace("https://", "").replace("http://", "").rstrip("/")
        host = f"{cfg.bucket}.{bare}"
        canonical_uri = f"/{quote(object_key, safe='/')}"
        scheme = "https" if cfg.endpoint.startswith("https://") else "http"
        url_base = f"{scheme}://{host}{canonical_uri}"

    canonical_headers = f"host:{host}\n"
    signed_headers = "host"

    query_params = {
        "X-Amz-Algorithm": algorithm,
        "X-Amz-Credential": f"{cfg.access_key_id}/{credential_scope}",
        "X-Amz-Date": amz_date,
        "X-Amz-Expires": str(expires_seconds),
        "X-Amz-SignedHeaders": signed_headers,
        "X-Amz-ContentSha256": "UNSIGNED-PAYLOAD",
    }
    canonical_querystring = "&".join(
        f"{quote(k, safe='')}={quote(v, safe='')}" for k, v in sorted(query_params.items())
    )

    canonical_request = (
        f"PUT\n"
        f"{canonical_uri}\n"
        f"{canonical_querystring}\n"
        f"{canonical_headers}\n"
        f"{signed_headers}\n"
        f"UNSIGNED-PAYLOAD"
    )
    string_to_sign = (
        f"{algorithm}\n"
        f"{amz_date}\n"
        f"{credential_scope}\n"
        f"{hashlib.sha256(canonical_request.encode('utf-8')).hexdigest()}"
    )
    signing_key = _signing_key(cfg.secret_access_key, date_stamp, cfg.region, service)
    signature = hmac.new(signing_key, string_to_sign.encode("utf-8"), hashlib.sha256).hexdigest()

    # content_type is intentionally not included in canonical headers — clients
    # set it on the PUT but it is not part of the signed surface, matching
    # boto3's default UNSIGNED-PAYLOAD presigned PUTs.
    _ = content_type
    return f"{url_base}?{canonical_querystring}&X-Amz-Signature={signature}"
