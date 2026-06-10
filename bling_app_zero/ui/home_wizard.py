from __future__ import annotations

import streamlit as st

from bling_app_zero.core.audit import add_audit_event
from bling_app_zero.core.flow_spine import build_flow_spine_plan, pending_message_for, resolve_step
from bling_app_zero.core.interaction_guard import (
    activate_manual_back_lock,
    clear_manual_back_lock,
    locked_manual_back_target,
    manual_back_lock_active,
)
from bling_app_zero.features_runtime.router import (
    active_contract,
    feature_needs_model,
    feature_needs_pricing,
    feature_needs_rules_review,
)
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
    bind_price_update_single_sheet,
    is_price_update_contract,
    render_price_update_single_sheet_notice,
)
from bling_app_zero.ui.home_wizard_pricing_step import render_pricing_step
from bling_app_zero.ui.home_wizard_rerun import safe_rerun, set_step_without_rerun
from bling_app_zero.ui.home_wizard_review import render_final_checker, render_safe_fixes
from bling_app_zero.ui.home_wizard_scroll import inject_scroll_to_target, render_step_anchor
from bling_app_zero.ui.home_wizard_state import (
    HOME_CHOICE_TARGET,
    SINGLE_PAGE_FLOW,
    UNIVERSAL_OPERATION,
    UNIVERSAL_REVIEW_OPERATION,
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


def _flow_plan():
    return build_flow_spine_plan(render_steps=ACTIVE_RENDER_STEPS)


def _active_steps() -> list[str]:
    return list(_flow_plan().steps)


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


def _real_model_available() -> bool:
    try:
        from bling_app_zero.ui.home_wizard_state import _has_real_destination_model

        return bool(_has_real_destination_model())
    except Exception:
        return bool(has_home_models())


def _model_available() -> bool:
    if not feature_needs_model() or _is_api_direct_mode():
        return True
    current_step = str(st.session_state.get(WIZARD_STEP_KEY) or '').strip().lower()
    if current_step == STEP_MODELO:
        return _real_model_available()
    return bool(has_home_models())


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
    if normalized not in _active_steps():
        return
    set_step_without_rerun(normalized)


def _label_for(step: str) -> str:
    plan = _flow_plan()
    label = plan.label_for(step)
    if label:
        return label
    return str(STEP_LABELS.get(step, step)).strip()


def _step_is_done(step: str) -> bool:
    if step == STEP_MODELO:
        return _real_model_available() if feature_needs_model() and not _is_api_direct_mode() else True
    if step == STEP_ORIGEM:
        return current_origin_choice() in {'arquivo', 'site'}
    if step == STEP_ENTRADA:
        return universal_context_ready()
    if step == STEP_PRECIFICACAO:
        return True
    if step in {STEP_MAPEAMENTO, STEP_REGRAS, STEP_PREVIEW, STEP_DOWNLOAD}:
        return universal_mapping_ready()
    return False


def _can_advance_from(step: str) -> bool:
    if step == STEP_MODELO:
        return _real_model_available() if feature_needs_model() and not _is_api_direct_mode() else True
    if step == STEP_ORIGEM:
        return current_origin_choice() in {'arquivo', 'site'}
    if step == STEP_ENTRADA:
        return universal_context_ready()
    if step == STEP_PRECIFICACAO:
        return True
    if step in {STEP_MAPEAMENTO, STEP_REGRAS, STEP_PREVIEW}:
        return universal_mapping_ready()
    return False


def _pending_message_for(step: str) -> str:
    return pending_message_for(_flow_plan(), step)


def _render_blocked_next_state(next_step: str) -> None:
    st.caption(f'🔒 Próximo bloqueado: {_label_for(next_step)}')


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


def _render_persistent_process_bar(steps: list[str], active_step: str, *, locked: bool) -> None:
    if active_step not in steps:
        return
    index = steps.index(active_step)
    total = max(1, len(steps))
    percent = int(((index + 1) / total) * 100)
    lock_text = ' · avanço automático pausado' if locked else ''
    lock_class = ' blingfix-progress-locked' if locked else ''
    st.markdown(
        '''
<style>
.blingfix-progress-card{border:1px solid rgba(15,23,42,.10);background:linear-gradient(135deg,#ffffff 0%,#f8fafc 100%);border-radius:16px;padding:.72rem .82rem;margin:.55rem 0 .85rem 0;box-shadow:0 8px 22px rgba(15,23,42,.05);}
.blingfix-progress-title{font-size:.82rem;font-weight:900;color:#0f172a;margin-bottom:.22rem;}
.blingfix-progress-subtitle{font-size:.78rem;color:#475569;line-height:1.25;}
.blingfix-progress-locked{color:#9a3412;font-weight:850;}
</style>
''',
        unsafe_allow_html=True,
    )
    st.markdown(
        f'''
<div class="blingfix-progress-card">
  <div class="blingfix-progress-title">Acompanhamento do processo</div>
  <div class="blingfix-progress-subtitle{lock_class}">Etapa {index + 1} de {total} · {_label_for(active_step)}{lock_text}</div>
</div>
''',
        unsafe_allow_html=True,
    )
    st.progress(max(1, min(100, percent)))


def _render_safe_step_nav(steps: list[str], active_step: str) -> None:
    if active_step not in steps:
        return
    plan = _flow_plan()
    previous_step = plan.previous_step(active_step)
    next_step = plan.next_step(active_step)
    can_go_next = bool(next_step) and _can_advance_from(active_step)
    contract = active_contract()
    locked = manual_back_lock_active(active_step)

    _render_persistent_process_bar(steps, active_step, locked=locked)

    if contract.is_api and can_go_next and not locked:
        _go_to_step(next_step)
        add_audit_event(
            'wizard_api_auto_next_applied',
            area='WIZARD',
            step=next_step,
            details={'from': active_step, 'to': next_step, 'flow_spine': plan.to_dict(), 'responsible_file': RESPONSIBLE_FILE},
        )
        safe_rerun('wizard_api_auto_next', target_step=next_step)
        return

    if contract.is_api and can_go_next and locked:
        add_audit_event(
            'wizard_api_auto_next_blocked_by_manual_back',
            area='WIZARD',
            step=active_step,
            status='OK',
            details={'active_step': active_step, 'next_step': next_step, 'responsible_file': RESPONSIBLE_FILE},
        )

    st.markdown('---')
    col_back, col_status, col_next = st.columns([1, 1.4, 1])
    with col_back:
        if previous_step and st.button('⬅️ Voltar', use_container_width=True, key=f'wizard_local_back_{active_step}'):
            activate_manual_back_lock(active_step, previous_step)
            _go_to_step(previous_step)
            add_audit_event('wizard_local_back_clicked', area='WIZARD', step=previous_step, details={'from': active_step, 'to': previous_step, 'state_preserved': True, 'flow_spine': plan.to_dict(), 'responsible_file': RESPONSIBLE_FILE})
            safe_rerun('wizard_back_clicked', target_step=previous_step)
        elif not previous_step:
            st.caption('Início do fluxo')
    with col_status:
        if next_step:
            if can_go_next:
                if locked:
                    st.info(f'Você voltou para revisar: {_label_for(active_step)}. O avanço automático está pausado até tocar em Próximo.')
                else:
                    st.success(f'Próxima etapa liberada: {_label_for(next_step)}')
            else:
                render_pending_notice(_pending_message_for(active_step))
        else:
            st.success('Última etapa do fluxo.')
    with col_next:
        if next_step:
            if can_go_next:
                if st.button(f'Próximo: {_label_for(next_step)}', use_container_width=True, key=f'wizard_local_next_{active_step}'):
                    clear_manual_back_lock('manual_next_clicked')
                    _go_to_step(next_step)
                    add_audit_event('wizard_local_next_clicked', area='WIZARD', step=next_step, details={'from': active_step, 'to': next_step, 'prerequisite_ok': True, 'state_preserved': True, 'flow_spine': plan.to_dict(), 'responsible_file': RESPONSIBLE_FILE})
                    safe_rerun('wizard_next_clicked', target_step=next_step)
            else:
                _render_blocked_next_state(next_step)
        else:
            st.caption('Final')


def _resolve_active_step(active_step: str, *, has_model: bool, start_at_origin: bool) -> str:
    plan = _flow_plan()
    steps = list(plan.steps)
    locked_target = locked_manual_back_target('')
    if locked_target and locked_target in steps:
        return locked_target
    active_step = resolve_step(plan, active_step)
    contract = active_contract()
    real_model = _real_model_available()
    if start_at_origin and active_step == STEP_MODELO and not real_model:
        return STEP_MODELO
    if start_at_origin and active_step == STEP_MODELO:
        return STEP_ORIGEM if STEP_ORIGEM in steps else steps[0]
    if has_model and active_step == STEP_MODELO and real_model:
        return STEP_ORIGEM if STEP_ORIGEM in steps else steps[0]
    if active_step == STEP_ORIGEM and current_origin_choice() in {'arquivo', 'site'}:
        return STEP_ENTRADA if STEP_ENTRADA in steps else active_step
    if active_step == STEP_ENTRADA and universal_context_ready():
        if contract.is_api:
            return STEP_DOWNLOAD if STEP_DOWNLOAD in steps else active_step
        if feature_needs_model() and not real_model:
            return STEP_MODELO if STEP_MODELO in steps else active_step
        if not feature_needs_pricing():
            return STEP_MAPEAMENTO if STEP_MAPEAMENTO in steps else active_step
        return STEP_PRECIFICACAO if STEP_PRECIFICACAO in steps else active_step
    if active_step == STEP_PRECIFICACAO and not feature_needs_pricing():
        return STEP_MAPEAMENTO if STEP_MAPEAMENTO in steps else active_step
    return active_step


def _render_model_step(section_number: int = 2) -> None:
    if not feature_needs_model() or _is_api_direct_mode():
        return
    from bling_app_zero.ui.home_models import render_home_bling_models
    render_step_anchor(STEP_MODELO)
    _section_title(section_number, _label_for(STEP_MODELO))
    with st.container(border=True):
        render_home_bling_models()
    ensure_universal_operation_state()
    if _is_price_update_contract() and not _is_universal_entry():
        bind_price_update_single_sheet()


def _render_origin_step(section_number: int = 3) -> None:
    render_step_anchor(STEP_ORIGEM)
    if _is_price_update_contract() and not _is_api_direct_mode() and not _is_universal_entry():
        _section_title(section_number, _label_for(STEP_ENTRADA))
        render_price_update_single_sheet_notice()
        return
    _section_title(section_number, _label_for(STEP_ORIGEM))
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
    with col2:
        if st.button('🌐 Site', use_container_width=True, key='origin_choose_site'):
            select_origin('site', set_scroll_target=None)
    if selected in {'arquivo', 'site'}:
        st.success('Origem selecionada.')
    else:
        render_pending_notice('Escolha Arquivo ou Site.')


def _render_universal_entrada(section_number: int = 4) -> None:
    origin = current_origin_choice()
    render_step_anchor(STEP_ENTRADA)
    if _is_price_update_contract() and not _is_api_direct_mode() and not _is_universal_entry():
        _section_title(section_number, _label_for(STEP_ENTRADA))
        render_price_update_single_sheet_notice()
        return
    _section_title(section_number, _label_for(STEP_ENTRADA))
    if not _model_available():
        render_pending_notice('Liberado após escolher o caminho do fluxo.')
        return
    if origin not in {'arquivo', 'site'}:
        render_pending_notice('Escolha a origem primeiro.')
        return
    add_audit_event('single_page_origin_data_rendered', area='UNIVERSAL', step=STEP_ENTRADA, details={'origin': origin, 'operation': _current_contract_operation(), 'finish_mode': _finish_mode(), 'home_entry_context': _entry_context(), 'single_page_flow': SINGLE_PAGE_FLOW, 'flow_spine': _flow_plan().to_dict(), 'responsible_file': RESPONSIBLE_FILE})
    if origin == 'site':
        from bling_app_zero.ui.site_panel import render_site_panel
        render_site_panel()
    render_universal_entrada_step()


def _render_pricing_step(section_number: int = 5) -> None:
    if not feature_needs_pricing():
        return
    render_pricing_step(section_number=section_number, step_key=STEP_PRECIFICACAO, section_title=_section_title, model_available=_model_available(), is_price_update=_is_price_update_contract(), is_api_direct=_is_api_direct_mode(), is_universal_entry=_is_universal_entry(), render_price_update_notice=render_price_update_single_sheet_notice)


def _render_universal_mapeamento(section_number: int = 6) -> None:
    render_step_anchor(STEP_MAPEAMENTO)
    _section_title(section_number, _label_for(STEP_MAPEAMENTO))
    if not _model_available():
        render_pending_notice('Liberado após escolher o caminho do fluxo e carregar os dados.')
        return
    if not universal_context_ready():
        render_pending_notice('Carregue os dados primeiro.')
        return
    if _is_api_direct_mode():
        apply_direct_api_contract()
        st.caption('Modo Envio direto: o sistema prepara os campos internos da API do Bling sem exigir modelo de planilha.')
    elif _is_price_update_contract() and not _is_universal_entry():
        st.caption('A mesma planilha foi vinculada como origem e modelo. Confirme os campos para manter o contrato do arquivo final.')
    render_universal_mapeamento_step()


def _render_ai_review_step(section_number: int = 7) -> None:
    if not feature_needs_rules_review():
        return
    render_step_anchor(STEP_REGRAS)
    _section_title(section_number, _label_for(STEP_REGRAS))
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
    st.caption('Revise os campos ligados e aplique as proteções finais antes da prévia final.')
    render_mapping_review_panel(operation=UNIVERSAL_REVIEW_OPERATION, mapping=_context_mapping(), confidence=_context_confidence(), df_source=df_source, target_columns=[str(column) for column in getattr(df_modelo, 'columns', [])])
    render_final_checker(df_source, df_modelo)
    render_safe_fixes()
    render_ai_real_advanced_panel()
    st.markdown('#### Ajustes avançados do arquivo final')
    render_rules_center_step()


def _render_universal_preview(section_number: int = 8) -> None:
    render_step_anchor(STEP_PREVIEW)
    _section_title(section_number, _label_for(STEP_PREVIEW))
    if not _model_available():
        render_pending_notice('Liberado após o preparo dos dados.')
        return
    if not universal_mapping_ready():
        render_pending_notice('Confirme o preparo dos campos primeiro.')
        return
    render_universal_preview_step()


def _render_universal_download(section_number: int = 9) -> None:
    render_step_anchor(STEP_DOWNLOAD)
    _section_title(section_number, _label_for(STEP_DOWNLOAD))
    if _is_api_direct_mode():
        st.caption('Envio direto pela API do Bling. CSV fica apenas como backup opcional.')
    if not _model_available():
        render_pending_notice('Liberado no final.')
        return
    if not universal_mapping_ready():
        render_pending_notice('Confirme o preparo dos campos primeiro.')
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
    plan = _flow_plan()
    current = str(st.session_state.get(WIZARD_STEP_KEY) or _query_step() or (plan.steps[0] if plan.steps else STEP_ORIGEM)).strip().lower()
    return resolve_step(plan, current)


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
    plan = _flow_plan()
    steps = [step for step in plan.steps if not (skip_model and step == STEP_MODELO)]
    if not steps:
        steps = [STEP_ORIGEM, STEP_ENTRADA, STEP_DOWNLOAD]
    if start_step not in steps:
        start_step = steps[0]
    _go_to_step(start_step)
    _render_step_progress(steps, start_step)
    section_number = (2 if _is_bling_api_entry() else 1) + steps.index(start_step)
    _render_active_step(start_step, section_number)
    _render_safe_step_nav(steps, start_step)


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

    current_start = _active_start_step()
    if direct_mode:
        apply_direct_api_contract()
        has_model = True
    elif feature_needs_model() and not has_model and current_start not in {STEP_ORIGEM, STEP_ENTRADA}:
        set_step_without_rerun(STEP_MODELO)
        st.session_state.pop('home_slim_flow_origin', None)
        plan = _flow_plan()
        add_audit_event('wizard_model_first_guard_active', area='WIZARD', step=STEP_MODELO, details={'reason': 'missing_destination_model', 'single_page_flow': SINGLE_PAGE_FLOW, 'finish_mode': mode, 'home_entry_context': context, 'flow_spine': plan.to_dict(), 'responsible_file': RESPONSIBLE_FILE})
        _render_step_progress([STEP_MODELO], STEP_MODELO)
        _render_model_step(1 if context != CONTEXT_BLING_API else 2)
        _render_safe_step_nav([STEP_MODELO], STEP_MODELO)
        inject_scroll_to_target()
        return

    start_at_origin = came_from_bling_quick_model() or direct_mode or not feature_needs_model()
    active_step = _resolve_active_step(current_start, has_model=has_model, start_at_origin=start_at_origin)
    plan = _flow_plan()
    steps = list(plan.steps)
    add_audit_event('wizard_single_step_rendered', area='WIZARD', step=active_step, details={'operation': operation or 'universal', 'feature_contract': plan.contract_key, 'steps': steps, 'render_mode': 'flow_spine_safe_nav_native', 'single_page_flow': SINGLE_PAGE_FLOW, 'skip_model_step': start_at_origin, 'active_start_step': active_step, 'finish_mode': mode, 'home_entry_context': context, 'flow_spine': plan.to_dict(), 'manual_back_lock_native': True, 'source_before_model': True, 'responsible_file': RESPONSIBLE_FILE})
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
