from __future__ import annotations

import time

import pandas as pd
import streamlit as st

PROGRESS_LOG_KEY = 'site_progress_log'
PROGRESS_LAST_KEY = 'site_progress_last'


def reset_site_progress() -> None:
    st.session_state[PROGRESS_LOG_KEY] = []
    st.session_state[PROGRESS_LAST_KEY] = {}


def append_site_progress(payload: dict) -> None:
    log = list(st.session_state.get(PROGRESS_LOG_KEY, []))
    item = dict(payload or {})
    item['time'] = time.strftime('%H:%M:%S')
    log.append(item)
    st.session_state[PROGRESS_LOG_KEY] = log[-80:]
    st.session_state[PROGRESS_LAST_KEY] = item


def progress_rows(log: list[dict]) -> list[dict]:
    return [
        {
            'Hora': item.get('time', ''),
            'Etapa': item.get('stage', ''),
            'Mensagem': item.get('message', ''),
            'Links': item.get('urls_found', item.get('total', '')),
            'Processados': item.get('processed', ''),
            'Produtos': item.get('found', ''),
            'Falhas': item.get('errors', ''),
            'Tempo': item.get('total_seconds', item.get('discovery_seconds', '')),
        }
        for item in log
    ]


def _render_progress_metrics(payload: dict) -> None:
    st.caption(str(payload.get('stage') or 'Buscando'))
    col_a, col_b = st.columns(2)
    col_a.metric('Links encontrados', int(payload.get('urls_found') or payload.get('total') or 0))
    col_b.metric('Links lidos', int(payload.get('processed') or 0))
    col_c, col_d = st.columns(2)
    col_c.metric('Produtos encontrados', int(payload.get('found') or 0))
    col_d.metric('Falhas', int(payload.get('errors') or 0))


def render_sidebar_progress_details(payload: dict) -> None:
    """Mostra o andamento da busca por site na barra lateral."""
    log = st.session_state.get(PROGRESS_LOG_KEY) or []
    with st.sidebar:
        st.markdown('##### Busca em andamento')
        _render_progress_metrics(payload)
        if log:
            st.markdown('##### Histórico da busca')
            st.dataframe(pd.DataFrame(progress_rows(log)), use_container_width=True, height=260)


def make_site_progress_callback(progress_bar, status_box):
    def callback(payload: dict) -> None:
        append_site_progress(payload)
        progress = max(0.0, min(1.0, float(payload.get('progress') or 0.0)))
        stage = str(payload.get('stage') or 'Buscando')
        message = str(payload.get('message') or '')
        progress_bar.progress(progress, text=f'{stage} · {int(progress * 100)}%')
        status_box.info(message or stage)
        render_sidebar_progress_details(payload)

    return callback


def render_site_progress_history() -> None:
    log = st.session_state.get(PROGRESS_LOG_KEY) or []
    if not log:
        return
    with st.sidebar:
        st.markdown('##### Histórico da busca')
        st.dataframe(pd.DataFrame(progress_rows(log)), use_container_width=True, height=280)
