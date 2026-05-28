from __future__ import annotations

import streamlit as st

from bling_app_zero.core.audit import add_audit_event
from bling_app_zero.ui.ai_real_advanced_panel import render_ai_real_advanced_panel
from bling_app_zero.ui.flow_context import (
    CONTEXT_BLING_API,
    CONTEXT_BLING_CSV,
    CONTEXT_UNIVERSAL,
    FINISH_MODE_CSV,
    activate_csv_finish_mode,
    entry_context as _entry_context,
    finish_mode as _finish_mode,
    is_api_direct_mode as _is_api_direct_mode,
    is_bling_api_context as _is_bling_api_entry,
    is_universal_context as _is_universal_entry,
)
from bling_app_zero.ui.home_bling_api_flow import apply_direct_api_contract, render_bling_connection_step
from bling_app_zero.ui.home_wizard_constants import (
    CADASTRO_STEPS,
    ESTOQUE_STEPS,
    STEP_DOWNLOAD,
    STEP_ENTRADA,
    STEP_GERAR_ESTOQUE,
    STEP_LABELS,
    STEP_MAPEAMENTO,
    STEP_MODELO,
    STEP_ORIGEM,
    STEP_PRECIFICACAO,
    STEP_PREVIEW,
    STEP_REGRAS,
    WIZARD_STEP_KEY,
)
from bling_app_zero.ui.home_wizard_price_update import (
    PRICE_UPDATE_OPERATION,
    bind_price_update_single_sheet,
    is_price_update_contract,
    render_price_update_single_sheet_notice,
)
from bling_app_zero.ui.home_wizard_pricing_step import render_pricing_step
from bling_app_zero.ui.home_wizard_review import render_final_checker, render_safe_fixes
from bling_app_zero.ui.home_wizard_scroll import inject_scroll_to_target, render_step_anchor
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
from bling_app_zero.ui.universal_download_step import render_universal_download_step
from bling_app_zero.ui.universal_entry_step import render_universal_entrada_step
from bling_app_zero.ui.universal_mapping_step import render_universal_mapeamento_step
from bling_app_zero.ui.universal_preview_step import render_universal_preview_step
from bling_app_zero.ui.universal_wizard_state import (
    UNIVERSAL_MODELO_KEY,
    UNIVERSAL_ORIGEM_KEY,
    UNIVERSAL_ORIGEM_PRICED_KEY,
    universal_context_ready,
    universal_mapping_ready,
)
from bling_app_zero.universal.model_contract_detector import MODEL_CONTRACT_TYPE_KEY, normalize_contract_operation

RESPONSIBLE_FILE = 'bling_app_zero/ui/home_wizard.py'

CONTEXT_MAPPING_KEYS = {
    CONTEXT_BLING_API: ('mapping_bling_api', 'mapping_confidence_bling_api'),
    CONTEXT_BLING_CSV: ('mapping_bling_csv', 'mapping_confidence_bling_csv'),
    CONTEXT_UNIVERSAL: ('mapping_universal', 'mapping_confidence_universal'),
}

ACTIVE_RENDER_STEPS = [
    STEP_MODELO,
    STEP_ORIGEM,
    STEP_ENTRADA,
    STEP_PRECIFICACAO,
    STEP_MAPEAMENTO,
    STEP_REGRAS,
    STEP_PREVIEW,
    STEP_DOWNLOAD,
]


def _section_title(number: int, title: str) -> None:
    st.markdown('---')
    st.markdown(f'### {number}. {title}')


def _context_mapping_keys() -> tuple[str, str]:
    return CONTEXT_MAPPING_KEYS.get(_entry_context(), CONTEXT_MAPPING_KEYS[CONTEXT_BLING_API])


def _context_mapping() -> dict:
    mapping_key, _confidence_key = _context_mapping_keys()
    mapping = st.session_state.get(mapping_key)
    if isinstance(mapping, dict):
        return mapping
    fallback = st.session_state.get('mapping_cadastro')
    return fallback if isinstance(fallback, dict) else {}


def _context_confidence() -> dict:
    _mapping_key, confidence_key = _context_mapping_keys()
    confidence = st.session_state.get(confidence_key)
    if isinstance(confidence, dict):
        return confidence
    fallback = st.session_state.get('mapping_confidence_cadastro')
    return fallback if isinstance(fallback, dict) else {}


def _model_available() -> bool:
    return bool(has_home_models()) or _is_api_direct_mode()


def _current_contract_operation() -> str:
    for value in (
        st.session_state.get(MODEL_CONTRACT_TYPE_KEY),
        st.session_state.get('home_slim_flow_operation'),
        st.session_state.get('home_detected_operation'),
        st.session_state.get('operacao_final'),
        st.session_state.get('tipo_operacao_final'),
    ):
        operation = normalize_contract_operation(value)
        if operation:
            return operation
    return UNIVERSAL_OPERATION


def _is_price_update_contract() -> bool:
    return is_price_update_contract(_current_contract_operation())


def _go_to_step(step: str) -> None:
    normalized = str(step or '').strip().lower()
    if normalized not in ACTIVE_RENDER_STEPS:
        return
    st.session_state[WIZARD_STEP_KEY] = normalized
    try:
        st.query_params['step'] = normalized
    except Exception:
        pass


def _label_for(step: str) -> str:
    return str(STEP_LABELS.get(step, step)).strip()


def _step_is_done(step: str) -> bool:
    if step == STEP_MODELO:
        return _model_available()
    if step == STEP_ORIGEM:
        return current_origin_choice() in {'arquivo', 'site'}
    if step == STEP_ENTRADA:
        return universal_context_ready()
    if step == STEP_PRECIFICACAO:
        return True
    if step in {STEP_MAPEAMENTO, STEP_REGRAS, STEP_PREVIEW, STEP_DOWNLOAD}:
        return universal_mapping_ready()
    return False


def _render_step_progress(steps: list[str], active_step: str) -> None:
    if active_step not in steps:
        return
    index = steps.index(active_step)
    total = len(steps)
    percent = int(((index + 1) / total) * 100)

    st.caption(f'Etapa {index + 1} de {total} · {_label_for(active_step)}')
    st.progress(max(1, min(100, percent)))

    done_labels = [_label_for(step) for step in steps[:index] if _step_is_done(step)]
    if done_labels:
        with st.expander('Resumo das etapas concluídas', expanded=False):
            for label in done_labels:
                st.success(f'{label} concluído.')


def _resolve_active_step(active_step: str, *, has_model: bool, start_at_origin: bool) -> str:
    """Evita tela parada em etapa já concluída e mantém foco na próxima ação.

    BLINGFIX:
    - modelo carregado leva para Origem;
    - origem escolhida leva para Dados do fornecedor;
    - dados carregados levam para Preço, mantendo a etapa opcional visível;
    - preço só é pulado automaticamente quando não houver configuração ativa.
    """
    if start_at_origin and active_step == STEP_MODELO:
        return STEP_ORIGEM
    if has_model and active_step == STEP_MODELO:
        return STEP_ORIGEM
    if active_step == STEP_ORIGEM and current_origin_choice() in {'arquivo', 'site'}:
        return STEP_ENTRADA
    if active_step == STEP_ENTRADA and universal_context_ready():
        return STEP_PRECIFICACAO
    if active_step == STEP_PRECIFICACAO:
        pricing_enabled = bool(st.session_state.get('home_precificacao_inicial')) or bool(st.session_state.get('home_pricing_enabled_toggle'))
        pricing_configured = isinstance(st.session_state.get('home_pricing_config'), dict) and bool(st.session_state.get('home_pricing_config'))
        if not pricing_enabled and not pricing_configured:
            return STEP_MAPEAMENTO
    return active_step


def _render_model_step(section_number: int = 2) -> None:
    if _is_api_direct_mode():
        return
    from bling_app_zero.ui.home_models import render_home_bling_models

    render_step_anchor(STEP_MODELO)
    title = 'Modelo Universal' if _is_universal_entry() else 'Modelos Bling'
    _section_title(section_number, title)
    with st.container(border=True):
        render_home_bling_models()
    ensure_universal_operation_state()
    if _is_price_update_contract() and not _is_universal_entry():
        bind_price_update_single_sheet()


def _render_origin_step(section_number: int = 3) -> None:
    render_step_anchor(STEP_ORIGEM)
    if _is_price_update_contract() and not _is_api_direct_mode() and not _is_universal_entry():
        _section_title(section_number, 'Planilha única de atualização de preços')
        render_price_update_single_sheet_notice()
        return

    _section_title(section_number, 'Origem dos dados')
    if not _model_available():
        render_pending_notice('Liberado após escolher o caminho do fluxo.')
        return
    ensure_universal_operation_state()
    if _is_api_direct_mode():
        apply_direct_api_contract()
        st.caption('Modo Envio direto: não é necessário anexar modelo. O sistema usará o contrato interno da API do Bling.')
    selected = current_origin_choice()
    col1, col2 = st.columns(2)
    with col1:
        if st.button('📎 Arquivo', use_container_width=True, key='origin_choose_file'):
            select_origin('arquivo', set_scroll_target=None)
            _go_to_step(STEP_ENTRADA)
            st.rerun()
    with col2:
        if st.button('🌐 Site', use_container_width=True, key='origin_choose_site'):
            select_origin('site', set_scroll_target=None)
            _go_to_step(STEP_ENTRADA)
            st.rerun()
    if selected in {'arquivo', 'site'}:
        st.success('Origem selecionada.')
    else:
        render_pending_notice('Escolha Arquivo ou Site.')


def _render_universal_entrada(section_number: int = 4) -> None:
    origin = current_origin_choice()
    render_step_anchor(STEP_ENTRADA)
    if _is_price_update_contract() and not _is_api_direct_mode() and not _is_universal_entry():
        _section_title(section_number, 'Dados da atualização de preços')
        render_price_update_single_sheet_notice()
        return
    _section_title(section_number, 'Dados do fornecedor')
    if not _model_available():
        render_pending_notice('Liberado após escolher o caminho do fluxo.')
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
            'operation': _current_contract_operation(),
            'finish_mode': _finish_mode(),
            'home_entry_context': _entry_context(),
            'single_page_flow': SINGLE_PAGE_FLOW,
            'responsible_file': RESPONSIBLE_FILE,
        },
    )
    if origin == 'site':
        from bling_app_zero.ui.site_panel import render_site_panel

        render_site_panel()
    render_universal_entrada_step()


def _render_pricing_step(section_number: int = 5) -> None:
    render_pricing_step(
        section_number=section_number,
        step_key=STEP_PRECIFICACAO,
        section_title=_section_title,
        model_available=_model_available(),
        is_price_update=_is_price_update_contract(),
        is_api_direct=_is_api_direct_mode(),
        is_universal_entry=_is_universal_entry(),
        render_price_update_notice=render_price_update_single_sheet_notice,
    )


def _render_universal_mapeamento(section_number: int = 6) -> None:
    render_step_anchor(STEP_MAPEAMENTO)
    if _is_api_direct_mode():
        title = 'Mapear campos da API'
    elif _is_price_update_contract() and not _is_universal_entry():
        title = 'Conferir campos da atualização'
    else:
        title = 'Mapear campos'
    _section_title(section_number, title)
    if not _model_available():
        render_pending_notice('Liberado após escolher o caminho do fluxo e carregar os dados.')
        return
    if not universal_context_ready():
        render_pending_notice('Carregue os dados primeiro.')
        return
    if _is_api_direct_mode():
        apply_direct_api_contract()
        st.caption('Modo Envio direto: confirme a ligação dos dados de origem com os campos da API do Bling.')
    elif _is_price_update_contract() and not _is_universal_entry():
        st.caption('A mesma planilha foi vinculada como origem e modelo. Confirme os campos para manter o contrato do arquivo final.')
    render_universal_mapeamento_step()


def _render_ai_review_step(section_number: int = 7) -> None:
    render_step_anchor(STEP_REGRAS)
    _section_title(section_number, 'Revisão final')
    if not _model_available():
        render_pending_notice('Liberado após modelo/dados e mapeamento.')
        return
    if not universal_mapping_ready():
        render_pending_notice('Confirme o mapeamento manual primeiro.')
        return

    df_source = st.session_state.get(UNIVERSAL_ORIGEM_PRICED_KEY)
    if not looks_like_loaded_df(df_source):
        df_source = st.session_state.get(UNIVERSAL_ORIGEM_KEY)
    df_modelo = st.session_state.get(UNIVERSAL_MODELO_KEY)

    st.caption('Revise os campos ligados e aplique as proteções finais antes do preview.')
    render_mapping_review_panel(
        operation=UNIVERSAL_REVIEW_OPERATION,
        mapping=_context_mapping(),
        confidence=_context_confidence(),
        df_source=df_source,
        target_columns=[str(column) for column in getattr(df_modelo, 'columns', [])],
    )

    render_final_checker(df_source, df_modelo)
    render_safe_fixes()
    render_ai_real_advanced_panel()

    st.markdown('#### Ajustes avançados do arquivo final')
    render_rules_center_step()


def _render_universal_preview(section_number: int = 8) -> None:
    render_step_anchor(STEP_PREVIEW)
    _section_title(section_number, 'Preview')
    if not _model_available():
        render_pending_notice('Liberado após o mapeamento.')
        return
    if not universal_mapping_ready():
        render_pending_notice('Confirme o mapeamento primeiro.')
        return
    render_universal_preview_step()


def _render_universal_download(section_number: int = 9) -> None:
    render_step_anchor(STEP_DOWNLOAD)
    title = 'Envio direto' if _is_api_direct_mode() else 'Download'
    _section_title(section_number, title)
    if not _model_available():
        render_pending_notice('Liberado no final.')
        return
    if not universal_mapping_ready():
        render_pending_notice('Confirme o mapeamento primeiro.')
        return
    clear_stale_cadastro_operation_state()
    render_universal_download_step()
    if st.button('Recomeçar fluxo', use_container_width=True, key='wizard_download_reset_single_page'):
        reset_wizard()


def _query_step() -> str:
    try:
        value = st.query_params.get('step', '')
    except Exception:
        value = ''
    if isinstance(value, list):
        value = value[0] if value else ''
    return str(value or '').strip().lower()


def _active_start_step() -> str:
    current = str(st.session_state.get(WIZARD_STEP_KEY) or _query_step() or STEP_MODELO).strip().lower()
    if current not in ACTIVE_RENDER_STEPS:
        return STEP_MODELO
    return current


def _render_active_step(step: str, section_number: int) -> None:
    if step == STEP_MODELO:
        _render_model_step(section_number)
    elif step == STEP_ORIGEM:
        _render_origin_step(section_number)
    elif step == STEP_ENTRADA:
        _render_universal_entrada(section_number)
    elif step == STEP_PRECIFICACAO:
        _render_pricing_step(section_number)
    elif step == STEP_MAPEAMENTO:
        _render_universal_mapeamento(section_number)
    elif step == STEP_REGRAS:
        _render_ai_review_step(section_number)
    elif step == STEP_PREVIEW:
        _render_universal_preview(section_number)
    elif step == STEP_DOWNLOAD:
        _render_universal_download(section_number)


def _render_steps_from(start_step: str, *, skip_model: bool) -> None:
    """Renderiza somente a etapa ativa.

    BLINGFIX:
    - antes o wizard renderizava da etapa atual até o download, criando uma tela longa;
    - agora mantém foco em uma etapa por vez;
    - a numeração continua refletindo a posição real da etapa no fluxo.
    """
    steps = [step for step in ACTIVE_RENDER_STEPS if not (skip_model and step == STEP_MODELO)]
    if start_step not in steps:
        start_step = steps[0]
    _go_to_step(start_step)
    _render_step_progress(steps, start_step)
    section_number = (2 if _is_bling_api_entry() else 1) + steps.index(start_step)
    _render_active_step(start_step, section_number)


def render_home_wizard() -> None:
    inject_scroll_guard('home_wizard')
    has_model = has_home_models()
    operation = ensure_universal_operation_state()
    context = _entry_context()
    st.session_state['wizard_bottom_nav_rendered_current_cycle'] = True
    st.session_state['home_single_page_flow_active'] = True

    if context == CONTEXT_BLING_API:
        render_bling_connection_step(_section_title)
        mode = _finish_mode()
        direct_mode = _is_api_direct_mode()
        if not mode:
            inject_scroll_to_target()
            return
    else:
        mode = FINISH_MODE_CSV
        direct_mode = False
        activate_csv_finish_mode()

    if direct_mode:
        apply_direct_api_contract()
        has_model = True
    elif not has_model:
        st.session_state[WIZARD_STEP_KEY] = STEP_MODELO
        st.session_state.pop('home_slim_flow_origin', None)
        add_audit_event(
            'wizard_model_first_guard_active',
            area='WIZARD',
            step=STEP_MODELO,
            details={
                'reason': 'missing_destination_model',
                'single_page_flow': SINGLE_PAGE_FLOW,
                'finish_mode': mode,
                'home_entry_context': context,
                'responsible_file': RESPONSIBLE_FILE,
            },
        )
        _render_step_progress(ACTIVE_RENDER_STEPS, STEP_MODELO)
        _render_model_step(1 if context != CONTEXT_BLING_API else 2)
        inject_scroll_to_target()
        return

    start_at_origin = came_from_bling_quick_model() or direct_mode
    active_step = _active_start_step()
    active_step = _resolve_active_step(active_step, has_model=has_model, start_at_origin=start_at_origin)

    add_audit_event(
        'wizard_single_step_rendered',
        area='WIZARD',
        step=active_step,
        details={
            'operation': operation or 'universal',
            'steps': UNIVERSAL_STEPS,
            'render_mode': 'one_step_at_a_time_with_progress',
            'single_page_flow': SINGLE_PAGE_FLOW,
            'skip_model_step': start_at_origin,
            'active_start_step': active_step,
            'finish_mode': mode,
            'home_entry_context': context,
            'responsible_file': RESPONSIBLE_FILE,
        },
    )

    _render_steps_from(active_step, skip_model=start_at_origin)
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
