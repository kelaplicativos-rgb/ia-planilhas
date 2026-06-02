from __future__ import annotations

from typing import Any

import pandas as pd
import streamlit as st

from bling_app_zero.core.audit import add_audit_event
from bling_app_zero.core.bling_direct_sender_safe import is_direct_send_available, preview_payloads, send_dataframe_to_bling
from bling_app_zero.core.bling_oauth import connection_status
from bling_app_zero.core.blingsmartcore_autocadastro import render_autocadastro_panel
from bling_app_zero.core.operation_contract import OP_CADASTRO, OP_ESTOQUE, normalize_operation

RESPONSIBLE_FILE = 'bling_app_zero/ui/bling_api_batch_panel.py'
BATCH_SIZE = 25
BATCH_STATE_KEY = 'bling_api_batch_send_state_v1'

DIRECT_SEND_TEXT = {
    OP_CADASTRO: 'Cadastrar produtos no Bling',
    OP_ESTOQUE: 'Atualizar estoque no Bling',
}


def _state_id(operation: str, key: str, signature: str, rules_sig: str) -> str:
    return f'{normalize_operation(operation)}::{key}::{signature}::{rules_sig}'


def _empty_state(identity: str, total: int, operation: str) -> dict[str, Any]:
    return {
        'identity': identity,
        'operation': normalize_operation(operation),
        'total': int(total),
        'offset': 0,
        'attempted': 0,
        'sent': 0,
        'failed': 0,
        'skipped': 0,
        'errors': [],
        'not_found_indices': [],
        'done': False,
        'started': False,
    }


def _get_state(identity: str, total: int, operation: str) -> dict[str, Any]:
    state = st.session_state.get(BATCH_STATE_KEY)
    if not isinstance(state, dict) or state.get('identity') != identity:
        state = _empty_state(identity, total, operation)
        st.session_state[BATCH_STATE_KEY] = state
    return state


def _reset_state(identity: str, total: int, operation: str) -> dict[str, Any]:
    state = _empty_state(identity, total, operation)
    st.session_state[BATCH_STATE_KEY] = state
    return state


def _render_payload_preview(download_df: pd.DataFrame, operation: str) -> None:
    preview_limit = 5
    preview_df = download_df.head(preview_limit).copy().fillna('')
    payload_preview = preview_payloads(preview_df, operation, limit=preview_limit)
    if not payload_preview:
        st.warning('Não consegui montar prévia de payload para envio. Confira os campos obrigatórios.')
        return
    ok_count = sum(1 for item in payload_preview if item.get('status') == 'OK')
    ignored_count = len(payload_preview) - ok_count
    if ok_count:
        st.success(f'Payload pronto para prévia: {ok_count} linha(s) válida(s).')
    if ignored_count:
        st.warning(f'{ignored_count} linha(s) da prévia seriam ignoradas por falta de campo obrigatório.')
    with st.expander('Prévia curta do payload', expanded=False):
        st.caption('Prévia limitada a 5 linhas. O envio real roda em lotes para não travar a tela.')
        for index, item in enumerate(payload_preview, start=1):
            st.markdown(f'**Linha {index} · {item.get("status", "")}**')
            motivo = str(item.get('motivo') or '').strip()
            if motivo:
                st.caption(motivo)
            st.json(item.get('payload') or {})


def _render_progress(state: dict[str, Any]) -> None:
    total = int(state.get('total') or 0)
    attempted = int(state.get('attempted') or 0)
    sent = int(state.get('sent') or 0)
    failed = int(state.get('failed') or 0)
    skipped = int(state.get('skipped') or 0)
    progress = attempted / max(total, 1)
    st.progress(min(100, int(progress * 100)), text=f'Progresso: {attempted}/{total} · enviados {sent} · falhas {failed} · ignorados {skipped}')
    cols = st.columns(4)
    cols[0].metric('Processados', attempted)
    cols[1].metric('Enviados', sent)
    cols[2].metric('Falhas', failed)
    cols[3].metric('Ignorados', skipped)


def _append_batch_result(state: dict[str, Any], result, batch_start: int) -> None:
    state['attempted'] = int(state.get('attempted') or 0) + int(result.attempted)
    state['sent'] = int(state.get('sent') or 0) + int(result.sent)
    state['failed'] = int(state.get('failed') or 0) + int(result.failed)
    state['skipped'] = int(state.get('skipped') or 0) + int(result.skipped)
    errors = list(state.get('errors') or [])
    errors.extend(list(result.errors or ()))
    state['errors'] = errors[:80]
    not_found = list(state.get('not_found_indices') or [])
    for item in list(result.not_found_indices or ()): 
        try:
            not_found.append(batch_start + int(item))
        except Exception:
            pass
    state['not_found_indices'] = sorted(set(not_found))


def _result_payload_from_state(state: dict[str, Any]) -> dict[str, Any]:
    return {
        'attempted': int(state.get('attempted') or 0),
        'sent': int(state.get('sent') or 0),
        'failed': int(state.get('failed') or 0),
        'skipped': int(state.get('skipped') or 0),
        'errors': list(state.get('errors') or []),
        'not_found_indices': list(state.get('not_found_indices') or []),
    }


def _render_final_result(download_df: pd.DataFrame, state: dict[str, Any], key: str) -> None:
    payload = _result_payload_from_state(state)
    attempted = payload['attempted']
    sent = payload['sent']
    failed = payload['failed']
    skipped = payload['skipped']
    st.markdown('### Resultado do envio ao Bling')
    if attempted == 0:
        st.error('Envio não iniciado: nenhum produto foi processado.')
    elif failed == 0 and skipped == 0:
        st.success(f'Envio concluído com sucesso: {sent}/{attempted} produto(s) enviado(s) ao Bling.')
    elif sent > 0:
        st.warning(f'Envio parcialmente concluído: {sent}/{attempted} enviado(s), {failed} falha(s), {skipped} ignorado(s).')
    else:
        st.error(f'Envio não concluído: 0/{attempted} enviado(s), {failed} falha(s), {skipped} ignorado(s).')
    for error in payload['errors'][:8]:
        st.error(str(error))
    render_autocadastro_panel(download_df, payload, key=key)


def render_bling_api_batch_panel(download_df: pd.DataFrame, operation: str, key: str, signature: str, rules_sig: str) -> None:
    operation = normalize_operation(operation)
    st.markdown('### Envio direto ao Bling')

    status = connection_status()
    if not status.get('connected'):
        st.warning('Bling não conectado. Conecte o Bling no início do fluxo para enviar direto pela API.')
        return
    if not is_direct_send_available():
        st.warning('Token do Bling indisponível. Reconecte o Bling e tente novamente.')
        return

    identity = _state_id(operation, key, signature, rules_sig)
    state = _get_state(identity, len(download_df), operation)
    _render_payload_preview(download_df, operation)
    _render_progress(state)

    total = int(state.get('total') or len(download_df))
    offset = int(state.get('offset') or 0)
    done = bool(state.get('done'))
    started = bool(state.get('started'))

    col1, col2 = st.columns(2)
    with col1:
        start_label = 'Iniciar envio em lotes' if not started else 'Enviar próximo lote'
        if not done and st.button(start_label, use_container_width=True, key=f'batch_send_next_{identity}'):
            state['started'] = True
            batch_start = int(state.get('offset') or 0)
            batch_end = min(batch_start + BATCH_SIZE, total)
            batch_df = download_df.iloc[batch_start:batch_end].copy().fillna('')
            progress_bar = st.progress(0, text=f'Enviando lote {batch_start + 1}-{batch_end} de {total}...')
            status_box = st.empty()

            def _progress(payload: dict[str, Any]) -> None:
                processed = int(payload.get('processed') or 0)
                batch_total = int(payload.get('total') or len(batch_df))
                sent = int(payload.get('sent') or 0)
                failed = int(payload.get('failed') or 0)
                skipped = int(payload.get('skipped') or 0)
                ratio = float(payload.get('progress') or 0.0)
                progress_bar.progress(min(100, int(ratio * 100)), text=f'Lote: {processed}/{batch_total} · enviados {sent} · falhas {failed} · ignorados {skipped}')
                status_box.caption(f'Lote {batch_start + 1}-{batch_end} de {total}')

            result = send_dataframe_to_bling(batch_df, operation, progress_callback=_progress)
            _append_batch_result(state, result, batch_start)
            state['offset'] = batch_end
            state['done'] = batch_end >= total
            st.session_state[BATCH_STATE_KEY] = state
            add_audit_event(
                'bling_api_batch_sent',
                area='BLING_ENVIO',
                status='OK' if int(result.failed) == 0 else 'PARCIAL',
                details={
                    'operation': operation,
                    'batch_start': batch_start,
                    'batch_end': batch_end,
                    'total': total,
                    'sent': int(result.sent),
                    'failed': int(result.failed),
                    'skipped': int(result.skipped),
                    'responsible_file': RESPONSIBLE_FILE,
                },
            )
            try:
                progress_bar.empty()
                status_box.empty()
            except Exception:
                pass
            st.rerun()
    with col2:
        if st.button('Reiniciar envio em lotes', use_container_width=True, key=f'batch_send_reset_{identity}'):
            _reset_state(identity, len(download_df), operation)
            st.rerun()

    if done or int(state.get('failed') or 0) or int(state.get('skipped') or 0):
        _render_final_result(download_df, state, key=f'{key}_{signature}_{rules_sig}')


__all__ = ['render_bling_api_batch_panel']
