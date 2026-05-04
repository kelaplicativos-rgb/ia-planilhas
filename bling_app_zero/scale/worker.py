from __future__ import annotations

import time
from typing import Callable

from bling_app_zero.scale.job_queue import list_jobs, update_job


def run_once(handler_map: dict[str, Callable[[dict], None]], max_jobs: int = 3) -> int:
    jobs = list_jobs()
    processed = 0

    for job in jobs:
        if processed >= max_jobs:
            break
        if job.get("status") != "pending":
            continue

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

        processed += 1
        time.sleep(0.2)

    return processed
