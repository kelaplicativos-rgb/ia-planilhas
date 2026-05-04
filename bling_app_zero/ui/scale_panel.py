from __future__ import annotations

import os

import streamlit as st

from bling_app_zero.scale.job_queue import enqueue_job, list_jobs, retry_failed, stats
from bling_app_zero.scale.worker import run_parallel


def _scale_enabled() -> bool:
    try:
        raw = st.secrets.get("scale", {}).get("enabled", False)
    except Exception:
        raw = os.getenv("SCALE_PANEL_ENABLED", "false")
    return str(raw).lower() in {"1", "true", "yes", "sim"}


def render_scale_panel():
    if not _scale_enabled():
        return

    with st.sidebar.expander("⚙️ Scale técnico", expanded=False):
        col1, col2 = st.columns(2)

        with col1:
            if st.button("Job teste", key="scale_job_teste"):
                enqueue_job("demo", {"msg": "hello"}, priority=5)
                st.success("Job adicionado")

        with col2:
            if st.button("Retry", key="scale_retry"):
                count = retry_failed()
                st.info(f"Reenfileirados: {count}")

        if st.button("Processar fila", key="scale_processar"):
            processed = run_parallel({"demo": lambda p: None}, max_workers=3, batch_size=10)
            st.info(f"Processados: {processed}")

        st.json(stats())

        with st.expander("Jobs", expanded=False):
            st.write(list_jobs()[:10])
