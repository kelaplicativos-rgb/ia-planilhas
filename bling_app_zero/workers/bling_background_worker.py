from __future__ import annotations

import time
from typing import Any

from bling_app_zero.core.audit import add_audit_event
from bling_app_zero.core.background_jobs import (
    JOB_STATUS_DONE,
    JOB_STATUS_ERROR,
    JOB_STATUS_RUNNING,
    decode_dataframe,
    list_queued_jobs,
    update_job_payload,
)
from bling_app_zero.core.bling_intelligent_update_sender import send_dataframe_to_bling_intelligent
from bling_app_zero.core.bling_send_state import batch_size_for_operation
from bling_app_zero.core.operation_contract import normalize_operation

RESPONSIBLE_FILE = 'bling_app_zero/workers/bling_background_worker.py'
DEFAULT_MAX_JOBS = 3
DEFAULT_MAX_BATCHES_PER_JOB = 1000


def _mark_error(job_id: str, error: str, payload: dict[str, Any] | None = None) -> None:
    changes = {
        'status': JOB_STATUS_ERROR,
        'last_error': str(error or '')[:900],
        'finished_at': _now_from_time(),
    }
    if isinstance(payload, dict):
        changes.setdefault('attempted', int(payload.get('attempted') or 0))
    update_job_payload(job_id, changes)
    add_audit_event(
        'background_bling_job_error',
        area='BACKGROUND_JOBS',
        status='ERRO',
        details={'job_id': job_id, 'error': str(error)[:300], 'responsible_file': RESPONSIBLE_FILE},
    )


def _now_from_time() -> str:
    return time.strftime('%Y-%m-%d %H:%M:%S')


def run_one_background_job(job: dict[str, Any], *, max_batches: int = DEFAULT_MAX_BATCHES_PER_JOB) -> dict[str, Any]:
    job_id = str(job.get('job_id') or '').strip()
    if not job_id:
        return {'ok': False, 'error': 'job_id ausente'}

    operation = normalize_operation(job.get('operation'))
    df = decode_dataframe(job.get('dataframe') if isinstance(job.get('dataframe'), dict) else {})
    if df.empty:
        _mark_error(job_id, 'DataFrame da tarefa está vazio ou inválido.', job)
        return {'ok': False, 'job_id': job_id, 'error': 'DataFrame vazio'}

    total = int(job.get('total_rows') or len(df))
    offset = int(job.get('offset') or 0)
    batch_size = int(job.get('batch_size') or 0) or batch_size_for_operation(operation)
    attempted_total = int(job.get('attempted') or 0)
    sent_total = int(job.get('sent') or 0)
    failed_total = int(job.get('failed') or 0)
    skipped_total = int(job.get('skipped') or 0)
    errors = list(job.get('errors') or [])
    not_found_indices = list(job.get('not_found_indices') or [])

    update_job_payload(
        job_id,
        {
            'status': JOB_STATUS_RUNNING,
            'started_at': job.get('started_at') or _now_from_time(),
            'last_error': '',
            'worker_file': RESPONSIBLE_FILE,
        },
    )

    batches = 0
    while offset < total and batches < max_batches:
        batch_end = min(offset + batch_size, total)
        batch_df = df.iloc[offset:batch_end].copy().fillna('')
        started = time.monotonic()
        try:
            result = send_dataframe_to_bling_intelligent(batch_df, operation)
        except Exception as exc:
            _mark_error(job_id, f'Falha no lote {offset + 1}-{batch_end}: {exc}', job)
            return {'ok': False, 'job_id': job_id, 'error': str(exc), 'offset': offset}

        elapsed = max(0.0, time.monotonic() - started)
        attempted_total += int(result.attempted)
        sent_total += int(result.sent)
        failed_total += int(result.failed)
        skipped_total += int(result.skipped)
        errors.extend([str(error) for error in tuple(result.errors or ())])
        not_found_indices.extend([int(index) for index in tuple(result.not_found_indices or ()) if isinstance(index, int)])
        offset = batch_end
        batches += 1

        update_job_payload(
            job_id,
            {
                'status': JOB_STATUS_RUNNING if offset < total else JOB_STATUS_DONE,
                'offset': offset,
                'attempted': attempted_total,
                'sent': sent_total,
                'failed': failed_total,
                'skipped': skipped_total,
                'errors': errors[-50:],
                'not_found_indices': not_found_indices[-200:],
                'last_batch': {
                    'start': int(offset - len(batch_df)),
                    'end': int(batch_end),
                    'elapsed_seconds': round(elapsed, 2),
                    'attempted': int(result.attempted),
                    'sent': int(result.sent),
                    'failed': int(result.failed),
                    'skipped': int(result.skipped),
                },
                'finished_at': _now_from_time() if offset >= total else '',
            },
        )

        add_audit_event(
            'background_bling_job_batch_finished',
            area='BACKGROUND_JOBS',
            status='OK' if int(result.failed) == 0 else 'PARCIAL',
            details={
                'job_id': job_id,
                'operation': operation,
                'offset': offset,
                'total': total,
                'sent': int(result.sent),
                'failed': int(result.failed),
                'skipped': int(result.skipped),
                'elapsed_seconds': round(elapsed, 2),
                'responsible_file': RESPONSIBLE_FILE,
            },
        )

        if int(result.failed) > 0 and sent_total == 0:
            # Evita insistir em centenas de lotes quando a API/permissão falhou logo no início.
            break

    done = offset >= total
    final_status = JOB_STATUS_DONE if done else JOB_STATUS_RUNNING
    update_job_payload(job_id, {'status': final_status, 'finished_at': _now_from_time() if done else ''})
    return {
        'ok': True,
        'job_id': job_id,
        'status': final_status,
        'offset': offset,
        'total': total,
        'sent': sent_total,
        'failed': failed_total,
        'skipped': skipped_total,
        'batches': batches,
    }


def run_queued_background_jobs(*, max_jobs: int = DEFAULT_MAX_JOBS, max_batches_per_job: int = DEFAULT_MAX_BATCHES_PER_JOB) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for job in list_queued_jobs(limit=max_jobs):
        results.append(run_one_background_job(job, max_batches=max_batches_per_job))
    return results


if __name__ == '__main__':
    for item in run_queued_background_jobs():
        print(item)


__all__ = ['run_one_background_job', 'run_queued_background_jobs']
