from __future__ import annotations

import time
from typing import Any

import pandas as pd
import streamlit as st

from bling_app_zero.core.audit import add_audit_event
from bling_app_zero.core.bling_direct_sender_smart_diff import is_direct_send_available, preview_payloads, send_dataframe_to_bling
from bling_app_zero.core.bling_oauth import connection_status
from bling_app_zero.core.bling_preflight_scan import build_bling_preflight_report
from bling_app_zero.core.bling_send_engine import (
    append_batch_result,
    ensure_send_state,
    mark_manual_batch_mode,
    pause_send,
    reset_send,
    result_payload,
    start_auto_send,
)
from bling_app_zero.core.bling_send_state import batch_size_for_operation
from bling_app_zero.core.blingsmartcore_autocadastro import render_autocadastro_panel, render_stock_pending_panel
from bling_app_zero.core.operation_contract import OP_CADASTRO, OP_ESTOQUE, normalize_operation

RESPONSIBLE_FILE = 'bling_app_zero/ui/bling_api_batch_panel.py'
BATCH_STATE_KEY = 'bling_api_batch_send_state_v2'
NEUTRAL_BLING_SEND_STATE_KEY = 'neutral_bling_send_state_v1'
NEUTRAL_BLING_SEND_REPORT_KEY = 'neutral_bling_send_report_v1'
PREFLIGHT_CACHE_KEY = 'bling_api_preflight_cache_v1'
PAYLOAD_PREVIEW_CACHE_KEY = 'bling_api_payload_preview_cache_v2'
LAST_BATCH_SECONDS_KEY = 'bling_api_last_batch_seconds_v1'
MAX_AUTO_BATCH_SECONDS = 22.0

DIRECT_SEND_TEXT = {
    OP_CADASTRO: 'Cadastrar produtos no Bling',
    OP_ESTOQUE: 'Atualizar estoque no Bling',
}


def _batch_size_for_operation(operation: str) -> int:
    return batch_size_for_operation(operation)


def _state_id(operation: str, key: str, signature: str, rules_sig: str) -> str:
    return f'{normalize_operation(operation)}::{key}::{signature}::{rules_sig}'


def _sync_state(state_obj) -> dict[str, Any]:
    data = state_obj.to_dict()
    legacy = {
        'identity': data.get('request', {}).get('identity', ''),
        'operation': data.get('request', {}).get('operation', OP_CADASTRO),
        'total': int(data.get('request', {}).get('total') or 0),
        'offset': int(data.get('offset') or 0),
        'attempted': int(data.get('attempted') or 0),
        'sent': int(data.get('sent') or 0),
        'failed': int(data.get('failed') or 0),
        'skipped': int(data.get('skipped') or 0),
        'errors': list(data.get('errors') or []),
        'not_found_indices': list(data.get('not_found_indices') or []),
        'done': bool(data.get('done')),
        'started': bool(data.get('started')),
        'auto_running': bool(data.get('auto_running')),
        'paused': bool(data.get('paused')),
        'status': data.get('status', ''),
    }
    st.session_state[BATCH_STATE_KEY] = legacy
    st.session_state[NEUTRAL_BLING_SEND_STATE_KEY] = data
    st.session_state[NEUTRAL_BLING_SEND_REPORT_KEY] = result_payload(state_obj)
    return legacy


def _get_state(identity: str, total: int, operation: str) -> dict[str, Any]:
    state_obj = ensure_send_state(st.session_state.get(BATCH_STATE_KEY), identity=identity, total=total, operation=operation)
    return _sync_state(state_obj)


def _reset_state(identity: str, total: int, operation: str) -> dict[str, Any]:
    result = reset_send(identity=identity, total=total, operation=operation)
    st.session_state.pop(LAST_BATCH_SECONDS_KEY, None)
    return _sync_state(result.state)


def _cached_payload_preview(preview_df: pd.DataFrame, operation: str, identity: str, preview_limit: int) -> list[dict[str, Any]]:
    preview_signature = f'{identity}::preview::{preview_limit}'
    cache = st.session_state.get(PAYLOAD_PREVIEW_CACHE_KEY)
    if isinstance(cache, dict) and cache.get('signature') == preview_signature:
        payload = cache.get('payload')
        if isinstance(payload, list):
            return payload

    payload_preview = preview_payloads(preview_df, operation, limit=preview_limit)
    st.session_state[PAYLOAD_PREVIEW_CACHE_KEY] = {
        'signature': preview_signature,
        'payload': payload_preview,
    }
    return payload_preview


def _render_preflight(download_df: pd.DataFrame, operation: str, identity: str) -> None:
    cache = st.session_state.get(PREFLIGHT_CACHE_KEY)
    if isinstance(cache, dict) and cache.get('identity') == identity:
        report = cache.get('report') if isinstance(cache.get('report'), dict) else {}
    else:
        built = build_bling_preflight_report(download_df, operation, batch_size=_batch_size_for_operation(operation))
        report = built.to_dict()
        st.session_state[PREFLIGHT_CACHE_KEY] = {'identity': identity, 'report': report}

    with st.expander('BLINGSCAN · pré-varredura antes do envio', expanded=False):
        st.caption('Varredura local leve para evitar envio pesado e detectar risco antes de chamar a API.')
        cols = st.columns(4)
        cols[0].metric('Linhas', int(report.get('total_rows') or 0))
        cols[1].metric('Aptas', int(report.get('safe_to_send_rows') or 0))
        cols[2].metric('Pendências', int(report.get('missing_required_rows') or 0))
        cols[3].metric('Lotes previstos', int(report.get('estimated_batches') or 0))
        for warning in list(report.get('warnings') or [])[:6]:
            st.warning(str(warning))


def _render_payload_preview(download_df: pd.DataFrame, operation: str, identity: str) -> str:
    preview_limit = 5
    preview_df = download_df.head(preview_limit).copy().fillna('')
    payload_preview = _cached_payload_preview(preview_df, operation, identity, preview_limit)
    if not payload_preview:
        st.warning('Não consegui montar prévia de payload para envio. Confira os campos obrigatórios.')
        return ''

    blocked_items = [item for item in payload_preview if str(item.get('status') or '').upper() == 'BLOQUEADO']
    if blocked_items:
        reason = str(blocked_items[0].get('motivo') or 'Envio bloqueado por segurança.').strip()
        st.error(reason)
        add_audit_event(
            'bling_api_batch_preview_blocked',
            area='BLING_ENVIO',
            status='BLOQUEADO',
            details={'operation': operation, 'reason': reason, 'responsible_file': RESPONSIBLE_FILE},
        )
        return reason

    ok_count = sum(1 for item in payload_preview if item.get('status') == 'OK')
    ignored_count = len(payload_preview) - ok_count
    total_rows = len(download_df) if isinstance(download_df, pd.DataFrame) else 0
    if ok_count:
        st.success(f'Prévia do payload: {ok_count} linha(s) válida(s) entre as {len(payload_preview)} exibidas. Total preparado: {total_rows} linha(s).')
    if ignored_count:
        st.warning(f'{ignored_count} linha(s) da prévia seriam ignoradas por falta de campo obrigatório. Isso vale apenas para a prévia exibida.')
    with st.expander('Prévia curta do payload inteligente', expanded=False):
        st.caption('Prévia limitada a 5 linhas. O envio real usa todas as linhas preparadas pelo BLINGSMARTCORE.')
        for index, item in enumerate(payload_preview, start=1):
            st.markdown(f'**Linha {index} · {item.get("status", "")}**')
            motivo = str(item.get('motivo') or '').strip()
            if motivo:
                st.caption(motivo)
            st.json(item.get('payload') or {})
    return ''


def _render_progress(state: dict[str, Any]) -> None:
    total = int(state.get('total') or 0)
    attempted = int(state.get('attempted') or 0)
    sent = int(state.get('sent') or 0)
    failed = int(state.get('failed') or 0)
    skipped = int(state.get('skipped') or 0)
    operation = normalize_operation(str(state.get('operation') or ''))
    batch_size = _batch_size_for_operation(operation)
    progress = attempted / max(total, 1)
    label = 'Envio automático inteligente em andamento' if state.get('auto_running') and not state.get('done') else 'Progresso'
    st.progress(min(100, int(progress * 100)), text=f'{label}: {attempted}/{total} · enviados {sent} · falhas {failed} · ignorados {skipped}')
    cols = st.columns(4)
    cols[0].metric('Processados', attempted)
    cols[1].metric('Enviados', sent)
    cols[2].metric('Falhas', failed)
    cols[3].metric('Lote atual', batch_size)

    elapsed = st.session_state.get(LAST_BATCH_SECONDS_KEY)
    if isinstance(elapsed, (int, float)) and elapsed > 0:
        st.caption(f'Último lote: {elapsed:.1f}s · checkpoint salvo.')


def _state_obj_from_legacy(state: dict[str, Any]):
    return ensure_send_state(state, identity=str(state.get('identity') or ''), total=int(state.get('total') or 0), operation=str(state.get('operation') or OP_CADASTRO))


def _result_payload_from_state(state: dict[str, Any]) -> dict[str, Any]:
    return result_payload(_state_obj_from_legacy(state))


def _render_final_result(download_df: pd.DataFrame, state: dict[str, Any], key: str) -> None:
    payload = _result_payload_from_state(state)
    operation = normalize_operation(str(state.get('operation') or ''))
    attempted = payload['attempted']
    sent = payload['sent']
    failed = payload['failed']
    skipped = payload['skipped']
    st.markdown('### Resultado do envio ao Bling')
    if attempted == 0:
        st.error('Envio não iniciado: nenhum produto foi processado.')
    elif failed == 0 and skipped == 0:
        st.success(f'Envio concluído com sucesso: {sent}/{attempted} produto(s) enviado(s) ao Bling.')
    elif operation == OP_ESTOQUE and sent > 0:
        st.warning(f'Atualização de estoque concluída parcialmente: {sent}/{attempted} saldo(s) enviado(s), {failed} falha(s), {skipped} ignorado(s). Os itens não encontrados ficam como pendência.')
    elif sent > 0:
        st.warning(f'Envio parcialmente concluído: {sent}/{attempted} enviado(s), {failed} falha(s), {skipped} ignorado(s).')
    else:
        st.error(f'Envio não concluído: 0/{attempted} enviado(s), {failed} falha(s), {skipped} ignorado(s).')
    for error in payload['errors'][:8]:
        st.error(str(error))
    if operation == OP_ESTOQUE:
        render_stock_pending_panel(download_df, payload, key=key)
    else:
        render_autocadastro_panel(download_df, payload, key=key)


def _pause_after_slow_batch(state: dict[str, Any], elapsed: float) -> dict[str, Any]:
    if elapsed <= MAX_AUTO_BATCH_SECONDS or bool(state.get('done')) or not bool(state.get('auto_running')):
        return state
    result = pause_send(_state_obj_from_legacy(state))
    paused = _sync_state(result.state)
    st.warning(
        'Envio automático pausado por segurança: o último lote demorou demais. '
        'O checkpoint foi salvo; toque em continuar para processar o próximo lote.'
    )
    add_audit_event(
        'bling_api_batch_auto_paused_slow_batch',
        area='BLING_ENVIO',
        status='PAUSADO',
        details={
            'elapsed_seconds': round(float(elapsed), 2),
            'limit_seconds': MAX_AUTO_BATCH_SECONDS,
            'operation': state.get('operation'),
            'responsible_file': RESPONSIBLE_FILE,
        },
    )
    return paused


def _send_one_batch(download_df: pd.DataFrame, operation: str, state: dict[str, Any]) -> dict[str, Any]:
    total = int(state.get('total') or len(download_df))
    batch_start = int(state.get('offset') or 0)
    batch_size = _batch_size_for_operation(operation)
    batch_end = min(batch_start + batch_size, total)
    batch_df = download_df.iloc[batch_start:batch_end].copy().fillna('')

    progress_bar = st.progress(0, text=f'BLINGSMARTCORE comparando e enviando lote {batch_start + 1}-{batch_end} de {total}...')
    status_box = st.empty()
    started_at = time.monotonic()

    def _progress(payload: dict[str, Any]) -> None:
        processed = int(payload.get('processed') or 0)
        batch_total = int(payload.get('total') or len(batch_df))
        sent = int(payload.get('sent') or 0)
        failed = int(payload.get('failed') or 0)
        skipped = int(payload.get('skipped') or 0)
        ratio = float(payload.get('progress') or 0.0)
        progress_bar.progress(min(100, int(ratio * 100)), text=f'Lote inteligente: {processed}/{batch_total} · atualizados/criados {sent} · falhas {failed} · sem alteração/ignorados {skipped}')
        status_box.caption(f'Lote {batch_start + 1}-{batch_end} de {total} · tamanho {batch_size}')

    result = send_dataframe_to_bling(batch_df, operation, progress_callback=_progress)
    elapsed = max(0.0, time.monotonic() - started_at)
    st.session_state[LAST_BATCH_SECONDS_KEY] = elapsed

    state_obj = _state_obj_from_legacy(state)
    merged = append_batch_result(state_obj, result, batch_start=batch_start, batch_end=batch_end).state
    state = _sync_state(merged)
    state = _pause_after_slow_batch(state, elapsed)

    add_audit_event(
        'bling_api_batch_sent',
        area='BLING_ENVIO',
        status='OK' if int(result.failed) == 0 else 'PARCIAL',
        details={
            'operation': operation,
            'batch_start': batch_start,
            'batch_end': batch_end,
            'batch_size': batch_size,
            'total': total,
            'sent': int(result.sent),
            'failed': int(result.failed),
            'skipped': int(result.skipped),
            'elapsed_seconds': round(float(elapsed), 2),
            'auto_running': bool(state.get('auto_running')),
            'smart_sender_diff': True,
            'neutral_bling_send_state': True,
            'responsible_file': RESPONSIBLE_FILE,
        },
    )
    try:
        progress_bar.empty()
        status_box.empty()
    except Exception:
        pass
    return state


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
    _render_preflight(download_df, operation, identity)

    block_reason = _render_payload_preview(download_df, operation, identity)
    if block_reason:
        st.warning('O envio direto foi bloqueado. Revise a operação escolhida e gere novamente o preview final antes de enviar ao Bling.')
        return

    state = _get_state(identity, len(download_df), operation)
    _render_progress(state)

    total = int(state.get('total') or len(download_df))
    done = bool(state.get('done'))
    started = bool(state.get('started'))
    auto_running = bool(state.get('auto_running')) and not done and not bool(state.get('paused'))

    if auto_running:
        batch_size = _batch_size_for_operation(operation)
        st.info(f'Envio automático inteligente ativo. O sistema compara o produto atual do Bling, pula sem alteração e envia até {batch_size} item(ns) por lote.')
        _send_one_batch(download_df, operation, state)
        st.rerun()

    col1, col2 = st.columns(2)
    with col1:
        auto_label = 'Iniciar envio automático inteligente' if not started else 'Continuar automaticamente'
        if not done and st.button(auto_label, use_container_width=True, key=f'batch_send_auto_{identity}'):
            result = start_auto_send(_state_obj_from_legacy(state))
            _sync_state(result.state)
            st.rerun()
    with col2:
        if not done and st.button('Enviar apenas 1 lote seguro', use_container_width=True, key=f'batch_send_one_{identity}'):
            result = mark_manual_batch_mode(_state_obj_from_legacy(state))
            state = _sync_state(result.state)
            _send_one_batch(download_df, operation, state)
            st.rerun()

    col3, col4 = st.columns(2)
    with col3:
        if not done and started and st.button('Pausar envio automático', use_container_width=True, key=f'batch_send_pause_{identity}'):
            result = pause_send(_state_obj_from_legacy(state))
            _sync_state(result.state)
            st.rerun()
    with col4:
        if st.button('Reiniciar envio em lotes', use_container_width=True, key=f'batch_send_reset_{identity}'):
            _reset_state(identity, total, operation)
            st.rerun()

    if done or int(state.get('failed') or 0) or int(state.get('skipped') or 0):
        _render_final_result(download_df, state, key=f'{key}_{signature}_{rules_sig}')


__all__ = ['render_bling_api_batch_panel']
