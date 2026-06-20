from __future__ import annotations

import streamlit as st

from bling_app_zero.core.audit import add_audit_event
from bling_app_zero.ui.flow_context import CONTEXT_BLING_API, activate_csv_finish_mode, entry_context as _entry_context, finish_mode as _finish_mode
from bling_app_zero.ui.home_bling_api_flow import render_bling_connection_step
from bling_app_zero.ui.home_wizard_constants import (
    CADASTRO_STEPS,
    ESTOQUE_STEPS,
    HOME_CHOICE_TARGET,
    STEP_DOWNLOAD,
    STEP_ENTRADA,
    STEP_GERAR_ESTOQUE,
    STEP_LABELS,
    STEP_MAPEAMENTO,
    STEP_MODELO,
    STEP_OPERACAO,
    STEP_ORIGEM,
    STEP_PRECIFICACAO,
    STEP_PREVIEW,
    STEP_REGRAS,
    WIZARD_STEP_KEY,
)
from bling_app_zero.ui.home_wizard_pricing_step import render_pricing_step
from bling_app_zero.ui.home_wizard_rerun import safe_rerun, set_step_without_rerun
from bling_app_zero.ui.home_wizard_scroll import inject_scroll_to_target, render_step_anchor
from bling_app_zero.ui.home_wizard_state import (
    clear_stale_cadastro_operation_state,
    current_origin_choice,
    ensure_universal_operation_state,
    has_home_models,
    reset_wizard,
    select_origin,
    wizard_next_target,
    wizard_previous_target,
    wizard_steps_for_operation,
)
from bling_app_zero.ui.home_wizard_ui import render_pending_notice
from bling_app_zero.ui.rules_center_step import render_rules_center_step
from bling_app_zero.ui.scroll_guard import inject_scroll_guard
from bling_app_zero.ui.source_first_operation_gate import (
    clear_inferred_operation_until_user_chooses,
    operation_ready,
    render_operation_gate,
    selected_operation,
    source_data_ready,
)
from bling_app_zero.ui.universal_download_step import render_universal_download_step
from bling_app_zero.ui.universal_entry_step import render_universal_entrada_step
from bling_app_zero.ui.universal_mapping_step import render_universal_mapeamento_step
from bling_app_zero.ui.universal_preview_step import render_universal_preview_step
from bling_app_zero.ui.universal_wizard_state import universal_context_ready, universal_mapping_ready

RESPONSIBLE_FILE = 'bling_app_zero/ui/home_wizard.py'
OP_CADASTRO = 'cadastro'
OP_ESTOQUE = 'estoque'
OP_PRECO = 'atualizacao_preco'


def _section_title(number: int, title: str) -> None:
    st.markdown('---')
    st.markdown(f'### {number}. {title}')


def _label(step: str) -> str:
    return str(STEP_LABELS.get(step, step)).strip()


def _steps() -> list[str]:
    steps = [STEP_ORIGEM, STEP_ENTRADA, STEP_OPERACAO]
    op = selected_operation()
    if op == OP_ESTOQUE:
        steps += [STEP_MAPEAMENTO, STEP_PREVIEW, STEP_DOWNLOAD]
    elif op == OP_PRECO:
        steps += [STEP_PRECIFICACAO, STEP_MAPEAMENTO, STEP_PREVIEW, STEP_DOWNLOAD]
    elif op == OP_CADASTRO:
        steps += [STEP_PRECIFICACAO, STEP_MAPEAMENTO, STEP_REGRAS, STEP_PREVIEW, STEP_DOWNLOAD]
    return steps


def _go(step: str) -> None:
    if step in _steps():
        set_step_without_rerun(step)


def _done(step: str) -> bool:
    if step == STEP_ORIGEM:
        return current_origin_choice() in {'arquivo', 'site'}
    if step == STEP_ENTRADA:
        return source_data_ready()
    if step == STEP_OPERACAO:
        return operation_ready()
    if step == STEP_PRECIFICACAO:
        return True
    if step in {STEP_MAPEAMENTO, STEP_REGRAS, STEP_PREVIEW, STEP_DOWNLOAD}:
        return universal_mapping_ready()
    return False


def _active_step() -> str:
    current = str(st.session_state.get(WIZARD_STEP_KEY) or STEP_ORIGEM).strip().lower()
    if source_data_ready() and not operation_ready() and current not in {STEP_ORIGEM, STEP_ENTRADA, STEP_OPERACAO}:
        return STEP_OPERACAO
    if current in {STEP_ORIGEM, STEP_ENTRADA} and source_data_ready() and not operation_ready():
        return STEP_OPERACAO
    return current if current in _steps() else _steps()[0]


def _render_origin(n: int) -> None:
    render_step_anchor(STEP_ORIGEM)
    _section_title(n, _label(STEP_ORIGEM))
    ensure_universal_operation_state()
    st.caption('Primeiro escolha e carregue a origem. Esta etapa não define cadastro, estoque ou preço.')
    col1, col2 = st.columns(2)
    with col1:
        if st.button('📎 Arquivo', use_container_width=True, key='origin_choose_file'):
            select_origin('arquivo', set_scroll_target=None)
    with col2:
        if st.button('🌐 Site', use_container_width=True, key='origin_choose_site'):
            select_origin('site', set_scroll_target=None)
    st.success('Origem selecionada.') if current_origin_choice() in {'arquivo', 'site'} else render_pending_notice('Escolha Arquivo ou Site.')


def _render_entrada(n: int) -> None:
    render_step_anchor(STEP_ENTRADA)
    _section_title(n, _label(STEP_ENTRADA))
    origin = current_origin_choice()
    if origin not in {'arquivo', 'site'}:
        render_pending_notice('Escolha a origem primeiro.')
        return
    if origin == 'site':
        from bling_app_zero.ui.site_panel import render_site_panel
        render_site_panel()
    else:
        render_universal_entrada_step()


def _render_map(n: int) -> None:
    render_step_anchor(STEP_MAPEAMENTO)
    _section_title(n, _label(STEP_MAPEAMENTO))
    if not operation_ready():
        render_pending_notice('Escolha a operação e confirme os obrigatórios primeiro.')
        return
    render_universal_mapeamento_step()


def _render_rules(n: int) -> None:
    render_step_anchor(STEP_REGRAS)
    _section_title(n, _label(STEP_REGRAS))
    if selected_operation() != OP_CADASTRO:
        st.info('Esta etapa é exclusiva do cadastro.')
        return
    render_rules_center_step()


def _render_preview(n: int) -> None:
    render_step_anchor(STEP_PREVIEW)
    _section_title(n, _label(STEP_PREVIEW))
    render_universal_preview_step()


def _render_download(n: int) -> None:
    render_step_anchor(STEP_DOWNLOAD)
    _section_title(n, _label(STEP_DOWNLOAD))
    clear_stale_cadastro_operation_state()
    render_universal_download_step()
    if st.button('Recomeçar fluxo', use_container_width=True, key='wizard_download_reset_single_page'):
        reset_wizard()


def _render_step(step: str, n: int) -> None:
    if step == STEP_ORIGEM:
        _render_origin(n)
    elif step == STEP_ENTRADA:
        _render_entrada(n)
    elif step == STEP_OPERACAO:
        render_operation_gate(_section_title, n)
    elif step == STEP_PRECIFICACAO:
        render_pricing_step(section_number=n, step_key=STEP_PRECIFICACAO, section_title=_section_title, model_available=True, is_price_update=selected_operation() == OP_PRECO, is_api_direct=True, is_universal_entry=False, render_price_update_notice=lambda: None)
    elif step == STEP_MAPEAMENTO:
        _render_map(n)
    elif step == STEP_REGRAS:
        _render_rules(n)
    elif step == STEP_PREVIEW:
        _render_preview(n)
    elif step == STEP_DOWNLOAD:
        _render_download(n)


def _nav(step: str) -> None:
    steps = _steps()
    idx = steps.index(step)
    st.caption(f'Etapa {idx + 1} de {len(steps)} · {_label(step)}')
    st.progress(max(1, min(100, int(((idx + 1) / len(steps)) * 100))))
    st.markdown('---')
    prev_step = steps[idx - 1] if idx > 0 else ''
    next_step = steps[idx + 1] if idx + 1 < len(steps) else ''
    col1, col2 = st.columns(2)
    with col1:
        if prev_step and st.button('⬅️ Voltar', use_container_width=True, key=f'wizard_local_back_{step}'):
            _go(prev_step)
            safe_rerun('wizard_back_clicked', target_step=prev_step)
    with col2:
        if next_step:
            if _done(step):
                if st.button(f'Próximo: {_label(next_step)}', use_container_width=True, key=f'wizard_local_next_{step}'):
                    _go(next_step)
                    safe_rerun('wizard_next_clicked', target_step=next_step)
            else:
                st.caption(f'🔒 Próximo bloqueado: {_label(next_step)}')


def render_home_wizard() -> None:
    inject_scroll_guard('home_wizard')
    clear_inferred_operation_until_user_chooses()
    context = _entry_context()
    st.session_state['wizard_bottom_nav_rendered_current_cycle'] = True
    st.session_state['home_single_page_flow_active'] = True
    if context == CONTEXT_BLING_API:
        render_bling_connection_step(_section_title)
        if not _finish_mode():
            inject_scroll_to_target()
            return
    else:
        activate_csv_finish_mode()
    step = _active_step()
    _go(step)
    _nav(step)
    add_audit_event('wizard_source_first_step_rendered', area='WIZARD', step=step, details={'selected_operation': selected_operation() or 'pending', 'steps': _steps(), 'api_no_universal_operation': True, 'responsible_file': RESPONSIBLE_FILE})
    _render_step(step, (2 if context == CONTEXT_BLING_API else 1) + _steps().index(step))
    inject_scroll_to_target()


__all__ = ['CADASTRO_STEPS', 'ESTOQUE_STEPS', 'HOME_CHOICE_TARGET', 'STEP_DOWNLOAD', 'STEP_GERAR_ESTOQUE', 'STEP_MAPEAMENTO', 'STEP_REGRAS', 'render_home_wizard', 'wizard_next_target', 'wizard_previous_target', 'wizard_steps_for_operation']
