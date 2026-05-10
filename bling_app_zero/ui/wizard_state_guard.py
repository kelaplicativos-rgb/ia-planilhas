from __future__ import annotations

import streamlit as st

WIZARD_STEP_KEY = 'bling_wizard_step'
FLOW_OPERATION_KEY = 'home_slim_flow_operation'
FLOW_ORIGIN_KEY = 'home_slim_flow_origin'
STATE_GUARD_VERSION_KEY = 'bling_wizard_state_guard_version'
STATE_GUARD_VERSION = '2026-05-09-wizard-pro-1'

VALID_STEPS = {
    'modelo',
    'operacao',
    'precificacao',
    'origem',
    'entrada',
    'mapeamento',
    'gerar_estoque',
    'preview',
    'download',
}
VALID_OPERATIONS = {'cadastro', 'estoque'}
VALID_ORIGINS = {'arquivo', 'site'}

LEGACY_WIDGET_PREFIXES = (
    'frontpage_origin_radio_',
    'cadastro_manual_mapping_',
    'estoque_manual_mapping_from_cadastro_',
)

CURRENT_WIDGET_PREFIXES = (
    'frontpage_origin_radio_cadastro',
    'frontpage_origin_radio_estoque',
    'cad_map_',
    'stk_map_',
)

DANGEROUS_LEGACY_KEYS = {
    'frontpage_origin_radio',
    'home_slim_active_panel',
    'origem_dados',
    'origem_tipo',
    'etapa_origem',
    'etapa_fluxo',
    'etapa',
    'operation_site',
}


def _is_legacy_widget_key(key: str) -> bool:
    if key in DANGEROUS_LEGACY_KEYS:
        return True
    if key.startswith(CURRENT_WIDGET_PREFIXES):
        return False
    return key.startswith(LEGACY_WIDGET_PREFIXES)


def _normalize_scalar_state() -> None:
    step = str(st.session_state.get(WIZARD_STEP_KEY) or 'modelo').strip().lower()
    if step not in VALID_STEPS:
        st.session_state[WIZARD_STEP_KEY] = 'modelo'

    operation = str(st.session_state.get(FLOW_OPERATION_KEY) or '').strip().lower()
    if operation and operation not in VALID_OPERATIONS:
        st.session_state.pop(FLOW_OPERATION_KEY, None)
        st.session_state.pop('operacao_final', None)
        st.session_state.pop('tipo_operacao_final', None)

    origin = str(st.session_state.get(FLOW_ORIGIN_KEY) or '').strip().lower()
    if origin and origin not in VALID_ORIGINS:
        st.session_state.pop(FLOW_ORIGIN_KEY, None)
        st.session_state.pop('origem_final', None)
        st.session_state.pop('tipo_operacao_site', None)


def _clear_legacy_widgets() -> None:
    for key in list(st.session_state.keys()):
        text = str(key)
        if _is_legacy_widget_key(text):
            st.session_state.pop(text, None)


def run_wizard_state_guard(force: bool = False) -> None:
    """Limpa estados antigos que quebram widgets dinâmicos do Streamlit.

    A limpeza é controlada e preserva dados importantes atuais:
    - modelos carregados;
    - origem capturada;
    - df_final;
    - mapeamentos atuais cad_map_/stk_map_;
    - uploads atuais do smart_upload.
    """
    current_version = st.session_state.get(STATE_GUARD_VERSION_KEY)
    if force or current_version != STATE_GUARD_VERSION:
        _clear_legacy_widgets()
        st.session_state[STATE_GUARD_VERSION_KEY] = STATE_GUARD_VERSION
    _normalize_scalar_state()
