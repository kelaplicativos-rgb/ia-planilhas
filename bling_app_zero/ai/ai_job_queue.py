from __future__ import annotations

import time
import uuid
from typing import Any

import streamlit as st

from bling_app_zero.ai.ai_schema import AIJob, AIResult

AI_JOBS_KEY = 'mapeia_ai_jobs'
AI_JOB_HISTORY_KEY = 'mapeia_ai_job_history'


def _jobs() -> dict[str, AIJob]:
    jobs = st.session_state.get(AI_JOBS_KEY)
    if not isinstance(jobs, dict):
        jobs = {}
        st.session_state[AI_JOBS_KEY] = jobs
    return jobs


def _history() -> list[dict[str, Any]]:
    history = st.session_state.get(AI_JOB_HISTORY_KEY)
    if not isinstance(history, list):
        history = []
        st.session_state[AI_JOB_HISTORY_KEY] = history
    return history


def enqueue_ai_job(task: str, payload: dict[str, Any]) -> AIJob:
    job_id = f'ai_{int(time.time())}_{uuid.uuid4().hex[:8]}'
    job = AIJob(job_id=job_id, task=task, payload=payload, status='pendente')
    _jobs()[job_id] = job
    _history().append({'job_id': job_id, 'task': task, 'status': 'pendente', 'created_at': time.time()})
    return job


def update_ai_job(job_id: str, *, status: str, result: AIResult | None = None) -> None:
    jobs = _jobs()
    job = jobs.get(job_id)
    if job is None:
        return
    jobs[job_id] = AIJob(job_id=job.job_id, task=job.task, payload=job.payload, status=status, result=result)
    _history().append({'job_id': job_id, 'task': job.task, 'status': status, 'updated_at': time.time()})


def get_ai_jobs() -> list[AIJob]:
    return list(_jobs().values())


def clear_ai_jobs() -> None:
    st.session_state[AI_JOBS_KEY] = {}
    st.session_state[AI_JOB_HISTORY_KEY] = []


__all__ = ['AI_JOBS_KEY', 'AI_JOB_HISTORY_KEY', 'clear_ai_jobs', 'enqueue_ai_job', 'get_ai_jobs', 'update_ai_job']
