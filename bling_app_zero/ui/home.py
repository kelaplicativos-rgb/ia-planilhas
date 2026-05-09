from __future__ import annotations

import html

import streamlit as st

from bling_app_zero.flows.site_as_source import get_site_source_for_operation
from bling_app_zero.ui.home_pricing_config import (
    disable_home_pricing,
    render_home_pricing_config_form,
    set_home_pricing_config,
)
from bling_app_zero.ui.layout import inject_app_layout, render_compact_hero

HOME_CADASTRO_MODEL_KEY = 'home_modelo_cadastro_df'
HOME_ESTOQUE_MODEL_KEY = 'home_modelo_estoque_df'
GLOBAL_CADASTRO_MODEL_KEYS = ['df_modelo_cadastro', 'modelo_cadastro_df']
GLOBAL_ESTOQUE_MODEL_KEYS = ['df_modelo_estoque', 'modelo_estoque_df']
FLOW_ORIGIN_KEY = 'home_slim_flow_origin'
FLOW_OPERATION_KEY = 'home_slim_flow_operation'
FLOW_ACTIVE_KEY = 'home_slim_active_panel'


def _looks_like_loaded_df(value: object) -> bool:
    if value is None or not hasattr(value, 'columns'):
        return False
    try:
        return len(getattr(value, 'columns', [])) > 0
    except Exception:
        return False


def _has_any_model(keys: list[str]) -> bool:
    return any(_looks_like_loaded_df(st.session_state.get(key)) for key in keys)


def _preferred_operation_from_models() -> str:
    has_cadastro = _has_any_model([HOME_CADASTRO_MODEL_KEY] + GLOBAL_CADASTRO_MODEL_KEYS)
    has_estoque = _has_any_model([HOME_ESTOQUE_MODEL_KEY] + GLOBAL_ESTOQUE_MODEL_KEYS)
    if has_estoque and not has_cadastro:
        return 'estoque'
    return 'cadastro'


def _render_home_bling_models_lazy() -> None:
    from bling_app_zero.ui.home_models import render_home_bling_models

    render_home_bling_models()


def _render_section_card(kicker: str, title: str, text: str) -> None:
    st.markdown(
        f"""
        <section class="bling-flow-card">
            <div class="bling-flow-card-kicker">{html.escape(kicker)}</div>
            <h2 class="bling-flow-card-title">{html.escape(title)}</h2>
            <p class="bling-flow-card-text">{html.escape(text)}</p>
        </section>
        """,
        unsafe_allow_html=True,
    )


def _sync_flow_state(origin: str, operation: str) -> None:
    origin = 'arquivo' if origin == 'arquivo' else 'site'
    operation = 'estoque' if operation == 'estoque' else 'cadastro'
    st.session_state[FLOW_ORIGIN_KEY] = origin
    st.session_state[FLOW_OPERATION_KEY] = operation
    st.session_state.pop(FLOW_ACTIVE_KEY, None)
    st.session_state['operacao_final'] = operation
    st.session_state['tipo_operacao_final'] = operation
    st.session_state['origem_final'] = origin
    st.session_state['tipo_operacao_site'] = operation if origin == 'site' else ''
    try:
        st.query_params['origem'] = origin
        st.query_params['operacao'] = operation
        st.query_params['flow'] = 'site' if origin == 'site' else 'planilha'
    except Exception:
        pass


def _current_origin_choice() -> str:
    current = str(st.session_state.get(FLOW_ORIGIN_KEY) or '').strip().lower()
    if current in {'arquivo', 'site'}:
        return current

    try:
        origem = str(st.query_params.get('origem', '') or '').strip().lower()
        flow = str(st.query_params.get('flow', '') or '').strip().lower()
    except Exception:
        origem = ''
        flow = ''

    if origem in {'arquivo', 'planilha', 'planilhas', 'xml', 'pdf'}:
        return 'arquivo'
    if origem == 'site':
        return 'site'
    if flow in {'arquivo', 'planilha', 'planilhas', 'xml', 'pdf'}:
        return 'arquivo'
    if flow == 'site':
        return 'site'
    return ''


def _render_pricing_frontpage() -> None:
    _render_section_card(
        'Precificação',
        'Preço de venda opcional',
        'Preencha se quiser que o sistema calcule o preço de venda antes do mapeamento. Se não quiser usar, deixe desativado.',
    )
    use_pricing = st.toggle(
        'Usar calculadora de preço',
        value=bool(st.session_state.get('home_precificacao_inicial', False)),
        key='home_pricing_enabled_toggle',
    )
    if use_pricing:
        config = render_home_pricing_config_form()
        set_home_pricing_config(config)
    else:
        disable_home_pricing()


def _render_origin_frontpage() -> str:
    operation = _preferred_operation_from_models()
    operation_label = 'atualização de estoque' if operation == 'estoque' else 'cadastro de produtos'
    _render_section_card(
        'Origem dos dados',
        'Escolha como os produtos entram no sistema',
        f'No fluxo de {operation_label}, você pode anexar planilha/XML/PDF do fornecedor ou informar links para buscar os dados por site.',
    )

    selected = _current_origin_choice()
    options = {
        'arquivo': '📎 Anexar planilha/XML/PDF do fornecedor',
        'site': '🌐 Buscar por site/link',
    }
    labels = list(options.values())
    values = list(options.keys())
    index = values.index(selected) if selected in values else None

    st.caption('Selecione uma das opções abaixo:')
    choice_label = st.radio(
        'Origem dos dados',
        labels,
        index=index,
        key='frontpage_origin_radio',
        label_visibility='collapsed',
    )

    if choice_label is None:
        return ''

    choice = values[labels.index(choice_label)]
    _sync_flow_state(choice, operation)
    return choice


def _render_operation_panel(operation: str) -> None:
    if operation == 'estoque':
        from bling_app_zero.ui.estoque_panel import render_estoque_panel

        render_estoque_panel()
        return

    from bling_app_zero.ui.cadastro_panel_modular import render_cadastro_panel

    render_cadastro_panel()


def _render_inline_data_entry(origin: str) -> None:
    operation = _preferred_operation_from_models()
    if not origin:
        st.info('Escolha a origem dos dados acima. A entrada, o mapeamento, o preview e o download aparecem aqui mesmo, na tela principal.')
        return

    operation_label = 'Estoque' if operation == 'estoque' else 'Cadastro'
    origin_label = 'site/link' if origin == 'site' else 'planilha/arquivo'
    st.markdown(
        f'<div class="bling-selected-flow-badge"><span class="bling-selected-flow-dot"></span>{operation_label} por {origin_label}</div>',
        unsafe_allow_html=True,
    )

    if origin == 'site':
        from bling_app_zero.ui.site_panel import render_site_panel

        render_site_panel()
        df_site_source = get_site_source_for_operation(operation)
        if df_site_source is not None:
            _render_section_card(
                'Mapeamento e download',
                'Origem do site pronta',
                'A busca por site virou uma origem interna. O mapeamento, preview e CSV final aparecem logo abaixo, sem trocar de tela.',
            )
            _render_operation_panel(operation)
        return

    _render_operation_panel(operation)


def render_home() -> None:
    inject_app_layout()
    render_compact_hero()

    _render_section_card(
        'Modelos do Bling',
        'Envie o modelo uma vez e siga rolando',
        'O modelo define as colunas que o sistema precisa preencher. Pode enviar cadastro, estoque ou ambos.',
    )
    _render_home_bling_models_lazy()

    _render_pricing_frontpage()
    origin = _render_origin_frontpage()
    _render_inline_data_entry(origin)
