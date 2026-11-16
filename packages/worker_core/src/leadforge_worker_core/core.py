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
from sqlalchemy import insert

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

        try:
            await self.processor(data, self.logger)
            duration = int((time.time() - start) * 1000)
            self.logger.info("job_completed", jobId=job_id, duration=duration)
            await self._log_to_db(job_id, "COMPLETED", duration, business_id=business_id)
        except Exception as e:
            duration = int((time.time() - start) * 1000)
            self.logger.error("job_failed", jobId=job_id, duration=duration, error=str(e))
            await self._log_to_db(job_id, "FAILED", duration, error=str(e), business_id=business_id)
            raise e

    def get_function(self) -> Callable[..., Coroutine[Any, Any, None]]:
        """Return a coroutine function compatible with arq."""

        async def _wrapper(ctx: dict[str, Any], data: T) -> None:
            return await self.__call__(ctx, data)

        _wrapper.__name__ = self.name
        _wrapper.__qualname__ = self.name
        return _wrapper

    async def _log_to_db(
        self,
        job_id: str,
        status: str,
        duration: int,
        error: str | None = None,
        *,
        business_id: UUID | None = None,
    ) -> None:
        from leadforge_database import get_session_ctx

        async with get_session_ctx() as session:
            try:
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
                if business_id is not None:
                    completed_at = datetime.now(UTC)
                    started_at = completed_at - timedelta(milliseconds=duration)
                    await session.execute(
                        insert(EnrichmentRun).values(
                            business_id=business_id,
                            worker_name=self.name,
                            status=(
                                EnrichmentStatus.COMPLETED
                                if status == "COMPLETED"
                                else EnrichmentStatus.FAILED
                            ),
                            started_at=started_at,
                            completed_at=completed_at,
                            error_message=error,
                        )
                    )
                await session.commit()
            except Exception:
                await session.rollback()
                self.logger.warning("failed_to_log_job_to_db", jobId=job_id)


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
