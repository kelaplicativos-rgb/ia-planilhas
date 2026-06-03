from __future__ import annotations

import re
from typing import Any

import pandas as pd
import streamlit as st

from bling_app_zero.core.audit import add_audit_event
from bling_app_zero.core.operation_contract import OP_CADASTRO

RESPONSIBLE_FILE = 'bling_app_zero/core/blingsmartcore_autocadastro.py'
AUTOCADASTRO_SOURCE_KEY = 'blingsmartcore_autocadastro_source_df'
AUTOCADASTRO_SIGNATURE_KEY = 'blingsmartcore_autocadastro_signature'
AUTOCADASTRO_REASON_KEY = 'blingsmartcore_autocadastro_reason'
CADASTRO_ORIGEM_KEY = 'cadastro_wizard_df_origem'
CADASTRO_ORIGEM_PRICED_KEY = 'cadastro_wizard_df_para_mapear'
WIZARD_STEP_KEY = 'bling_wizard_step'
STEP_MAPEAMENTO = 'mapeamento'


def _line_indices_from_errors(errors: list[str] | tuple[str, ...]) -> set[int]:
    indices: set[int] = set()
    for error in errors or []:
        match = re.search(r'linha\s+(\d+)', str(error or ''), flags=re.IGNORECASE)
        if not match:
            continue
        try:
            line = int(match.group(1))
            if line > 0:
                indices.add(line - 1)
        except Exception:
            pass
    return indices


def _reason_for_index(index: int, errors: list[str] | tuple[str, ...], not_found_indices: set[int]) -> tuple[str, str, str]:
    if index in not_found_indices:
        return (
            'PRODUTO_NAO_ENCONTRADO_NO_BLING',
            'Produto nao encontrado no Bling por codigo, SKU, GTIN ou ID de referencia.',
            'Cadastrar produto no Bling e depois atualizar estoque automaticamente.',
        )
    line = index + 1
    for error in errors or []:
        text = str(error or '')
        if re.search(rf'linha\s+{line}\b', text, flags=re.IGNORECASE):
            low = text.lower()
            if 'quantidade' in low or 'saldo' in low:
                return ('ESTOQUE_INVALIDO', text, 'Corrigir quantidade/saldo antes de reenviar estoque.')
            if 'deposito' in low or 'depósito' in low:
                return ('DEPOSITO_NAO_RESOLVIDO', text, 'Corrigir deposito antes de reenviar estoque.')
            return ('FALHA_API_BLING', text, 'Revisar retorno da API e tentar reenviar estoque.')
    return ('FALHA_NAO_CLASSIFICADA', 'Produto nao confirmado como enviado.', 'Revisar antes de reenviar ou cadastrar.')


def build_not_sent_dataframe(download_df: pd.DataFrame, result_payload: dict[str, Any]) -> pd.DataFrame:
    if not isinstance(download_df, pd.DataFrame) or download_df.empty:
        return pd.DataFrame()

    errors = list(result_payload.get('errors') or [])
    not_found_indices = {int(item) for item in list(result_payload.get('not_found_indices') or []) if str(item).lstrip('-').isdigit()}
    error_indices = _line_indices_from_errors(errors)
    candidate_indices = sorted(index for index in (not_found_indices | error_indices) if 0 <= index < len(download_df))

    if not candidate_indices and (int(result_payload.get('failed') or 0) > 0 or int(result_payload.get('skipped') or 0) > 0):
        candidate_indices = list(range(len(download_df)))

    if not candidate_indices:
        return pd.DataFrame()

    out = download_df.iloc[candidate_indices].copy().fillna('')
    statuses: list[str] = []
    reasons: list[str] = []
    actions: list[str] = []
    eligible: list[str] = []

    for index in candidate_indices:
        status, reason, action = _reason_for_index(index, errors, not_found_indices)
        statuses.append(status)
        reasons.append(reason)
        actions.append(action)
        eligible.append('SIM' if status == 'PRODUTO_NAO_ENCONTRADO_NO_BLING' else 'NAO')

    out.insert(0, 'autocadastro_elegivel', eligible)
    out.insert(1, 'status_envio_bling', statuses)
    out.insert(2, 'motivo_bling', reasons)
    out.insert(3, 'acao_recomendada', actions)
    return out


def build_stock_pending_dataframe(download_df: pd.DataFrame, result_payload: dict[str, Any]) -> pd.DataFrame:
    df_pending = build_not_sent_dataframe(download_df, result_payload)
    if df_pending.empty:
        return df_pending

    fixed = df_pending.copy().fillna('')
    fixed['autocadastro_elegivel'] = 'NAO'
    if 'status_envio_bling' in fixed.columns and 'acao_recomendada' in fixed.columns:
        mask = fixed['status_envio_bling'].astype(str).eq('PRODUTO_NAO_ENCONTRADO_NO_BLING')
        fixed.loc[mask, 'acao_recomendada'] = 'Produto nao localizado no Bling. Corrigir codigo/SKU/GTIN/ID ou cadastrar manualmente com dados completos antes de reenviar estoque.'
    return fixed


def _force_autocadastro_navigation() -> None:
    st.session_state[WIZARD_STEP_KEY] = STEP_MAPEAMENTO
    st.session_state['home_active_operation_v2'] = 'wizard_cadastro_estoque'
    st.session_state['home_single_page_flow_active'] = True
    st.session_state['home_wizard_scroll_target_step'] = STEP_MAPEAMENTO
    st.session_state['cadastro_mapping_confirmed'] = False
    st.session_state.pop('df_final_download_operation', None)
    st.session_state.pop('final_download_operation', None)
    st.session_state.pop('df_final_preview_operation', None)
    try:
        st.query_params['operation_v2'] = 'wizard_cadastro_estoque'
        st.query_params['step'] = STEP_MAPEAMENTO
        st.query_params['operation'] = OP_CADASTRO
    except Exception:
        pass


def save_autocadastro_source(df: pd.DataFrame, *, reason: str = 'produtos_nao_enviados') -> None:
    if not isinstance(df, pd.DataFrame) or df.empty:
        return
    fixed = df.copy().fillna('')
    eligible = fixed[fixed.get('autocadastro_elegivel', '') == 'SIM'].copy() if 'autocadastro_elegivel' in fixed.columns else fixed
    if eligible.empty:
        eligible = fixed
    st.session_state[AUTOCADASTRO_SOURCE_KEY] = eligible
    st.session_state[AUTOCADASTRO_REASON_KEY] = reason
    st.session_state[CADASTRO_ORIGEM_KEY] = eligible
    st.session_state[CADASTRO_ORIGEM_PRICED_KEY] = eligible
    st.session_state['home_slim_flow_operation'] = OP_CADASTRO
    st.session_state['operacao_final'] = OP_CADASTRO
    st.session_state['tipo_operacao_final'] = OP_CADASTRO
    st.session_state['home_detected_operation'] = OP_CADASTRO
    st.session_state['df_origem_cadastro_precificada'] = eligible
    _force_autocadastro_navigation()
    add_audit_event(
        'blingsmartcore_autocadastro_source_saved',
        area='AUTOCADASTRO',
        status='OK',
        details={'rows': len(eligible), 'reason': reason, 'target_step': STEP_MAPEAMENTO, 'responsible_file': RESPONSIBLE_FILE},
    )


def render_stock_pending_panel(download_df: pd.DataFrame, result_payload: dict[str, Any], *, key: str) -> None:
    df_pending = build_stock_pending_dataframe(download_df, result_payload)
    if df_pending.empty:
        return

    csv_bytes = df_pending.to_csv(index=False, sep=';', encoding='utf-8-sig').encode('utf-8-sig')
    st.markdown('### Pendencias da atualizacao de estoque')
    st.warning(
        f'{len(df_pending)} produto(s) nao foram atualizados porque nao foram confirmados no Bling. Neste fluxo, eles ficam como pendencia; o sistema nao oferece AutoCadastro por falta de dados completos de produto.'
    )
    st.download_button(
        'Baixar relatorio de pendencias de estoque',
        data=csv_bytes,
        file_name='pendencias_estoque_bling.csv',
        mime='text/csv; charset=utf-8',
        use_container_width=True,
        key=f'estoque_download_pendencias_{key}_{len(df_pending)}',
    )
    st.dataframe(df_pending.head(100), use_container_width=True)
    add_audit_event(
        'blingsmartcore_stock_pending_panel_rendered',
        area='ESTOQUE',
        status='AVISO',
        details={'rows': len(df_pending), 'responsible_file': RESPONSIBLE_FILE},
    )


def render_autocadastro_panel(download_df: pd.DataFrame, result_payload: dict[str, Any], *, key: str) -> None:
    df_not_sent = build_not_sent_dataframe(download_df, result_payload)
    if df_not_sent.empty:
        return

    eligible_count = int((df_not_sent.get('autocadastro_elegivel', '') == 'SIM').sum()) if 'autocadastro_elegivel' in df_not_sent.columns else 0
    csv_bytes = df_not_sent.to_csv(index=False, sep=';', encoding='utf-8-sig').encode('utf-8-sig')

    st.markdown('### BLINGSMARTCORE AutoCadastro')
    st.warning(f'{len(df_not_sent)} produto(s) nao foram confirmados no envio. {eligible_count} elegivel(is) para cadastro automatico por produto nao encontrado.')
    st.download_button(
        'Baixar planilha dos produtos nao enviados',
        data=csv_bytes,
        file_name='produtos_nao_enviados_bling_autocadastro.csv',
        mime='text/csv; charset=utf-8',
        use_container_width=True,
        key=f'autocadastro_download_not_sent_{key}_{len(df_not_sent)}',
    )
    st.dataframe(df_not_sent.head(100), use_container_width=True)

    if eligible_count > 0:
        if st.button('Usar produtos nao encontrados como origem de cadastro', use_container_width=True, key=f'autocadastro_use_as_origin_{key}_{eligible_count}'):
            save_autocadastro_source(df_not_sent, reason='produto_nao_encontrado_no_bling')
            st.success('Produtos nao encontrados foram preparados como origem de cadastro. Abrindo mapeamento...')
            st.rerun()


__all__ = [
    'build_not_sent_dataframe',
    'build_stock_pending_dataframe',
    'render_autocadastro_panel',
    'render_stock_pending_panel',
    'save_autocadastro_source',
]
