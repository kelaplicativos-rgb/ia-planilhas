from __future__ import annotations

import html

import streamlit as st

from bling_app_zero.ui.home_flow import deactivate_panel, get_active_panel, step_to_panel_operation
from bling_app_zero.ui.home_pricing_config import disable_home_pricing, render_home_pricing_config_form, set_home_pricing_config
from bling_app_zero.ui.lazy_panels import render_lazy_panel
from bling_app_zero.ui.layout import (
    close_home_start_card,
    inject_app_layout,
    render_compact_hero,
    render_home_start_card,
)

HOME_STAGE_KEY = 'home_stage'
STAGE_START = 'inicio'
STAGE_MODELOS = 'modelos'
STAGE_PRECIFICACAO = 'precificacao'

HOME_CADASTRO_MODEL_KEY = 'home_modelo_cadastro_df'
HOME_ESTOQUE_MODEL_KEY = 'home_modelo_estoque_df'
GLOBAL_CADASTRO_MODEL_KEYS = ['df_modelo_cadastro', 'modelo_cadastro_df']
GLOBAL_ESTOQUE_MODEL_KEYS = ['df_modelo_estoque', 'modelo_estoque_df']


def _looks_like_loaded_df(value: object) -> bool:
    if value is None or not hasattr(value, 'columns'):
        return False
    try:
        return len(getattr(value, 'columns', [])) > 0
    except Exception:
        return False


def _has_any_model(keys: list[str]) -> bool:
    return any(_looks_like_loaded_df(st.session_state.get(key)) for key in keys)


def _has_home_models_light() -> bool:
    keys = [HOME_CADASTRO_MODEL_KEY, HOME_ESTOQUE_MODEL_KEY] + GLOBAL_CADASTRO_MODEL_KEYS + GLOBAL_ESTOQUE_MODEL_KEYS
    return _has_any_model(keys)


def _preferred_operation_from_models() -> str:
    has_cadastro = _has_any_model([HOME_CADASTRO_MODEL_KEY] + GLOBAL_CADASTRO_MODEL_KEYS)
    has_estoque = _has_any_model([HOME_ESTOQUE_MODEL_KEY] + GLOBAL_ESTOQUE_MODEL_KEYS)
    if has_estoque and not has_cadastro:
        return 'estoque'
    return 'cadastro'


def _open_next_panel() -> None:
    operation = _preferred_operation_from_models()
    st.session_state['home_slim_flow_operation'] = operation
    st.session_state['home_slim_flow_origin'] = 'site'
    st.session_state['home_slim_active_panel'] = f'{operation}_site'
    st.session_state['operacao_final'] = operation
    st.session_state['tipo_operacao_final'] = operation
    st.session_state['tipo_operacao_site'] = operation
    st.session_state['origem_final'] = 'site'
    st.session_state['selected_flow_label'] = 'Estoque por site' if operation == 'estoque' else 'Cadastro por site'


def _render_selected_flow_badge(active_panel: str) -> None:
    label = st.session_state.get('selected_flow_label')
    if not label:
        if active_panel == 'estoque_site':
            label = 'Estoque por site'
        elif active_panel == 'cadastro_site':
            label = 'Cadastro por site'
        elif active_panel == 'estoque':
            label = 'Estoque por arquivo'
        elif active_panel == 'cadastro':
            label = 'Cadastro por arquivo'
        else:
            label = 'Fluxo selecionado'

    safe_label = html.escape(str(label))
    st.markdown(
        f'<div class="bling-selected-flow-badge"><span class="bling-selected-flow-dot"></span>Selecionado: {safe_label}</div>',
        unsafe_allow_html=True,
    )


def _render_home_bling_models_lazy() -> None:
    from bling_app_zero.ui.home_models import render_home_bling_models

    render_home_bling_models()


def _has_home_models_strict() -> bool:
    from bling_app_zero.ui.home_models import has_home_models

    return has_home_models()


def _current_home_stage() -> str:
    stage = str(st.session_state.get(HOME_STAGE_KEY) or '')
    valid = {STAGE_START, STAGE_MODELOS, STAGE_PRECIFICACAO}
    if stage in valid:
        return stage
    if _has_home_models_light():
        return STAGE_PRECIFICACAO
    return STAGE_START


def _set_home_stage(stage: str) -> None:
    if stage not in {STAGE_START, STAGE_MODELOS, STAGE_PRECIFICACAO}:
        stage = STAGE_START
    st.session_state[HOME_STAGE_KEY] = stage


def _centered_button(label: str, key: str, disabled: bool = False) -> bool:
    left, middle, right = st.columns([1, 1.65, 1])
    with middle:
        return st.button(label, use_container_width=True, key=key, disabled=disabled)


def _centered_two_buttons(left_label: str, left_key: str, right_label: str, right_key: str) -> tuple[bool, bool]:
    _pad_l, col_l, col_r, _pad_r = st.columns([0.8, 1.35, 1.35, 0.8])
    with col_l:
        left_clicked = st.button(left_label, use_container_width=True, key=left_key)
    with col_r:
        right_clicked = st.button(right_label, use_container_width=True, key=right_key)
    return left_clicked, right_clicked


def _render_home_start() -> None:
    render_home_start_card()
    if _centered_button('Começar agora', key='home_start_open_models'):
        _set_home_stage(STAGE_MODELOS)
        st.rerun()
    close_home_start_card()


def _render_home_models_step() -> None:
    _render_home_bling_models_lazy()

    back_clicked, continue_clicked = _centered_two_buttons('← Voltar', 'home_models_back', 'Continuar', 'home_models_continue')
    if back_clicked:
        _set_home_stage(STAGE_START)
        st.rerun()
    if continue_clicked:
        if not _has_home_models_strict():
            st.warning('Anexe o modelo do Bling: cadastro, estoque ou ambos.')
        else:
            _set_home_stage(STAGE_PRECIFICACAO)
            st.rerun()


def _render_pricing_choice_step() -> None:
    pricing_config = render_home_pricing_config_form()

    save_clicked, no_pricing_clicked = _centered_two_buttons(
        'Salvar preço e continuar',
        'home_pricing_save_continue',
        'Continuar sem calcular preço',
        'home_pricing_disable_continue',
    )
    if save_clicked:
        set_home_pricing_config(pricing_config)
        _open_next_panel()
        st.rerun()
    if no_pricing_clicked:
        disable_home_pricing()
        _open_next_panel()
        st.rerun()

    if _centered_button('← Voltar aos modelos', key='home_pricing_back'):
        _set_home_stage(STAGE_MODELOS)
        st.rerun()


def _render_home_intro() -> None:
    stage = _current_home_stage()
    if stage == STAGE_MODELOS:
        _render_home_models_step()
        return
    if stage == STAGE_PRECIFICACAO:
        _render_pricing_choice_step()
        return
    _render_home_start()


def _render_back_home() -> None:
    if _centered_button('← Voltar para modelos', key='home_back_to_light_start'):
        deactivate_panel()
        st.session_state.pop('selected_flow_label', None)
        _set_home_stage(STAGE_MODELOS if _has_home_models_light() else STAGE_START)
        st.rerun()


def render_home() -> None:
    inject_app_layout()
    render_compact_hero()

    active_panel = get_active_panel()
    if not active_panel:
        _render_home_intro()
        return

    _render_selected_flow_badge(active_panel)
    _render_back_home()
    render_lazy_panel(step_to_panel_operation(active_panel))
