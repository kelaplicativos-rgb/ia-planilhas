from __future__ import annotations

import time

import pandas as pd
import streamlit as st

from bling_app_zero.core.site_progress_model import SiteProgressMetrics, SiteProgressState, safe_int, safe_text

PROGRESS_LOG_KEY = 'site_progress_log'
PROGRESS_LAST_KEY = 'site_progress_last'
NEUTRAL_PROGRESS_STATE_KEY = 'neutral_site_progress_state_v1'


def _progress_state_from_streamlit() -> SiteProgressState:
    stored = st.session_state.get(NEUTRAL_PROGRESS_STATE_KEY)
    if isinstance(stored, dict) and isinstance(stored.get('events'), list):
        return SiteProgressState.from_log(stored.get('events'))
    return SiteProgressState.from_log(st.session_state.get(PROGRESS_LOG_KEY) or [])


def _sync_progress_state(state: SiteProgressState) -> None:
    data = state.to_dict()
    st.session_state[NEUTRAL_PROGRESS_STATE_KEY] = data
    st.session_state[PROGRESS_LOG_KEY] = data.get('events', [])
    st.session_state[PROGRESS_LAST_KEY] = data.get('last', {})


def reset_site_progress() -> None:
    _sync_progress_state(SiteProgressState())


def append_site_progress(payload: dict) -> None:
    state = _progress_state_from_streamlit().append(payload or {})
    _sync_progress_state(state)


def _elapsed_seconds() -> int:
    try:
        started_at = float(st.session_state.get('site_capture_started_at') or 0.0)
    except Exception:
        started_at = 0.0
    if started_at <= 0:
        return 0
    return max(0, int(time.time() - started_at))


def _safe_progress_dataframe(rows: list[dict]) -> pd.DataFrame:
    df = pd.DataFrame(rows)
    if df.empty:
        return df
    for column in df.columns:
        df[column] = df[column].map(safe_text).astype(str)
    return df


def progress_rows(log: list[dict]) -> list[dict]:
    return SiteProgressState.from_log(log).rows()


def _render_progress_metrics(payload: dict) -> None:
    metrics = SiteProgressMetrics.from_event(SiteProgressState.from_log([payload] if payload else []).last, elapsed_seconds=_elapsed_seconds())
    st.caption(metrics.stage)
    col_a, col_b = st.columns(2)
    col_a.metric('Links/produtos localizados', safe_int(metrics.urls_found))
    col_b.metric('Páginas visitadas', safe_int(metrics.visited_pages))
    col_c, col_d = st.columns(2)
    col_c.metric('Itens processados', safe_int(metrics.processed))
    col_d.metric('Tempo decorrido', f'{metrics.elapsed_seconds}s')


def _render_progress_table(log: list[dict], height: int) -> None:
    rows = progress_rows(log)
    if not rows:
        return
    st.dataframe(_safe_progress_dataframe(rows), use_container_width=True, height=height)


def _render_execution_plan() -> None:
    st.markdown('#### O que o sistema está fazendo agora')
    st.caption('1. Lendo o link inicial/categoria informado.')
    st.caption('2. Procurando links reais de produtos dentro do site.')
    st.caption('3. Abrindo os produtos encontrados em lote seguro.')
    st.caption('4. Extraindo código/SKU/GTIN/ID e saldo disponível.')
    st.caption('5. Validando depósito, preparando tabela e salvando para envio ao Bling.')


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
        progress = max(0.0, min(1.0, float((payload or {}).get('progress') or 0.0)))
        stage = str((payload or {}).get('stage') or 'Buscando')
        message = str((payload or {}).get('message') or '')
        progress_bar.progress(progress, text=f'{stage} · {int(progress * 100)}%')
        status_box.info(message or stage)
        render_sidebar_progress_details(payload)

    return callback


def render_site_progress_history() -> None:
    state = _progress_state_from_streamlit()
    data = state.to_dict()
    log = data.get('events', []) or []
    last = data.get('last', {}) or {}

    st.markdown('### Detalhes da busca')
    elapsed = _elapsed_seconds()
    if isinstance(last, dict) and last:
        metrics = SiteProgressMetrics.from_event(state.last, elapsed_seconds=elapsed)
        message = metrics.message or 'Busca em andamento.'
        st.info(f'Última atividade registrada: {message}')
        _render_progress_metrics(last)
    else:
        st.info(f'A captura foi iniciada há {elapsed}s. O sistema está trabalhando em modo seguro; algumas etapas só aparecem quando um lote termina.')
        col_a, col_b = st.columns(2)
        col_a.metric('Tempo decorrido', f'{elapsed}s')
        col_b.metric('Modo', 'Seguro')

    _render_execution_plan()

    if log:
        with st.expander('Últimos eventos da busca', expanded=True):
            _render_progress_table(log, height=320)
    else:
        st.warning('Ainda não houve evento detalhado gravado nesta execução. Se ficar mais de 2 minutos sem mudança, use “Limpar busca travada e tentar novamente”.')

    with st.sidebar:
        st.markdown('##### Histórico da busca')
        if log:
            _render_progress_table(log, height=280)
        else:
            st.caption(f'Busca iniciada há {elapsed}s. Aguardando primeiro evento detalhado.')
