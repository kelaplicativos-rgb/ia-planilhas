from __future__ import annotations

import time

import pandas as pd
import streamlit as st

from bling_app_zero.core.site_progress_model import SiteProgressMetrics, SiteProgressState, safe_int, safe_text

PROGRESS_LOG_KEY = 'site_progress_log'
PROGRESS_LAST_KEY = 'site_progress_last'
PROGRESS_LAST_SEEN_AT_KEY = 'site_progress_last_seen_at'
NEUTRAL_PROGRESS_STATE_KEY = 'neutral_site_progress_state_v1'
LIVE_WARNING_SECONDS = 60
LIVE_HARD_STALE_SECONDS = 900


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
    st.session_state[PROGRESS_LAST_SEEN_AT_KEY] = time.time()


def append_site_progress(payload: dict) -> None:
    state = _progress_state_from_streamlit().append(payload or {})
    _sync_progress_state(state)
    st.session_state[PROGRESS_LAST_SEEN_AT_KEY] = time.time()


def last_site_progress_seen_at() -> float:
    try:
        return float(st.session_state.get(PROGRESS_LAST_SEEN_AT_KEY) or 0.0)
    except Exception:
        return 0.0


def _elapsed_seconds() -> int:
    try:
        started_at = float(st.session_state.get('site_capture_started_at') or 0.0)
    except Exception:
        started_at = 0.0
    if started_at <= 0:
        return 0
    return max(0, int(time.time() - started_at))


def _last_seen_delta() -> int:
    last_seen_at = last_site_progress_seen_at()
    if last_seen_at <= 0:
        return 0
    return max(0, int(time.time() - last_seen_at))


def _safe_progress_dataframe(rows: list[dict]) -> pd.DataFrame:
    df = pd.DataFrame(rows)
    if df.empty:
        return df
    for column in df.columns:
        df[column] = df[column].map(safe_text).astype(str)
    return df


def progress_rows(log: list[dict]) -> list[dict]:
    return SiteProgressState.from_log(log).rows()


def _payload_progress(payload: dict) -> int:
    try:
        value = float((payload or {}).get('progress') or 0.0)
    except Exception:
        value = 0.0
    if value <= 1:
        value = value * 100
    return max(0, min(100, int(value)))


def _payload_text(payload: dict, fallback: str = 'Busca em andamento.') -> str:
    if not isinstance(payload, dict):
        return fallback
    message = safe_text(payload.get('message') or '')
    stage = safe_text(payload.get('stage') or '')
    if stage and message:
        return f'{stage}: {message}'
    return message or stage or fallback


def _short_url(value: object, *, max_chars: int = 96) -> str:
    text = safe_text(value)
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 3] + '...'


def _render_progress_metrics(payload: dict) -> None:
    metrics = SiteProgressMetrics.from_event(
        SiteProgressState.from_log([payload] if payload else []).last,
        elapsed_seconds=_elapsed_seconds(),
    )
    st.caption(metrics.stage)
    col_a, col_b = st.columns(2)
    col_a.metric('Produtos localizados', safe_int(metrics.urls_found))
    col_b.metric('Páginas visitadas', safe_int(metrics.visited_pages))
    col_c, col_d = st.columns(2)
    col_c.metric('Páginas lidas', safe_int(metrics.processed))
    col_d.metric('Tempo decorrido', f'{metrics.elapsed_seconds}s')
    col_e, col_f = st.columns(2)
    col_e.metric('Fila de páginas', safe_int(metrics.queued_pages))
    if metrics.max_products:
        col_f.metric('Meta de produtos', safe_int(metrics.max_products))
    else:
        col_f.metric('Tempo restante', f'{metrics.seconds_left:.0f}s' if metrics.seconds_left else 'calculando')
    if metrics.current_url:
        st.caption(f'URL atual: {_short_url(metrics.current_url)}')


def _render_progress_table(log: list[dict], height: int) -> None:
    rows = progress_rows(log)
    if not rows:
        return
    st.dataframe(_safe_progress_dataframe(rows), use_container_width=True, height=height)


def _render_execution_plan() -> None:
    st.markdown('#### O que o sistema está fazendo agora')
    st.caption('1. Lendo o link inicial/categoria informado.')
    st.caption('2. Procurando links reais de produtos dentro do site.')
    st.caption('3. Atualizando a tela a cada página lida e a cada lote encontrado.')
    st.caption('4. Abrindo os produtos encontrados em lote inteligente.')
    st.caption('5. Validando depósito, preparando tabela e salvando para envio ao Bling.')


def _render_live_alerts(last_delta: int, has_payload: bool) -> None:
    if not has_payload:
        st.warning('A operação já começou, mas ainda não gravou o primeiro evento detalhado. Acompanhe o tempo decorrido abaixo.')
        return
    if last_delta >= LIVE_HARD_STALE_SECONDS:
        st.error('Sem sinal vivo há muito tempo. A busca provavelmente travou; use o botão de destravar com segurança.')
    elif last_delta >= LIVE_WARNING_SECONDS:
        st.warning('A busca está processando uma etapa pesada e está há mais de 60s sem novo evento. O sistema ainda preserva o checkpoint.')
    else:
        st.success('Operação com sinal vivo registrado. A barra está sendo atualizada pelo processamento minucioso.')


def render_live_site_operation_panel() -> None:
    """Painel fixo para nunca deixar o usuário cego durante captura por site/API.

    BLINGFIX: a barra criada dentro da execução pode sumir após rerun do Streamlit.
    Este painel reconstrói a barra a partir do estado persistido em session_state.
    """
    state = _progress_state_from_streamlit()
    data = state.to_dict()
    log = data.get('events', []) or []
    last = data.get('last', {}) or {}
    elapsed = _elapsed_seconds()
    last_delta = _last_seen_delta()
    has_payload = isinstance(last, dict) and bool(last)
    percent = _payload_progress(last) if has_payload else 3
    status_text = _payload_text(last, 'Preparando captura inteligente...')

    st.markdown('### Painel vivo da operação')
    st.progress(percent, text=f'{status_text} · {percent}%')
    _render_live_alerts(last_delta, has_payload)

    col_a, col_b = st.columns(2)
    col_a.metric('Tempo rodando', f'{elapsed}s')
    col_b.metric('Último sinal vivo', f'{last_delta}s' if has_payload else 'aguardando')

    if has_payload:
        _render_progress_metrics(last)
    else:
        col_c, col_d = st.columns(2)
        col_c.metric('Produtos localizados', 0)
        col_d.metric('Itens processados', 0)

    with st.expander('Histórico minucioso da operação', expanded=True):
        if log:
            _render_progress_table(log, height=360)
        else:
            st.caption('Nenhum evento detalhado foi gravado ainda. A primeira atualização aparece assim que o motor localizar ou processar dados.')

    with st.sidebar:
        st.markdown('##### Operação viva')
        st.progress(percent, text=f'{percent}%')
        st.caption(status_text)
        st.caption(f'Tempo rodando: {elapsed}s')
        st.caption(f'Último sinal: {last_delta}s' if has_payload else 'Aguardando primeiro sinal detalhado')


def render_sidebar_progress_details(payload: dict) -> None:
    """Mostra o andamento da busca por site na barra lateral."""
    log = st.session_state.get(PROGRESS_LOG_KEY) or []
    with st.sidebar:
        st.markdown('##### Busca em andamento')
        _render_progress_metrics(payload)
        if log:
            st.markdown('##### Histórico da busca')
            _render_progress_table(log, height=280)


def make_site_progress_callback(progress_bar, status_box):
    def callback(payload: dict) -> None:
        append_site_progress(payload)
        progress = max(0.0, min(1.0, float((payload or {}).get('progress') or 0.0)))
        stage = str((payload or {}).get('stage') or 'Buscando')
        message = str((payload or {}).get('message') or '')
        current_url = _short_url((payload or {}).get('current_url') or '', max_chars=72)
        detail = f'{stage} · {int(progress * 100)}%'
        if current_url:
            detail = f'{detail} · {current_url}'
        try:
            progress_bar.progress(progress, text=detail)
        except Exception:
            pass
        try:
            status_box.info(message or stage)
        except Exception:
            try:
                status_box.caption(message or stage)
            except Exception:
                pass
        render_sidebar_progress_details(payload)

    return callback


def render_site_progress_history() -> None:
    state = _progress_state_from_streamlit()
    data = state.to_dict()
    log = data.get('events', []) or []
    last = data.get('last', {}) or {}

    st.markdown('### Detalhes da busca')
    elapsed = _elapsed_seconds()
    last_seen_at = last_site_progress_seen_at()
    last_seen_delta = int(time.time() - last_seen_at) if last_seen_at > 0 else 0

    if isinstance(last, dict) and last:
        metrics = SiteProgressMetrics.from_event(state.last, elapsed_seconds=elapsed)
        message = metrics.message or 'Busca em andamento.'
        st.info(f'Última atividade registrada: {message}')
        if last_seen_at > 0:
            st.caption(f'Último sinal vivo há {last_seen_delta}s.')
        _render_progress_metrics(last)
    else:
        st.info(f'A captura foi iniciada há {elapsed}s. O sistema está trabalhando em modo inteligente; algumas etapas aparecem conforme cada página ou lote termina.')
        col_a, col_b = st.columns(2)
        col_a.metric('Tempo decorrido', f'{elapsed}s')
        col_b.metric('Modo', 'Inteligente')

    _render_execution_plan()

    if log:
        st.markdown('#### Últimos eventos da busca')
        with st.container():
            _render_progress_table(log, height=360)
    else:
        st.warning('Ainda não houve evento detalhado gravado nesta execução. Se ficar muito tempo sem mudança, use “Limpar busca travada e tentar novamente”.')

    with st.sidebar:
        st.markdown('##### Histórico da busca')
        if log:
            _render_progress_table(log, height=300)
        else:
            st.caption(f'Busca iniciada há {elapsed}s. Aguardando primeiro evento detalhado.')


__all__ = [
    'PROGRESS_LAST_SEEN_AT_KEY',
    'append_site_progress',
    'last_site_progress_seen_at',
    'make_site_progress_callback',
    'progress_rows',
    'render_live_site_operation_panel',
    'render_sidebar_progress_details',
    'render_site_progress_history',
    'reset_site_progress',
]