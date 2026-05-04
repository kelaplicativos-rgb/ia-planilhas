from __future__ import annotations

import streamlit as st

from bling_app_zero.scale.job_queue import enqueue_job, list_jobs, retry_failed, stats
from bling_app_zero.scale.worker import run_parallel


def render_scale_panel():
    st.sidebar.markdown("---")
    st.sidebar.subheader("⚙️ Scale")

    col1, col2 = st.sidebar.columns(2)

    with col1:
        if st.button("Job teste"):
            enqueue_job("demo", {"msg": "hello"}, priority=5)
            st.success("Job adicionado")

    with col2:
        if st.button("Retry"):
            count = retry_failed()
            st.info(f"Reenfileirados: {count}")

    if st.sidebar.button("Processar fila"):
        processed = run_parallel({"demo": lambda p: None}, max_workers=3, batch_size=10)
        st.sidebar.info(f"Processados: {processed}")

    st.sidebar.write(stats())

    with st.sidebar.expander("Jobs"):
        st.write(list_jobs()[:10])
