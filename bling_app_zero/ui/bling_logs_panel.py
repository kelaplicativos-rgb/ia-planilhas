from __future__ import annotations

from collections import Counter
from datetime import datetime
from typing import Any

import pandas as pd
import streamlit as st

from bling_app_zero.core.audit import get_audit_events, get_audit_session_id
from bling_app_zero.core.debug import LOG_SESSION_KEY

RESPONSIBLE_FILE = 'bling_app_zero/ui/bling_logs_panel.py'
SITE_DATA_KEYS = ('df_site_bruto_cadastro', 'df_site_bruto', 'df_origem_site', 'df_origem', 'df_final_cadastro')


def _preview(value: Any, limit: int = 220) -> str:
    text = str(value or '').replace('\x00', '').strip()
    return text[:limit] + ('...' if len(text) > limit else '')


def _audit_rows() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for event in get_audit_events()[-200:]:
        if isinstance(event, dict):
            rows.append({
                'timestamp': event.get('timestamp'),
                'area': event.get('area'),
                'step': event.get('step'),
                'action': event.get('action'),
                'status': event.get('status'),
            })
    return rows


def _debug_rows() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in list(st.session_state.get(LOG_SESSION_KEY, []))[-200:]:
        if isinstance(item, dict):
            rows.append({
                'hora': item.get('hora'),
                'nivel': item.get('nivel'),
                'origem': item.get('origem'),
                'mensagem': _preview(item.get('mensagem'), 700),
            })
    return rows


def _state_rows() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for key, value in st.session_state.items():
        text_key = str(key)
        if isinstance(value, pd.DataFrame):
            resumo = f'{value.shape[0]} x {value.shape[1]} · ' + ', '.join(map(str, list(value.columns)[:12]))
        else:
            resumo = type(value).__name__
        rows.append({'chave': text_key, 'tipo': type(value).__name__, 'resumo': resumo})
    return sorted(rows, key=lambda item: item['chave'].lower())


def _find_site_df() -> tuple[str, pd.DataFrame | None]:
    for key in SITE_DATA_KEYS:
        value = st.session_state.get(key)
        if isinstance(value, pd.DataFrame) and not value.empty:
            return key, value
    return '', None


def _description_columns(df: pd.DataFrame) -> list[str]:
    tokens = ('descr', 'caracter', 'ficha', 'detalh')
    return [str(column) for column in df.columns if any(token in str(column).lower() for token in tokens)]


def diagnose_site_descriptions() -> dict[str, Any]:
    key, df = _find_site_df()
    if not isinstance(df, pd.DataFrame) or df.empty:
        return {'status': 'SEM_DADOS_SITE_NA_SESSAO', 'mensagem': 'Nenhuma origem por site encontrada nesta sessão.'}

    columns = _description_columns(df)
    result: dict[str, Any] = {
        'status': 'OK',
        'state_key': key,
        'linhas': int(len(df)),
        'colunas': int(len(df.columns)),
        'colunas_descricao': columns,
        'metricas': [],
        'alertas': [],
    }
    if not columns:
        result['status'] = 'SEM_COLUNA_DESCRICAO'
        result['alertas'].append('A origem por site não possui coluna relacionada a descrição.')
        return result

    for column in columns:
        series = df[column].fillna('').astype(str)
        lengths = series.map(lambda text: len(text.strip()))
        result['metricas'].append({
            'coluna': column,
            'preenchidos': int((lengths > 0).sum()),
            'vazios': int((lengths <= 0).sum()),
            'curtos_menor_80': int(((lengths > 0) & (lengths < 80)).sum()),
            'longos_240_mais': int((lengths >= 240).sum()),
            'media_caracteres': round(float(lengths.mean()) if len(lengths) else 0.0, 1),
        })

    if all(item['longos_240_mais'] == 0 for item in result['metricas']):
        result['alertas'].append('Nenhuma descrição longa detectada; a captura pode estar pegando apenas título/nome.')
    if any(item['vazios'] > 0 for item in result['metricas']):
        result['alertas'].append('Há produtos com descrição vazia.')
    return result


def build_blinglogs_payload() -> dict[str, Any]:
    audit = _audit_rows()
    debug = _debug_rows()
    state = _state_rows()
    return {
        'generated_at': datetime.now().isoformat(timespec='seconds'),
        'audit_session_id': get_audit_session_id(),
        'responsible_file': RESPONSIBLE_FILE,
        'counts': {'audit': len(audit), 'debug': len(debug), 'state_keys': len(state)},
        'top_audit_actions': Counter(row['action'] for row in audit if row.get('action')).most_common(20),
        'top_debug_origins': Counter(row['origem'] for row in debug if row.get('origem')).most_common(20),
        'site_description_diagnosis': diagnose_site_descriptions(),
    }


__all__ = ['build_blinglogs_payload', 'diagnose_site_descriptions']
