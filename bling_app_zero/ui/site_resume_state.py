from __future__ import annotations

import re
from collections.abc import Iterable, Mapping

import pandas as pd
import streamlit as st

from bling_app_zero.core.audit import add_audit_event

RESPONSIBLE_FILE = 'bling_app_zero/ui/site_resume_state.py'
AUTO_RESUME_KEY = 'site_capture_auto_resume_requested'
AUTO_RESUME_OPERATION_KEY = 'site_capture_auto_resume_operation'
AUTO_RESUME_REASON_KEY = 'site_capture_auto_resume_reason'
AUTO_RESUME_ATTEMPTS_KEY = 'site_capture_auto_resume_attempts'
AUTO_RESUME_MAX_ATTEMPTS = 3
CHECKPOINT_KEY = 'site_capture_auto_resume_checkpoint_v2'
CHECKPOINT_OPERATION_KEY = 'site_capture_auto_resume_checkpoint_operation_v2'
LAST_NOTICE_KEY = 'site_capture_auto_resume_notice_v2'
MAX_CHECKPOINT_ROWS = 2500
URL_KEYS = ('site_capture_raw_urls', 'site_capture_raw_urls_universal', 'site_capture_raw_urls_cadastro', 'site_capture_raw_urls_estoque', 'site_capture_raw_urls_atualizacao_preco')


def _normalize_operation(operation: object) -> str:
    text = str(operation or '').strip().lower()
    if text in {'estoque', 'stock', 'saldo', 'atualizacao_estoque', 'atualização de estoque'}:
        return 'estoque'
    if text in {'preco', 'preço', 'atualizacao_preco', 'atualização de preço'}:
        return 'atualizacao_preco'
    if text in {'cadastro', 'produto', 'produtos'}:
        return 'cadastro'
    if text in {'universal', 'modelo', 'modelo_destino', 'planilha', 'wizard_cadastro_estoque'}:
        return 'universal'
    return text or 'universal'


def _operation_matches(payload_operation: object, operation: str | None) -> bool:
    wanted = _normalize_operation(operation or '')
    found = _normalize_operation(payload_operation or '')
    if not operation or wanted == 'universal':
        return True
    return found in {'', 'universal', wanted}


def _as_dict(value: object) -> dict:
    return dict(value) if isinstance(value, Mapping) else {}


def _as_rows(value: object) -> list[dict[str, object]]:
    if not isinstance(value, list):
        return []
    rows: list[dict[str, object]] = []
    for row in value[:MAX_CHECKPOINT_ROWS]:
        if isinstance(row, Mapping):
            rows.append(dict(row))
    return rows


def _as_string_list(value: object) -> list[str]:
    if isinstance(value, str):
        raw = re.split(r'[\n,;]+', value)
    elif isinstance(value, Iterable) and not isinstance(value, (bytes, bytearray, Mapping)):
        raw = list(value)
    else:
        raw = []
    out: list[str] = []
    seen: set[str] = set()
    for item in raw:
        text = str(item or '').strip()
        if not text or text in seen:
            continue
        out.append(text)
        seen.add(text)
    return out


def _payload_candidates() -> list[dict]:
    candidates: list[dict] = []
    for key in (CHECKPOINT_KEY, 'site_progress_last', 'live_operation_progress_last_v1'):
        payload = _as_dict(st.session_state.get(key))
        if payload:
            candidates.append(payload)
    neutral = _as_dict(st.session_state.get('neutral_site_progress_state_v1'))
    neutral_last = _as_dict(neutral.get('last'))
    if neutral_last:
        candidates.append(neutral_last)
    events = neutral.get('events')
    if isinstance(events, list):
        for event in reversed(events[-25:]):
            payload = _as_dict(event)
            if payload:
                candidates.append(payload)
    progress_log = st.session_state.get('site_progress_log')
    if isinstance(progress_log, list):
        for event in reversed(progress_log[-25:]):
            payload = _as_dict(event)
            if payload:
                candidates.append(payload)
    return candidates


def _payload_score(payload: dict) -> int:
    rows = _as_rows(payload.get('partial_checkpoint_rows'))
    count = len(rows)
    for key in ('partial_checkpoint_found', 'found', 'rows'):
        try:
            count = max(count, int(float(payload.get(key) or 0)))
        except Exception:
            pass
    pending = _as_string_list(payload.get('partial_checkpoint_pending_urls') or payload.get('pending_urls'))
    processed = _as_string_list(payload.get('partial_checkpoint_processed_urls') or payload.get('processed_urls'))
    return count * 10 + len(pending) + len(processed)


def checkpoint_payload(operation: str | None = None) -> dict:
    best: dict = {}
    best_score = 0
    for payload in _payload_candidates():
        payload_operation = payload.get('partial_checkpoint_operation') or payload.get('operation') or payload.get('mode') or st.session_state.get(CHECKPOINT_OPERATION_KEY)
        if not _operation_matches(payload_operation, operation):
            continue
        score = _payload_score(payload)
        if score > best_score:
            best = payload
            best_score = score
    return best


def _freeze_checkpoint(operation: str) -> None:
    payload = checkpoint_payload(operation)
    if not payload:
        return
    frozen = dict(payload)
    frozen['partial_checkpoint_operation'] = frozen.get('partial_checkpoint_operation') or _normalize_operation(operation)
    st.session_state[CHECKPOINT_KEY] = frozen
    st.session_state[CHECKPOINT_OPERATION_KEY] = _normalize_operation(operation)


def checkpoint_count(operation: str | None = None) -> int:
    payload = checkpoint_payload(operation)
    if not payload:
        return 0
    count = 0
    for key in ('partial_checkpoint_found', 'found', 'rows'):
        try:
            count = max(count, int(float(payload.get(key) or 0)))
        except Exception:
            pass
    rows = _as_rows(payload.get('partial_checkpoint_rows'))
    return max(count, len(rows))


def checkpoint_df(operation: str | None = None, requested_columns: list[str] | None = None) -> pd.DataFrame:
    payload = checkpoint_payload(operation)
    rows = _as_rows(payload.get('partial_checkpoint_rows'))
    if not rows:
        return pd.DataFrame(columns=requested_columns or [])
    df = pd.DataFrame(rows).fillna('')
    requested = [str(col).strip() for col in (requested_columns or []) if str(col).strip()]
    payload_columns = [str(col).strip() for col in (payload.get('partial_checkpoint_columns') or []) if str(col).strip()]
    columns = list(dict.fromkeys([*requested, *payload_columns, *[str(col) for col in df.columns]]))
    for column in columns:
        if column not in df.columns:
            df[column] = ''
    return df[columns].fillna('')


def _column_key(column: object) -> str:
    text = str(column or '').strip().lower()
    text = text.replace('ã', 'a').replace('á', 'a').replace('à', 'a').replace('â', 'a')
    text = text.replace('é', 'e').replace('ê', 'e').replace('í', 'i')
    text = text.replace('ó', 'o').replace('ô', 'o').replace('õ', 'o').replace('ú', 'u').replace('ç', 'c')
    return re.sub(r'[^a-z0-9]+', '_', text).strip('_')


def _dedupe_columns(df: pd.DataFrame) -> list[str]:
    keys = [_column_key(col) for col in df.columns]
    priority_signals = ('url', 'link', 'produto_url', 'url_produto', 'codigo', 'sku', 'id_produto', 'gtin', 'ean')
    out: list[str] = []
    for signal in priority_signals:
        for column, key in zip(df.columns, keys, strict=False):
            if signal == key or signal in key:
                text = str(column)
                if text not in out:
                    out.append(text)
        if out:
            return out[:2]
    for column, key in zip(df.columns, keys, strict=False):
        if 'descricao' in key or 'nome' in key or 'produto' in key:
            out.append(str(column))
            break
    return out


def _dedupe_checkpoint_rows(df: pd.DataFrame) -> pd.DataFrame:
    if not isinstance(df, pd.DataFrame) or df.empty:
        return df
    columns = _dedupe_columns(df)
    if not columns:
        return df.drop_duplicates().reset_index(drop=True)
    work = df.copy().fillna('')
    work['_blingfix_dedupe_key'] = work[columns].astype(str).agg('|'.join, axis=1).str.lower().str.strip()
    work['_blingfix_dedupe_key'] = work['_blingfix_dedupe_key'].where(work['_blingfix_dedupe_key'].str.len() > 0, work.index.astype(str))
    work = work.drop_duplicates('_blingfix_dedupe_key', keep='last').drop(columns=['_blingfix_dedupe_key'])
    return work.reset_index(drop=True).fillna('')


def merge_checkpoint_with_result(operation: str, df_site: pd.DataFrame | None, requested_columns: list[str] | None = None) -> pd.DataFrame:
    checkpoint = checkpoint_df(operation, requested_columns=requested_columns)
    current = df_site.copy().fillna('') if isinstance(df_site, pd.DataFrame) else pd.DataFrame()
    if checkpoint.empty:
        return current
    if current.empty:
        return checkpoint
    columns = list(dict.fromkeys([*[str(col) for col in checkpoint.columns], *[str(col) for col in current.columns]]))
    for frame in (checkpoint, current):
        for column in columns:
            if column not in frame.columns:
                frame[column] = ''
    merged = pd.concat([checkpoint[columns], current[columns]], ignore_index=True).fillna('')
    return _dedupe_checkpoint_rows(merged)


def checkpoint_pending_urls(operation: str | None = None) -> list[str]:
    payload = checkpoint_payload(operation)
    for key in ('partial_checkpoint_pending_urls', 'pending_urls', 'site_checkpoint_pending_urls'):
        values = _as_string_list(payload.get(key))
        if values:
            return values
    return []


def remember_capture_inputs(operation: str, raw_urls: str) -> None:
    operation = _normalize_operation(operation)
    raw_urls = str(raw_urls or '').strip()
    if not raw_urls:
        return
    st.session_state['site_capture_raw_urls'] = raw_urls
    st.session_state[f'site_capture_raw_urls_{operation}'] = raw_urls
    st.session_state['home_slim_flow_origin'] = 'site'
    st.session_state['origem_final'] = 'site'
    st.session_state['origem_dados'] = 'site'


def resume_raw_urls(operation: str, fallback_raw_urls: str) -> str:
    pending = checkpoint_pending_urls(operation)
    if pending:
        return '\n'.join(pending)
    operation = _normalize_operation(operation)
    saved = str(
        st.session_state.get(f'site_capture_raw_urls_{operation}')
        or st.session_state.get('site_capture_raw_urls')
        or ''
    ).strip()
    return saved or str(fallback_raw_urls or '').strip()


def mark_resume_context(operation: str, reason: str, *, raw_urls: str = '') -> None:
    operation = _normalize_operation(operation)
    remember_capture_inputs(operation, raw_urls)
    _freeze_checkpoint(operation)
    st.session_state['site_capture_running'] = False
    st.session_state['site_capture_finished'] = False
    st.session_state['site_capture_result_ready'] = False
    st.session_state['site_capture_error'] = ''
    st.session_state['site_capture_operation'] = operation
    st.session_state['home_slim_flow_origin'] = 'site'
    st.session_state['origem_final'] = 'site'
    st.session_state['bling_wizard_step'] = 'entrada'
    st.session_state[LAST_NOTICE_KEY] = str(reason or 'Busca retomada automaticamente do checkpoint.')
    add_audit_event(
        'site_capture_resume_context_marked',
        area='SITE',
        step='entrada',
        status='OK',
        details={
            'operation': operation,
            'reason': reason,
            'checkpoint_count': checkpoint_count(operation),
            'pending_urls': len(checkpoint_pending_urls(operation)),
            'auto_resume': True,
            'responsible_file': RESPONSIBLE_FILE,
        },
    )


def clear_checkpoint(operation: str | None = None) -> None:
    st.session_state.pop(CHECKPOINT_KEY, None)
    st.session_state.pop(CHECKPOINT_OPERATION_KEY, None)
    st.session_state.pop(LAST_NOTICE_KEY, None)
    _ = operation


def request_resume(operation: str, reason: str) -> bool:
    operation = _normalize_operation(operation)
    attempts = int(st.session_state.get(AUTO_RESUME_ATTEMPTS_KEY) or 0)
    if attempts >= AUTO_RESUME_MAX_ATTEMPTS:
        st.session_state['site_capture_running'] = False
        st.session_state['site_capture_finished'] = False
        st.session_state['site_capture_result_ready'] = False
        st.session_state['site_capture_error'] = 'A busca tentou continuar automaticamente várias vezes. Reduza o lote ou revise o link inicial.'
        add_audit_event('site_search_resume_limit_reached', area='SITE', status='AVISO', details={'operation': operation, 'attempts': attempts, 'reason': reason, 'responsible_file': RESPONSIBLE_FILE})
        return False
    st.session_state[AUTO_RESUME_KEY] = True
    st.session_state[AUTO_RESUME_OPERATION_KEY] = operation
    st.session_state[AUTO_RESUME_REASON_KEY] = reason
    st.session_state[AUTO_RESUME_ATTEMPTS_KEY] = attempts + 1
    st.session_state['site_capture_running'] = False
    st.session_state['site_capture_finished'] = False
    st.session_state['site_capture_result_ready'] = False
    st.session_state['site_capture_error'] = ''
    mark_resume_context(operation, reason)
    add_audit_event('site_search_resume_requested', area='SITE', status='OK', details={'operation': operation, 'attempts': attempts + 1, 'checkpoint_count': checkpoint_count(operation), 'reason': reason, 'auto_resume': True, 'responsible_file': RESPONSIBLE_FILE})
    return True


def resume_requested(operation: str) -> bool:
    operation = _normalize_operation(operation)
    requested_operation = _normalize_operation(st.session_state.get(AUTO_RESUME_OPERATION_KEY) or operation)
    if operation == 'universal':
        return bool(st.session_state.get(AUTO_RESUME_KEY))
    return bool(st.session_state.get(AUTO_RESUME_KEY)) and requested_operation in {operation, 'universal'}


def clear_resume_request(*, reset_attempts: bool = False) -> None:
    st.session_state.pop(AUTO_RESUME_KEY, None)
    st.session_state.pop(AUTO_RESUME_OPERATION_KEY, None)
    st.session_state.pop(AUTO_RESUME_REASON_KEY, None)
    if reset_attempts:
        st.session_state.pop(AUTO_RESUME_ATTEMPTS_KEY, None)


__all__ = [
    'CHECKPOINT_KEY',
    'checkpoint_count',
    'checkpoint_df',
    'checkpoint_payload',
    'checkpoint_pending_urls',
    'clear_checkpoint',
    'clear_resume_request',
    'mark_resume_context',
    'merge_checkpoint_with_result',
    'remember_capture_inputs',
    'request_resume',
    'resume_raw_urls',
    'resume_requested',
]
