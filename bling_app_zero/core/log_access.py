from __future__ import annotations

import json
from collections import Counter
from datetime import datetime
from typing import Any

import pandas as pd
import streamlit as st

from bling_app_zero.core.audit import get_audit_events, get_audit_session_id
from bling_app_zero.core.debug import LOG_SESSION_KEY

RESPONSIBLE_FILE = 'bling_app_zero/core/log_access.py'
SENSITIVE_KEYWORDS = (
    'password', 'senha', 'secret', 'token', 'client_secret', 'authorization', 'cookie',
    'api_key', 'apikey', 'credential', 'credentials', 'auth', 'security_code', 'captcha', '2fa',
)
IMPORTANT_STATE_KEYS = (
    'bling_wizard_step',
    'home_slim_flow_operation',
    'home_slim_flow_origin',
    'origem_final',
    'tipo_operacao',
    'operation_site',
    'site_capture_running',
    'site_capture_finished',
    'site_capture_result_ready',
    'site_capture_error',
    'mapping_last_interruption_point',
    'df_site_bruto_cadastro',
    'df_site_bruto',
    'df_origem_site_como_planilha_cadastro',
    'cadastro_wizard_df_origem',
    'df_final_cadastro',
    'mapping_cadastro',
    'mapping_confidence_cadastro',
    'cadastro_mapping_confirmed',
    'cadastro_mapping_confirmed_signature',
)
DESCRIPTION_TOKENS = ('descr', 'caracter', 'ficha', 'detalh')
SITE_DF_KEYS = (
    'df_site_bruto_cadastro',
    'df_site_bruto',
    'df_origem_site_como_planilha_cadastro',
    'df_origem_site',
    'cadastro_wizard_df_origem',
    'df_final_cadastro',
)


def _safe_text(value: Any, limit: int = 700) -> str:
    text = str(value or '').replace('\x00', '').strip()
    return text[:limit] + ('...' if len(text) > limit else '')


def _is_sensitive_key(key: Any) -> bool:
    text = str(key or '').strip().lower()
    return any(word in text for word in SENSITIVE_KEYWORDS)


def _sanitize_value(key: Any, value: Any) -> Any:
    if _is_sensitive_key(key):
        return '[REDACTED]'
    if value is None or isinstance(value, (bool, int, float)):
        return value
    if isinstance(value, str):
        return _safe_text(value, 700)
    if isinstance(value, pd.DataFrame):
        return {
            'type': 'DataFrame',
            'shape': [int(value.shape[0]), int(value.shape[1])],
            'columns': [_safe_text(column, 120) for column in list(value.columns)[:120]],
        }
    if isinstance(value, dict):
        return {str(k): _sanitize_value(k, v) for k, v in list(value.items())[:80]}
    if isinstance(value, (list, tuple, set)):
        return [_sanitize_value('', item) for item in list(value)[:80]]
    return type(value).__name__


def _audit_rows() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for event in get_audit_events()[-600:]:
        if not isinstance(event, dict):
            continue
        rows.append({
            'timestamp': event.get('timestamp'),
            'area': event.get('area'),
            'step': event.get('step'),
            'action': event.get('action'),
            'status': event.get('status'),
            'details': _sanitize_value('details', event.get('details') or {}),
        })
    return rows


def _debug_rows() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in list(st.session_state.get(LOG_SESSION_KEY, []))[-500:]:
        if not isinstance(item, dict):
            continue
        rows.append({
            'hora': item.get('hora'),
            'nivel': item.get('nivel'),
            'origem': item.get('origem'),
            'arquivo': item.get('arquivo'),
            'estado': _sanitize_value('estado', item.get('estado') or {}),
            'detalhes': _sanitize_value('detalhes', item.get('detalhes') or {}),
            'mensagem': _safe_text(item.get('mensagem'), 1000),
        })
    return rows


def _state_snapshot() -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key in IMPORTANT_STATE_KEYS:
        if key in st.session_state:
            out[key] = _sanitize_value(key, st.session_state.get(key))
    return out


def _all_state_index() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for key, value in st.session_state.items():
        if _is_sensitive_key(key):
            summary = '[REDACTED]'
        elif isinstance(value, pd.DataFrame):
            summary = f'DataFrame {value.shape[0]} x {value.shape[1]}: ' + ', '.join(map(str, list(value.columns)[:20]))
        elif isinstance(value, (list, tuple, set, dict, str)):
            try:
                size = len(value)
            except Exception:
                size = ''
            summary = f'{type(value).__name__} tamanho={size}'
        else:
            summary = type(value).__name__
        rows.append({'key': str(key), 'type': type(value).__name__, 'summary': summary})
    return sorted(rows, key=lambda row: row['key'].lower())


def _description_columns(df: pd.DataFrame) -> list[str]:
    return [str(col) for col in df.columns if any(token in str(col).lower() for token in DESCRIPTION_TOKENS)]


def _dataframe_metrics(key: str, df: pd.DataFrame) -> dict[str, Any]:
    metrics: dict[str, Any] = {
        'key': key,
        'shape': [int(df.shape[0]), int(df.shape[1])],
        'columns': [_safe_text(col, 120) for col in list(df.columns)[:120]],
        'description_columns': [],
    }
    desc_cols = _description_columns(df)
    for col in desc_cols:
        series = df[col].fillna('').astype(str)
        lengths = series.map(lambda text: len(text.strip()))
        filled = int((lengths > 0).sum())
        metrics['description_columns'].append({
            'column': col,
            'filled': filled,
            'empty': int(len(df) - filled),
            'short_under_80': int(((lengths > 0) & (lengths < 80)).sum()),
            'long_240_plus': int((lengths >= 240).sum()),
            'avg_chars': round(float(lengths.mean()) if len(lengths) else 0.0, 1),
            'sample': _safe_text(series[series.str.strip() != ''].head(1).iloc[0] if filled else '', 280),
        })
    return metrics


def _dataframes_report() -> list[dict[str, Any]]:
    report: list[dict[str, Any]] = []
    seen: set[str] = set()
    for key in SITE_DF_KEYS + tuple(str(k) for k in st.session_state.keys()):
        if key in seen:
            continue
        seen.add(key)
        value = st.session_state.get(key)
        if isinstance(value, pd.DataFrame) and not value.empty:
            report.append(_dataframe_metrics(key, value))
    return report[:40]


def build_internal_log_payload() -> dict[str, Any]:
    audit = _audit_rows()
    debug = _debug_rows()
    state = _state_snapshot()
    df_report = _dataframes_report()
    return {
        'generated_at': datetime.now().isoformat(timespec='seconds'),
        'audit_session_id': get_audit_session_id(),
        'responsible_file': RESPONSIBLE_FILE,
        'counts': {
            'audit_events': len(audit),
            'debug_logs': len(debug),
            'state_keys_total': len(st.session_state.keys()),
            'dataframes_reported': len(df_report),
        },
        'current_position': {
            'wizard_step': st.session_state.get('bling_wizard_step'),
            'operation': st.session_state.get('home_slim_flow_operation') or st.session_state.get('tipo_operacao'),
            'origin': st.session_state.get('home_slim_flow_origin') or st.session_state.get('origem_final'),
            'mapping_last_interruption_point': st.session_state.get('mapping_last_interruption_point'),
            'site_capture_error': st.session_state.get('site_capture_error'),
        },
        'top_audit_actions': Counter(row.get('action') for row in audit if row.get('action')).most_common(40),
        'top_debug_origins': Counter(row.get('origem') for row in debug if row.get('origem')).most_common(40),
        'state_snapshot': state,
        'dataframes': df_report,
        'audit_recent': audit[-200:],
        'debug_recent': debug[-200:],
        'state_index': _all_state_index(),
    }


def build_internal_log_json_bytes() -> bytes:
    return json.dumps(build_internal_log_payload(), ensure_ascii=False, indent=2, default=str).encode('utf-8-sig')


__all__ = ['build_internal_log_json_bytes', 'build_internal_log_payload']
