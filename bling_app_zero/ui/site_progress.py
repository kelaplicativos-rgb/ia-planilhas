from __future__ import annotations

import time

import pandas as pd
import streamlit as st

PROGRESS_LOG_KEY = 'site_progress_log'
PROGRESS_LAST_KEY = 'site_progress_last'
PROGRESS_HEARTBEAT_KEY = 'site_capture_heartbeat_at'


def reset_site_progress() -> None:
    st.session_state[PROGRESS_LOG_KEY] = []
    st.session_state[PROGRESS_LAST_KEY] = {}
    st.session_state[PROGRESS_HEARTBEAT_KEY] = time.time()


def append_site_progress(payload: dict) -> None:
    log = list(st.session_state.get(PROGRESS_LOG_KEY, []))
    item = dict(payload or {})
    item['time'] = time.strftime('%H:%M:%S')
    log.append(item)
    st.session_state[PROGRESS_LOG_KEY] = log[-80:]
    st.session_state[PROGRESS_LAST_KEY] = item
    st.session_state[PROGRESS_HEARTBEAT_KEY] = time.time()


def _safe_cell(value: object) -> str:
    if value is None:
        return ''
    try:
        if pd.isna(value):
            return ''
    except Exception:
        pass
    return str(value)


def _safe_progress_value(payload: dict | None) -> float:
    if not isinstance(payload, dict):
        return 0.05
    try:
        value = float(payload.get('progress') or 0.0)
    except Exception:
        value = 0.0
    if value > 1:
        value = value / 100.0
    return max(0.05, min(0.95, value))


def _safe_progress_dataframe(rows: list[dict]) -> pd.DataFrame:
    df = pd.DataFrame(rows)
    if df.empty:
        return df
    for column in df.columns:
        df[column] = df[column].map(_safe_cell).astype(str)
    return df


def progress_rows(log: list[dict]) -> list[dict]:
    return [
        {
            'Hora': _safe_cell(item.get('time', '')),
            'Etapa': _safe_cell(item.get('stage', '')),
            'Mensagem': _safe_cell(item.get('message', '')),
            'Links': _safe_cell(item.get('urls_found', item.get('total', ''))),
            'Processados': _safe_cell(item.get('processed', '')),
            'Produtos': _safe_cell(item.get('found', '')),
            'Falhas': _safe_cell(item.get('errors', '')),
            'Tempo': _safe_cell(item.get('total_seconds', item.get('discovery_seconds', ''))),
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


def _render_progress_table(log: list[dict], height: int) -> None:
    rows = progress_rows(log)
    if not rows:
        return
    st.dataframe(_safe_progress_dataframe(rows), use_container_width=True, height=height)


def render_sidebar_progress_details(payload: dict) -> None:
    """Mostra o andamento da busca por site na barra lateral."""
    log = st.session_state.get(PROGRESS_LOG_KEY) or []
    with st.sidebar:
        st.markdown('##### Busca em andamento')
        _render_progress_metrics(payload)
        if log:
            st.markdown('##### Histórico da busca')
            _render_progress_table(log, height=260)


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
    """Recria o feedback visual quando o Streamlit reroda durante uma captura.

    No celular, a barra original pode sumir após rerun/WebSocket. O histórico salvo em
    session_state permite reconstruir uma barra leve em vez de deixar a tela parecendo travada.
    """
    log = st.session_state.get(PROGRESS_LOG_KEY) or []
    last = st.session_state.get(PROGRESS_LAST_KEY) or {}
    running = bool(st.session_state.get('site_capture_running', False))

    if isinstance(last, dict) and last:
        progress = _safe_progress_value(last)
        stage = str(last.get('stage') or 'Busca em andamento')
        message = str(last.get('message') or stage)
        st.progress(progress, text=f'{stage} · {int(progress * 100)}%')
        st.caption(message)
    elif running:
        try:
            started_at = float(st.session_state.get('site_capture_started_at') or 0.0)
        except Exception:
            started_at = 0.0
        age = max(0.0, time.time() - started_at) if started_at > 0 else 0.0
        progress = max(0.05, min(0.75, age / 90.0))
        st.progress(progress, text=f'Busca em andamento · {int(progress * 100)}%')
        st.caption('A captura está rodando em modo seguro. Se ficar parada por muito tempo, use “Limpar busca travada”.')

    if not log:
        return
    with st.sidebar:
        st.markdown('##### Histórico da busca')
        _render_progress_table(log, height=280)
