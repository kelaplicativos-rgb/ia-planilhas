from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st

from bling_app_zero.core.audit import add_audit_event
from bling_app_zero.core.bling_token_store import get_user_session_id
from bling_app_zero.core.operation_contract import normalize_operation

RESPONSIBLE_FILE = 'bling_app_zero/core/oauth_return_snapshot.py'
SNAPSHOT_DIR = Path('bling_oauth_flow_snapshots')
OAUTH_RETURN_CONTEXT_KEY = 'bling_oauth_return_context'


def _safe_id(value: object) -> str:
    text = str(value or '').strip()
    return ''.join(ch for ch in text if ch.isalnum() or ch in {'-', '_'})[:80]


def _snapshot_paths(session_id: str) -> tuple[Path, Path]:
    safe = _safe_id(session_id) or get_user_session_id()
    SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
    return SNAPSHOT_DIR / f'{safe}.csv', SNAPSHOT_DIR / f'{safe}.json'


def prepare_download_oauth_return(df: pd.DataFrame, operation: str, *, signature: str = '') -> dict[str, Any]:
    session_id = get_user_session_id()
    operation = normalize_operation(operation)
    csv_path, meta_path = _snapshot_paths(session_id)

    if isinstance(df, pd.DataFrame) and not df.empty:
        df.copy().fillna('').to_csv(csv_path, sep=';', index=False, encoding='utf-8-sig')

    context = {
        'return_to': 'download',
        'flow': 'wizard_cadastro_estoque',
        'step': 'download',
        'operation': operation,
        'signature': signature,
        'session_id': session_id,
        'columns': [str(column) for column in df.columns] if isinstance(df, pd.DataFrame) else [],
        'rows': int(len(df)) if isinstance(df, pd.DataFrame) else 0,
    }
    meta_path.write_text(json.dumps(context, ensure_ascii=False, indent=2), encoding='utf-8')
    st.session_state[OAUTH_RETURN_CONTEXT_KEY] = dict(context)
    add_audit_event(
        'oauth_download_return_snapshot_saved',
        area='BLING_OAUTH',
        status='OK',
        details={'operation': operation, 'rows': context['rows'], 'responsible_file': RESPONSIBLE_FILE},
    )
    return context


def _set_model_keys(df: pd.DataFrame, operation: str) -> None:
    model = pd.DataFrame(columns=[str(column) for column in df.columns])
    st.session_state['home_modelo_universal_df'] = model.copy()
    st.session_state['df_modelo_universal'] = model.copy()
    st.session_state['modelo_universal_df'] = model.copy()
    st.session_state['cadastro_wizard_df_modelo'] = model.copy()

    if operation == 'cadastro':
        st.session_state['home_modelo_cadastro_df'] = model.copy()
        st.session_state['df_modelo_cadastro'] = model.copy()
        st.session_state['modelo_cadastro_df'] = model.copy()
    elif operation == 'estoque':
        st.session_state['home_modelo_estoque_df'] = model.copy()
        st.session_state['df_modelo_estoque'] = model.copy()
        st.session_state['modelo_estoque_df'] = model.copy()
        st.session_state['cadastro_wizard_df_modelo_estoque'] = model.copy()
    elif operation == 'atualizacao_preco':
        st.session_state['home_modelo_atualizacao_preco_df'] = model.copy()
        st.session_state['df_modelo_atualizacao_preco'] = model.copy()
        st.session_state['modelo_atualizacao_preco_df'] = model.copy()


def restore_download_oauth_return(session_id: str | None = None) -> bool:
    session_id = session_id or get_user_session_id()
    csv_path, meta_path = _snapshot_paths(session_id)
    if not csv_path.exists():
        return False

    try:
        df = pd.read_csv(csv_path, sep=';', dtype=str).fillna('')
    except Exception:
        try:
            df = pd.read_csv(csv_path, sep=None, engine='python', dtype=str).fillna('')
        except Exception as exc:
            add_audit_event(
                'oauth_download_return_snapshot_restore_error',
                area='BLING_OAUTH',
                status='ERRO',
                details={'error': str(exc), 'responsible_file': RESPONSIBLE_FILE},
            )
            return False

    try:
        meta = json.loads(meta_path.read_text(encoding='utf-8')) if meta_path.exists() else {}
    except Exception:
        meta = {}

    operation = normalize_operation(meta.get('operation') or st.session_state.get('final_download_operation') or 'universal')
    st.session_state['df_final_universal'] = df.copy()
    st.session_state['df_final_cadastro'] = df.copy()
    st.session_state['final_download_df_snapshot'] = df.copy()
    st.session_state['final_download_operation'] = operation
    st.session_state['df_final_download_operation'] = operation
    st.session_state['home_active_operation_v2'] = 'wizard_cadastro_estoque'
    st.session_state['home_allow_operation_v2_session'] = True
    st.session_state['home_single_page_flow_active'] = True
    st.session_state['bling_wizard_step'] = 'download'
    st.session_state['home_slim_flow_operation'] = operation
    st.session_state['home_detected_operation'] = operation
    st.session_state['operacao_final'] = operation
    st.session_state['tipo_operacao_final'] = operation
    _set_model_keys(df, operation)

    add_audit_event(
        'oauth_download_return_snapshot_restored',
        area='BLING_OAUTH',
        status='OK',
        details={'operation': operation, 'rows': len(df), 'responsible_file': RESPONSIBLE_FILE},
    )
    return True


__all__ = ['OAUTH_RETURN_CONTEXT_KEY', 'prepare_download_oauth_return', 'restore_download_oauth_return']
