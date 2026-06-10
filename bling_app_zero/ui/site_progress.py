from __future__ import annotations

import time

import pandas as pd
import streamlit as st

from bling_app_zero.core.site_progress_model import SiteProgressMetrics, SiteProgressState, safe_int, safe_text

PROGRESS_LOG_KEY = 'site_progress_log'
PROGRESS_LAST_KEY = 'site_progress_last'
PROGRESS_LAST_SEEN_AT_KEY = 'site_progress_last_seen_at'
NEUTRAL_PROGRESS_STATE_KEY = 'neutral_site_progress_state_v1'
PROGRESS_CALLBACK_LAST_RENDER_KEY = 'site_progress_callback_last_render_at'
PROGRESS_CALLBACK_LAST_PERCENT_KEY = 'site_progress_callback_last_percent'
LIVE_WARNING_SECONDS = 60
LIVE_HARD_STALE_SECONDS = 900
MAX_PROGRESS_EVENTS = 25
CALLBACK_RENDER_INTERVAL_SECONDS = 4.0
CALLBACK_RENDER_MIN_PERCENT_DELTA = 8


# BLINGFIX 2026-06-10:
# Em celular/Android/WebView o Streamlit pode abrir o popup:
# "Bad message format - Tried to use SessionInfo before it was initialized"
# quando o backend envia muitas mensagens de UI durante uma captura longa.
# A correção abaixo mantém o progresso salvo em session_state, mas reduz o volume
# de renderizações em tempo real e remove tabelas/sidebar pesadas durante o loop.


def _progress_state_from_streamlit() -> SiteProgressState:
    stored = st.session_state.get(NEUTRAL_PROGRESS_STATE_KEY)
    if isinstance(stored, dict) and isinstance(stored.get('events'), list):
        return SiteProgressState.from_log(stored.get('events'))
    return SiteProgressState.from_log(st.session_state.get(PROGRESS_LOG_KEY) or [])


def _trim_events(events: list[dict]) -> list[dict]:
    safe_events = [event for event in (events or []) if isinstance(event, dict)]
    return safe_events[-MAX_PROGRESS_EVENTS:]


def _sync_progress_state(state: SiteProgressState) -> None:
    data = state.to_dict()
    events = _trim_events(data.get('events', []) or [])
    data['events'] = events
    st.session_state[NEUTRAL_PROGRESS_STATE_KEY] = data
    st.session_state[PROGRESS_LOG_KEY] = events
    st.session_state[PROGRESS_LAST_KEY] = data.get('last', {})


def reset_site_progress() -> None:
    _sync_progress_state(SiteProgressState())
    st.session_state[PROGRESS_LAST_SEEN_AT_KEY] = time.time()
    st.session_state.pop(PROGRESS_CALLBACK_LAST_RENDER_KEY, None)
    st.session_state.pop(PROGRESS_CALLBACK_LAST_PERCENT_KEY, None)


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
    return SiteProgressState.from_log(_trim_events(log)).rows()


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
    st.caption('3. Salvando progresso leve, sem sobrecarregar a tela.')
    st.caption('4. Abrindo os produtos encontrados em lote inteligente.')
    st.caption('5. Validando e salvando o resultado final.')


def _render_live_alerts(last_delta: int, has_payload: bool) -> None:
    if not has_payload:
        st.info('A operação começou em modo seguro. Aguarde o primeiro sinal salvo.')
        return
    if last_delta >= LIVE_HARD_STALE_SECONDS:
        st.error('Sem sinal vivo há muito tempo. A busca provavelmente travou; use o botão de destravar com segurança.')
    elif last_delta >= LIVE_WARNING_SECONDS:
        st.warning('A busca está processando uma etapa pesada. O checkpoint foi preservado.')
    else:
        st.success('Busca em andamento com checkpoint salvo.')


def render_live_site_operation_panel() -> None:
    """Painel leve para captura por site.

    O painel evita tabelas/sidebar durante execução para não gerar excesso de
    mensagens no frontend do Streamlit, especialmente em Android/WebView.
    """
    state = _progress_state_from_streamlit()
    data = state.to_dict()
    last = data.get('last', {}) or {}
    elapsed = _elapsed_seconds()
    last_delta = _last_seen_delta()
    has_payload = isinstance(last, dict) and bool(last)
    percent = _payload_progress(last) if has_payload else 3
    status_text = _payload_text(last, 'Preparando captura inteligente...')

    st.markdown('### Busca em andamento')
    st.progress(percent, text=f'{status_text} · {percent}%')
    _render_live_alerts(last_delta, has_payload)

    col_a, col_b = st.columns(2)
    col_a.metric('Tempo rodando', f'{elapsed}s')
    col_b.metric('Último sinal vivo', f'{last_delta}s' if has_payload else 'aguardando')

    if has_payload:
        _render_progress_metrics(last)
    else:
        st.caption('O sistema está trabalhando. A tela será atualizada de forma leve para evitar queda da sessão.')


def render_sidebar_progress_details(payload: dict) -> None:
    """Compatibilidade: não renderiza sidebar durante captura longa."""
    append_site_progress(payload)


def _should_render_callback(percent: int) -> bool:
    now = time.time()
    try:
        last_render = float(st.session_state.get(PROGRESS_CALLBACK_LAST_RENDER_KEY) or 0.0)
    except Exception:
        last_render = 0.0
    try:
        last_percent = int(st.session_state.get(PROGRESS_CALLBACK_LAST_PERCENT_KEY) or -100)
    except Exception:
        last_percent = -100

    if last_render <= 0:
        return True
    if now - last_render >= CALLBACK_RENDER_INTERVAL_SECONDS:
        return True
    if abs(percent - last_percent) >= CALLBACK_RENDER_MIN_PERCENT_DELTA:
        return True
    return False


def _mark_callback_rendered(percent: int) -> None:
    st.session_state[PROGRESS_CALLBACK_LAST_RENDER_KEY] = time.time()
    st.session_state[PROGRESS_CALLBACK_LAST_PERCENT_KEY] = int(percent)


def make_site_progress_callback(progress_bar, status_box):
    def callback(payload: dict) -> None:
        append_site_progress(payload)
        try:
            progress = max(0.0, min(1.0, float((payload or {}).get('progress') or 0.0)))
        except Exception:
            progress = 0.0
        percent = int(progress * 100)

        if not _should_render_callback(percent):
            return

        stage = str((payload or {}).get('stage') or 'Buscando')
        message = str((payload or {}).get('message') or '')
        current_url = _short_url((payload or {}).get('current_url') or '', max_chars=52)
        detail = f'{stage} · {percent}%'
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
        _mark_callback_rendered(percent)

    return callback


def render_site_progress_history() -> None:
    state = _progress_state_from_streamlit()
    data = state.to_dict()
    log = _trim_events(data.get('events', []) or [])
    last = data.get('last', {}) or {}

    st.markdown('### Detalhes leves da busca')
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
        st.info(f'A captura foi iniciada há {elapsed}s. O sistema está trabalhando em modo inteligente e leve.')
        col_a, col_b = st.columns(2)
        col_a.metric('Tempo decorrido', f'{elapsed}s')
        col_b.metric('Modo', 'Seguro')

    _render_execution_plan()

    if log:
        with st.expander('Últimos eventos salvos', expanded=False):
            _render_progress_table(log, height=220)
    else:
        st.caption('Aguardando primeiro evento detalhado salvo.')


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
