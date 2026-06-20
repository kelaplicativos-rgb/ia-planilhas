from __future__ import annotations

import streamlit as st

from bling_app_zero.core.audit import add_audit_event
from bling_app_zero.core.operation_contract import OP_ATUALIZACAO_PRECO, OP_CADASTRO, OP_ESTOQUE, OP_UNIVERSAL, normalize_operation

RESPONSIBLE_FILE = 'bling_app_zero/ui/source_first_operation_gate.py'
SELECTED_OPERATION_KEY = 'source_first_selected_operation'
CONFIRMED_KEY = 'source_first_operation_user_confirmed'
PENDING_CHOICE = '__pending__'
OPERATION_STEP = 'operacao'
CONCRETE_OPERATIONS = {OP_CADASTRO, OP_ESTOQUE, OP_ATUALIZACAO_PRECO}
LABELS = {
    OP_CADASTRO: 'Cadastrar produtos',
    OP_ESTOQUE: 'Atualizar estoque por depósito',
    OP_ATUALIZACAO_PRECO: 'Atualizar preços',
}
SOURCE_KEYS = (
    'cadastro_wizard_df_origem',
    'df_origem',
    'df_origem_planilha',
    'df_produtos_origem',
    'df_origem_site_como_planilha',
    'df_site_bruto',
)
OPERATION_KEYS = (
    'api_operation',
    'bling_api_operation',
    'home_bling_api_operation_choice',
    'bling_connected_api_operation',
    'direct_bling_operation_choice',
    'direct_bling_operation_applied',
    'flow_spine_sender_operation',
    'flow_spine_operation_resolved_for_api',
    'flow_spine_api_batch_operation',
    'final_download_operation',
    'df_final_download_operation',
    'df_final_preview_operation',
    'home_slim_flow_operation',
    'home_detected_operation',
    'operacao_final',
    'tipo_operacao_final',
    'site_capture_operation',
)
DOWNSTREAM_KEYS = (
    'df_final_bling_api',
    'df_final_download_operation',
    'df_final_preview_operation',
    'final_download_operation',
    'final_download_df_snapshot',
    'cadastro_mapping_confirmed',
    'cadastro_mapping_confirmed_signature',
    'mapping_bling_api',
    'mapping_confidence_bling_api',
    'mapping_cadastro',
    'mapping_confidence_cadastro',
)


def _normalize(value: object, default: str = '') -> str:
    op = normalize_operation(value, default=OP_UNIVERSAL)
    return op if op in CONCRETE_OPERATIONS else default


def _has_dataframe(value: object) -> bool:
    try:
        return bool(value is not None and not getattr(value, 'empty', True) and len(getattr(value, 'columns', [])) > 0)
    except Exception:
        return False


def source_data_ready() -> bool:
    if any(_has_dataframe(st.session_state.get(key)) for key in SOURCE_KEYS):
        return True
    try:
        from bling_app_zero.ui.universal_wizard_state import universal_context_ready
        return bool(universal_context_ready())
    except Exception:
        return False


def _user_confirmed() -> bool:
    return bool(st.session_state.get(CONFIRMED_KEY))


def selected_operation() -> str:
    if not _user_confirmed():
        return ''
    return _normalize(st.session_state.get(SELECTED_OPERATION_KEY))


def deposit_selected() -> bool:
    return bool(str(st.session_state.get('bling_api_stock_deposit_id') or st.session_state.get('bling_api_stock_deposit_name') or '').strip())


def operation_ready() -> bool:
    op = selected_operation()
    if op not in CONCRETE_OPERATIONS:
        return False
    if op == OP_ESTOQUE and bool(st.session_state.get('home_bling_connected_same_flow_api_send')):
        return deposit_selected()
    return True


def _clear_operation_keys(reason: str) -> None:
    removed = []
    for key in OPERATION_KEYS + (SELECTED_OPERATION_KEY,):
        if key in st.session_state:
            st.session_state.pop(key, None)
            removed.append(key)
    st.session_state[CONFIRMED_KEY] = False
    st.session_state['home_slim_flow_operation'] = OP_UNIVERSAL
    st.session_state['home_detected_operation'] = OP_UNIVERSAL
    st.session_state['operacao_final'] = OP_UNIVERSAL
    st.session_state['tipo_operacao_final'] = OP_UNIVERSAL
    st.session_state['source_first_operation_pending_choice'] = True
    add_audit_event('source_first_operation_cleared_until_confirmed', area='WIZARD', status='OK', details={'removed_keys': removed, 'reason': reason, 'responsible_file': RESPONSIBLE_FILE})


def clear_inferred_operation_until_user_chooses() -> None:
    if not source_data_ready():
        return
    if _user_confirmed() and _normalize(st.session_state.get(SELECTED_OPERATION_KEY)) in CONCRETE_OPERATIONS:
        return
    has_auto_operation = any(_normalize(st.session_state.get(key)) in CONCRETE_OPERATIONS for key in OPERATION_KEYS + (SELECTED_OPERATION_KEY,))
    if has_auto_operation:
        _clear_operation_keys('origem carregada; escolha de operação ainda não foi confirmada pelo usuário')
    else:
        st.session_state['source_first_operation_pending_choice'] = True
        st.session_state['home_slim_flow_operation'] = OP_UNIVERSAL


def _clear_downstream_outputs(previous: str, new: str) -> None:
    if not previous or previous == new:
        return
    removed = []
    for key in DOWNSTREAM_KEYS:
        if key in st.session_state:
            st.session_state.pop(key, None)
            removed.append(key)
    if removed:
        add_audit_event('source_first_downstream_cleared_after_operation_change', area='WIZARD', status='OK', details={'previous_operation': previous, 'new_operation': new, 'removed_keys': removed, 'responsible_file': RESPONSIBLE_FILE})


def write_selected_operation(operation: object) -> str:
    op = _normalize(operation)
    if op not in CONCRETE_OPERATIONS:
        return ''
    previous = _normalize(st.session_state.get(SELECTED_OPERATION_KEY)) if _user_confirmed() else ''
    _clear_downstream_outputs(previous, op)
    st.session_state[SELECTED_OPERATION_KEY] = op
    st.session_state[CONFIRMED_KEY] = True
    st.session_state['source_first_operation_pending_choice'] = False
    for key in OPERATION_KEYS:
        st.session_state[key] = op
    try:
        from bling_app_zero.ui.home_bling_api_flow import apply_direct_api_contract
        apply_direct_api_contract(op)
    except Exception:
        pass
    add_audit_event('source_first_operation_selected', area='WIZARD', status='OK', details={'operation': op, 'explicit_confirmation': True, 'responsible_file': RESPONSIBLE_FILE})
    return op


def render_operation_gate(section_title, section_number: int) -> None:
    from bling_app_zero.ui.home_bling_api_flow import _render_stock_deposit_field

    section_title(section_number, 'Operação')
    if not source_data_ready():
        st.info('Carregue a origem dos dados primeiro. A operação só será escolhida depois da origem.')
        return
    st.caption('A origem não define o fluxo. Escolha e confirme se estes dados serão cadastro, estoque por depósito ou atualização de preços.')
    options = [PENDING_CHOICE, OP_CADASTRO, OP_ESTOQUE, OP_ATUALIZACAO_PRECO]
    option_labels = {
        PENDING_CHOICE: 'Escolha a operação...',
        OP_CADASTRO: LABELS[OP_CADASTRO],
        OP_ESTOQUE: LABELS[OP_ESTOQUE],
        OP_ATUALIZACAO_PRECO: LABELS[OP_ATUALIZACAO_PRECO],
    }
    current = selected_operation() or PENDING_CHOICE
    chosen = st.selectbox(
        'Qual operação deseja executar?',
        options,
        index=options.index(current) if current in options else 0,
        format_func=lambda value: option_labels.get(value, str(value)),
        key='source_first_operation_selectbox',
    )
    if chosen == PENDING_CHOICE:
        st.info('Selecione uma operação real para liberar as próximas etapas.')
        return
    if st.button('Confirmar operação', use_container_width=True, key='source_first_confirm_operation'):
        write_selected_operation(chosen)
    op = selected_operation()
    if not op:
        st.warning('A operação ainda não foi confirmada. Nada será tratado como cadastro, estoque ou preço automaticamente.')
        return
    if op == OP_ESTOQUE:
        st.warning('Depósito obrigatório antes de calculadora, IA, regras, prévia e envio.')
        _render_stock_deposit_field(OP_ESTOQUE)
        if deposit_selected():
            st.success('Depósito confirmado. O fluxo de estoque está liberado para seguir.')
        else:
            st.error('Selecione o depósito do Bling para liberar o próximo passo.')
    elif op == OP_ATUALIZACAO_PRECO:
        st.success('Atualização de preços confirmada. O próximo fluxo será preço/canal, sem categoria e sem IA de cadastro.')
    else:
        st.success('Cadastro confirmado. O próximo fluxo seguirá com calculadora, mapeamento, regras e IA quando aplicável.')


__all__ = [
    'OPERATION_STEP',
    'clear_inferred_operation_until_user_chooses',
    'operation_ready',
    'render_operation_gate',
    'selected_operation',
    'source_data_ready',
]
