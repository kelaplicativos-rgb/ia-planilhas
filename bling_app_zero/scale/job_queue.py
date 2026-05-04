from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from bling_app_zero.core.saas_store import read_json, write_json

QUEUE_FILE = "job_queue.json"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def list_jobs() -> list[dict[str, Any]]:
    jobs = read_json(QUEUE_FILE, [], None)
    return jobs if isinstance(jobs, list) else []


def save_jobs(jobs: list[dict[str, Any]]) -> bool:
    return write_json(QUEUE_FILE, jobs[-1000:], None)


def enqueue_job(kind: str, payload: dict[str, Any] | None = None) -> str:
    jobs = list_jobs()
    job_id = str(uuid.uuid4())
    jobs.append({
        "id": job_id,
        "kind": kind,
        "payload": payload or {},
        "status": "pending",
        "created_at": _now(),
        "updated_at": _now(),
        "error": "",
    })
    save_jobs(jobs)
    return job_id


def update_job(job_id: str, status: str, error: str = "") -> None:
    jobs = list_jobs()
    for job in jobs:
        if job.get("id") == job_id:
            job["status"] = status
            job["updated_at"] = _now()
            job["error"] = error
            break
    save_jobs(jobs)


def stats() -> dict[str, int]:
    out = {"pending": 0, "running": 0, "done": 0, "failed": 0}
    for job in list_jobs():
        status = str(job.get("status", "pending"))
        out[status] = out.get(status, 0) + 1
    return out
