from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from bling_app_zero.core.saas_store import read_json, write_json

QUEUE_FILE = "job_queue.json"
MAX_RETRIES = 3


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def list_jobs() -> list[dict[str, Any]]:
    jobs = read_json(QUEUE_FILE, [], None)
    return jobs if isinstance(jobs, list) else []


def save_jobs(jobs: list[dict[str, Any]]) -> bool:
    jobs = sorted(jobs, key=lambda j: int(j.get("priority", 5)))
    return write_json(QUEUE_FILE, jobs[-3000:], None)


def enqueue_job(kind: str, payload: dict[str, Any] | None = None, priority: int = 5) -> str:
    jobs = list_jobs()
    job_id = str(uuid.uuid4())
    jobs.append({
        "id": job_id,
        "kind": kind,
        "payload": payload or {},
        "priority": priority,
        "attempts": 0,
        "max_retries": MAX_RETRIES,
        "status": "pending",
        "created_at": _now(),
        "updated_at": _now(),
        "started_at": "",
        "finished_at": "",
        "error": "",
    })
    save_jobs(jobs)
    return job_id


def get_pending_jobs(limit: int = 10) -> list[dict[str, Any]]:
    jobs = [j for j in list_jobs() if j.get("status") == "pending"]
    jobs = sorted(jobs, key=lambda j: (int(j.get("priority", 5)), str(j.get("created_at", ""))))
    return jobs[:limit]


def update_job(job_id: str, status: str, error: str = "") -> None:
    jobs = list_jobs()
    for job in jobs:
        if job.get("id") == job_id:
            job["status"] = status
            job["updated_at"] = _now()
            job["error"] = error
            if status == "running":
                job["started_at"] = _now()
                job["attempts"] = int(job.get("attempts", 0)) + 1
            if status in {"done", "failed"}:
                job["finished_at"] = _now()
            break
    save_jobs(jobs)


def retry_failed() -> int:
    jobs = list_jobs()
    count = 0
    for job in jobs:
        if job.get("status") == "failed" and int(job.get("attempts", 0)) < int(job.get("max_retries", MAX_RETRIES)):
            job["status"] = "pending"
            job["updated_at"] = _now()
            job["error"] = ""
            count += 1
    save_jobs(jobs)
    return count


def stats() -> dict[str, int]:
    out = {"pending": 0, "running": 0, "done": 0, "failed": 0}
    for job in list_jobs():
        status = str(job.get("status", "pending"))
        out[status] = out.get(status, 0) + 1
    return out
