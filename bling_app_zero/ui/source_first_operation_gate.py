from __future__ import annotations

import streamlit as st

from bling_app_zero.core.audit import add_audit_event
from bling_app_zero.core.operation_contract import OP_ATUALIZACAO_PRECO, OP_CADASTRO, OP_ESTOQUE, OP_UNIVERSAL, normalize_operation

RESPONSIBLE_FILE = 'bling_app_zero/ui/source_first_operation_gate.py'
SELECTED_OPERATION_KEY = 'source_first_selected_operation'
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


def selected_operation() -> str:
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


def clear_inferred_operation_until_user_chooses() -> None:
    if not source_data_ready() or selected_operation():
        return
    removed = []
    for key in OPERATION_KEYS:
        if _normalize(st.session_state.get(key)) in CONCRETE_OPERATIONS:
            st.session_state.pop(key, None)
            removed.append(key)
    st.session_state['home_slim_flow_operation'] = OP_UNIVERSAL
    st.session_state['source_first_operation_pending_choice'] = True
    if removed:
        add_audit_event(
            'source_first_auto_operation_removed',
            area='WIZARD',
            status='OK',
            details={
                'removed_keys': removed,
                'reason': 'Depois da origem, API deve aguardar escolha real: cadastro, estoque ou preco.',
                'responsible_file': RESPONSIBLE_FILE,
            },
        )


def write_selected_operation(operation: object) -> str:
    op = _normalize(operation, default=OP_CADASTRO)
    st.session_state[SELECTED_OPERATION_KEY] = op
    st.session_state['source_first_operation_pending_choice'] = False
    for key in OPERATION_KEYS:
        st.session_state[key] = op
    try:
        from bling_app_zero.ui.home_bling_api_flow import apply_direct_api_contract

        apply_direct_api_contract(op)
    except Exception:
        pass
    add_audit_event(
        'source_first_operation_selected',
        area='WIZARD',
        status='OK',
        details={'operation': op, 'responsible_file': RESPONSIBLE_FILE},
    )
    return op


def render_operation_gate(section_title, section_number: int) -> None:
    from bling_app_zero.ui.home_bling_api_flow import _render_stock_deposit_field

    section_title(section_number, 'Operação')
    if not source_data_ready():
        st.info('Carregue a origem dos dados primeiro. A operação só será escolhida depois da origem.')
        return
    st.caption('A origem não define o fluxo. Escolha agora se estes dados serão cadastro, estoque por depósito ou atualização de preços.')
    labels = list(LABELS.values())
    reverse = {label: op for op, label in LABELS.items()}
    current = LABELS.get(selected_operation(), LABELS[OP_CADASTRO])
    chosen = st.radio('Qual operação deseja executar?', labels, index=labels.index(current), key='source_first_operation_radio')
    op = write_selected_operation(reverse[chosen])
    if op == OP_ESTOQUE:
        st.warning('Depósito obrigatório antes de calculadora, IA, regras, prévia e envio.')
        _render_stock_deposit_field(OP_ESTOQUE)
        if deposit_selected():
            st.success('Depósito confirmado. O fluxo de estoque está liberado para seguir.')
        else:
            st.error('Selecione o depósito do Bling para liberar o próximo passo.')
    elif op == OP_ATUALIZACAO_PRECO:
        st.success('Atualização de preços selecionada. O próximo fluxo será preço/canal, sem categoria e sem IA de cadastro.')
    else:
        st.success('Cadastro selecionado. O próximo fluxo seguirá com calculadora, mapeamento, regras e IA quando aplicável.')


__all__ = [
    'OPERATION_STEP',
    'clear_inferred_operation_until_user_chooses',
    'operation_ready',
    'render_operation_gate',
    'selected_operation',
    'source_data_ready',
]
