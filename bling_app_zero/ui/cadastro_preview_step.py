from __future__ import annotations

import pandas as pd
import streamlit as st

from bling_app_zero.agents.blingsmartcore import apply_blingsmartcore
from bling_app_zero.core.exporter import sanitize_for_bling
from bling_app_zero.ui.cadastro_wizard_state import (
    enforce_cadastro_model_columns,
    get_universal_final_df,
    render_row_count_blocker,
    set_universal_final_df,
    valid_df,
)
from bling_app_zero.ui.flow_guard import render_flow_blocker
from bling_app_zero.ui.home_shared import preview_df
from bling_app_zero.universal.model_contract_detector import MODEL_CONTRACT_TYPE_KEY, normalize_contract_operation

RESPONSIBLE_FILE = 'bling_app_zero/ui/cadastro_preview_step.py'
VALID_OPERATIONS = {'cadastro', 'estoque', 'universal', 'atualizacao_preco'}
LEGACY_OPERATION_ALIASES = {'modelo', 'modelo_destino', 'planilha', 'wizard_cadastro_estoque'}
HOME_ENTRY_CONTEXT_KEY = 'home_entry_context'
CONTEXT_BLING_API = 'bling_api'
CONTEXT_BLING_CSV = 'bling_csv'
CONTEXT_UNIVERSAL = 'universal'
CONTEXT_FINAL_KEYS = {
    CONTEXT_BLING_API: 'df_final_bling_api',
    CONTEXT_BLING_CSV: 'df_final_bling_csv',
    CONTEXT_UNIVERSAL: 'df_final_universal',
}
SMARTCORE_PREVIEW_KEY = 'blingsmartcore_preview_report'


def _entry_context() -> str:
    value = str(st.session_state.get(HOME_ENTRY_CONTEXT_KEY) or '').strip().lower()
    if value in CONTEXT_FINAL_KEYS:
        return value
    return CONTEXT_UNIVERSAL


def _context_final_key() -> str:
    return CONTEXT_FINAL_KEYS.get(_entry_context(), 'df_final_universal')


def _context_title() -> str:
    context = _entry_context()
    if context == CONTEXT_BLING_API:
        return 'Prévia final do envio direto ao Bling'
    if context == CONTEXT_BLING_CSV:
        return 'Prévia final do CSV Bling'
    return 'Prévia final'


def _context_caption() -> str:
    context = _entry_context()
    if context == CONTEXT_BLING_API:
        return 'Confira os dados que serão enviados pela API. O envio usará exatamente esta base revisada.'
    if context == CONTEXT_BLING_CSV:
        return 'Confira se o arquivo final segue o modelo Bling anexado no início.'
    return 'Confira se o arquivo final segue o modelo de destino anexado no início.'


def _normalize_operation(value: object) -> str:
    operation = normalize_contract_operation(value)
    if operation:
        return operation
    text = str(value or '').strip().lower()
    if text in LEGACY_OPERATION_ALIASES:
        return 'universal'
    return ''


def _current_operation() -> str:
    """Resolve a operação real do contrato antes de aplicar regras da prévia final."""
    for key in (
        MODEL_CONTRACT_TYPE_KEY,
        'df_final_preview_operation',
        'df_final_download_operation',
        'final_download_operation',
        'home_slim_flow_operation',
        'home_detected_operation',
        'operacao_final',
        'tipo_operacao_final',
        'tipo_operacao_site',
    ):
        operation = _normalize_operation(st.session_state.get(key))
        if operation:
            return operation

    for key in ('operacao', 'operation', 'operation_v2'):
        try:
            operation = _normalize_operation(st.query_params.get(key, ''))
            if operation:
                return operation
        except Exception:
            pass

    return 'universal'


def _context_final_df() -> pd.DataFrame | None:
    context_key = _context_final_key()
    df = st.session_state.get(context_key)
    if valid_df(df):
        return df.copy().fillna('')
    legacy = get_universal_final_df()
    return legacy.copy().fillna('') if valid_df(legacy) else None


def _store_context_preview(df_preview: pd.DataFrame, operation: str) -> None:
    context_key = _context_final_key()
    st.session_state[context_key] = df_preview.copy()
    set_universal_final_df(df_preview)
    st.session_state['df_final_cadastro_preview_rules_applied'] = df_preview
    st.session_state['df_final_preview_operation'] = operation


def _store_smartcore_report(result) -> None:
    try:
        st.session_state[SMARTCORE_PREVIEW_KEY] = {
            'origin': result.origin,
            'operation': result.operation,
            'score': int(result.quality.score),
            'rows': int(result.quality.rows),
            'warnings': list(result.quality.warnings),
        }
    except Exception:
        st.session_state[SMARTCORE_PREVIEW_KEY] = {}


def _render_smartcore_report() -> None:
    report = st.session_state.get(SMARTCORE_PREVIEW_KEY) or {}
    if not report:
        return
    with st.expander('BLINGSMARTCORE · validação inteligente da prévia', expanded=False):
        st.caption(f"Origem: {report.get('origin', '')} · Operação: {report.get('operation', '')} · Linhas: {report.get('rows', 0)}")
        st.metric('Qualidade da prévia', f"{report.get('score', 0)}/100")
        for warning in list(report.get('warnings') or [])[:8]:
            st.warning(str(warning))


def _final_preview_df(df_final: pd.DataFrame, operation: str) -> pd.DataFrame:
    """Aplica na prévia final a blindagem correta para cada caminho."""
    safe_operation = operation if operation in VALID_OPERATIONS else 'universal'
    safe = sanitize_for_bling(df_final.copy().fillna(''), operation=safe_operation)
    safe, smartcore_result = apply_blingsmartcore(safe, origin='preview_final', operation=safe_operation)
    _store_smartcore_report(smartcore_result)
    if _entry_context() == CONTEXT_BLING_API:
        return safe
    fixed = enforce_cadastro_model_columns(safe)
    return fixed if isinstance(fixed, pd.DataFrame) else safe


def render_cadastro_preview_step() -> None:
    operation = _current_operation()
    st.markdown(f'### {_context_title()}')
    st.caption(_context_caption())

    df_final = _context_final_df()

    if not valid_df(df_final):
        render_flow_blocker(
            'A prévia final ainda não foi gerada. Volte para o mapeamento e confirme os campos obrigatórios antes de continuar.',
            title='Prévia final bloqueada',
            action_label='Continuar',
        )
        return

    df_preview = _final_preview_df(df_final, operation)
    _store_context_preview(df_preview, operation)

    if _entry_context() != CONTEXT_BLING_API and render_row_count_blocker(df_preview):
        return

    _render_smartcore_report()
    preview_df('Resultado final preenchido', df_preview)


__all__ = ['render_cadastro_preview_step']
