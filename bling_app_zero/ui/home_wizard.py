from __future__ import annotations

import pandas as pd
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
    STEP_IA,
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
from bling_app_zero.ui.rules_center_state import rules_center_ready
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


def _is_api_context() -> bool:
    try:
        context_is_api = _entry_context() == CONTEXT_BLING_API
    except Exception:
        context_is_api = False
    return bool(
        context_is_api
        or st.session_state.get('home_bling_connected_same_flow_api_send')
        or st.session_state.get('bling_connected_api_flow_active')
        or st.session_state.get('direct_bling_api_contract_active')
    )


def _steps() -> list[str]:
    op = selected_operation()

    # MapeiaAI 2026-06-22: Bling conectado cai em Origem -> Dados -> Operação.
    # O contrato da saída vem do padrão Bling da operação escolhida; não usa
    # modelo livre anexado pelo usuário.
    if _is_api_context():
        steps = [STEP_ORIGEM, STEP_ENTRADA, STEP_OPERACAO]
        if op == OP_ESTOQUE:
            steps += [STEP_MAPEAMENTO, STEP_REGRAS, STEP_IA, STEP_PREVIEW, STEP_DOWNLOAD]
        elif op == OP_PRECO:
            steps += [STEP_PRECIFICACAO, STEP_MAPEAMENTO, STEP_REGRAS, STEP_IA, STEP_PREVIEW, STEP_DOWNLOAD]
        elif op == OP_CADASTRO:
            steps += [STEP_PRECIFICACAO, STEP_MAPEAMENTO, STEP_REGRAS, STEP_IA, STEP_PREVIEW, STEP_DOWNLOAD]
        return steps

    steps = [STEP_ORIGEM, STEP_ENTRADA, STEP_OPERACAO]
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
    if step == STEP_OPERACAO:
        return operation_ready()
    if step == STEP_ORIGEM:
        return current_origin_choice() in {'arquivo', 'site'}
    if step == STEP_ENTRADA:
        return source_data_ready()
    if step == STEP_PRECIFICACAO:
        return True
    if step == STEP_REGRAS:
        if _is_api_context():
            return bool(universal_mapping_ready() and rules_center_ready())
        return universal_mapping_ready()
    if step == STEP_IA:
        return bool(universal_mapping_ready() and rules_center_ready())
    if step in {STEP_MAPEAMENTO, STEP_PREVIEW, STEP_DOWNLOAD}:
        return universal_mapping_ready()
    return False


def _fallback_active_step_for_invalid_current(current: str, steps: list[str]) -> str:
    if _is_api_context():
        if current_origin_choice() not in {'arquivo', 'site'}:
            return STEP_ORIGEM
        if not source_data_ready() and STEP_ENTRADA in steps:
            return STEP_ENTRADA
        if not operation_ready() and STEP_OPERACAO in steps:
            return STEP_OPERACAO
        return steps[0]
    if source_data_ready() and not operation_ready():
        return STEP_OPERACAO
    if source_data_ready() and selected_operation() and STEP_OPERACAO in steps:
        return STEP_OPERACAO
    if source_data_ready() and STEP_ENTRADA in steps:
        return STEP_ENTRADA
    return steps[0]


def _active_step() -> str:
    current = str(st.session_state.get(WIZARD_STEP_KEY) or STEP_ORIGEM).strip().lower()
    steps = _steps()
    if _is_api_context():
        if current_origin_choice() not in {'arquivo', 'site'}:
            return STEP_ORIGEM
        if not source_data_ready() and current not in {STEP_ORIGEM, STEP_ENTRADA}:
            return STEP_ENTRADA
        if source_data_ready() and not operation_ready() and current not in {STEP_ORIGEM, STEP_ENTRADA, STEP_OPERACAO}:
            return STEP_OPERACAO
        if current in steps:
            return current
        fallback = _fallback_active_step_for_invalid_current(current, steps)
        add_audit_event(
            'wizard_api_origin_first_redirected',
            area='WIZARD',
            step=fallback,
            status='OK',
            details={
                'invalid_current_step': current,
                'fallback_step': fallback,
                'selected_operation': selected_operation() or 'pending',
                'source_data_ready': source_data_ready(),
                'operation_ready': operation_ready(),
                'steps': steps,
                'responsible_file': RESPONSIBLE_FILE,
            },
        )
        return fallback
    if source_data_ready() and not operation_ready() and current not in {STEP_ORIGEM, STEP_ENTRADA, STEP_OPERACAO}:
        return STEP_OPERACAO
    if current in {STEP_ORIGEM, STEP_ENTRADA} and source_data_ready() and not operation_ready():
        return STEP_OPERACAO
    if current in steps:
        return current
    fallback = _fallback_active_step_for_invalid_current(current, steps)
    add_audit_event(
        'wizard_invalid_step_redirected_without_returning_origin',
        area='WIZARD',
        step=fallback,
        status='OK',
        details={
            'invalid_current_step': current,
            'fallback_step': fallback,
            'selected_operation': selected_operation() or 'pending',
            'source_data_ready': source_data_ready(),
            'operation_ready': operation_ready(),
            'steps': steps,
            'responsible_file': RESPONSIBLE_FILE,
        },
    )
    return fallback


def _render_origin(n: int) -> None:
    render_step_anchor(STEP_ORIGEM)
    _section_title(n, _label(STEP_ORIGEM))
    ensure_universal_operation_state()
    if _is_api_context():
        st.caption('Bling conectado. Primeiro escolha a origem dos dados: buscar produtos por site ou anexar arquivo.')
    else:
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


def _first_loaded_dataframe() -> pd.DataFrame | None:
    for key in (
        'cadastro_wizard_df_para_mapear',
        'cadastro_wizard_df_origem',
        'df_origem_planilha',
        'df_produtos_origem',
        'df_origem_site_como_planilha',
        'df_site_bruto',
        'df_origem',
    ):
        value = st.session_state.get(key)
        if isinstance(value, pd.DataFrame) and not value.empty:
            return value.copy().fillna('')
    return None


def _render_locked_bling_contract() -> None:
    from bling_app_zero.adapters.streamlit_mapping_bridge import build_and_sync_mapping
    from bling_app_zero.ui.cadastro_wizard_state import (
        CADASTRO_MAPPING_CONFIRMED_KEY,
        CADASTRO_MAPPING_SIGNATURE_KEY,
        LEGACY_CADASTRO_FINAL_KEY,
        UNIVERSAL_FINAL_KEY,
        set_context_final_df,
    )
    from bling_app_zero.ui.home_bling_api_flow import apply_direct_api_contract
    from bling_app_zero.ui.home_shared import df_signature
    from bling_app_zero.ui.shared_final_csv import build_shared_final_dataframe
    from bling_app_zero.ui.shared_mapping import suggest_shared_mapping

    operation = selected_operation() or OP_CADASTRO
    source = _first_loaded_dataframe()
    if not isinstance(source, pd.DataFrame) or source.empty:
        render_pending_notice('Carregue a origem dos dados antes de preparar o contrato fixo do Bling.')
        return

    model = apply_direct_api_contract(operation).copy().fillna('')
    if not isinstance(model, pd.DataFrame) or len(model.columns) <= 0:
        st.warning('Contrato fixo da operação Bling não carregou. Volte para Operação e confirme novamente.')
        return

    signature = f'bling_locked:{operation}:{df_signature(source)}:{df_signature(model)}'
    current_signature = str(st.session_state.get('bling_api_locked_contract_signature') or '')
    current_mapping = st.session_state.get('mapping_bling_api')
    if current_signature == signature and isinstance(current_mapping, dict) and current_mapping:
        mapping = {str(k): str(v) for k, v in current_mapping.items()}
        engine = str(st.session_state.get('bling_api_locked_contract_engine') or 'locked_cached')
    else:
        try:
            suggested, engine = suggest_shared_mapping(source, model, operation=operation)
        except Exception as exc:
            suggested, engine = {}, f'locked_fallback:{exc}'[:100]
        identity = {str(column): str(column) for column in model.columns if str(column) in source.columns}
        mapping = {str(column): str(suggested.get(str(column)) or identity.get(str(column)) or '') for column in model.columns}
        st.session_state['mapping_bling_api'] = mapping
        st.session_state['bling_api_locked_contract_signature'] = signature
        st.session_state['bling_api_locked_contract_engine'] = engine

    mapping, rows = build_and_sync_mapping(
        source,
        model,
        mapping,
        operation=operation,
        signature=signature,
        engine=str(st.session_state.get('bling_api_locked_contract_engine') or 'locked_contract'),
        mapping_state_key='mapping_bling_api',
        engine_state_key='bling_api_locked_contract_engine',
    )
    try:
        final_df = build_shared_final_dataframe(source, model, mapping).fillna('')
    except Exception as exc:
        st.error(f'Não consegui montar a base fixa do Bling: {exc}')
        return

    st.session_state['df_final_bling_api'] = final_df
    st.session_state[UNIVERSAL_FINAL_KEY] = final_df
    st.session_state[LEGACY_CADASTRO_FINAL_KEY] = final_df
    st.session_state['mapping_bling_api'] = mapping
    st.session_state['mapping_cadastro'] = mapping
    st.session_state['mapping_confidence_bling_api'] = {str(row.get('target') or row.get('Contrato final') or ''): str(row.get('confidence') or row.get('Farol') or '') for row in rows}
    st.session_state['mapping_confidence_cadastro'] = st.session_state['mapping_confidence_bling_api']
    st.session_state[CADASTRO_MAPPING_CONFIRMED_KEY] = True
    st.session_state[CADASTRO_MAPPING_SIGNATURE_KEY] = signature
    st.session_state['bling_api_manual_mapping_required'] = False
    st.session_state['bling_api_locked_contract_ready'] = True
    set_context_final_df(final_df)

    st.info('Fluxo Bling: contrato fixo automático da operação. Não há alteração livre de modelo neste caminho.')
    st.success(f'Contrato Bling preparado: {len(final_df)} linha(s) x {len(final_df.columns)} coluna(s).')
    with st.expander('Ver vínculo automático do contrato Bling', expanded=False):
        table = pd.DataFrame(rows) if rows else pd.DataFrame({'Contrato Bling': list(model.columns), 'Origem usada': [mapping.get(str(col), '') for col in model.columns]})
        st.dataframe(table, use_container_width=True, hide_index=True, height=260)
    st.dataframe(final_df.head(40).astype(str), use_container_width=True, height=260)
    add_audit_event(
        'wizard_bling_locked_contract_rendered',
        area='MAPEAMENTO',
        status='OK',
        details={
            'operation': operation,
            'rows': int(len(final_df)),
            'columns': int(len(final_df.columns)),
            'manual_mapping_allowed': False,
            'responsible_file': RESPONSIBLE_FILE,
        },
    )


def _render_map(n: int) -> None:
    render_step_anchor(STEP_MAPEAMENTO)
    _section_title(n, _label(STEP_MAPEAMENTO))
    if not operation_ready():
        render_pending_notice('Escolha a operação e confirme os obrigatórios primeiro.')
        return
    if _is_api_context():
        _render_locked_bling_contract()
        return
    render_universal_mapeamento_step()


def _render_rules(n: int) -> None:
    render_step_anchor(STEP_REGRAS)
    _section_title(n, _label(STEP_REGRAS))
    if selected_operation() != OP_CADASTRO and not _is_api_context():
        st.info('Esta etapa é exclusiva do cadastro.')
        return
    render_rules_center_step()


def _render_ai(n: int) -> None:
    render_step_anchor(STEP_IA)
    _section_title(n, _label(STEP_IA))
    if not universal_mapping_ready():
        render_pending_notice('Confirme a revisão dos campos antes da Inteligência Artificial.')
        return
    if not rules_center_ready():
        render_pending_notice('Revise e salve as Regras e Recursos Inteligentes antes de usar ou pular a IA.')
        return
    try:
        from bling_app_zero.ui.ai_real_advanced_panel import render_ai_real_advanced_panel
        render_ai_real_advanced_panel()
    except Exception as exc:
        st.caption(f'IA opcional indisponível neste ambiente: {exc}')


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
    elif step == STEP_IA:
        _render_ai(n)
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
    add_audit_event('wizard_source_first_step_rendered', area='WIZARD', step=step, details={'selected_operation': selected_operation() or 'pending', 'steps': _steps(), 'api_no_universal_operation': True, 'operation_first_for_api': False, 'responsible_file': RESPONSIBLE_FILE})
    _render_step(step, (2 if context == CONTEXT_BLING_API else 1) + _steps().index(step))
    inject_scroll_to_target()


__all__ = ['CADASTRO_STEPS', 'ESTOQUE_STEPS', 'HOME_CHOICE_TARGET', 'STEP_DOWNLOAD', 'STEP_GERAR_ESTOQUE', 'STEP_MAPEAMENTO', 'STEP_REGRAS', 'render_home_wizard', 'wizard_next_target', 'wizard_previous_target', 'wizard_steps_for_operation']
