from __future__ import annotations

import time
from typing import Any

import pandas as pd
import streamlit as st

from bling_app_zero.core.live_operation_progress import (
    get_live_operation_last_seen_at,
    get_live_operation_state,
    safe_int,
    safe_text,
)

RESPONSIBLE_FILE = 'bling_app_zero/ui/live_operation_panel.py'
LIVE_WARNING_SECONDS = 60
LIVE_HARD_STALE_SECONDS = 900


def _safe_dataframe(rows: list[dict[str, str]]) -> pd.DataFrame:
    df = pd.DataFrame(rows)
    if df.empty:
        return df
    for column in df.columns:
        df[column] = df[column].map(safe_text).astype(str)
    return df


def _payload_progress(payload: dict[str, Any]) -> int:
    try:
        value = float((payload or {}).get('progress') or 0.0)
    except Exception:
        value = 0.0
    if value <= 1:
        value = value * 100
    return max(0, min(100, int(value)))


def _payload_text(payload: dict[str, Any], fallback: str = 'Processamento em andamento.') -> str:
    if not isinstance(payload, dict):
        return fallback
    stage = safe_text(payload.get('stage') or '')
    message = safe_text(payload.get('message') or '')
    if stage and message:
        return f'{stage}: {message}'
    return message or stage or fallback


def _last_seen_delta() -> int:
    last_seen_at = get_live_operation_last_seen_at()
    if last_seen_at <= 0:
        return 0
    return max(0, int(time.time() - last_seen_at))


def _render_live_alerts(last_delta: int, has_payload: bool) -> None:
    if not has_payload:
        st.warning('A operação começou, mas ainda não gravou o primeiro evento minucioso.')
        return
    if last_delta >= LIVE_HARD_STALE_SECONDS:
        st.error('Sem sinal vivo há muito tempo. Confira o checkpoint antes de iniciar nova tentativa.')
    elif last_delta >= LIVE_WARNING_SECONDS:
        st.warning('Etapa pesada em andamento. A tela não recebeu novo evento há mais de 60s, mas o checkpoint foi preservado.')
    else:
        st.success('Sinal vivo ativo. O processamento está registrando andamento minucioso.')


def render_live_operation_panel(*, title: str = 'Painel vivo da operação', expanded_history: bool = True) -> None:
    state = get_live_operation_state()
    data = state.to_dict()
    last = data.get('last', {}) or {}
    has_payload = isinstance(last, dict) and bool(last)
    percent = _payload_progress(last) if has_payload else 3
    status_text = _payload_text(last, 'Preparando processamento inteligente...')
    last_delta = _last_seen_delta()

    st.markdown(f'### {title}')
    st.progress(percent, text=f'{status_text} · {percent}%')
    _render_live_alerts(last_delta, has_payload)

    processed = safe_int(last.get('processed') if has_payload else 0)
    total = safe_int(last.get('total') if has_payload else 0)
    success = safe_int(last.get('success') if has_payload else 0)
    failed = safe_int(last.get('failed') if has_payload else 0)
    skipped = safe_int(last.get('skipped') if has_payload else 0)
    checkpoint = safe_text(last.get('checkpoint') if has_payload else '') or 'aguardando'

    col_a, col_b = st.columns(2)
    col_a.metric('Processados', f'{processed}/{total}' if total else processed)
    col_b.metric('Último sinal vivo', f'{last_delta}s' if has_payload else 'aguardando')
    col_c, col_d, col_e = st.columns(3)
    col_c.metric('Sucesso', success)
    col_d.metric('Falhas', failed)
    col_e.metric('Ignorados', skipped)
    st.caption(f'Checkpoint: {checkpoint}')

    current_item = safe_text(last.get('current_item') or last.get('current_url') or '') if has_payload else ''
    if current_item:
        if len(current_item) > 140:
            current_item = current_item[:137] + '...'
        st.caption(f'Item atual: {current_item}')

    with st.expander('Histórico minucioso global', expanded=expanded_history):
        rows = state.rows()
        if rows:
            st.dataframe(_safe_dataframe(rows), use_container_width=True, height=360)
        else:
            st.caption('Nenhum evento global registrado ainda. A primeira atualização aparece quando algum recurso começar a processar dados.')


def render_live_operation_sidebar() -> None:
    state = get_live_operation_state()
    last = state.to_dict().get('last', {}) or {}
    if not isinstance(last, dict) or not last:
        return
    percent = _payload_progress(last)
    status_text = _payload_text(last)
    with st.sidebar:
        st.markdown('##### Processamento vivo')
        st.progress(percent, text=f'{percent}%')
        st.caption(status_text)
        st.caption(f'Último sinal: {_last_seen_delta()}s')


__all__ = ['render_live_operation_panel', 'render_live_operation_sidebar']
