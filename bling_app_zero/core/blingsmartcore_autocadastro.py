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


def _safe_int(value: object, default: int = 0) -> int:
    try:
        return int(value or 0)
    except Exception:
        return int(default or 0)


def _line_indices_from_errors(errors: list[str] | tuple[str, ...]) -> set[int]:
    indices: set[int] = set()
    for error in errors or []:
        text = str(error or '')
        matches = re.findall(r'linha\s+(\d+)', text, flags=re.IGNORECASE)
        for raw_line in matches:
            try:
                line = int(raw_line)
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
            if 'pendência inteligente' in low or 'pendencia inteligente' in low or 'antes da api' in low:
                return ('IGNORADO_PRE_API', text, 'Revisar qualidade/identidade do produto antes de reenviar ao Bling.')
            return ('FALHA_API_BLING', text, 'Revisar retorno da API e tentar reenviar estoque.')
    return ('FALHA_NAO_CLASSIFICADA', 'Produto nao confirmado como enviado.', 'Revisar antes de reenviar ou cadastrar.')


def _candidate_indices_from_payload(download_df: pd.DataFrame, result_payload: dict[str, Any]) -> list[int]:
    errors = list(result_payload.get('errors') or [])
    not_found_indices = {int(item) for item in list(result_payload.get('not_found_indices') or []) if str(item).lstrip('-').isdigit()}
    error_indices = _line_indices_from_errors(errors)
    candidate_indices = sorted(index for index in (not_found_indices | error_indices) if 0 <= index < len(download_df))
    if candidate_indices:
        return candidate_indices

    attempted = _safe_int(result_payload.get('attempted'))
    sent = _safe_int(result_payload.get('sent'))
    failed = _safe_int(result_payload.get('failed'))
    skipped = _safe_int(result_payload.get('skipped'))

    if sent > 0:
        return []
    if attempted > 0 and sent == 0 and (failed > 0 or skipped > 0):
        limit = min(len(download_df), attempted)
        return list(range(limit))
    return []


def build_not_sent_dataframe(download_df: pd.DataFrame, result_payload: dict[str, Any]) -> pd.DataFrame:
    if not isinstance(download_df, pd.DataFrame) or download_df.empty:
        return pd.DataFrame()

    errors = list(result_payload.get('errors') or [])
    not_found_indices = {int(item) for item in list(result_payload.get('not_found_indices') or []) if str(item).lstrip('-').isdigit()}
    candidate_indices = _candidate_indices_from_payload(download_df, result_payload)

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


def _unclassified_partial_count(result_payload: dict[str, Any]) -> int:
    sent = _safe_int(result_payload.get('sent'))
    failed = _safe_int(result_payload.get('failed'))
    skipped = _safe_int(result_payload.get('skipped'))
    if sent <= 0:
        return 0
    return max(0, failed + skipped)


def _render_unclassified_partial_notice(result_payload: dict[str, Any], *, operation_label: str) -> None:
    count = _unclassified_partial_count(result_payload)
    if count <= 0:
        return
    st.warning(
        f'{count} item(ns) ficaram sem indice individual no retorno do envio de {operation_label}. '
        'Por segurança, o BLINGFIX nao vai gerar uma planilha falsa com todos os produtos como nao confirmados. '
        'Quando o sender informar a linha exata, apenas essas linhas entram no relatorio.'
    )
    add_audit_event(
        'blingsmartcore_partial_without_line_indices',
        area='AUTOCADASTRO',
        status='CORRIGIDO',
        details={'count': count, 'operation_label': operation_label, 'responsible_file': RESPONSIBLE_FILE},
    )


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
        _render_unclassified_partial_notice(result_payload, operation_label='estoque')
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
    """Renderiza AutoCadastro usando o motor novo via API.

    BLINGFIX: este wrapper mantém compatibilidade com o import antigo usado no
    painel principal, mas remove o fluxo contraditório que mandava o usuário de
    volta para o mapeamento. Agora produtos elegíveis são cadastrados direto no
    Bling e, quando houver quantidade/depósito, o estoque é atualizado em seguida.
    """
    try:
        from bling_app_zero.core.blingsmartcore_autocadastro_api_panel import render_autocadastro_panel as render_api_autocadastro_panel

        render_api_autocadastro_panel(download_df, result_payload, key=key)
        add_audit_event(
            'blingsmartcore_autocadastro_delegated_to_api_panel',
            area='AUTOCADASTRO',
            status='OK',
            details={'responsible_file': RESPONSIBLE_FILE, 'api_panel': 'bling_app_zero/core/blingsmartcore_autocadastro_api_panel.py'},
        )
        return
    except Exception as exc:
        add_audit_event(
            'blingsmartcore_autocadastro_api_panel_fallback',
            area='AUTOCADASTRO',
            status='AVISO',
            details={'error': str(exc)[:240], 'responsible_file': RESPONSIBLE_FILE},
        )

    df_not_sent = build_not_sent_dataframe(download_df, result_payload)
    if df_not_sent.empty:
        _render_unclassified_partial_notice(result_payload, operation_label='cadastro')
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
    st.error('AutoCadastro via API nao carregou. Corrija o erro acima antes de reenviar ao Bling.')


__all__ = [
    'build_not_sent_dataframe',
    'build_stock_pending_dataframe',
    'render_autocadastro_panel',
    'render_stock_pending_panel',
    'save_autocadastro_source',
]
