"""Admin / queue stats service.

arq 0.28 storage layout (verified against the installed version):
  - queue backlog: ZSET keyed by the queue name itself (``scoring``)
  - running jobs:  ``arq:in-progress:{job_id}`` (no queue association)
  - finished jobs: ``arq:result:{job_id}`` with a TTL (``keep_result``)

There is no ``arq:failed:*`` key and no per-queue result zset. The previous
implementation read those keys, so retry always reported 0.
"""

from __future__ import annotations

from typing import Any

from arq.jobs import JobResult, deserialize_job, deserialize_result
from leadforge_config import get_redis_client

from leadforge_api.core.queue import get_pool

_QUEUE_NAMES = ("discovery", "website", "contact", "social", "scoring", "export")

_RESULT_PREFIX = "arq:result:"
_JOB_PREFIX = "arq:job:"
_IN_PROGRESS_PREFIX = "arq:in-progress:"
_SCAN_LIMIT = 5000


def _key_suffix(key: bytes, prefix: str) -> str:
    text = key.decode() if isinstance(key, bytes) else str(key)
    return text[len(prefix) :] if text.startswith(prefix) else text


async def _all_results() -> list[JobResult]:
    """Deserialize every retained job result (bounded by ``_SCAN_LIMIT``)."""
    client: Any = get_redis_client()
    try:
        keys: list[bytes] = []
        async for key in client.scan_iter(match=f"{_RESULT_PREFIX}*", count=500):
            keys.append(key)
            if len(keys) >= _SCAN_LIMIT:
                break
        if not keys:
            return []
        payloads = await client.mget(keys)
    finally:
        await client.aclose()

    results: list[JobResult] = []
    for raw in payloads:
        if not raw:
            continue
        try:
            results.append(deserialize_result(raw))
        except Exception:
            continue
    return results


async def _in_progress_by_queue() -> dict[str, int]:
    """Map running jobs to queues via the job payload's function name.

    Function names match queue names in this codebase; unknown jobs are
    ignored.
    """
    counts = dict.fromkeys(_QUEUE_NAMES, 0)
    client: Any = get_redis_client()
    try:
        scanned = 0
        async for key in client.scan_iter(match=f"{_IN_PROGRESS_PREFIX}*", count=500):
            scanned += 1
            if scanned > _SCAN_LIMIT:
                break
            job_id = _key_suffix(key, _IN_PROGRESS_PREFIX)
            raw = await client.get(f"{_JOB_PREFIX}{job_id}")
            if not raw:
                continue
            try:
                function = deserialize_job(raw).function
            except Exception:
                continue
            if function in counts:
                counts[function] += 1
    finally:
        await client.aclose()
    return counts


async def get_queue_stats() -> dict[str, dict[str, int]]:
    results = await _all_results()
    in_progress = await _in_progress_by_queue()

    complete = dict.fromkeys(_QUEUE_NAMES, 0)
    failed = dict.fromkeys(_QUEUE_NAMES, 0)
    for result in results:
        queue = result.queue_name
        if queue not in complete:
            continue
        if result.success:
            complete[queue] += 1
        else:
            failed[queue] += 1

    client: Any = get_redis_client()
    try:
        waiting = {name: int(await client.zcard(name) or 0) for name in _QUEUE_NAMES}
    finally:
        await client.aclose()

    return {
        name: {
            "waiting": waiting[name],
            "in_progress": in_progress[name],
            "complete": complete[name],
            "failed": failed[name],
        }
        for name in _QUEUE_NAMES
    }


async def retry_failed() -> int:
    """Re-enqueue failed jobs that still have a retained result."""
    pool = await get_pool()
    client: Any = get_redis_client()
    total = 0
    try:
        for result in await _all_results():
            if result.success or not result.job_id:
                continue
            await pool.enqueue_job(
                result.function,
                *result.args,
                _queue_name=result.queue_name,
                **result.kwargs,
            )
            await client.delete(f"{_RESULT_PREFIX}{result.job_id}")
            total += 1
    finally:
        await client.aclose()
    return total
