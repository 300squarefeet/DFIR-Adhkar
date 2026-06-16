"""Analyzer job runner: poll queued analyzer_jobs and execute them in-process."""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from adhkar.analyzers._bootstrap import register_builtins
from adhkar.analyzers.registry import get_registry
from adhkar.core.settings import Settings
from adhkar.db.engine import create_engine
from adhkar.db.models import AnalyzerJob, Observable

_log = logging.getLogger(__name__)
POLL_INTERVAL_SECONDS = 1.0
BATCH_SIZE = 10


async def _run_pending(settings: Settings) -> int:
    engine = create_engine(settings)
    sf = async_sessionmaker(engine, expire_on_commit=False)
    processed = 0
    try:
        async with sf() as session, session.begin():
            rows = (
                (
                    await session.execute(
                        select(AnalyzerJob)
                        .where(AnalyzerJob.status == "queued")
                        .order_by(AnalyzerJob.created_at)
                        .limit(BATCH_SIZE)
                    )
                )
                .scalars()
                .all()
            )
            for job in rows:
                job.status = "running"
                job.started_at = datetime.now(tz=UTC)
            await session.commit()
        for job_id in [r.id for r in rows]:
            async with sf() as session, session.begin():
                job = (
                    await session.execute(select(AnalyzerJob).where(AnalyzerJob.id == job_id))
                ).scalar_one()
                obs = (
                    await session.execute(
                        select(Observable).where(Observable.id == job.observable_id)
                    )
                ).scalar_one()
                analyzer = get_registry().get(job.analyzer_name)
                if analyzer is None:
                    job.status = "failure"
                    job.error_message = f"analyzer_not_found:{job.analyzer_name}"
                    job.finished_at = datetime.now(tz=UTC)
                else:
                    try:
                        result = await analyzer.run(obs.data_type, obs.data)
                        job.status = "success"
                        job.report = {"summary": result.summary, "full": result.full}
                    except Exception as e:
                        job.status = "failure"
                        job.error_message = str(e)
                    job.finished_at = datetime.now(tz=UTC)
                processed += 1
    finally:
        await engine.dispose()
    return processed


async def run_analyzer_runner(settings: Settings) -> None:
    register_builtins()
    while True:
        try:
            count = await _run_pending(settings)
            if count > 0:
                _log.debug("analyzer.runner processed=%d", count)
        except asyncio.CancelledError:
            raise
        except Exception:
            _log.exception("analyzer runner iteration failed")
        await asyncio.sleep(POLL_INTERVAL_SECONDS)
