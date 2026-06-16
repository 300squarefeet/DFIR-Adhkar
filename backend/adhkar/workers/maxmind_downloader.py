"""MaxMind GeoLite2 .mmdb auto-downloader.

Polls the MaxMind permalink URLs once per day and replaces the cached
.mmdb files when the upstream Last-Modified is newer than what's on disk.
Skips when no license key is configured."""

from __future__ import annotations

import asyncio
import logging
import os
import tarfile
import tempfile
from email.utils import parsedate_to_datetime
from pathlib import Path

import httpx

from adhkar.core.settings import Settings

_log = logging.getLogger(__name__)

_POLL_INTERVAL_SECONDS = 24 * 3600

# Database SKUs → conventional on-disk filenames inside the tarball.
_EDITIONS = (
    ("GeoLite2-City", "GeoLite2-City.mmdb"),
    ("GeoLite2-ASN", "GeoLite2-ASN.mmdb"),
)


def _do_blocking_download(
    resp_bytes: bytes,
    last_modified: str | None,
    target_dir: Path,
    out_path: Path,
    mmdb_name: str,
    edition_id: str,
) -> bool:
    with tempfile.NamedTemporaryFile(suffix=".tar.gz", delete=False) as tmp:
        tmp.write(resp_bytes)
        tar_path = Path(tmp.name)
    try:
        with tarfile.open(tar_path, mode="r:gz") as tar:
            extracted: bytes | None = None
            for member in tar.getmembers():
                if member.isfile() and member.name.endswith(mmdb_name):
                    fh = tar.extractfile(member)
                    if fh is None:
                        continue
                    extracted = fh.read()
                    break
        if extracted is None:
            _log.warning("maxmind_mmdb_not_in_tarball edition=%s", edition_id)
            return False
        target_dir.mkdir(parents=True, exist_ok=True)
        tmp_out = out_path.with_suffix(".mmdb.tmp")
        tmp_out.write_bytes(extracted)
        os.replace(tmp_out, out_path)
        if last_modified:
            try:
                ts = parsedate_to_datetime(last_modified).timestamp()
                os.utime(out_path, (ts, ts))
            except (TypeError, ValueError):
                pass
        _log.info(
            "maxmind_updated edition=%s bytes=%d -> %s",
            edition_id,
            len(extracted),
            out_path,
        )
        return True
    finally:
        try:
            tar_path.unlink()
        except OSError:
            pass


async def _download_once(
    license_key: str, target_dir: Path, edition_id: str, mmdb_name: str
) -> bool:
    """Fetch one edition's tar.gz, extract the .mmdb, atomically replace."""
    url = (
        "https://download.maxmind.com/app/geoip_download"
        f"?edition_id={edition_id}"
        f"&license_key={license_key}"
        "&suffix=tar.gz"
    )
    out_path = target_dir / mmdb_name
    headers: dict[str, str] = {}
    if await asyncio.to_thread(out_path.exists):
        mtime = (await asyncio.to_thread(out_path.stat)).st_mtime
        from email.utils import formatdate

        headers["If-Modified-Since"] = formatdate(mtime, usegmt=True)
    async with httpx.AsyncClient(timeout=120.0) as client:
        resp = await client.get(url, headers=headers)
    if resp.status_code == 304:
        _log.info("maxmind_unchanged edition=%s", edition_id)
        return False
    if resp.status_code != 200:
        _log.warning("maxmind_download_failed edition=%s status=%d", edition_id, resp.status_code)
        return False
    return await asyncio.to_thread(
        _do_blocking_download,
        resp.content,
        resp.headers.get("Last-Modified"),
        target_dir,
        out_path,
        mmdb_name,
        edition_id,
    )


async def run_maxmind_downloader(settings: Settings) -> None:
    license_key = getattr(settings, "maxmind_license_key", "") or ""
    if not license_key:
        _log.info("maxmind_downloader_disabled_no_license_key")
        return
    target_dir = Path(getattr(settings, "maxmind_db_dir", "/var/lib/adhkar/maxmind"))
    while True:
        for edition_id, mmdb_name in _EDITIONS:
            try:
                await _download_once(license_key, target_dir, edition_id, mmdb_name)
            except Exception:
                _log.exception("maxmind_download_round_failed edition=%s", edition_id)
        await asyncio.sleep(_POLL_INTERVAL_SECONDS)
