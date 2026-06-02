from __future__ import annotations

import pandas as pd
import streamlit as st

from bling_app_zero.agents.blingsmartcore import apply_blingsmartcore
from bling_app_zero.core.exporter import sanitize_for_bling
from bling_app_zero.ui.cadastro_wizard_state import (
    enforce_cadastro_model_columns,
    get_context_final_df,
    render_row_count_blocker,
    set_context_final_df,
    valid_df,
)
from bling_app_zero.ui.home_download import _render_api_final
from bling_app_zero.ui.home_shared import download_final, df_signature
from bling_app_zero.universal.model_contract_detector import MODEL_CONTRACT_TYPE_KEY, normalize_contract_operation

RESPONSIBLE_FILE = 'bling_app_zero/ui/cadastro_download_step.py'
VALID_OPERATIONS = {'cadastro', 'estoque', 'universal', 'atualizacao_preco'}
LEGACY_OPERATION_ALIASES = {'modelo', 'modelo_destino', 'planilha', 'wizard_cadastro_estoque'}
HOME_ENTRY_CONTEXT_KEY = 'home_entry_context'
CONTEXT_BLING_API = 'bling_api'
CONTEXT_BLING_CSV = 'bling_csv'
CONTEXT_UNIVERSAL = 'universal'
PREVIEW_SAFE_KEY = 'df_final_cadastro_preview_rules_applied'
PREVIEW_OPERATION_KEY = 'df_final_preview_operation'
PREVIEW_SIGNATURE_KEY = 'df_final_preview_signature'
DOWNLOAD_SIGNATURE_KEY = 'df_final_download_signature'
SMARTCORE_DOWNLOAD_KEY = 'blingsmartcore_download_report'


def _entry_context() -> str:
    value = str(st.session_state.get(HOME_ENTRY_CONTEXT_KEY) or '').strip().lower()
    if value in {CONTEXT_BLING_API, CONTEXT_BLING_CSV, CONTEXT_UNIVERSAL}:
        return value
    return CONTEXT_UNIVERSAL


def _is_api_context() -> bool:
    return _entry_context() == CONTEXT_BLING_API


def _title() -> str:
    if _is_api_context():
        return 'Enviar para o Bling'
    return 'Download'


def _caption() -> str:
    if _is_api_context():
        return 'Envie exatamente o resultado revisado na prévia final para o Bling conectado. Este caminho não baixa planilha como etapa principal.'
    return 'Baixe exatamente o mesmo arquivo conferido na prévia final.'


def _normalize_operation(value: object) -> str:
    operation = normalize_contract_operation(value)
    if operation:
        return operation
    text = str(value or '').strip().lower()
    if text in LEGACY_OPERATION_ALIASES:
        return 'universal'
    return ''


def _current_operation() -> str:
    """Resolve a operação real antes de gerar a saída final."""
    for key in (
        PREVIEW_OPERATION_KEY,
        MODEL_CONTRACT_TYPE_KEY,
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


def _safe_operation(operation: str) -> str:
    return operation if operation in VALID_OPERATIONS else 'universal'


def _store_smartcore_download_report(result) -> None:
    try:
        st.session_state[SMARTCORE_DOWNLOAD_KEY] = {
            'origin': result.origin,
            'operation': result.operation,
            'score': int(result.quality.score),
            'rows': int(result.quality.rows),
            'warnings': list(result.quality.warnings),
        }
    except Exception:
        st.session_state[SMARTCORE_DOWNLOAD_KEY] = {}


def _render_smartcore_download_report() -> None:
    report = st.session_state.get(SMARTCORE_DOWNLOAD_KEY) or {}
    if not report:
        return
    with st.expander('BLINGSMARTCORE · validação antes da saída final', expanded=False):
        st.caption(f"Origem: {report.get('origin', '')} · Operação: {report.get('operation', '')} · Linhas: {report.get('rows', 0)}")
        st.metric('Qualidade da saída', f"{report.get('score', 0)}/100")
        for warning in list(report.get('warnings') or [])[:8]:
            st.warning(str(warning))


def _preview_safe_df(operation: str) -> pd.DataFrame | None:
    df_preview = st.session_state.get(PREVIEW_SAFE_KEY)
    if valid_df(df_preview):
        safe, report = apply_blingsmartcore(df_preview.copy().fillna(''), origin='preview_final', operation=_safe_operation(operation))
        _store_smartcore_download_report(report)
        return safe
    return None


def _build_safe_download_df(operation: str) -> pd.DataFrame | None:
    df_final = get_context_final_df()
    if not valid_df(df_final):
        return None
    safe = sanitize_for_bling(df_final.copy().fillna(''), operation=_safe_operation(operation))
    safe, report = apply_blingsmartcore(safe, origin='preview_final', operation=_safe_operation(operation))
    _store_smartcore_download_report(report)
    if not _is_api_context():
        safe = enforce_cadastro_model_columns(safe)
    return safe.copy().fillna('') if valid_df(safe) else None


def _final_df_for_context(operation: str) -> pd.DataFrame | None:
    preview_df = _preview_safe_df(operation)
    if preview_df is not None:
        return preview_df
    return _build_safe_download_df(operation)


def _store_output_consistency(df_final: pd.DataFrame, operation: str) -> None:
    signature = df_signature(df_final)
    st.session_state['df_final_download_operation'] = operation
    st.session_state[DOWNLOAD_SIGNATURE_KEY] = signature
    st.session_state[PREVIEW_SAFE_KEY] = df_final.copy()
    st.session_state[PREVIEW_SIGNATURE_KEY] = signature
    set_context_final_df(df_final)


def _render_optional_csv_backup(df_final: pd.DataFrame, operation: str) -> None:
    with st.expander('Opcional · baixar cópia de segurança em CSV', expanded=False):
        st.caption('Use apenas para auditoria local. A ação principal deste caminho é enviar pela API do Bling.')
        download_final(df_final, operation, f'backup_{_entry_context()}_{operation}')


def render_cadastro_download_step() -> None:
    operation = _current_operation()
    st.markdown(f'### {_title()}')
    st.caption(_caption())

    df_final = _final_df_for_context(operation)
    if not valid_df(df_final):
        st.warning('O resultado final ainda não foi gerado. Volte para a prévia final.')
        return

    if not _is_api_context() and render_row_count_blocker(df_final):
        return

    _store_output_consistency(df_final, operation)
    _render_smartcore_download_report()

    if _is_api_context():
        st.success('Base revisada pronta para envio direto ao Bling.')
        _render_api_final(df_final, operation, f'{_entry_context()}_{operation}')
        _render_optional_csv_backup(df_final, operation)
        return

    st.success('Download usando a mesma base blindada da prévia final.')
    download_final(df_final, operation, f'{_entry_context()}_{operation}')


__all__ = ['render_cadastro_download_step']
