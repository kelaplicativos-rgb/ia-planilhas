from __future__ import annotations

from io import BytesIO

import pandas as pd
import streamlit as st

from bling_app_zero.core.bling_connected_flow_policy import (
    OP_CADASTRO,
    OP_ESTOQUE,
    OP_PRECO,
    activate_connected_flow,
    annotate_dataframe_for_connected_flow,
    api_flow_explicitly_selected,
)
from bling_app_zero.core.files import read_uploaded_file
from bling_app_zero.core.flow_spine_output import output_diagnostics, output_is_api, output_operation, output_plan
from bling_app_zero.ui.cadastro_wizard_state import (
    CADASTRO_MAPPING_CONFIRMED_KEY,
    CADASTRO_MAPPING_SIGNATURE_KEY,
    CADASTRO_MODELO_KEY,
    CADASTRO_ORIGEM_KEY,
    CADASTRO_ORIGEM_PRICED_KEY,
    LEGACY_CADASTRO_FINAL_KEY,
    UNIVERSAL_FINAL_KEY,
    cadastro_mapping_ready,
    ensure_api_direct_final_df,
    render_row_count_blocker,
    store_expected_source_rows,
    valid_df,
    valid_model,
)
from bling_app_zero.ui.home_shared import df_signature
from bling_app_zero.ui.shared_mapping import render_shared_cadastro_mapping

RESPONSIBLE_FILE = 'bling_app_zero/ui/cadastro_mapping_step.py'
HOME_ENTRY_CONTEXT_KEY = 'home_entry_context'
CONTEXT_BLING_API = 'bling_api'
MODEL_BYTES_KEY = 'destination_model_upload_bytes'
MODEL_NAME_KEY = 'destination_model_upload_name'
API_OPERATION_CHOICE_KEY = 'home_bling_api_operation_choice'
API_OPERATION_OPTIONS = {
    'Cadastrar produtos no Bling': OP_CADASTRO,
    'Atualizar preços multilojas/canais': OP_PRECO,
    'Atualizar estoque por depósito': OP_ESTOQUE,
}
API_OPERATION_HELP = {
    OP_CADASTRO: 'Cadastro cria ou atualiza produtos. Não exige loja/canal nem depósito.',
    OP_PRECO: 'Preços multilojas exigem escolher Preço geral ou loja/canal de venda antes do envio.',
    OP_ESTOQUE: 'Estoque exige escolher o depósito do Bling antes de atualizar o saldo.',
}
API_OPERATION_SESSION_KEYS = (
    API_OPERATION_CHOICE_KEY,
    'bling_connected_api_operation',
    'flow_spine_sender_operation',
    'flow_spine_operation_resolved_for_api',
    'direct_bling_operation_applied',
    'api_operation',
    'bling_api_operation',
)

MODEL_FALLBACK_KEYS = (
    CADASTRO_MODELO_KEY,
    'df_modelo_universal',
    'home_modelo_universal_df',
    'modelo_universal_df',
    'mapeiaai_final_contract_df',
    'home_modelo_cadastro_df',
    'df_modelo_cadastro',
    'modelo_cadastro_df',
    'home_modelo_estoque_df',
    'df_modelo_estoque',
    'modelo_estoque_df',
    'estoque_wizard_df_modelo',
)


class _NamedBytesIO(BytesIO):
    def __init__(self, data: bytes, name: str):
        super().__init__(data)
        self.name = name


def _is_api_context() -> bool:
    """API exige escolha explícita; conexão isolada não altera o mapeamento."""
    if not api_flow_explicitly_selected():
        return False
    try:
        return bool(output_is_api())
    except Exception:
        return False


def _normalize_api_operation(value: object) -> str:
    text = str(value or '').strip().lower()
    if text in {OP_CADASTRO, OP_ESTOQUE, OP_PRECO}:
        return text
    if 'estoque' in text or 'saldo' in text or 'stock' in text or 'deposit' in text:
        return OP_ESTOQUE
    if 'preco' in text or 'preço' in text or 'price' in text or 'loja' in text or 'canal' in text:
        return OP_PRECO
    if 'cadastro' in text or 'produto' in text or 'produtos' in text:
        return OP_CADASTRO
    return ''


def _store_api_operation(operation: object) -> str:
    op = _normalize_api_operation(operation) or OP_CADASTRO
    for key in API_OPERATION_SESSION_KEYS:
        st.session_state[key] = op
    return op


def _current_operation() -> str:
    keys = [
        API_OPERATION_CHOICE_KEY,
        'bling_connected_api_operation',
        'flow_spine_sender_operation',
        'flow_spine_operation_resolved_for_api',
        'direct_bling_operation_applied',
        'api_operation',
        'bling_api_operation',
        'active_feature_operation',
        'flow_spine_operation',
        'operacao_final',
        'operation',
        'selected_operation',
    ]
    for key in keys:
        value = str(st.session_state.get(key) or '').strip()
        op = _normalize_api_operation(value)
        if op:
            return op
    try:
        op = _normalize_api_operation(output_operation())
        if op:
            return op
    except Exception:
        pass
    return OP_CADASTRO


def _render_api_operation_selector() -> str:
    current = _current_operation()
    labels = list(API_OPERATION_OPTIONS.keys())
    index = 0
    for pos, label in enumerate(labels):
        if API_OPERATION_OPTIONS[label] == current:
            index = pos
            break

    st.markdown('### Operação da API Bling')
    st.caption('Escolha a função real antes de preparar o envio. API não pode seguir como modelo universal.')
    selected_label = st.radio(
        'O que você quer fazer no Bling?',
        labels,
        index=index,
        horizontal=False,
        key='bling_api_operation_selector_radio',
    )
    operation = _store_api_operation(API_OPERATION_OPTIONS[selected_label])
    st.info(API_OPERATION_HELP.get(operation, ''))
    return operation


def _origin_kind() -> str:
    for key in ('bling_connected_origin_kind', 'origem_tipo', 'tipo_origem', 'home_source_kind', 'source_kind'):
        value = str(st.session_state.get(key) or '').strip().lower()
        if value:
            return value
    return ''


def _operation_label() -> str:
    try:
        plan = output_plan()
        return str(plan.primary_action_label or plan.operation or '').strip()
    except Exception:
        return ''


def _resolve_model_df() -> pd.DataFrame | None:
    for key in MODEL_FALLBACK_KEYS:
        value = st.session_state.get(key)
        if valid_model(value):
            model = value.copy().fillna('')
            st.session_state[CADASTRO_MODELO_KEY] = model
            st.session_state['df_modelo_universal'] = model
            st.session_state['home_modelo_universal_df'] = model
            return model

    data = st.session_state.get(MODEL_BYTES_KEY)
    name = str(st.session_state.get(MODEL_NAME_KEY) or 'modelo.csv')
    if isinstance(data, (bytes, bytearray)) and data:
        try:
            df = read_uploaded_file(_NamedBytesIO(bytes(data), name))
        except Exception:
            df = None
        if valid_model(df):
            model = df.copy().fillna('')
            st.session_state[CADASTRO_MODELO_KEY] = model
            st.session_state['df_modelo_universal'] = model
            st.session_state['home_modelo_universal_df'] = model
            return model
    return None


def _current_final_df() -> pd.DataFrame | None:
    for key in ('df_final_bling_api', UNIVERSAL_FINAL_KEY, LEGACY_CADASTRO_FINAL_KEY, 'df_final_cadastro'):
        value = st.session_state.get(key)
        if isinstance(value, pd.DataFrame):
            return value
    return None


def _render_mapping_spine_caption() -> None:
    try:
        plan = output_plan()
        operation = _normalize_api_operation(st.session_state.get('flow_spine_sender_operation')) if _is_api_context() else 'universal'
        st.caption(f"Fluxo ativo: {plan.contract_key} · destino: {plan.final_destination} · operação: {operation or 'universal'}")
        st.session_state['flow_spine_mapping_ready'] = True
        st.session_state['flow_spine_mapping_diagnostics'] = output_diagnostics()
    except Exception:
        pass


def _render_post_mapping_notice() -> None:
    if not cadastro_mapping_ready():
        st.info('A automação ainda está preparando os dados para liberar a revisão, a prévia e o envio.')
        return

    if _is_api_context():
        op = _current_operation()
        if op == OP_PRECO:
            st.success('Automação preparada. Continue para a prévia; antes do envio será obrigatório escolher Preço geral ou loja/canal.')
        elif op == OP_ESTOQUE:
            st.success('Automação preparada. Continue para a prévia; antes do envio será obrigatório escolher o depósito do estoque.')
        else:
            label = _operation_label() or 'enviar'
            st.success(f'Automação preparada. Continue para a prévia e {label}.')
        return

    st.success('Mapeamento confirmado. O download será liberado no final, após a revisão e a prévia.')


def _df_for_mapping(df_origem: pd.DataFrame) -> pd.DataFrame:
    df_precificado = st.session_state.get(CADASTRO_ORIGEM_PRICED_KEY)
    if isinstance(df_precificado, pd.DataFrame) and not df_precificado.empty:
        return df_precificado
    return df_origem


def _api_automation_source_df(df_origem: pd.DataFrame) -> pd.DataFrame:
    df_precificado = st.session_state.get(CADASTRO_ORIGEM_PRICED_KEY)
    if isinstance(df_precificado, pd.DataFrame) and not df_precificado.empty:
        return df_precificado.copy().fillna('')
    return df_origem.copy().fillna('')


def _prepare_bling_api_automation(df_origem: pd.DataFrame) -> pd.DataFrame | None:
    """Prepara a base para API sem mapeamento manual, apenas quando escolhida."""
    operation = _render_api_operation_selector()
    policy = activate_connected_flow(operation, _origin_kind())
    if not policy.api_enabled:
        return None

    df_final = ensure_api_direct_final_df()
    if not valid_df(df_final):
        df_final = _api_automation_source_df(df_origem)
    if not valid_df(df_final):
        return None

    fixed = annotate_dataframe_for_connected_flow(df_final.copy().fillna(''), policy)
    signature = df_signature(fixed)
    st.session_state['df_final_bling_api'] = fixed
    st.session_state[UNIVERSAL_FINAL_KEY] = fixed
    st.session_state[LEGACY_CADASTRO_FINAL_KEY] = fixed
    st.session_state['mapping_bling_api'] = {str(column): str(column) for column in fixed.columns}
    st.session_state['mapping_confidence_bling_api'] = {str(column): {'level': 'verde', 'score': 100, 'api_auto': True} for column in fixed.columns}
    st.session_state['mapping_cadastro'] = st.session_state['mapping_bling_api']
    st.session_state['mapping_confidence_cadastro'] = st.session_state['mapping_confidence_bling_api']
    st.session_state[CADASTRO_MAPPING_CONFIRMED_KEY] = True
    st.session_state[CADASTRO_MAPPING_SIGNATURE_KEY] = signature
    st.session_state['bling_api_automation_mapping_skipped'] = True
    st.session_state['bling_api_automation_rows'] = int(len(fixed))
    st.session_state['bling_api_automation_columns'] = int(len(fixed.columns))
    st.session_state['bling_api_required_selector'] = policy.required_selector
    st.session_state['bling_api_must_run_ai_check'] = policy.must_run_ai_check
    st.session_state['bling_api_final_action'] = policy.final_action
    st.session_state['bling_connected_api_operation'] = policy.operation
    st.session_state['flow_spine_sender_operation'] = policy.operation
    st.session_state['flow_spine_operation_resolved_for_api'] = policy.operation
    st.session_state['direct_bling_operation_applied'] = policy.operation
    return fixed


def _render_connected_policy_notice() -> None:
    selector = str(st.session_state.get('bling_api_required_selector') or '').strip()
    final_action = str(st.session_state.get('bling_api_final_action') or '').strip()
    if selector == 'price_channel_or_general':
        st.info('Próxima regra: selecionar preço geral ou loja/canal de venda antes de enviar o preço calculado ao Bling.')
    elif selector == 'stock_deposit':
        st.info('Próxima regra: selecionar depósito do Bling antes de atualizar estoque.')
    else:
        st.info('Próxima regra: comparar, rodar check IA e enviar ao Bling com mínima intervenção humana.')
    if final_action:
        st.caption(f'Ação final planejada: {final_action}.')


def render_cadastro_mapeamento_step() -> None:
    df_origem = st.session_state.get(CADASTRO_ORIGEM_KEY)
    df_modelo = _resolve_model_df()
    _render_mapping_spine_caption()

    if not valid_df(df_origem):
        st.warning('Nenhuma planilha com dados carregada. Volte para Dados importados.')
        return

    store_expected_source_rows(df_origem)

    if _is_api_context():
        df_final_api = _prepare_bling_api_automation(df_origem)
        if valid_df(df_final_api):
            col_a, col_b = st.columns(2)
            with col_a:
                st.metric('Linhas preparadas', len(df_final_api))
            with col_b:
                st.metric('Campos para API', len(df_final_api.columns))
            st.info('Fluxo API escolhido: o sistema preparou os campos automaticamente; o usuário não precisa mapear manualmente.')
            _render_connected_policy_notice()
            _render_post_mapping_notice()
            return
        st.warning('A automação da API ainda não conseguiu preparar os dados. Volte para Dados importados e confira a origem.')
        return

    if not valid_model(df_modelo):
        st.warning('Modelo para mapear ausente. Volte para Modelo para mapear.')
        return

    df_para_mapear = _df_for_mapping(df_origem)

    col_a, col_b = st.columns(2)
    with col_a:
        st.metric('Linhas encontradas', len(df_origem))
    with col_b:
        st.metric('Colunas do modelo', len(df_modelo.columns))

    if bool(st.session_state.get('cadastro_preco_calculado_ativo', False)):
        st.success('Preço calculado na etapa anterior. O valor calculado está disponível para o mapeamento.')

    render_shared_cadastro_mapping(df_para_mapear, df_modelo)

    df_final = _current_final_df()
    if isinstance(df_final, pd.DataFrame) and len(df_final) != len(df_origem):
        if render_row_count_blocker(df_final):
            return

    _render_post_mapping_notice()


__all__ = ['render_cadastro_mapeamento_step']
