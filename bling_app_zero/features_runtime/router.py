from __future__ import annotations

import re

import streamlit as st
from streamlit.errors import StreamlitAPIException

from bling_app_zero.features_runtime.contracts import FeatureContract
from bling_app_zero.features_runtime.registry import get_feature_contract

HOME_ENTRY_CONTEXT_KEY = 'home_entry_context'
FINISH_MODE_KEY = 'bling_finish_mode'
UNIFIED_BLING_SEND_KEY = 'home_bling_connected_same_flow_api_send'
WIZARD_STEP_KEY = 'bling_wizard_step'
SOURCE_FIRST_CONFIRMED_KEY = 'source_first_operation_user_confirmed'
SOURCE_FIRST_SELECTED_KEY = 'source_first_selected_operation'

OP_UNIVERSAL = 'universal'
OP_API_PENDING = 'api_pending'
OP_CADASTRO = 'cadastro'
OP_ESTOQUE = 'estoque'
OP_ATUALIZACAO_PRECO = 'atualizacao_preco'
CONCRETE_API_OPERATIONS = {OP_CADASTRO, OP_ESTOQUE, OP_ATUALIZACAO_PRECO}
API_CONTRACT_BY_OPERATION = {
    OP_API_PENDING: 'api_pending',
    OP_CADASTRO: 'api_cadastro',
    OP_ESTOQUE: 'api_estoque',
    OP_ATUALIZACAO_PRECO: 'api_atualizacao_preco',
}

API_FINISH_MODES = {'api_direct', 'api', 'bling_api'}
SOURCE_FIRST_STEPS = {'origem', 'entrada'}
SOURCE_DF_KEYS = (
    'cadastro_wizard_df_origem',
    'df_origem',
    'df_origem_planilha',
    'df_produtos_origem',
    'df_origem_site',
    'df_origem_site_como_planilha',
    'df_origem_site_como_planilha_universal',
    'df_origem_site_como_planilha_cadastro',
    'df_origem_site_como_planilha_estoque',
    'df_origem_site_como_planilha_atualizacao_preco',
    'df_origem_cadastro',
    'df_origem_estoque',
    'df_origem_universal',
    'df_site_bruto',
    'df_site_bruto_universal',
    'df_site_bruto_cadastro',
    'df_site_bruto_estoque',
    'df_site_bruto_atualizacao_preco',
    'estoque_wizard_df_origem_site',
)
API_OPERATION_STATE_KEYS = (
    'api_operation',
    'bling_api_operation',
    'home_bling_api_operation_choice',
    'bling_connected_api_operation',
    'flow_spine_sender_operation',
    'flow_spine_operation_resolved_for_api',
    'direct_bling_operation_choice',
    'direct_bling_operation_applied',
    'final_download_operation',
    'df_final_download_operation',
    'df_final_preview_operation',
    'operacao_final',
    'tipo_operacao_final',
    'home_detected_operation',
    'home_slim_flow_operation',
    'site_capture_operation',
)
API_OPERATION_HINT_KEYS = (
    'site_capture_scan_goal',
    'scan_goal',
    'site_capture_goal',
    'blingsmartscan_goal',
    'home_entry_context',
    'home_slim_flow_origin',
    'origem_final',
)
API_OPERATION_DF_KEYS = (
    'final_download_df_snapshot',
    'df_final_download',
    'df_final_preview',
    'df_final',
    'df_origem_site_como_planilha_cadastro',
    'df_origem_site_como_planilha_estoque',
    'df_origem_site_como_planilha_atualizacao_preco',
    'df_origem_site_como_planilha',
    'df_origem_site',
    'df_site_bruto_cadastro',
    'df_site_bruto_estoque',
    'df_site_bruto_atualizacao_preco',
    'df_site_bruto',
    'cadastro_wizard_df_origem',
    'df_origem_cadastro',
    'df_origem_estoque',
)


def _clean(value: object) -> str:
    return str(value or '').strip().lower()


def _norm(value: object) -> str:
    text = _clean(value)
    for old, new in {
        'ã': 'a', 'á': 'a', 'à': 'a', 'â': 'a',
        'é': 'e', 'ê': 'e', 'í': 'i',
        'ó': 'o', 'ô': 'o', 'õ': 'o',
        'ú': 'u', 'ç': 'c',
    }.items():
        text = text.replace(old, new)
    return re.sub(r'\s+', ' ', re.sub(r'[^a-z0-9]+', ' ', text)).strip()


def _normalize_api_operation(value: object, *, default: str = '') -> str:
    text = _norm(value)
    if not text:
        return default
    underscored = text.replace(' ', '_')
    if underscored in CONCRETE_API_OPERATIONS:
        return underscored
    if 'estoque' in text or 'saldo' in text or 'stock' in text:
        return OP_ESTOQUE
    if 'preco' in text or 'price' in text:
        return OP_ATUALIZACAO_PRECO
    if 'cadastro' in text or 'catalogo' in text:
        return OP_CADASTRO
    return default


def _safe_state_set(key: str, value: object) -> None:
    try:
        st.session_state[key] = value
    except StreamlitAPIException:
        st.session_state.setdefault('flow_spine_widget_state_warnings', {})[key] = str(value)
    except Exception:
        pass


def _state_value(key: str) -> object:
    try:
        return st.session_state.get(key)
    except Exception:
        return None


def _state_text(key: str) -> str:
    return _clean(_state_value(key))


def _looks_like_loaded_df(value: object) -> bool:
    try:
        return bool(value is not None and not value.empty and len(value.columns) > 0)
    except Exception:
        return False


def _normalized_columns(value: object) -> list[str]:
    try:
        columns = list(getattr(value, 'columns', []))
    except Exception:
        return []
    return [_norm(column) for column in columns]


def _has_any(columns: list[str], terms: tuple[str, ...]) -> bool:
    return any(any(term in column for term in terms) for column in columns)


def _operation_from_dataframe(value: object) -> str:
    if not _looks_like_loaded_df(value):
        return ''
    columns = _normalized_columns(value)
    if not columns:
        return ''
    has_name = _has_any(columns, ('nome', 'descricao', 'produto', 'titulo'))
    has_price = _has_any(columns, ('preco', 'valor', 'unitario', 'venda'))
    has_image = _has_any(columns, ('imagem', 'imagens', 'foto'))
    has_category = _has_any(columns, ('categoria', 'departamento', 'grupo'))
    has_qty = _has_any(columns, ('quantidade', 'qtd', 'saldo', 'estoque', 'balanco', 'stock'))
    has_deposit = _has_any(columns, ('deposito', 'deposito id'))
    has_identifier = _has_any(columns, ('codigo', 'sku', 'gtin', 'ean', 'id bling', 'id produto'))
    stock_like_only = has_qty and has_identifier and not (has_name or has_price or has_image or has_category)
    price_like_only = has_price and has_identifier and not (has_name or has_qty or has_image or has_category)
    cadastro_like = has_name or has_image or has_category or (has_price and not stock_like_only)
    if stock_like_only or (has_qty and has_deposit and not cadastro_like):
        return OP_ESTOQUE
    if price_like_only:
        return OP_ATUALIZACAO_PRECO
    if cadastro_like:
        return OP_CADASTRO
    return ''


def _source_data_ready() -> bool:
    for key in SOURCE_DF_KEYS:
        if _looks_like_loaded_df(st.session_state.get(key)):
            return True
    try:
        from bling_app_zero.ui.universal_wizard_state import universal_context_ready

        return bool(universal_context_ready())
    except Exception:
        return False


def _site_capture_ready() -> bool:
    if bool(st.session_state.get('site_capture_finished')):
        return True
    if bool(st.session_state.get('blingsmartscan_ready_to_continue')):
        return True
    neutral_state = st.session_state.get('neutral_site_capture_state_v1')
    if isinstance(neutral_state, dict):
        result = neutral_state.get('result')
        if isinstance(result, dict) and int(result.get('rows') or 0) > 0:
            return True
    return False


def _source_first_operation_confirmed() -> bool:
    return bool(st.session_state.get(SOURCE_FIRST_CONFIRMED_KEY))


def _confirmed_source_first_operation() -> str:
    if not _source_first_operation_confirmed():
        return ''
    return _normalize_api_operation(st.session_state.get(SOURCE_FIRST_SELECTED_KEY))


def _source_first_choice_required() -> bool:
    if _source_data_ready() or _site_capture_ready():
        return True
    if bool(st.session_state.get('source_first_operation_pending_choice')):
        return True
    if SOURCE_FIRST_SELECTED_KEY in st.session_state or SOURCE_FIRST_CONFIRMED_KEY in st.session_state:
        return True
    return False


def _source_first_choice_pending() -> bool:
    if not _source_first_choice_required():
        return False
    return _confirmed_source_first_operation() not in CONCRETE_API_OPERATIONS


def active_mode() -> str:
    # A conexão OAuth apenas libera recursos. Ela nunca escolhe o fluxo.
    # O modo API curto exige uma escolha explícita registrada no finish mode.
    if bool(st.session_state.get(UNIFIED_BLING_SEND_KEY)):
        return 'api'
    finish = _clean(st.session_state.get(FINISH_MODE_KEY))
    return 'api' if finish in API_FINISH_MODES else 'csv'


def active_api_operation(default: str = '') -> str:
    """Resolve a operação concreta somente para envio API.

    BLINGFIX 2026-06-20:
    - No modo API não existe operação universal.
    - Depois que a origem foi carregada, a API fica pendente até o usuário escolher
      cadastro, estoque por depósito ou atualização de preços.
    - Chaves antigas em cache não valem sem source_first_operation_user_confirmed.
    """
    confirmed = _confirmed_source_first_operation()
    if confirmed in CONCRETE_API_OPERATIONS:
        return confirmed

    if _source_first_choice_pending():
        return ''

    # Compatibilidade: só usa sinais antigos quando ainda não é fluxo source-first.
    for key in API_OPERATION_STATE_KEYS:
        op = _normalize_api_operation(_state_value(key))
        if op in CONCRETE_API_OPERATIONS:
            return op

    joined_hints = ' '.join(_state_text(key) for key in API_OPERATION_HINT_KEYS)
    op = _normalize_api_operation(joined_hints)
    if op in CONCRETE_API_OPERATIONS:
        return op

    if not (_source_data_ready() or _site_capture_ready()):
        for key in API_OPERATION_DF_KEYS:
            op = _operation_from_dataframe(_state_value(key))
            if op in CONCRETE_API_OPERATIONS:
                return op

    return default if default in CONCRETE_API_OPERATIONS else ''


def active_operation() -> str:
    if active_mode() != 'api':
        return OP_UNIVERSAL
    return active_api_operation(default='') or OP_API_PENDING


def _api_contract_key(api_operation: str) -> str:
    return API_CONTRACT_BY_OPERATION.get(api_operation, OP_API_PENDING)


def _apply_runtime_state(contract: FeatureContract) -> None:
    api_operation = active_api_operation()
    _safe_state_set('active_feature_mode', contract.mode)
    _safe_state_set('active_feature_steps', list(contract.steps))

    if contract.mode == 'api':
        resolved_operation = api_operation if api_operation in CONCRETE_API_OPERATIONS else OP_API_PENDING
        contract_key = _api_contract_key(resolved_operation)
        _safe_state_set('active_feature_contract_key', contract_key)
        _safe_state_set('active_feature_operation', resolved_operation)
        _safe_state_set('flow_spine_contract_key', contract_key)
        _safe_state_set('flow_spine_operation', resolved_operation)
        _safe_state_set('flow_spine_final_destination', 'api_bling')
        _safe_state_set('flow_spine_final_title', 'Enviar' if api_operation else 'Escolher operação')
        _safe_state_set('flow_spine_primary_action_label', 'Enviar' if api_operation else 'Escolher operação')
        if api_operation in CONCRETE_API_OPERATIONS:
            _safe_state_set('direct_bling_operation_applied', api_operation)
            _safe_state_set('flow_spine_sender_operation', api_operation)
            _safe_state_set('flow_spine_operation_resolved_for_api', api_operation)
        else:
            _safe_state_set('direct_bling_operation_applied', '')
            _safe_state_set('flow_spine_sender_operation', '')
            _safe_state_set('flow_spine_operation_resolved_for_api', '')
        return

    _safe_state_set('active_feature_contract_key', 'universal_mapping')
    _safe_state_set('active_feature_operation', OP_UNIVERSAL)
    _safe_state_set('flow_spine_contract_key', 'universal_mapping')
    _safe_state_set('flow_spine_operation', OP_UNIVERSAL)
    _safe_state_set('flow_spine_primary_action_label', 'Download Modelo Mapeado')
    _safe_state_set('flow_spine_final_destination', 'download')
    _safe_state_set('flow_spine_final_title', 'Download')
    if bool(st.session_state.get(UNIFIED_BLING_SEND_KEY)) and api_operation in CONCRETE_API_OPERATIONS:
        _safe_state_set('flow_spine_sender_operation', api_operation)
        _safe_state_set('flow_spine_operation_resolved_for_api', api_operation)
        _safe_state_set('direct_bling_operation_applied', api_operation)


def active_contract() -> FeatureContract:
    mode = active_mode()
    operation = active_operation() if mode == 'api' else OP_UNIVERSAL
    contract = get_feature_contract(operation, mode)
    _apply_runtime_state(contract)
    return contract


def active_steps() -> list[str]:
    return list(active_contract().steps)


def step_allowed(step: str) -> bool:
    return str(step or '').strip().lower() in active_steps()


def feature_requires_destination_model() -> bool:
    """Retorna o requisito permanente do contrato, sem depender da etapa atual."""
    if bool(st.session_state.get(UNIFIED_BLING_SEND_KEY)):
        return False
    return bool(active_contract().needs_model)


def feature_needs_model() -> bool:
    if not feature_requires_destination_model():
        return False
    current_step = _clean(st.session_state.get(WIZARD_STEP_KEY))
    if current_step in SOURCE_FIRST_STEPS and not (_source_data_ready() or _site_capture_ready()):
        return False
    return True


def feature_needs_pricing() -> bool:
    return active_contract().needs_pricing


def feature_needs_mapping() -> bool:
    return active_contract().needs_mapping


def feature_needs_rules_review() -> bool:
    return active_contract().needs_rules_review


def feature_needs_download() -> bool:
    return active_contract().needs_download


def feature_primary_action_label() -> str:
    if active_mode() == 'api':
        return 'Enviar' if active_api_operation() else 'Escolher operação'
    return 'Download Modelo Mapeado'


__all__ = [
    'active_api_operation',
    'active_contract',
    'active_mode',
    'active_operation',
    'active_steps',
    'feature_needs_download',
    'feature_needs_mapping',
    'feature_needs_model',
    'feature_needs_pricing',
    'feature_needs_rules_review',
    'feature_primary_action_label',
    'feature_requires_destination_model',
    'step_allowed',
]
