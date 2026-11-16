"""Worker core: Arq wrapper, structlog, and DB job logging. Mirrors packages/worker-core/src/index.ts."""

from __future__ import annotations

import time
from collections.abc import Callable, Coroutine
from datetime import UTC, datetime, timedelta
from typing import Any, TypeVar
from uuid import UUID

import structlog
from arq.connections import ArqRedis, RedisSettings, create_pool
from leadforge_config import get_settings
from leadforge_database.models import EnrichmentRun, EnrichmentStatus, JobQueueLog
from sqlalchemy import insert, update

T = TypeVar("T")
Processor = Callable[[T, structlog.BoundLogger], Coroutine[Any, Any, None]]


class WorkerWrapper[T]:
    def __init__(self, name: str, processor: Processor):
        self.name = name
        self.processor = processor
        self.logger = structlog.get_logger(name).bind(service=name)

    async def __call__(self, ctx: dict[str, Any], data: T) -> None:
        start = time.time()
        job_id = ctx.get("job_id", "unknown")
        business_id = getattr(data, "business_id", None)
        if not isinstance(business_id, UUID):
            business_id = None

        self.logger.info("job_started", jobId=job_id, businessId=business_id)
        job_log_id, run_id = await self._start_tracking(job_id, business_id)

        try:
            await self.processor(data, self.logger)
            duration = int((time.time() - start) * 1000)
            self.logger.info("job_completed", jobId=job_id, duration=duration)
            await self._finish_tracking(
                job_log_id, run_id, job_id, "COMPLETED", duration, None, business_id
            )
        except Exception as e:
            duration = int((time.time() - start) * 1000)
            self.logger.error("job_failed", jobId=job_id, duration=duration, error=str(e))
            await self._finish_tracking(
                job_log_id, run_id, job_id, "FAILED", duration, str(e), business_id
            )
            raise e

    async def _start_tracking(
        self, job_id: str, business_id: UUID | None
    ) -> tuple[UUID | None, UUID | None]:
        """Create RUNNING rows so the UI can show live pipeline activity."""
        from leadforge_database import get_session_ctx

        try:
            async with get_session_ctx() as session:
                job_log_id = await session.scalar(
                    insert(JobQueueLog)
                    .values(
                        job_id=job_id,
                        queue_name=self.name,
                        worker_name=self.name,
                        status="RUNNING",
                        duration_ms=None,
                    )
                    .returning(JobQueueLog.id)
                )
                run_id = None
                if business_id is not None:
                    run_id = await session.scalar(
                        insert(EnrichmentRun)
                        .values(
                            business_id=business_id,
                            worker_name=self.name,
                            status=EnrichmentStatus.RUNNING,
                            started_at=datetime.now(UTC),
                            metadata_={"job_id": job_id},
                        )
                        .returning(EnrichmentRun.id)
                    )
                await session.commit()
                return job_log_id, run_id
        except Exception:
            self.logger.warning("failed_to_start_job_tracking", jobId=job_id)
            return None, None

    async def _finish_tracking(
        self,
        job_log_id: UUID | None,
        run_id: UUID | None,
        job_id: str,
        status: str,
        duration: int,
        error: str | None,
        business_id: UUID | None,
    ) -> None:
        from leadforge_database import get_session_ctx

        run_status = (
            EnrichmentStatus.COMPLETED if status == "COMPLETED" else EnrichmentStatus.FAILED
        )
        now = datetime.now(UTC)
        try:
            async with get_session_ctx() as session:
                if job_log_id is not None:
                    await session.execute(
                        update(JobQueueLog)
                        .where(JobQueueLog.id == job_log_id)
                        .values(status=status, duration_ms=duration, error_message=error)
                    )
                else:
                    await session.execute(
                        insert(JobQueueLog).values(
                            job_id=job_id,
                            queue_name=self.name,
                            worker_name=self.name,
                            status=status,
                            duration_ms=duration,
                            error_message=error,
                        )
                    )
                if run_id is not None:
                    await session.execute(
                        update(EnrichmentRun)
                        .where(EnrichmentRun.id == run_id)
                        .values(
                            status=run_status,
                            completed_at=now,
                            error_message=error,
                            metadata_={"job_id": job_id, "duration_ms": duration},
                        )
                    )
                elif business_id is not None:
                    await session.execute(
                        insert(EnrichmentRun).values(
                            business_id=business_id,
                            worker_name=self.name,
                            status=run_status,
                            started_at=now - timedelta(milliseconds=duration),
                            completed_at=now,
                            error_message=error,
                            metadata_={"job_id": job_id, "duration_ms": duration},
                        )
                    )
                await session.commit()
        except Exception:
            self.logger.warning("failed_to_finish_job_tracking", jobId=job_id)

    def get_function(self) -> Callable[..., Coroutine[Any, Any, None]]:
        """Return a coroutine function compatible with arq."""

        async def _wrapper(ctx: dict[str, Any], data: T) -> None:
            return await self.__call__(ctx, data)

        _wrapper.__name__ = self.name
        _wrapper.__qualname__ = self.name
        return _wrapper


def arq_redis_settings() -> RedisSettings:
    settings = get_settings()
    return RedisSettings(
        host=settings.redis_host,
        port=settings.redis_port,
        password=settings.redis_password or None,
    )


def run_worker(queue_name: str, function: Callable[..., Coroutine[Any, Any, None]]) -> None:
    """Run one arq worker for ``queue_name`` with restart-on-crash semantics.

    Single implementation so all six workers cannot drift on logging,
    redis auth, or concurrency settings.
    """
    import time

    from arq import Worker

    logger = structlog.get_logger(f"worker.{queue_name}")
    settings = get_settings()
    redis_settings = arq_redis_settings()

    while True:
        try:
            worker_instance = Worker(
                functions=[function],
                queue_name=queue_name,
                redis_settings=redis_settings,
                max_jobs=settings.worker_concurrency,
            )
            worker_instance.run()
            return
        except KeyboardInterrupt:
            logger.info("worker.stopped", queue=queue_name)
            return
        except Exception as exc:
            logger.error("worker.crashed", queue=queue_name, error=str(exc))
            time.sleep(3)


_arq_pool: ArqRedis | None = None


async def get_arq_pool() -> ArqRedis:
    global _arq_pool
    if _arq_pool is None:
        _arq_pool = await create_pool(arq_redis_settings())
    return _arq_pool


async def close_arq_pool() -> None:
    global _arq_pool
    if _arq_pool is not None:
        await _arq_pool.aclose()
        _arq_pool = None


def verification_job_id(business_id: str | UUID) -> str:
    """Collapse duplicate verification enqueues within the same minute."""
    minute = int(time.time() // 60)
    return f"verify:{business_id}:{minute}"


async def enqueue_job(
    queue_name: str,
    job_name: str,
    payload: dict[str, Any],
    *,
    job_id: str | None = None,
) -> None:
    pool = await get_arq_pool()
    extra: dict[str, Any] = {"_queue_name": queue_name}
    if job_id:
        extra["_job_id"] = job_id
    await pool.enqueue_job(job_name, **extra, **payload)
