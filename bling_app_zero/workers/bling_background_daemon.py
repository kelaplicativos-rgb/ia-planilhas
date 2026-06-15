from __future__ import annotations

import os
import time

from bling_app_zero.core.audit import add_audit_event
from bling_app_zero.workers.bling_background_worker import run_queued_background_jobs

RESPONSIBLE_FILE = 'bling_app_zero/workers/bling_background_daemon.py'


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, str(default)) or default)
    except Exception:
        return default


def run_forever() -> None:
    interval = max(5, _env_int('BLING_BACKGROUND_WORKER_INTERVAL_SECONDS', 30))
    max_jobs = max(1, _env_int('BLING_BACKGROUND_WORKER_MAX_JOBS', 3))
    max_batches = max(1, _env_int('BLING_BACKGROUND_WORKER_MAX_BATCHES_PER_JOB', 1000))
    add_audit_event(
        'background_bling_daemon_started',
        area='BACKGROUND_JOBS',
        status='OK',
        details={'interval_seconds': interval, 'max_jobs': max_jobs, 'max_batches_per_job': max_batches, 'responsible_file': RESPONSIBLE_FILE},
    )
    while True:
        try:
            results = run_queued_background_jobs(max_jobs=max_jobs, max_batches_per_job=max_batches)
            if results:
                print({'background_results': results}, flush=True)
        except Exception as exc:
            add_audit_event(
                'background_bling_daemon_cycle_error',
                area='BACKGROUND_JOBS',
                status='ERRO',
                details={'error': str(exc)[:500], 'responsible_file': RESPONSIBLE_FILE},
            )
            print({'background_error': str(exc)[:500]}, flush=True)
        time.sleep(interval)


if __name__ == '__main__':
    run_forever()


__all__ = ['run_forever']
