from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Callable

from bling_app_zero.scale.job_queue import get_pending_jobs, update_job


def _run_job(job: dict, handler_map: dict[str, Callable[[dict], None]]):
    job_id = job.get("id")
    kind = job.get("kind")
    payload = job.get("payload") or {}

    update_job(job_id, "running")
    try:
        handler = handler_map.get(kind)
        if handler:
            handler(payload)
            update_job(job_id, "done")
        else:
            update_job(job_id, "failed", "no handler")
    except Exception as exc:
        update_job(job_id, "failed", str(exc))


def run_parallel(handler_map: dict[str, Callable[[dict], None]], max_workers: int = 5, batch_size: int = 10) -> int:
    jobs = get_pending_jobs(batch_size)
    if not jobs:
        return 0

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [executor.submit(_run_job, job, handler_map) for job in jobs]

        for _ in as_completed(futures):
            pass

    time.sleep(0.1)
    return len(jobs)
