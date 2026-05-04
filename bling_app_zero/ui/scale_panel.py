from __future__ import annotations

import streamlit as st

from bling_app_zero.scale.job_queue import enqueue_job, stats, list_jobs
from bling_app_zero.scale.worker import run_once


def render_scale_panel():
    st.sidebar.markdown("---")
    st.sidebar.subheader("⚙️ Scale")

    if st.sidebar.button("Adicionar job teste"):
        enqueue_job("demo", {"msg": "hello"})
        st.sidebar.success("Job adicionado")

    if st.sidebar.button("Processar fila"):
        processed = run_once({"demo": lambda p: None})
        st.sidebar.info(f"Processados: {processed}")

    s = stats()
    st.sidebar.write(s)

    with st.sidebar.expander("Jobs"):
        st.write(list_jobs()[:10])
