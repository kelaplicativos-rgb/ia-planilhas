from __future__ import annotations

import streamlit as st

from bling_app_zero.core.audit import add_audit_event
from bling_app_zero.ui.ai_real_advanced_panel import render_ai_real_advanced_panel
from bling_app_zero.ui.cadastro_wizard_state import (
    CADASTRO_MODELO_KEY,
    CADASTRO_ORIGEM_KEY,
    CADASTRO_ORIGEM_PRICED_KEY,
)
from bling_app_zero.ui.cadastro_wizard_steps import (
    render_universal_download_step,
    render_universal_entrada_step,
    render_universal_mapeamento_step,
    render_universal_preview_step,
    universal_context_ready,
    universal_mapping_ready,
)
from bling_app_zero.ui.home_pricing_config import (
    disable_home_pricing,
    get_home_pricing_config,
    render_home_pricing_config_form,
    set_home_pricing_config,
)
from bling_app_zero.ui.home_wizard_constants import (
    CADASTRO_STEPS,
    ESTOQUE_STEPS,
    STEP_DOWNLOAD,
    STEP_ENTRADA,
    STEP_GERAR_ESTOQUE,
    STEP_MAPEAMENTO,
    STEP_MODELO,
    STEP_ORIGEM,
    STEP_PRECIFICACAO,
    STEP_PREVIEW,
    STEP_REGRAS,
    WIZARD_STEP_KEY,
)
from bling_app_zero.ui.home_wizard_review import render_final_checker, render_safe_fixes
from bling_app_zero.ui.home_wizard_scroll import inject_scroll_to_target, render_step_anchor, set_scroll_target
from bling_app_zero.ui.home_wizard_state import (
    HOME_CHOICE_TARGET,
    SINGLE_PAGE_FLOW,
    UNIVERSAL_OPERATION,
    UNIVERSAL_REVIEW_OPERATION,
    UNIVERSAL_STEPS,
    came_from_bling_quick_model,
    clear_stale_cadastro_operation_state,
    current_origin_choice,
    ensure_universal_operation_state,
    has_home_models,
    looks_like_loaded_df,
    reset_wizard,
    select_origin,
    wizard_next_target,
    wizard_previous_target,
    wizard_steps_for_operation,
)
from bling_app_zero.ui.home_wizard_ui import render_pending_notice
from bling_app_zero.ui.mapping_review_panel import render_mapping_review_panel
from bling_app_zero.ui.rules_center_step import render_rules_center_step
from bling_app_zero.ui.scroll_guard import inject_scroll_guard

RESPONSIBLE_FILE = 'bling_app_zero/ui/home_wizard.py'


def _section_title(number: int, title: str) -> None:
    st.markdown('---')
    st.markdown(f'### {number}. {title}')


def _render_model_step() -> None:
    from bling_app_zero.ui.home_models import render_home_bling_models

    render_step_anchor(STEP_MODELO)
    _section_title(1, 'Modelos Universal')
    with st.container(border=True):
        render_home_bling_models()
    ensure_universal_operation_state()


def _render_origin_step(section_number: int = 2) -> None:
    render_step_anchor(STEP_ORIGEM)
    _section_title(section_number, 'Origem dos dados')
    if not has_home_models():
        render_pending_notice('Liberado após anexar o modelo.')
        return
    ensure_universal_operation_state()
    selected = current_origin_choice()
    col1, col2 = st.columns(2)
    with col1:
        if st.button('📎 Arquivo', use_container_width=True, key='origin_choose_file'):
            select_origin('arquivo', set_scroll_target=set_scroll_target)
    with col2:
        if st.button('🌐 Site', use_container_width=True, key='origin_choose_site'):
            select_origin('site', set_scroll_target=set_scroll_target)
    if selected in {'arquivo', 'site'}:
        st.success('Origem selecionada.')
    else:
        render_pending_notice('Escolha Arquivo ou Site.')


def _render_universal_entrada(section_number: int = 3) -> None:
    origin = current_origin_choice()
    render_step_anchor(STEP_ENTRADA)
    _section_title(section_number, 'Dados do fornecedor')
    if not has_home_models():
        render_pending_notice('Liberado após anexar o modelo.')
        return
    if origin not in {'arquivo', 'site'}:
        render_pending_notice('Escolha a origem primeiro.')
        return
    add_audit_event(
        'single_page_origin_data_rendered',
        area='UNIVERSAL',
        step=STEP_ENTRADA,
        details={
            'origin': origin,
            'operation': UNIVERSAL_OPERATION,
            'single_page_flow': SINGLE_PAGE_FLOW,
            'responsible_file': RESPONSIBLE_FILE,
        },
    )
    if origin == 'site':
        from bling_app_zero.ui.site_panel import render_site_panel

        render_site_panel()
    render_universal_entrada_step()


def _render_pricing_step(section_number: int = 4) -> None:
    render_step_anchor(STEP_PRECIFICACAO)
    _section_title(section_number, 'Preço')
    if not has_home_models():
        render_pending_notice('Liberado após anexar o modelo.')
        return
    if not universal_context_ready():
        render_pending_notice('Carregue os dados primeiro.')
        return
    current_config = get_home_pricing_config()
    use_pricing = st.toggle('Usar calculadora', value=bool(current_config.get('enabled', False)), key='home_pricing_enabled_toggle')
    if use_pricing:
        with st.container(border=True):
            config = render_home_pricing_config_form()
            set_home_pricing_config(config)
    else:
        disable_home_pricing()
        st.caption('Opcional. Se desligada, mantém o preço da origem ou do mapeamento.')


def _render_universal_mapeamento(section_number: int = 5) -> None:
    render_step_anchor(STEP_MAPEAMENTO)
    _section_title(section_number, 'Mapear campos')
    if not has_home_models():
        render_pending_notice('Liberado após modelo e dados.')
        return
    if not universal_context_ready():
        render_pending_notice('Carregue os dados primeiro.')
        return
    render_universal_mapeamento_step()


def _render_ai_review_step(section_number: int = 6) -> None:
    render_step_anchor(STEP_REGRAS)
    _section_title(section_number, 'Revisão final')
    if not has_home_models():
        render_pending_notice('Liberado após modelo e mapeamento.')
        return
    if not universal_mapping_ready():
        render_pending_notice('Confirme o mapeamento manual primeiro.')
        return

    df_source = st.session_state.get(CADASTRO_ORIGEM_PRICED_KEY)
    if not looks_like_loaded_df(df_source):
        df_source = st.session_state.get(CADASTRO_ORIGEM_KEY)
    df_modelo = st.session_state.get(CADASTRO_MODELO_KEY)

    st.caption('Revise os campos ligados e aplique as proteções finais antes do preview.')
    render_mapping_review_panel(
        operation=UNIVERSAL_REVIEW_OPERATION,
        mapping=st.session_state.get('mapping_cadastro'),
        confidence=st.session_state.get('mapping_confidence_cadastro'),
        df_source=df_source,
        target_columns=[str(column) for column in getattr(df_modelo, 'columns', [])],
    )

    render_final_checker(df_source, df_modelo)
    render_safe_fixes()
    render_ai_real_advanced_panel()

    st.markdown('#### Ajustes avançados do arquivo final')
    render_rules_center_step()


def _render_universal_preview(section_number: int = 7) -> None:
    render_step_anchor(STEP_PREVIEW)
    _section_title(section_number, 'Preview')
    if not has_home_models():
        render_pending_notice('Liberado após o mapeamento.')
        return
    if not universal_mapping_ready():
        render_pending_notice('Confirme o mapeamento primeiro.')
        return
    render_universal_preview_step()


def _render_universal_download(section_number: int = 8) -> None:
    render_step_anchor(STEP_DOWNLOAD)
    _section_title(section_number, 'Download')
    if not has_home_models():
        render_pending_notice('Liberado no final.')
        return
    if not universal_mapping_ready():
        render_pending_notice('Confirme o mapeamento primeiro.')
        return
    clear_stale_cadastro_operation_state()
    render_universal_download_step()
    if st.button('Recomeçar fluxo', use_container_width=True, key='wizard_download_reset_single_page'):
        reset_wizard()


def render_home_wizard() -> None:
    inject_scroll_guard('home_wizard')
    has_model = has_home_models()
    operation = ensure_universal_operation_state()
    st.session_state['wizard_bottom_nav_rendered_current_cycle'] = True
    st.session_state['home_single_page_flow_active'] = True

    if not has_model:
        st.session_state[WIZARD_STEP_KEY] = STEP_MODELO
        st.session_state.pop('home_slim_flow_origin', None)
        add_audit_event(
            'wizard_model_first_guard_active',
            area='WIZARD',
            step=STEP_MODELO,
            details={'reason': 'missing_destination_model', 'single_page_flow': SINGLE_PAGE_FLOW, 'responsible_file': RESPONSIBLE_FILE},
        )
        _render_model_step()
        inject_scroll_to_target()
        return

    start_at_origin = came_from_bling_quick_model()
    add_audit_event(
        'wizard_single_page_rendered',
        area='WIZARD',
        step='single_page',
        details={
            'operation': operation or 'universal',
            'steps': UNIVERSAL_STEPS,
            'single_page_flow': SINGLE_PAGE_FLOW,
            'skip_model_step': start_at_origin,
            'responsible_file': RESPONSIBLE_FILE,
        },
    )

    if start_at_origin:
        _render_origin_step(1)
        _render_universal_entrada(2)
        _render_pricing_step(3)
        _render_universal_mapeamento(4)
        _render_ai_review_step(5)
        _render_universal_preview(6)
        _render_universal_download(7)
        inject_scroll_to_target()
        return

    _render_model_step()
    _render_origin_step()
    _render_universal_entrada()
    _render_pricing_step()
    _render_universal_mapeamento()
    _render_ai_review_step()
    _render_universal_preview()
    _render_universal_download()
    inject_scroll_to_target()


__all__ = [
    'CADASTRO_STEPS',
    'ESTOQUE_STEPS',
    'HOME_CHOICE_TARGET',
    'STEP_DOWNLOAD',
    'STEP_GERAR_ESTOQUE',
    'STEP_MAPEAMENTO',
    'STEP_REGRAS',
    'render_home_wizard',
    'wizard_next_target',
    'wizard_previous_target',
    'wizard_steps_for_operation',
]
