from __future__ import annotations

import re
import time
from typing import Any

import pandas as pd
import streamlit as st

from bling_app_zero.core.audit import add_audit_event
from bling_app_zero.core.background_jobs import background_jobs_available, background_jobs_mode, create_background_bling_job, list_my_background_jobs
from bling_app_zero.core.bling_direct_sender_smart_diff import is_direct_send_available, preview_payloads
from bling_app_zero.core.bling_intelligent_update_sender import send_dataframe_to_bling_intelligent
from bling_app_zero.core.bling_oauth import connection_status
from bling_app_zero.core.bling_preflight_scan import build_bling_preflight_report, build_pending_rows_dataframe, filter_sendable_dataframe
from bling_app_zero.core.bling_send_auto_tuner import intelligent_batch_size, progress_caption
from bling_app_zero.core.bling_send_engine import (
    append_batch_result,
    ensure_send_state,
    pause_send,
    reset_send,
    result_payload,
    start_auto_send,
)
from bling_app_zero.core.bling_send_state import batch_size_for_operation
from bling_app_zero.core.blingsmartcore_autocadastro import render_autocadastro_panel, render_price_pending_panel, render_stock_pending_panel
from bling_app_zero.core.final_output_rule_engine import apply_final_output_rules
from bling_app_zero.core.flow_spine_output import output_diagnostics, output_operation
from bling_app_zero.core.intelligent_flow_decision import decide_before_api_send
from bling_app_zero.core.operation_contract import OP_ATUALIZACAO_PRECO, OP_CADASTRO, OP_ESTOQUE, normalize_operation

RESPONSIBLE_FILE = 'bling_app_zero/ui/bling_api_batch_panel.py'
BATCH_STATE_KEY = 'bling_api_batch_send_state_v2'
NEUTRAL_BLING_SEND_STATE_KEY = 'neutral_bling_send_state_v1'
NEUTRAL_BLING_SEND_REPORT_KEY = 'neutral_bling_send_report_v1'
PREFLIGHT_CACHE_KEY = 'bling_api_preflight_cache_v1'
PAYLOAD_PREVIEW_CACHE_KEY = 'bling_api_payload_preview_cache_v2'
LAST_BATCH_SECONDS_KEY = 'bling_api_last_batch_seconds_v1'
LIVE_PROGRESS_KEY = 'bling_api_live_progress_v2'
INTELLIGENT_BATCH_PLAN_KEY = 'bling_api_intelligent_batch_plan_v1'
BACKGROUND_JOB_CREATED_KEY = 'bling_background_job_created_v1'
FAILED_RETRY_ROWS_KEY = 'bling_api_failed_retry_rows_v1'
FAILED_RETRY_RESULT_KEY = 'bling_api_failed_retry_result_v1'
MAX_AUTO_BATCH_SECONDS = 22.0

DIRECT_SEND_TEXT = {
    OP_CADASTRO: 'Cadastrar produtos no Bling',
    OP_ESTOQUE: 'Atualizar estoque no Bling',
    OP_ATUALIZACAO_PRECO: 'Atualizar preços no Bling',
}


def _spine_operation_or(operation: str) -> str:
    try:
        spine_operation = normalize_operation(output_operation())
        if spine_operation:
            return spine_operation
    except Exception:
        pass
    return normalize_operation(operation)


def _operation_action_label(operation: str) -> str:
    return DIRECT_SEND_TEXT.get(normalize_operation(operation), 'Enviar ao Bling')


def _batch_size_for_operation(operation: str) -> int:
    return batch_size_for_operation(operation)


def _df_signature(df: pd.DataFrame) -> str:
    if not isinstance(df, pd.DataFrame) or df.empty:
        return 'empty'
    columns = '|'.join(map(str, df.columns))
    shape = f'{len(df)}x{len(df.columns)}'
    sample = pd.util.hash_pandas_object(df.head(200).astype(str), index=True).sum()
    return f'{shape}:{columns}:{sample}'


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
    st.session_state['flow_spine_api_batch_operation'] = legacy['operation']
    st.session_state['flow_spine_api_batch_diagnostics'] = output_diagnostics()
    return legacy


def _get_state(identity: str, total: int, operation: str) -> dict[str, Any]:
    state_obj = ensure_send_state(st.session_state.get(BATCH_STATE_KEY), identity=identity, total=total, operation=operation)
    return _sync_state(state_obj)


def _clear_failed_retry_rows(identity: str) -> None:
    store = st.session_state.get(FAILED_RETRY_ROWS_KEY)
    if isinstance(store, dict) and identity in store:
        store.pop(identity, None)
        st.session_state[FAILED_RETRY_ROWS_KEY] = store
    result_store = st.session_state.get(FAILED_RETRY_RESULT_KEY)
    if isinstance(result_store, dict) and result_store.get('identity') == identity:
        st.session_state.pop(FAILED_RETRY_RESULT_KEY, None)


def _reset_state(identity: str, total: int, operation: str) -> dict[str, Any]:
    result = reset_send(identity=identity, total=total, operation=operation)
    st.session_state.pop(LAST_BATCH_SECONDS_KEY, None)
    st.session_state.pop(LIVE_PROGRESS_KEY, None)
    st.session_state.pop(INTELLIGENT_BATCH_PLAN_KEY, None)
    _clear_failed_retry_rows(identity)
    return _sync_state(result.state)


def _line_indices_from_errors(errors: list[Any]) -> set[int]:
    indices: set[int] = set()
    for error in errors or []:
        text = str(error or '')
        for match in re.finditer(r'(?i)linha\s+(\d+)', text):
            try:
                line_number = int(match.group(1))
            except Exception:
                continue
            if line_number > 0:
                indices.add(line_number - 1)
    return indices


def _store_failed_retry_rows(identity: str, batch_start: int, batch_len: int, result: Any) -> list[int]:
    if not identity or batch_len <= 0:
        return []
    local_indices: set[int] = set()
    for item in list(getattr(result, 'not_found_indices', []) or []):
        try:
            local_index = int(item)
        except Exception:
            continue
        if 0 <= local_index < batch_len:
            local_indices.add(local_index)
    local_indices.update(index for index in _line_indices_from_errors(list(getattr(result, 'errors', []) or [])) if 0 <= index < batch_len)

    failed_count = int(getattr(result, 'failed', 0) or 0) + int(getattr(result, 'skipped', 0) or 0)
    sent_count = int(getattr(result, 'sent', 0) or 0)
    attempted = int(getattr(result, 'attempted', 0) or 0)
    if failed_count > 0 and not local_indices and sent_count == 0:
        local_indices.update(range(min(batch_len, attempted or batch_len)))

    absolute_indices = sorted({batch_start + index for index in local_indices if 0 <= index < batch_len})
    if not absolute_indices:
        return []

    store = st.session_state.get(FAILED_RETRY_ROWS_KEY)
    if not isinstance(store, dict):
        store = {}
    current = store.get(identity)
    current_indices = set(current.get('indices') or []) if isinstance(current, dict) else set()
    current_indices.update(absolute_indices)
    store[identity] = {'indices': sorted(current_indices), 'updated_at': time.time()}
    st.session_state[FAILED_RETRY_ROWS_KEY] = store
    add_audit_event(
        'bling_api_failed_rows_marked_for_retry',
        area='BLING_ENVIO',
        status='OK',
        details={'identity': identity, 'rows': len(absolute_indices), 'batch_start': batch_start, 'responsible_file': RESPONSIBLE_FILE},
    )
    return absolute_indices


def _failed_retry_indices(identity: str, total_rows: int) -> list[int]:
    store = st.session_state.get(FAILED_RETRY_ROWS_KEY)
    if not isinstance(store, dict):
        return []
    entry = store.get(identity)
    if not isinstance(entry, dict):
        return []
    indices: list[int] = []
    for item in list(entry.get('indices') or []):
        try:
            index = int(item)
        except Exception:
            continue
        if 0 <= index < total_rows:
            indices.append(index)
    return sorted(set(indices))


def _render_retry_result(identity: str) -> None:
    payload = st.session_state.get(FAILED_RETRY_RESULT_KEY)
    if not isinstance(payload, dict) or payload.get('identity') != identity:
        return
    attempted = int(payload.get('attempted') or 0)
    sent = int(payload.get('sent') or 0)
    failed = int(payload.get('failed') or 0)
    skipped = int(payload.get('skipped') or 0)
    if attempted <= 0:
        return
    if failed == 0 and skipped == 0 and sent > 0:
        st.success(f'Reenvio das falhas concluído: {sent}/{attempted} linha(s) enviada(s).')
    elif sent > 0:
        st.warning(f'Reenvio parcial: {sent}/{attempted} enviada(s), {failed} falha(s), {skipped} ignorada(s).')
    else:
        st.error(f'Reenvio não concluído: 0/{attempted} enviada(s), {failed} falha(s), {skipped} ignorada(s).')
    for error in list(payload.get('errors') or [])[:5]:
        st.error(str(error))


def _render_retry_failed_rows(download_df: pd.DataFrame, state: dict[str, Any], key: str) -> None:
    identity = str(state.get('identity') or '')
    operation = normalize_operation(str(state.get('operation') or ''))
    indices = _failed_retry_indices(identity, len(download_df) if isinstance(download_df, pd.DataFrame) else 0)
    if not indices:
        _render_retry_result(identity)
        return

    retry_df = download_df.iloc[indices].copy().fillna('')
    st.markdown('### Reenviar falhas')
    st.warning(f'{len(retry_df)} linha(s) com falha ficaram separadas para reenvio. O botão abaixo manda somente essas linhas novamente.')
    _render_retry_result(identity)
    if st.button('Reenviar somente falhas', use_container_width=True, key=f'bling_retry_failed_rows_{key}_{identity}'):
        try:
            result = send_dataframe_to_bling_intelligent(retry_df, operation)
            result_data = {
                'identity': identity,
                'operation': operation,
                'attempted': int(result.attempted),
                'sent': int(result.sent),
                'failed': int(result.failed),
                'skipped': int(result.skipped),
                'errors': list(result.errors or []),
            }
            st.session_state[FAILED_RETRY_RESULT_KEY] = result_data
            if int(result.failed or 0) == 0 and int(result.skipped or 0) == 0:
                _clear_failed_retry_rows(identity)
            add_audit_event(
                'bling_api_failed_rows_retry_sent',
                area='BLING_ENVIO',
                status='OK' if int(result.failed or 0) == 0 else 'PARCIAL',
                details={**result_data, 'rows': len(retry_df), 'responsible_file': RESPONSIBLE_FILE},
            )
            st.rerun()
        except Exception as exc:
            st.session_state[FAILED_RETRY_RESULT_KEY] = {'identity': identity, 'operation': operation, 'attempted': len(retry_df), 'sent': 0, 'failed': len(retry_df), 'skipped': 0, 'errors': [str(exc)]}
            add_audit_event('bling_api_failed_rows_retry_error', area='BLING_ENVIO', status='ERRO', details={'identity': identity, 'operation': operation, 'rows': len(retry_df), 'error': str(exc)[:300], 'responsible_file': RESPONSIBLE_FILE})
            st.rerun()


def _cached_payload_preview(preview_df: pd.DataFrame, operation: str, identity: str, preview_limit: int) -> list[dict[str, Any]]:
    preview_signature = f'{identity}::preview::{preview_limit}'
    cache = st.session_state.get(PAYLOAD_PREVIEW_CACHE_KEY)
    if isinstance(cache, dict) and cache.get('signature') == preview_signature:
        payload = cache.get('payload')
        if isinstance(payload, list):
            return payload
    payload_preview = preview_payloads(preview_df, operation, limit=preview_limit)
    st.session_state[PAYLOAD_PREVIEW_CACHE_KEY] = {'signature': preview_signature, 'payload': payload_preview}
    return payload_preview


def _apply_api_final_rules(download_df: pd.DataFrame, operation: str) -> pd.DataFrame:
    if not isinstance(download_df, pd.DataFrame) or download_df.empty:
        return pd.DataFrame()
    fixed_df, report = apply_final_output_rules(download_df, context='api')
    st.session_state['bling_api_final_output_rule_report'] = report.to_dict()
    if report.changed_cells:
        if report.rows_limited:
            st.success(f'Regra aplicada antes da API: {report.rows_limited} produto(s) limitado(s) ao máximo de 6 imagens.')
        else:
            st.caption(f'Regras finais aplicadas antes da API em {report.changed_cells} célula(s).')
    for warning in report.warnings:
        if report.blocked_for_api:
            st.error(warning)
        else:
            st.warning(warning)
    if report.blocked_for_api:
        st.info('Ligue “Limitar imagens para Bling” no centro de regras ou aplique a correção segura antes do envio por API.')
        add_audit_event(
            'bling_api_batch_blocked_by_final_output_rules',
            area='BLING_ENVIO',
            status='BLOQUEADO',
            details={'operation': normalize_operation(operation), 'report': report.to_dict(), 'responsible_file': RESPONSIBLE_FILE},
        )
        return pd.DataFrame(columns=list(download_df.columns))
    return fixed_df.copy().fillna('')


def _render_preflight(download_df: pd.DataFrame, operation: str, identity: str) -> dict[str, Any]:
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
        cols[2].metric('Pendências', int(report.get('blocked_rows') or report.get('missing_required_rows') or 0))
        cols[3].metric('Lotes previstos', int(report.get('estimated_batches') or 0))
        if int(report.get('rows_over_image_limit') or 0):
            st.warning(f"{int(report.get('rows_over_image_limit') or 0)} produto(s) com mais de 6 imagens foram separados antes da API.")
        for warning in list(report.get('warnings') or [])[:6]:
            st.warning(str(warning))
    return report


def _render_flow_decision(report: dict[str, Any], operation: str) -> dict[str, Any]:
    decision = decide_before_api_send(operation=operation, preflight_report=report)
    if decision.status == 'BLOQUEADO':
        st.error(f'{decision.title}: {decision.message}')
    elif decision.status == 'ATENCAO':
        st.warning(f'{decision.title}: {decision.message}')
    else:
        st.success(f'{decision.title}: {decision.message}')
    if decision.reasons:
        with st.expander('Decisão inteligente · motivos', expanded=False):
            for reason in decision.reasons[:10]:
                st.caption(f'• {reason}')
    add_audit_event('bling_api_intelligent_flow_decision', area='BLING_ENVIO', status=decision.status, details={'operation': operation, 'decision': decision.to_dict(), 'flow_spine': output_diagnostics(), 'responsible_file': RESPONSIBLE_FILE})
    return decision.to_dict()


def _render_pending_rows(download_df: pd.DataFrame, operation: str, identity: str, blocked_rows: int) -> None:
    if blocked_rows <= 0:
        return
    pending_df = build_pending_rows_dataframe(download_df, operation, limit=150)
    if not isinstance(pending_df, pd.DataFrame) or pending_df.empty:
        return
    with st.expander('Pendências do envio · linhas que não serão enviadas', expanded=True):
        st.caption('Essas linhas foram separadas antes da API para evitar erro, demora e queda do sistema.')
        st.dataframe(pending_df, use_container_width=True, hide_index=True)
        try:
            csv_bytes = pending_df.to_csv(index=False, sep=';', encoding='utf-8-sig').encode('utf-8-sig')
        except Exception:
            csv_bytes = b''
        if csv_bytes:
            st.download_button('⬇️ Baixar pendências CSV', data=csv_bytes, file_name='bling_pendencias_envio.csv', mime='text/csv; charset=utf-8', use_container_width=True, key=f'bling_pending_rows_csv_{identity}')


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
        add_audit_event('bling_api_batch_preview_blocked', area='BLING_ENVIO', status='BLOQUEADO', details={'operation': operation, 'reason': reason, 'flow_spine': output_diagnostics(), 'responsible_file': RESPONSIBLE_FILE})
        return reason
    ok_count = sum(1 for item in payload_preview if item.get('status') == 'OK')
    ignored_count = len(payload_preview) - ok_count
    total_rows = len(download_df) if isinstance(download_df, pd.DataFrame) else 0
    if ok_count:
        st.success(f'Prévia do payload: {ok_count} linha(s) válida(s) entre as {len(payload_preview)} exibidas. Total apto para envio: {total_rows} linha(s).')
    if ignored_count:
        st.warning(f'{ignored_count} linha(s) da prévia seriam ignoradas por falta de campo obrigatório. Isso vale apenas para a prévia exibida.')
    with st.expander('Prévia curta do payload inteligente', expanded=False):
        st.caption('Prévia limitada a 5 linhas. O envio real usa somente linhas aptas pela pré-varredura BLINGSCAN.')
        for index, item in enumerate(payload_preview, start=1):
            st.markdown(f'**Linha {index} · {item.get("status", "")}**')
            motivo = str(item.get('motivo') or '').strip()
            if motivo:
                st.caption(motivo)
            st.json(item.get('payload') or {})
    return ''


def _current_plan(operation: str, state: dict[str, Any] | None = None):
    state = state or {}
    stored = st.session_state.get(INTELLIGENT_BATCH_PLAN_KEY)
    current_batch_size = None
    if isinstance(stored, dict) and stored.get('operation') == normalize_operation(operation):
        current_batch_size = int(stored.get('batch_size') or 0)
    if not current_batch_size:
        current_batch_size = _batch_size_for_operation(operation)
    return intelligent_batch_size(
        operation,
        current_batch_size=current_batch_size,
        last_batch_seconds=st.session_state.get(LAST_BATCH_SECONDS_KEY),
        last_failed=int(state.get('last_batch_failed') or 0),
        last_skipped=int(state.get('last_batch_skipped') or 0),
    )


def _store_plan_after_batch(operation: str, *, batch_size: int, elapsed: float, failed: int, skipped: int) -> None:
    plan = intelligent_batch_size(
        operation,
        current_batch_size=batch_size,
        last_batch_seconds=elapsed,
        last_failed=failed,
        last_skipped=skipped,
    )
    st.session_state[INTELLIGENT_BATCH_PLAN_KEY] = plan.to_dict()


def _render_live_progress(identity: str) -> None:
    live = st.session_state.get(LIVE_PROGRESS_KEY)
    if not isinstance(live, dict) or live.get('identity') != identity:
        return
    processed = int(live.get('processed') or 0)
    total = int(live.get('total') or 0)
    sent = int(live.get('sent') or 0)
    failed = int(live.get('failed') or 0)
    skipped = int(live.get('skipped') or 0)
    pct = max(0, min(100, int(float(live.get('progress') or 0.0) * 100)))
    stage = str(live.get('stage') or 'Processando envio via API Bling')
    st.progress(pct, text=f'{stage}: {processed}/{max(total, 1)} · enviados {sent} · falhas {failed} · ignorados {skipped}')
    st.caption(str(live.get('detail') or 'Acompanhamento real do lote em execução/checkpoint salvo.'))


def _render_progress(state: dict[str, Any]) -> None:
    total = int(state.get('total') or 0)
    attempted = int(state.get('attempted') or 0)
    sent = int(state.get('sent') or 0)
    failed = int(state.get('failed') or 0)
    skipped = int(state.get('skipped') or 0)
    operation = normalize_operation(str(state.get('operation') or ''))
    plan = _current_plan(operation, state)
    progress = attempted / max(total, 1)
    label = 'Envio inteligente em andamento' if state.get('auto_running') and not state.get('done') else 'Progresso'
    st.progress(min(100, int(progress * 100)), text=f'{label}: {attempted}/{total} · enviados {sent} · falhas {failed} · ignorados {skipped}')
    _render_live_progress(str(state.get('identity') or ''))
    cols = st.columns(4)
    cols[0].metric('Processados', attempted)
    cols[1].metric('Enviados', sent)
    cols[2].metric('Falhas', failed)
    cols[3].metric('Lote inteligente', plan.batch_size)
    elapsed = st.session_state.get(LAST_BATCH_SECONDS_KEY)
    if isinstance(elapsed, (int, float)) and elapsed > 0:
        st.caption(f'Último lote: {elapsed:.1f}s · checkpoint salvo · {progress_caption(plan)}')
    else:
        st.caption(progress_caption(plan))


def _render_background_jobs_summary() -> None:
    try:
        jobs = list_my_background_jobs(limit=8)
    except Exception as exc:
        st.caption(f'Não consegui listar tarefas em segundo plano agora: {exc}')
        return
    if not jobs:
        return
    with st.expander('Minhas tarefas em segundo plano', expanded=False):
        for job in jobs:
            progress = int((int(job.attempted) / max(int(job.total_rows), 1)) * 100)
            st.markdown(f'**{job.title or job.operation}**')
            st.progress(min(100, progress), text=f'{job.status}: {job.attempted}/{job.total_rows} · enviados {job.sent} · falhas {job.failed} · ignorados {job.skipped}')
            if job.last_error:
                st.caption(f'Último erro: {job.last_error}')


def _render_background_job_launcher(send_df: pd.DataFrame, operation: str, identity: str, report: dict[str, Any], flow_decision: dict[str, Any], state: dict[str, Any]) -> None:
    st.markdown('### Modo segundo plano')
    if not background_jobs_available():
        st.warning('Segundo plano indisponível agora. Configure Firestore para continuar tarefas mesmo com o navegador fechado.')
        return
    mode = background_jobs_mode()
    if mode != 'firestore':
        st.warning('Modo segundo plano local disponível apenas como fallback. Para continuar após fechar a aba no Streamlit Cloud, use Firestore.')
    else:
        st.success('Modo segundo plano persistente disponível. Você pode iniciar a tarefa e voltar depois para conferir.')

    created = st.session_state.get(BACKGROUND_JOB_CREATED_KEY)
    if isinstance(created, dict) and created.get('identity') == identity:
        st.info(f'Tarefa criada: {created.get("job_id")}. Volte depois em “Minhas tarefas em segundo plano” para conferir.')
        return

    plan = _current_plan(operation, state)
    if st.button('Iniciar em segundo plano e poder fechar o navegador', use_container_width=True, key=f'background_job_create_{identity}'):
        try:
            snapshot = create_background_bling_job(
                send_df,
                operation=operation,
                title=_operation_action_label(operation),
                metadata={'identity': identity, 'preflight_report': report, 'flow_decision': flow_decision, 'flow_spine': output_diagnostics()},
                batch_size=int(plan.batch_size),
            )
            st.session_state[BACKGROUND_JOB_CREATED_KEY] = {'identity': identity, 'job_id': snapshot.job_id}
            st.success(f'Tarefa em segundo plano criada: {snapshot.job_id}. Você pode fechar o navegador e voltar depois para conferir.')
            add_audit_event('bling_api_background_job_created_from_panel', area='BACKGROUND_JOBS', status='OK', details={'job_id': snapshot.job_id, 'operation': operation, 'rows': len(send_df), 'responsible_file': RESPONSIBLE_FILE})
            st.rerun()
        except Exception as exc:
            st.error(f'Não consegui criar a tarefa em segundo plano: {exc}')
            add_audit_event('bling_api_background_job_create_failed', area='BACKGROUND_JOBS', status='ERRO', details={'operation': operation, 'rows': len(send_df), 'error': str(exc)[:300], 'responsible_file': RESPONSIBLE_FILE})


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
        if operation == OP_ATUALIZACAO_PRECO:
            st.success(f'Finalizado com sucesso. Atualização de preços concluída: {sent}/{attempted} preço(s) enviado(s) ao Bling.')
        else:
            st.success(f'Finalizado com sucesso. Envio concluído: {sent}/{attempted} produto(s) enviado(s) ao Bling.')
    elif operation == OP_ESTOQUE and sent > 0:
        st.warning(f'Finalizado com atenção. Estoque parcial: {sent}/{attempted} saldo(s) enviado(s), {failed} falha(s), {skipped} ignorado(s).')
    elif operation == OP_ATUALIZACAO_PRECO and sent > 0:
        st.warning(f'Finalizado com atenção. Preços parciais: {sent}/{attempted} preço(s) enviado(s), {failed} falha(s), {skipped} ignorado(s).')
    elif sent > 0:
        st.warning(f'Finalizado com atenção. Envio parcial: {sent}/{attempted} enviado(s), {failed} falha(s), {skipped} ignorado(s).')
    else:
        st.error(f'Finalizado com erro. Nenhum item enviado: 0/{attempted} enviado(s), {failed} falha(s), {skipped} ignorado(s).')
    for error in payload['errors'][:8]:
        st.error(str(error))
    if operation == OP_ESTOQUE:
        render_stock_pending_panel(download_df, payload, key=key)
    elif operation == OP_ATUALIZACAO_PRECO:
        render_price_pending_panel(download_df, payload, key=key)
        st.caption('Produtos sem vínculo no canal ficam separados em relatório próprio. Confira ID/SKU/GTIN, preço e vínculo produto-canal antes de reenviar.')
    else:
        render_autocadastro_panel(download_df, payload, key=key)
    _render_retry_failed_rows(download_df, state, key=key)


def _pause_after_slow_batch(state: dict[str, Any], elapsed: float) -> dict[str, Any]:
    operation = normalize_operation(str(state.get('operation') or ''))
    if elapsed <= MAX_AUTO_BATCH_SECONDS or bool(state.get('done')) or not bool(state.get('auto_running')):
        return state
    add_audit_event('bling_api_batch_slow_batch_kept_running_intelligent_mode', area='BLING_ENVIO', status='OK', details={'elapsed_seconds': round(float(elapsed), 2), 'operation': operation, 'reason': 'modo inteligente reduz o lote automaticamente sem exigir escolha do usuario', 'responsible_file': RESPONSIBLE_FILE})
    return state


def _send_one_batch(download_df: pd.DataFrame, operation: str, state: dict[str, Any]) -> dict[str, Any]:
    total = int(state.get('total') or len(download_df))
    batch_start = int(state.get('offset') or 0)
    plan = _current_plan(operation, state)
    batch_size = int(plan.batch_size)
    batch_end = min(batch_start + batch_size, total)
    batch_df = download_df.iloc[batch_start:batch_end].copy().fillna('')
    identity = str(state.get('identity') or '')

    progress_bar = st.progress(1, text=f'Iniciando envio inteligente {batch_start + 1}-{batch_end} de {total} no Bling...')
    status_box = st.empty()
    status_box.info(progress_caption(plan))
    st.session_state[INTELLIGENT_BATCH_PLAN_KEY] = plan.to_dict()
    st.session_state[LIVE_PROGRESS_KEY] = {
        'identity': identity,
        'stage': 'Iniciando envio inteligente via API Bling',
        'processed': 0,
        'total': len(batch_df),
        'sent': 0,
        'failed': 0,
        'skipped': 0,
        'progress': 0.01,
        'detail': f'Lote inteligente {batch_start + 1}-{batch_end} de {total} · operação {operation}',
    }
    started_at = time.monotonic()

    def _progress(payload: dict[str, Any]) -> None:
        processed = int(payload.get('processed') or 0)
        batch_total = int(payload.get('total') or len(batch_df))
        sent = int(payload.get('sent') or 0)
        failed = int(payload.get('failed') or 0)
        skipped = int(payload.get('skipped') or 0)
        ratio = max(0.01, min(1.0, float(payload.get('progress') or 0.0)))
        stage = str(payload.get('stage') or 'Processando envio inteligente via API Bling')
        detail = f'Lote inteligente {batch_start + 1}-{batch_end} de {total} · tamanho {batch_size} · operação {operation}'
        st.session_state[LIVE_PROGRESS_KEY] = {
            'identity': identity,
            'stage': stage,
            'processed': processed,
            'total': batch_total,
            'sent': sent,
            'failed': failed,
            'skipped': skipped,
            'progress': ratio,
            'detail': detail,
        }
        progress_bar.progress(min(100, int(ratio * 100)), text=f'{stage}: {processed}/{batch_total} · enviados {sent} · falhas {failed} · ignorados {skipped}')
        status_box.info(detail)

    result = send_dataframe_to_bling_intelligent(batch_df, operation, progress_callback=_progress)
    _store_failed_retry_rows(identity, batch_start, len(batch_df), result)
    elapsed = max(0.0, time.monotonic() - started_at)
    st.session_state[LAST_BATCH_SECONDS_KEY] = elapsed
    _store_plan_after_batch(operation, batch_size=batch_size, elapsed=elapsed, failed=int(result.failed), skipped=int(result.skipped))

    state_obj = _state_obj_from_legacy(state)
    merged = append_batch_result(state_obj, result, batch_start=batch_start, batch_end=batch_end).state
    state = _sync_state(merged)
    state = _pause_after_slow_batch(state, elapsed)

    final_total = max(int(result.attempted or len(batch_df)), 1)
    final_processed = min(final_total, int(result.attempted or final_total))
    final_progress = final_processed / max(final_total, 1)
    final_stage = 'Lote inteligente concluído' if int(result.failed) == 0 else 'Lote inteligente concluído com falhas'
    st.session_state[LIVE_PROGRESS_KEY] = {
        'identity': identity,
        'stage': final_stage,
        'processed': final_processed,
        'total': final_total,
        'sent': int(result.sent),
        'failed': int(result.failed),
        'skipped': int(result.skipped),
        'progress': final_progress,
        'detail': f'Último lote levou {elapsed:.1f}s · checkpoint salvo.',
    }
    progress_bar.progress(min(100, int(final_progress * 100)), text=f'{final_stage}: {final_processed}/{final_total} · enviados {int(result.sent)} · falhas {int(result.failed)} · ignorados {int(result.skipped)}')
    if int(result.failed) == 0:
        status_box.success(f'Lote inteligente finalizado em {elapsed:.1f}s. Checkpoint salvo.')
    else:
        status_box.warning(f'Lote inteligente finalizado com falhas em {elapsed:.1f}s. Checkpoint salvo; o sistema ajusta a velocidade automaticamente.')

    add_audit_event('bling_api_batch_sent', area='BLING_ENVIO', status='OK' if int(result.failed) == 0 else 'PARCIAL', details={'operation': operation, 'batch_start': batch_start, 'batch_end': batch_end, 'batch_size': batch_size, 'total': total, 'sent': int(result.sent), 'failed': int(result.failed), 'skipped': int(result.skipped), 'elapsed_seconds': round(float(elapsed), 2), 'auto_running': bool(state.get('auto_running')), 'live_progress_enabled': True, 'intelligent_update_sender': True, 'intelligent_batch_plan': st.session_state.get(INTELLIGENT_BATCH_PLAN_KEY), 'neutral_bling_send_state': True, 'flow_spine': output_diagnostics(), 'responsible_file': RESPONSIBLE_FILE})
    return state


def render_bling_api_batch_panel(download_df: pd.DataFrame, operation: str, key: str, signature: str, rules_sig: str) -> None:
    operation = _spine_operation_or(operation)
    st.markdown('### Envio direto ao Bling')
    st.caption(f'{_operation_action_label(operation)} · operação: {operation}')
    _render_background_jobs_summary()

    status = connection_status()
    if not status.get('connected'):
        st.warning('Bling não conectado. Conecte o Bling no início do fluxo para enviar direto pela API.')
        return
    if not is_direct_send_available():
        st.warning('Token do Bling indisponível. Reconecte o Bling e tente novamente.')
        return

    download_df = _apply_api_final_rules(download_df, operation)
    if not isinstance(download_df, pd.DataFrame) or download_df.empty:
        return
    signature = _df_signature(download_df)

    identity = _state_id(operation, key, signature, rules_sig)
    report = _render_preflight(download_df, operation, identity)
    flow_decision = _render_flow_decision(report, operation)
    send_df = filter_sendable_dataframe(download_df, operation)

    blocked_rows = int(report.get('blocked_rows') or 0)
    _render_pending_rows(download_df, operation, identity, blocked_rows)

    if bool(flow_decision.get('should_block')) or not isinstance(send_df, pd.DataFrame) or send_df.empty:
        st.error('Envio bloqueado: nenhuma linha apta para a API do Bling após a pré-varredura.')
        if operation == OP_ATUALIZACAO_PRECO:
            st.warning('Revise ID Bling/SKU/código/GTIN e preço antes de enviar.')
        else:
            st.warning('Revise SKU/código/GTIN e quantidade no estoque, nome/código no cadastro ou limite de imagens antes de enviar.')
        add_audit_event('bling_api_batch_blocked_no_sendable_rows', area='BLING_ENVIO', status='BLOQUEADO', details={'operation': operation, 'rows': len(download_df) if isinstance(download_df, pd.DataFrame) else 0, 'flow_spine': output_diagnostics(), 'responsible_file': RESPONSIBLE_FILE})
        return

    if blocked_rows:
        st.warning(f'{blocked_rows} linha(s) ficaram como pendência e não serão enviadas neste lote. O envio seguirá apenas com {len(send_df)} linha(s) apta(s).')

    block_reason = _render_payload_preview(send_df, operation, identity)
    if block_reason:
        st.warning('O envio direto foi bloqueado. Revise a operação escolhida e gere novamente o preview final antes de enviar ao Bling.')
        return

    state = _get_state(identity, len(send_df), operation)
    _render_progress(state)
    _render_background_job_launcher(send_df, operation, identity, report, flow_decision, state)

    total = int(state.get('total') or len(send_df))
    done = bool(state.get('done'))
    started = bool(state.get('started'))
    auto_running = bool(state.get('auto_running')) and not done and not bool(state.get('paused'))

    if auto_running:
        plan = _current_plan(operation, state)
        st.info(f'Envio inteligente ativo. {progress_caption(plan)}')
        _send_one_batch(send_df, operation, state)
        st.rerun()

    button_label = _operation_action_label(operation) if not started else 'Continuar envio inteligente'
    if not done and st.button(button_label, use_container_width=True, key=f'batch_send_auto_{identity}'):
        result = start_auto_send(_state_obj_from_legacy(state))
        _sync_state(result.state)
        st.rerun()

    col1, col2 = st.columns(2)
    with col1:
        if not done and started and st.button('Pausar envio', use_container_width=True, key=f'batch_send_pause_{identity}'):
            result = pause_send(_state_obj_from_legacy(state))
            _sync_state(result.state)
            st.rerun()
    with col2:
        if st.button('Reiniciar envio', use_container_width=True, key=f'batch_send_reset_{identity}'):
            _reset_state(identity, total, operation)
            st.rerun()

    if done or int(state.get('failed') or 0) or int(state.get('skipped') or 0):
        _render_final_result(send_df, state, key=f'{key}_{signature}_{rules_sig}')


__all__ = ['render_bling_api_batch_panel']
