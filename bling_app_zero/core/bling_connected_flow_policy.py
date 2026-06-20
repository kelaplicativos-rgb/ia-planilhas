from __future__ import annotations

from dataclasses import dataclass
from typing import Final

import pandas as pd
import streamlit as st

from bling_app_zero.core.api_operation_lock import lock_api_operation
from bling_app_zero.core.audit import add_audit_event
from bling_app_zero.core.bling_oauth import connection_status

RESPONSIBLE_FILE: Final[str] = 'bling_app_zero/core/bling_connected_flow_policy.py'

OP_CADASTRO: Final[str] = 'cadastro'
OP_ESTOQUE: Final[str] = 'estoque'
OP_PRECO: Final[str] = 'atualizacao_preco'
OP_ATUALIZAR_PRODUTOS: Final[str] = 'atualizacao_produtos'
OP_COMPLETAR_VAZIOS: Final[str] = 'completar_campos_vazios'

PRICE_TARGET_REQUIRED: Final[str] = 'price_channel_or_general'
STOCK_DEPOSIT_REQUIRED: Final[str] = 'stock_deposit'
AI_CHECK_REQUIRED: Final[str] = 'ai_check_before_send'
NO_MANUAL_MAPPING: Final[str] = 'no_manual_mapping_when_bling_connected'

CONNECTED_API_FLOW_KEY: Final[str] = 'bling_connected_api_flow_active'
CONNECTED_OPERATION_KEY: Final[str] = 'bling_connected_api_operation'
CONNECTED_ORIGIN_KIND_KEY: Final[str] = 'bling_connected_origin_kind'
CONNECTED_HUMAN_STEP_KEY: Final[str] = 'bling_connected_next_human_step'
EXPLICIT_API_SEND_KEY: Final[str] = 'home_bling_connected_same_flow_api_send'
FINISH_MODE_KEY: Final[str] = 'bling_finish_mode'
API_DESTINATION: Final[str] = 'api_bling'


@dataclass(frozen=True)
class ConnectedFlowPolicy:
    operation: str
    origin_kind: str
    api_enabled: bool
    manual_mapping_allowed: bool
    required_selector: str
    next_human_step: str
    must_run_ai_check: bool
    final_action: str


def normalize_operation(value: object) -> str:
    text = str(value or '').strip().lower()
    for old, new in {'ã': 'a', 'á': 'a', 'à': 'a', 'â': 'a', 'é': 'e', 'ê': 'e', 'í': 'i', 'ó': 'o', 'ô': 'o', 'õ': 'o', 'ú': 'u', 'ç': 'c'}.items():
        text = text.replace(old, new)
    text = ' '.join(text.replace('-', '_').replace('/', '_').split())
    if 'estoque' in text or 'saldo' in text or 'stock' in text:
        return OP_ESTOQUE
    if 'preco' in text or 'price' in text:
        return OP_PRECO
    if 'completar' in text or 'vazio' in text:
        return OP_COMPLETAR_VAZIOS
    if 'alterado' in text or 'atualizacao_produto' in text or 'atualizar produto' in text:
        return OP_ATUALIZAR_PRODUTOS
    if 'cadastro' in text or 'cadastrar' in text or 'produto' in text:
        return OP_CADASTRO
    return str(value or '').strip().lower() or OP_CADASTRO


def bling_connected() -> bool:
    try:
        return bool(connection_status().get('connected'))
    except Exception:
        return False


def api_flow_explicitly_selected() -> bool:
    """A conexão não escolhe o fluxo; a seleção explícita da Home escolhe."""
    if bool(st.session_state.get(EXPLICIT_API_SEND_KEY)):
        return True
    finish_mode = str(st.session_state.get(FINISH_MODE_KEY) or '').strip().lower()
    if finish_mode == 'api_direct':
        return True
    return False


def policy_for(operation: object, origin_kind: object = '') -> ConnectedFlowPolicy:
    op = normalize_operation(operation)
    origin = str(origin_kind or st.session_state.get(CONNECTED_ORIGIN_KIND_KEY) or '').strip().lower()
    api_enabled = bool(bling_connected() and api_flow_explicitly_selected())

    if not api_enabled:
        return ConnectedFlowPolicy(
            operation=op,
            origin_kind=origin,
            api_enabled=False,
            manual_mapping_allowed=True,
            required_selector='',
            next_human_step='manual_or_csv_flow',
            must_run_ai_check=False,
            final_action='download_or_manual_review',
        )

    if op == OP_PRECO:
        selector = PRICE_TARGET_REQUIRED
        next_step = 'selecionar_preco_geral_ou_canal_e_precificar'
        final_action = 'enviar_preco_calculado_ao_bling'
    elif op == OP_ESTOQUE:
        selector = STOCK_DEPOSIT_REQUIRED
        next_step = 'selecionar_deposito_para_atualizar_estoque'
        final_action = 'enviar_estoque_ao_deposito_bling'
    elif op == OP_CADASTRO:
        selector = ''
        next_step = 'comparar_novos_produtos_e_preparar_cadastro'
        final_action = 'cadastrar_produtos_novos_no_bling'
    elif op == OP_ATUALIZAR_PRODUTOS:
        selector = ''
        next_step = 'comparar_dados_alterados_e_preparar_atualizacao'
        final_action = 'atualizar_apenas_dados_alterados_no_bling'
    elif op == OP_COMPLETAR_VAZIOS:
        selector = ''
        next_step = 'comparar_campos_vazios_e_preparar_complemento'
        final_action = 'preencher_apenas_campos_vazios_no_bling'
    else:
        selector = ''
        next_step = 'preparar_automacao_api'
        final_action = 'enviar_ao_bling'

    return ConnectedFlowPolicy(
        operation=op,
        origin_kind=origin,
        api_enabled=True,
        manual_mapping_allowed=True,
        required_selector=selector,
        next_human_step=next_step,
        must_run_ai_check=True,
        final_action=final_action,
    )


def activate_connected_flow(operation: object, origin_kind: object = '') -> ConnectedFlowPolicy:
    policy = policy_for(operation, origin_kind)
    st.session_state[CONNECTED_API_FLOW_KEY] = bool(policy.api_enabled)
    st.session_state[CONNECTED_OPERATION_KEY] = policy.operation
    st.session_state[CONNECTED_ORIGIN_KIND_KEY] = policy.origin_kind
    st.session_state[CONNECTED_HUMAN_STEP_KEY] = policy.next_human_step
    if policy.api_enabled:
        lock_api_operation(policy.operation, source=RESPONSIBLE_FILE, force=True)
    add_audit_event(
        'bling_connected_flow_policy_applied',
        area='BLING_API_FLOW',
        status='OK' if policy.api_enabled else 'INFO',
        details={
            'operation': policy.operation,
            'origin_kind': policy.origin_kind,
            'bling_connected': bling_connected(),
            'api_explicitly_selected': api_flow_explicitly_selected(),
            'api_enabled': policy.api_enabled,
            'manual_mapping_allowed': policy.manual_mapping_allowed,
            'required_selector': policy.required_selector,
            'next_human_step': policy.next_human_step,
            'must_run_ai_check': policy.must_run_ai_check,
            'final_action': policy.final_action,
            'api_operation_locked': bool(policy.api_enabled),
            'responsible_file': RESPONSIBLE_FILE,
        },
    )
    return policy


def annotate_dataframe_for_connected_flow(df: pd.DataFrame, policy: ConnectedFlowPolicy) -> pd.DataFrame:
    if not isinstance(df, pd.DataFrame) or df.empty:
        return df
    out = df.copy().fillna('')
    if policy.api_enabled:
        out['Bling fluxo API conectado'] = 'Sim'
        out['Bling operação API'] = policy.operation
        out['Bling seletor obrigatório'] = policy.required_selector
        out['Bling check IA obrigatório'] = 'Sim' if policy.must_run_ai_check else 'Não'
        out['Bling ação final'] = policy.final_action
    return out


def should_skip_manual_mapping(operation: object) -> bool:
    policy = policy_for(operation)
    return bool(policy.api_enabled and not policy.manual_mapping_allowed)


def required_selector(operation: object) -> str:
    return policy_for(operation).required_selector


def must_run_ai_check(operation: object) -> bool:
    return policy_for(operation).must_run_ai_check


__all__ = [
    'AI_CHECK_REQUIRED',
    'CONNECTED_API_FLOW_KEY',
    'CONNECTED_HUMAN_STEP_KEY',
    'CONNECTED_OPERATION_KEY',
    'CONNECTED_ORIGIN_KIND_KEY',
    'NO_MANUAL_MAPPING',
    'OP_ATUALIZAR_PRODUTOS',
    'OP_CADASTRO',
    'OP_COMPLETAR_VAZIOS',
    'OP_ESTOQUE',
    'OP_PRECO',
    'PRICE_TARGET_REQUIRED',
    'STOCK_DEPOSIT_REQUIRED',
    'ConnectedFlowPolicy',
    'activate_connected_flow',
    'annotate_dataframe_for_connected_flow',
    'api_flow_explicitly_selected',
    'bling_connected',
    'must_run_ai_check',
    'normalize_operation',
    'policy_for',
    'required_selector',
    'should_skip_manual_mapping',
]
