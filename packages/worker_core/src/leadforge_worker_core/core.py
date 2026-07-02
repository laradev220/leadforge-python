"""Worker core: Arq wrapper, structlog, and DB job logging. Mirrors packages/worker-core/src/index.ts."""

from __future__ import annotations

import time
from collections.abc import Callable, Coroutine
from typing import Any, TypeVar

import structlog
from arq.connections import ArqRedis, RedisSettings, create_pool
from leadforge_config import get_settings
from leadforge_database.models import JobQueueLog
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
        business_id = data.get("business_id") if isinstance(data, dict) else None

        self.logger.info("job_started", jobId=job_id, businessId=business_id)

        try:
            await self.processor(data, self.logger)
            duration = int((time.time() - start) * 1000)
            self.logger.info("job_completed", jobId=job_id, duration=duration)
            await self._log_to_db(job_id, "COMPLETED", duration)
        except Exception as e:
            duration = int((time.time() - start) * 1000)
            self.logger.error("job_failed", jobId=job_id, duration=duration, error=str(e))
            await self._log_to_db(job_id, "FAILED", duration, error=str(e))
            raise e

    def get_function(self) -> Callable[..., Coroutine[Any, Any, None]]:
        """Return a coroutine function compatible with arq."""

        async def _wrapper(ctx: dict[str, Any], data: T) -> None:
            return await self.__call__(ctx, data)

        _wrapper.__name__ = self.name
        _wrapper.__qualname__ = self.name
        return _wrapper

    async def _log_to_db(
        self, job_id: str, status: str, duration: int, error: str | None = None
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
                await session.commit()
            except Exception:
                self.logger.warning("failed_to_log_job_to_db", jobId=job_id)


_arq_pool: ArqRedis | None = None


async def get_arq_pool() -> ArqRedis:
    global _arq_pool
    if _arq_pool is None:
        settings = get_settings()
        _arq_pool = await create_pool(
            RedisSettings(host=settings.redis_host, port=settings.redis_port)
        )
    return _arq_pool


async def close_arq_pool() -> None:
    global _arq_pool
    if _arq_pool is not None:
        await _arq_pool.aclose()
        _arq_pool = None


async def enqueue_job(queue_name: str, job_name: str, payload: dict[str, Any]) -> None:
    pool = await get_arq_pool()
    await pool.enqueue_job(job_name, _queue_name=queue_name, **payload)
