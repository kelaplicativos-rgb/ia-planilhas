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
    st.session_state[PROGRESS_LOG_KEY] = log[-120:]
    st.session_state[PROGRESS_LAST_KEY] = item


def _safe_cell(value: object) -> str:
    if value is None:
        return ''
    try:
        if pd.isna(value):
            return ''
    except Exception:
        pass
    return str(value)


def _safe_int(value: object) -> int:
    try:
        if value is None or value == '':
            return 0
        return int(float(value))
    except Exception:
        return 0


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
        df[column] = df[column].map(_safe_cell).astype(str)
    return df


def progress_rows(log: list[dict]) -> list[dict]:
    return [
        {
            'Hora': _safe_cell(item.get('time', '')),
            'Etapa': _safe_cell(item.get('stage', '')),
            'Mensagem': _safe_cell(item.get('message', '')),
            'Links': _safe_cell(item.get('urls_found', item.get('total', item.get('deep_capture_found_products', '')))),
            'Visitadas': _safe_cell(item.get('visited_pages', item.get('deep_capture_visited_pages', ''))),
            'Lidas': _safe_cell(item.get('processed', item.get('scanned_pages', item.get('deep_capture_scanned_pages', '')))),
            'Produtos': _safe_cell(item.get('found', item.get('rows', ''))),
            'Falhas': _safe_cell(item.get('errors', '')),
            'Tempo': _safe_cell(item.get('total_seconds', item.get('discovery_seconds', item.get('elapsed_seconds', '')))),
        }
        for item in log
    ]


def _render_progress_metrics(payload: dict) -> None:
    st.caption(str(payload.get('stage') or 'Buscando'))
    col_a, col_b = st.columns(2)
    col_a.metric('Links/produtos localizados', _safe_int(payload.get('urls_found') or payload.get('total') or payload.get('deep_capture_found_products') or 0))
    col_b.metric('Páginas visitadas', _safe_int(payload.get('visited_pages') or payload.get('deep_capture_visited_pages') or 0))
    col_c, col_d = st.columns(2)
    col_c.metric('Itens processados', _safe_int(payload.get('processed') or payload.get('scanned_pages') or payload.get('deep_capture_scanned_pages') or 0))
    col_d.metric('Tempo decorrido', f'{_elapsed_seconds()}s')


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
        progress = max(0.0, min(1.0, float(payload.get('progress') or 0.0)))
        stage = str(payload.get('stage') or 'Buscando')
        message = str(payload.get('message') or '')
        progress_bar.progress(progress, text=f'{stage} · {int(progress * 100)}%')
        status_box.info(message or stage)
        render_sidebar_progress_details(payload)

    return callback


def render_site_progress_history() -> None:
    log = st.session_state.get(PROGRESS_LOG_KEY) or []
    last = st.session_state.get(PROGRESS_LAST_KEY) or {}

    st.markdown('### Detalhes da busca')
    elapsed = _elapsed_seconds()
    if isinstance(last, dict) and last:
        message = str(last.get('message') or last.get('stage') or 'Busca em andamento.')
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
