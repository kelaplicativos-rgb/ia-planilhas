from __future__ import annotations

from io import BytesIO

import pandas as pd
import streamlit as st

from bling_app_zero.core.audit import add_audit_event
from bling_app_zero.core.bling_connected_flow_policy import (
    OP_CADASTRO,
    OP_ESTOQUE,
    OP_PRECO,
    activate_connected_flow,
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
    render_row_count_blocker,
    store_expected_source_rows,
    valid_df,
    valid_model,
)
from bling_app_zero.ui.home_bling_api_flow import _render_stock_deposit_field
from bling_app_zero.ui.home_shared import df_signature
from bling_app_zero.ui.shared_mapping import render_shared_cadastro_mapping

RESPONSIBLE_FILE = 'bling_app_zero/ui/cadastro_mapping_step.py'
HOME_ENTRY_CONTEXT_KEY = 'home_entry_context'
CONTEXT_BLING_API = 'bling_api'
MODEL_BYTES_KEY = 'destination_model_upload_bytes'
MODEL_NAME_KEY = 'destination_model_upload_name'
API_OPERATION_CHOICE_KEY = 'home_bling_api_operation_choice'
API_STOCK_DEPOSIT_AUTOLOAD_KEY = 'bling_api_stock_deposit_autoload_attempted'
API_STOCK_DEPOSIT_OPTIONS_KEY = 'bling_api_stock_deposit_options'
API_OPERATION_OPTIONS = {
    'Cadastrar produtos no Bling': OP_CADASTRO,
    'Atualizar preços multilojas/canais': OP_PRECO,
    'Atualizar estoque por depósito': OP_ESTOQUE,
}
API_OPERATION_LABEL_BY_VALUE = {value: label for label, value in API_OPERATION_OPTIONS.items()}
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
    'direct_bling_api_contract_df',
    'home_modelo_cadastro_df',
    'df_modelo_cadastro',
    'modelo_cadastro_df',
    'home_modelo_estoque_df',
    'df_modelo_estoque',
    'modelo_estoque_df',
    'estoque_wizard_df_modelo',
)

ORIGIN_FALLBACK_KEYS = (
    CADASTRO_ORIGEM_KEY,
    'df_origem_cadastro',
    'df_origem',
    'df_origem_planilha',
    'df_produtos_origem',
    'df_source',
    'df_origem_site',
    'df_origem_site_como_planilha',
    'df_origem_site_como_planilha_universal',
    'df_origem_site_como_planilha_cadastro',
    'df_origem_site_como_planilha_estoque',
    'df_origem_site_como_planilha_atualizacao_preco',
    'df_origem_estoque',
    'df_origem_universal',
    'df_site_bruto',
    'df_site_bruto_universal',
    'df_site_bruto_cadastro',
    'df_site_bruto_estoque',
    'df_site_bruto_atualizacao_preco',
    'estoque_wizard_df_origem_site',
    UNIVERSAL_FINAL_KEY,
    LEGACY_CADASTRO_FINAL_KEY,
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
    previous = _normalize_api_operation(st.session_state.get(API_OPERATION_CHOICE_KEY))
    if op == OP_ESTOQUE and previous != op:
        # Ao trocar para estoque, a busca automática precisa rodar de novo.
        # Isso evita cache antigo/erro anterior impedir a lista real de depósitos.
        st.session_state.pop(API_STOCK_DEPOSIT_AUTOLOAD_KEY, None)
    for key in API_OPERATION_SESSION_KEYS:
        st.session_state[key] = op
    return op


def _operation_label_for(operation: object) -> str:
    op = _normalize_api_operation(operation)
    return API_OPERATION_LABEL_BY_VALUE.get(op, str(operation or op or 'Operação API'))


def _operation_selected_before_mapping() -> str:
    # A operação deve nascer na entrada Bling API. A etapa de mapeamento apenas
    # herda essa escolha para não obrigar o usuário a escolher estoque de novo
    # quase no final do fluxo.
    keys = (
        'direct_bling_operation_choice',
        'direct_bling_operation_applied',
        API_OPERATION_CHOICE_KEY,
        'bling_connected_api_operation',
        'flow_spine_sender_operation',
        'flow_spine_operation_resolved_for_api',
    )
    for key in keys:
        op = _normalize_api_operation(st.session_state.get(key))
        if op in {OP_CADASTRO, OP_ESTOQUE, OP_PRECO}:
            return op
    return ''


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
    entry_operation = _operation_selected_before_mapping()
    st.markdown('### Operação da API Bling')

    if entry_operation:
        operation = _store_api_operation(entry_operation)
        st.success(f'Operação definida no início do fluxo: {_operation_label_for(operation)}.')
        if operation == OP_ESTOQUE:
            st.caption('Próximo passo obrigatório: confirmar o depósito do Bling antes de seguir com a atualização de saldo.')
        else:
            st.caption('A etapa atual herda a operação; o fluxo segue pelo mesmo mapeamento/revisão usado na origem por arquivo.')
        st.info(API_OPERATION_HELP.get(operation, ''))
        return operation

    current = _current_operation()
    labels = list(API_OPERATION_OPTIONS.keys())
    index = 0
    for pos, label in enumerate(labels):
        if API_OPERATION_OPTIONS[label] == current:
            index = pos
            break

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


def _resolve_origin_df() -> pd.DataFrame | None:
    for key in ORIGIN_FALLBACK_KEYS:
        value = st.session_state.get(key)
        if valid_df(value):
            df = value.copy().fillna('')
            st.session_state[CADASTRO_ORIGEM_KEY] = df
            st.session_state['df_origem'] = df
            st.session_state['df_produtos_origem'] = df
            try:
                add_audit_event(
                    'mapping_origin_resolved_from_fallback',
                    area='MAPEAMENTO',
                    step=st.session_state.get('bling_wizard_step'),
                    status='OK',
                    details={
                        'source_key': key,
                        'rows': int(len(df)),
                        'columns': [str(column) for column in list(df.columns)[:60]],
                        'operation': _current_operation(),
                        'api_context': _is_api_context(),
                        'responsible_file': RESPONSIBLE_FILE,
                    },
                )
            except Exception:
                pass
            return df
    return None


def _current_final_df() -> pd.DataFrame | None:
    # Prefere a saída recém-mapeada. df_final_bling_api pode existir de tentativa antiga.
    for key in (UNIVERSAL_FINAL_KEY, LEGACY_CADASTRO_FINAL_KEY, 'df_final_cadastro', 'df_final_bling_api'):
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
        st.info('Revise e confirme o mapeamento para liberar a prévia, a validação e o envio.')
        return

    if _is_api_context():
        op = _current_operation()
        if op == OP_PRECO:
            st.success('Mapeamento confirmado. Continue para a prévia; antes do envio será obrigatório escolher Preço geral ou loja/canal.')
        elif op == OP_ESTOQUE:
            st.success('Mapeamento confirmado. Continue para a prévia; antes do envio será obrigatório confirmar o depósito do Bling.')
        else:
            label = _operation_label() or 'enviar'
            st.success(f'Mapeamento confirmado. Continue para a prévia e {label}.')
        return

    st.success('Mapeamento confirmado. O download será liberado no final, após a revisão e a prévia.')


def _df_for_mapping(df_origem: pd.DataFrame) -> pd.DataFrame:
    df_precificado = st.session_state.get(CADASTRO_ORIGEM_PRICED_KEY)
    if isinstance(df_precificado, pd.DataFrame) and not df_precificado.empty:
        return df_precificado
    return df_origem


def _prepare_bling_api_connection_policy() -> str:
    """Prepara a conexão API sem pular o mapeamento/revisão da origem."""
    operation = _render_api_operation_selector()
    policy = activate_connected_flow(operation, _origin_kind())
    st.session_state['bling_api_required_selector'] = policy.required_selector
    st.session_state['bling_api_must_run_ai_check'] = policy.must_run_ai_check
    st.session_state['bling_api_final_action'] = policy.final_action
    st.session_state['bling_connected_api_operation'] = policy.operation
    st.session_state['flow_spine_sender_operation'] = policy.operation
    st.session_state['flow_spine_operation_resolved_for_api'] = policy.operation
    st.session_state['direct_bling_operation_applied'] = policy.operation
    st.session_state['bling_api_manual_mapping_required'] = True
    st.session_state.pop('bling_api_automation_mapping_skipped', None)
    try:
        add_audit_event(
            'bling_api_connection_prepared_with_mapping_guard',
            area='BLING_API_FLOW',
            status='OK' if policy.api_enabled else 'INFO',
            details={
                'operation': policy.operation,
                'origin_kind': policy.origin_kind,
                'manual_mapping_allowed': policy.manual_mapping_allowed,
                'required_selector': policy.required_selector,
                'next_human_step': policy.next_human_step,
                'responsible_file': RESPONSIBLE_FILE,
            },
        )
    except Exception:
        pass
    return policy.operation


def _sync_api_mapped_output() -> None:
    if not _is_api_context():
        return
    df_final = _current_final_df()
    if not valid_df(df_final):
        return
    fixed = df_final.copy().fillna('')
    st.session_state['df_final_bling_api'] = fixed
    st.session_state[UNIVERSAL_FINAL_KEY] = fixed
    st.session_state[LEGACY_CADASTRO_FINAL_KEY] = fixed
    mapping = st.session_state.get('mapping_cadastro') or st.session_state.get('mapping_universal')
    confidence = st.session_state.get('mapping_confidence_cadastro') or st.session_state.get('mapping_confidence_universal')
    if isinstance(mapping, dict):
        st.session_state['mapping_bling_api'] = mapping
    if isinstance(confidence, dict):
        st.session_state['mapping_confidence_bling_api'] = confidence
    st.session_state['bling_api_mapped_rows'] = int(len(fixed))
    st.session_state['bling_api_mapped_columns'] = int(len(fixed.columns))


def _stock_deposit_autoload_needs_retry() -> bool:
    deposits = st.session_state.get(API_STOCK_DEPOSIT_OPTIONS_KEY)
    return not isinstance(deposits, list) or not deposits


def _render_connected_policy_notice() -> None:
    selector = str(st.session_state.get('bling_api_required_selector') or '').strip()
    final_action = str(st.session_state.get('bling_api_final_action') or '').strip()
    if selector == 'price_channel_or_general':
        st.info('Próxima regra: selecionar preço geral ou loja/canal de venda antes de enviar o preço calculado ao Bling.')
    elif selector == 'stock_deposit':
        st.info('Depósito obrigatório: ao selecionar estoque, o sistema busca automaticamente os depósitos reais do Bling e já deixa um selecionado para o envio.')
        if _stock_deposit_autoload_needs_retry():
            st.session_state.pop(API_STOCK_DEPOSIT_AUTOLOAD_KEY, None)
        _render_stock_deposit_field(OP_ESTOQUE)
    else:
        st.info('Próxima regra: conferir prévia, rodar blindagem de validação e enviar ao Bling.')
    if final_action:
        st.caption(f'Ação final planejada: {final_action}.')


def render_cadastro_mapeamento_step() -> None:
    df_origem = _resolve_origin_df()
    df_modelo = _resolve_model_df()
    _render_mapping_spine_caption()

    if not valid_df(df_origem):
        st.warning('Nenhuma planilha com dados carregada. Volte para Dados importados.')
        return

    store_expected_source_rows(df_origem)

    if _is_api_context():
        _prepare_bling_api_connection_policy()

    if not valid_model(df_modelo):
        if _is_api_context():
            st.warning('Contrato/modelo da operação API ausente. Volte para a escolha da operação da API para carregar o contrato correto.')
        else:
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

    if _is_api_context():
        st.info('Conexão API blindada: a API usa a mesma origem, o mesmo mapeamento e a mesma prévia do fluxo por arquivo. Nenhum envio será liberado sem revisão/validação.')

    render_shared_cadastro_mapping(df_para_mapear, df_modelo)
    _sync_api_mapped_output()

    df_final = _current_final_df()
    if isinstance(df_final, pd.DataFrame) and len(df_final) != len(df_origem):
        if render_row_count_blocker(df_final):
            return

    if _is_api_context():
        _render_connected_policy_notice()

    _render_post_mapping_notice()


__all__ = ['render_cadastro_mapeamento_step']
