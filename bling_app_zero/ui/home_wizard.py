from __future__ import annotations

import streamlit as st

from bling_app_zero.core.audit import add_audit_event
from bling_app_zero.ui.cadastro_wizard_steps import (
    cadastro_context_ready,
    cadastro_mapping_ready,
    render_cadastro_download_step,
    render_cadastro_entrada_step,
    render_cadastro_mapeamento_step,
    render_cadastro_preview_step,
)
from bling_app_zero.ui.home_pricing_config import (
    disable_home_pricing,
    get_home_pricing_config,
    render_home_pricing_config_form,
    set_home_pricing_config,
)
from bling_app_zero.ui.home_wizard_constants import (
    CADASTRO_STEPS,
    FLOW_ACTIVE_KEY,
    FLOW_OPERATION_KEY,
    FLOW_ORIGIN_KEY,
    GLOBAL_CADASTRO_MODEL_KEYS,
    GLOBAL_ESTOQUE_MODEL_KEYS,
    HOME_CADASTRO_MODEL_KEY,
    HOME_ESTOQUE_MODEL_KEY,
    LEGACY_ORIGIN_RADIO_KEY,
    RESET_OUTPUT_KEYS,
    STEP_DOWNLOAD,
    STEP_ENTRADA,
    STEP_MAPEAMENTO,
    STEP_MODELO,
    STEP_OPERACAO,
    STEP_ORIGEM,
    STEP_PRECIFICACAO,
    STEP_PREVIEW,
    WIZARD_STEP_KEY,
    WizardNav,
)
from bling_app_zero.ui.home_wizard_ui import render_pending_notice, render_section_card, render_step_header

RESPONSIBLE_FILE = 'bling_app_zero/ui/home_wizard.py'
ORIGIN_AUTO_FORWARDED_KEY = 'wizard_origin_auto_forwarded_signature'
BOTTOM_NAV_RENDERED_KEY = 'wizard_bottom_nav_rendered_current_cycle'
HOME_ACTIVE_OPERATION_KEY = 'home_active_operation_v2'
HOME_ALLOW_OPERATION_KEY = 'home_allow_operation_v2_session'
HOME_CHOICE_TARGET = '__home_choice__'
AUTOFLOW_PAUSE_STEP_KEY = 'bling_autofluxo_pause_step'
AUTOFLOW_MANUAL_LOCK_KEY = 'bling_autofluxo_manual_navigation_lock'
AUTOFLOW_LAST_STEP_KEY = 'bling_autofluxo_last_step'
AUTOFLOW_LAST_MOVE_KEY = 'bling_autofluxo_last_move'
MANUAL_NAVIGATION_REASONS = {'next_button', 'back_button_previous_index'}

# BLINGFIX: a pergunta Cadastro/Estoque foi extinta da interface.
# O motor interno reutiliza o fluxo de cadastro apenas como pipeline universal
# de mapeamento para respeitar exatamente as colunas do modelo anexado.
UNIVERSAL_INTERNAL_OPERATION = 'cadastro'
REMOVED_OPERATION_STEP = True
UNIVERSAL_STEPS = [step for step in CADASTRO_STEPS if step != STEP_OPERACAO]


def _looks_like_loaded_df(value: object) -> bool:
    if value is None or not hasattr(value, 'columns'):
        return False
    try:
        return len(getattr(value, 'columns', [])) > 0
    except Exception:
        return False


def _has_any_model(keys: list[str]) -> bool:
    return any(_looks_like_loaded_df(st.session_state.get(key)) for key in keys)


def _has_cadastro_model() -> bool:
    return _has_any_model([HOME_CADASTRO_MODEL_KEY, *GLOBAL_CADASTRO_MODEL_KEYS])


def _has_estoque_model() -> bool:
    return _has_any_model([HOME_ESTOQUE_MODEL_KEY, *GLOBAL_ESTOQUE_MODEL_KEYS])


def _has_home_models() -> bool:
    return _has_cadastro_model() or _has_estoque_model()


def _ensure_universal_operation_state() -> str:
    """Mantem o estado interno necessario sem exibir escolha Cadastro/Estoque."""
    if not _has_home_models():
        return ''

    st.session_state[FLOW_OPERATION_KEY] = UNIVERSAL_INTERNAL_OPERATION
    st.session_state['operacao_final'] = UNIVERSAL_INTERNAL_OPERATION
    st.session_state['tipo_operacao_final'] = UNIVERSAL_INTERNAL_OPERATION
    st.session_state['home_operation_choice_removed'] = True
    st.session_state.pop('home_detected_operation', None)
    return UNIVERSAL_INTERNAL_OPERATION


def _selected_operation() -> str:
    return _ensure_universal_operation_state()


def wizard_steps_for_operation(operation: str | None = None) -> list[str]:
    _ = operation
    if _has_home_models():
        return list(UNIVERSAL_STEPS)
    return [STEP_MODELO]


def _target_by_delta(current_step: str, operation: str, delta: int) -> str:
    steps = wizard_steps_for_operation(operation)
    current = str(current_step or '').strip().lower()
    if current == STEP_OPERACAO:
        current = STEP_ORIGEM if STEP_ORIGEM in steps else STEP_MODELO
    if current not in steps:
        return STEP_ORIGEM if _has_home_models() and STEP_ORIGEM in steps else STEP_MODELO
    index = steps.index(current)
    if delta < 0 and index == 0:
        return HOME_CHOICE_TARGET
    target_index = max(0, min(len(steps) - 1, index + delta))
    return steps[target_index]


def wizard_previous_target(current_step: str, operation: str) -> str:
    return _target_by_delta(current_step, operation, -1)


def wizard_next_target(current_step: str, operation: str) -> str:
    return _target_by_delta(current_step, operation, 1)


def _active_steps() -> list[str]:
    return wizard_steps_for_operation(_selected_operation())


def _current_step() -> str:
    steps = _active_steps()
    step = str(st.session_state.get(WIZARD_STEP_KEY) or STEP_MODELO).strip().lower()
    if not _has_home_models():
        step = STEP_MODELO
    elif step == STEP_OPERACAO:
        step = STEP_ORIGEM
    elif step not in steps:
        step = STEP_ORIGEM if STEP_ORIGEM in steps else STEP_MODELO
    st.session_state[WIZARD_STEP_KEY] = step
    return step


def _pause_autofluxo_for_manual_navigation(target_step: str, *, reason: str) -> None:
    target = str(target_step or '').strip().lower()
    if not target or target == HOME_CHOICE_TARGET:
        return
    st.session_state[AUTOFLOW_PAUSE_STEP_KEY] = target
    st.session_state[AUTOFLOW_LAST_STEP_KEY] = target
    st.session_state.pop(AUTOFLOW_LAST_MOVE_KEY, None)
    st.session_state[AUTOFLOW_MANUAL_LOCK_KEY] = {
        'target_step': target,
        'reason': reason,
        'responsible_file': RESPONSIBLE_FILE,
    }
    add_audit_event(
        'wizard_manual_navigation_paused_autofluxo',
        area='WIZARD',
        step=target,
        details={'reason': reason, 'target_step': target, 'responsible_file': RESPONSIBLE_FILE},
    )


def _manual_pause_matches(step: str) -> bool:
    target = str(step or '').strip().lower()
    paused = str(st.session_state.get(AUTOFLOW_PAUSE_STEP_KEY) or '').strip().lower()
    lock = st.session_state.get(AUTOFLOW_MANUAL_LOCK_KEY)
    locked_step = str(lock.get('target_step') or '').strip().lower() if isinstance(lock, dict) else ''
    return bool(target and (paused == target or locked_step == target))


def _clear_manual_pause(step: str | None = None) -> None:
    target = str(step or '').strip().lower()
    paused = str(st.session_state.get(AUTOFLOW_PAUSE_STEP_KEY) or '').strip().lower()
    lock = st.session_state.get(AUTOFLOW_MANUAL_LOCK_KEY)
    locked_step = str(lock.get('target_step') or '').strip().lower() if isinstance(lock, dict) else ''
    if step is None or paused == target:
        st.session_state.pop(AUTOFLOW_PAUSE_STEP_KEY, None)
    if step is None or locked_step == target:
        st.session_state.pop(AUTOFLOW_MANUAL_LOCK_KEY, None)


def _go_to_step(step: str, *, reason: str = 'navigation') -> None:
    steps = _active_steps()
    previous = str(st.session_state.get(WIZARD_STEP_KEY) or '').strip().lower()
    requested = step
    if step == STEP_OPERACAO:
        step = STEP_ORIGEM
    if step not in steps:
        step = STEP_ORIGEM if _has_home_models() and STEP_ORIGEM in steps else STEP_MODELO

    if reason in MANUAL_NAVIGATION_REASONS:
        _pause_autofluxo_for_manual_navigation(step, reason=reason)

    if step == previous:
        add_audit_event(
            'wizard_step_kept',
            area='WIZARD',
            step=step,
            details={'from': previous, 'to': step, 'requested': requested, 'reason': reason, 'operation': _selected_operation(), 'operation_step_removed': REMOVED_OPERATION_STEP, 'state_preserved': True, 'responsible_file': RESPONSIBLE_FILE},
        )
        return

    st.session_state[WIZARD_STEP_KEY] = step
    add_audit_event(
        'wizard_step_changed',
        area='WIZARD',
        step=step,
        details={'from': previous, 'to': step, 'requested': requested, 'reason': reason, 'operation': _selected_operation(), 'operation_step_removed': REMOVED_OPERATION_STEP, 'state_preserved': True, 'responsible_file': RESPONSIBLE_FILE},
    )
    try:
        st.query_params['step'] = step
    except Exception:
        pass
    st.rerun()


def _back_to_home_choice() -> None:
    st.session_state.pop(HOME_ACTIVE_OPERATION_KEY, None)
    st.session_state.pop(HOME_ALLOW_OPERATION_KEY, None)
    _clear_manual_pause()
    for key in ('operation_v2', 'step'):
        try:
            st.query_params.pop(key, None)
        except Exception:
            pass
    add_audit_event('wizard_back_to_home_choice', area='WIZARD', step=_current_step(), details={'reason': 'back_button_first_step', 'state_preserved': True, 'responsible_file': RESPONSIBLE_FILE})
    st.rerun()


def _next_step() -> None:
    target = wizard_next_target(_current_step(), _selected_operation())
    _go_to_step(target, reason='next_button')


def _previous_step() -> None:
    target = wizard_previous_target(_current_step(), _selected_operation())
    if target == HOME_CHOICE_TARGET:
        _back_to_home_choice()
        return
    _go_to_step(target, reason='back_button_previous_index')


def _reset_outputs_for_operation_change() -> None:
    removed: list[str] = []
    for key in RESET_OUTPUT_KEYS:
        if key in st.session_state:
            removed.append(key)
        st.session_state.pop(key, None)
    st.session_state.pop(ORIGIN_AUTO_FORWARDED_KEY, None)
    _clear_manual_pause()
    add_audit_event('wizard_outputs_reset', area='WIZARD', step=st.session_state.get(WIZARD_STEP_KEY), details={'removed_keys': removed, 'operation_step_removed': REMOVED_OPERATION_STEP, 'responsible_file': RESPONSIBLE_FILE})


def _reset_wizard() -> None:
    _reset_outputs_for_operation_change()
    for key in (FLOW_ORIGIN_KEY, 'origem_final'):
        st.session_state.pop(key, None)
    _ensure_universal_operation_state()
    add_audit_event('wizard_reset', area='WIZARD', step=_current_step(), details={'operation_step_removed': REMOVED_OPERATION_STEP, 'responsible_file': RESPONSIBLE_FILE})
    _go_to_step(STEP_MODELO, reason='reset_wizard')


def _render_step_header() -> WizardNav:
    return render_step_header(steps=_active_steps(), current=_current_step())


def _audit_step_blocked(current: str, pending_message: str | None) -> None:
    marker_key = f'audit_blocked_notice_{current}_{hash(str(pending_message))}'
    if st.session_state.get(marker_key):
        return
    st.session_state[marker_key] = True
    add_audit_event('wizard_next_blocked', area='WIZARD', step=current, status='BLOQUEADO', details={'message': pending_message, 'operation': _selected_operation(), 'operation_step_removed': REMOVED_OPERATION_STEP, 'responsible_file': RESPONSIBLE_FILE})


def _sync_flow_state(origin: str, operation: str | None = None) -> None:
    operation = UNIVERSAL_INTERNAL_OPERATION
    origin = 'arquivo' if origin == 'arquivo' else 'site'
    previous_origin = st.session_state.get(FLOW_ORIGIN_KEY)

    st.session_state[FLOW_ORIGIN_KEY] = origin
    st.session_state[FLOW_OPERATION_KEY] = operation
    st.session_state.pop(FLOW_ACTIVE_KEY, None)
    st.session_state['operacao_final'] = operation
    st.session_state['tipo_operacao_final'] = operation
    st.session_state['origem_final'] = origin
    st.session_state['tipo_operacao_site'] = operation if origin == 'site' else ''
    st.session_state['home_operation_choice_removed'] = True

    if previous_origin != origin:
        st.session_state.pop(ORIGIN_AUTO_FORWARDED_KEY, None)
        add_audit_event('flow_state_synced_universal', area='WIZARD', step=_current_step(), details={'origin': origin, 'operation': operation, 'previous_origin': previous_origin, 'operation_step_removed': REMOVED_OPERATION_STEP, 'state_preserved': True, 'responsible_file': RESPONSIBLE_FILE})
    try:
        st.query_params['origem'] = origin
        st.query_params['flow'] = 'site' if origin == 'site' else 'planilha'
        st.query_params.pop('operacao', None)
    except Exception:
        pass


def _origin_from_radio_state(operation: str | None = None) -> str:
    _ = operation
    for key in ('frontpage_origin_radio_universal', f'frontpage_origin_radio_{UNIVERSAL_INTERNAL_OPERATION}', LEGACY_ORIGIN_RADIO_KEY):
        value = str(st.session_state.get(key) or '').strip().lower()
        if 'arquivo' in value:
            return 'arquivo'
        if 'site' in value:
            return 'site'
    return ''


def _current_origin_choice() -> str:
    current = str(st.session_state.get(FLOW_ORIGIN_KEY) or '').strip().lower()
    if current in {'arquivo', 'site'}:
        return current
    radio_origin = _origin_from_radio_state()
    if radio_origin:
        return radio_origin
    try:
        origem = str(st.query_params.get('origem', '') or '').strip().lower()
        flow = str(st.query_params.get('flow', '') or '').strip().lower()
    except Exception:
        origem = ''
        flow = ''
    if origem in {'arquivo', 'planilha', 'planilhas', 'xml', 'pdf'} or flow in {'arquivo', 'planilha', 'planilhas', 'xml', 'pdf'}:
        return 'arquivo'
    if origem == 'site' or flow == 'site':
        return 'site'
    return ''


def _nav_state_for_current_step() -> tuple[bool, str, str | None]:
    step = _current_step()

    if step == STEP_MODELO:
        return _has_home_models(), 'Avançar →', 'Envie ou mantenha um modelo para continuar.'
    if step == STEP_PRECIFICACAO:
        return True, 'Avançar →', None
    if step == STEP_ORIGEM:
        return _current_origin_choice() in {'arquivo', 'site'}, 'Avançar →', 'Escolha se os dados virão de um arquivo ou de um site.'
    if step == STEP_ENTRADA:
        return cadastro_context_ready(), 'Avançar →', 'Carregue ou capture os dados desta etapa.'
    if step == STEP_MAPEAMENTO:
        return cadastro_mapping_ready(), 'Avançar →', 'Confirme o mapeamento obrigatório.'
    if step == STEP_PREVIEW:
        return cadastro_mapping_ready(), 'Avançar →', 'O preview ainda depende da etapa anterior.'
    return False, 'Avançar →', None


def _render_nav_buttons(*, allow_next: bool = True, next_label: str = 'Continuar', pending_message: str | None = None) -> None:
    if bool(st.session_state.get(BOTTOM_NAV_RENDERED_KEY)):
        return
    _render_bottom_navigation(allow_next=allow_next, next_label=next_label, pending_message=pending_message)


def _render_bottom_navigation(*, allow_next: bool, next_label: str, pending_message: str | None) -> None:
    steps = _active_steps()
    current = _current_step()
    current_index = steps.index(current)
    is_last = current_index == len(steps) - 1

    st.markdown('<div data-testid="wizard-bottom-navigation"></div>', unsafe_allow_html=True)
    col_back, col_next = st.columns(2)
    with col_back:
        if st.button('← Voltar', use_container_width=True, key=f'wizard_bottom_back_{current}'):
            _previous_step()
    with col_next:
        if is_last:
            st.caption('Última etapa do fluxo.')
        elif allow_next:
            if st.button(next_label, use_container_width=True, key=f'wizard_bottom_next_{current}'):
                add_audit_event('wizard_next_clicked', area='WIZARD', step=current, details={'label': next_label, 'operation_step_removed': REMOVED_OPERATION_STEP, 'responsible_file': RESPONSIBLE_FILE})
                _next_step()
        else:
            _audit_step_blocked(current, pending_message)
            render_pending_notice(pending_message)

    st.session_state[BOTTOM_NAV_RENDERED_KEY] = True


def _render_bottom_navigation_for_current_step() -> None:
    allow_next, next_label, pending_message = _nav_state_for_current_step()
    _render_bottom_navigation(allow_next=allow_next, next_label=next_label, pending_message=pending_message)


def _clear_legacy_origin_widget_state() -> None:
    valid_keys = {'frontpage_origin_radio_universal', f'frontpage_origin_radio_{UNIVERSAL_INTERNAL_OPERATION}', 'home_pricing_enabled_toggle'}
    for key in list(st.session_state.keys()):
        text = str(key)
        if (text == LEGACY_ORIGIN_RADIO_KEY or text.startswith('frontpage_origin_radio')) and text not in valid_keys:
            st.session_state.pop(key, None)


def _render_model_step() -> None:
    from bling_app_zero.ui.home_models import render_home_bling_models

    with st.container(border=True):
        render_home_bling_models()
        _ensure_universal_operation_state()
        if not _has_home_models():
            add_audit_event('wizard_model_waiting_for_upload', area='WIZARD', step=STEP_MODELO, status='INFO', details={'operation_step_removed': REMOVED_OPERATION_STEP, 'responsible_file': RESPONSIBLE_FILE})


def _render_pricing_step() -> None:
    current_config = get_home_pricing_config()
    render_section_card(
        'Preço',
        'Calculadora compartilhada de preços',
        'Use a calculadora para calcular preço antes do mapeamento.',
    )
    use_pricing = st.toggle(
        'Usar calculadora compartilhada',
        value=bool(current_config.get('enabled', False)),
        key='home_pricing_enabled_toggle',
        help='Quando ativada, o preço calculado pode ser usado antes do mapeamento final.',
    )
    if use_pricing:
        with st.container(border=True):
            st.success('Calculadora compartilhada ativa para este fluxo.')
            config = render_home_pricing_config_form()
            set_home_pricing_config(config)
    else:
        disable_home_pricing()
        st.info('Calculadora desativada. O sistema manterá o preço da origem ou o valor definido no mapeamento.')


def _render_origin_explanation(origin: str) -> None:
    if origin == 'arquivo':
        st.success('Arquivo selecionado: na próxima etapa você vai anexar a planilha, CSV, XML ou PDF com os dados de origem.')
    elif origin == 'site':
        st.success('Site selecionado: na próxima etapa você vai colar os links do fornecedor para o sistema buscar os dados.')


def _render_origin_step() -> None:
    _ensure_universal_operation_state()
    _clear_legacy_origin_widget_state()

    st.markdown('### Escolha a origem dos dados')
    st.caption('De onde vêm os dados que você quer transformar para o modelo final?')
    st.info('Escolha Arquivo se você já tem uma planilha, CSV, XML ou PDF. Escolha Site se quer buscar os dados diretamente nos links do fornecedor.')

    options = {'arquivo': '📎 Arquivo do fornecedor', 'site': '🌐 Site do fornecedor'}
    labels = list(options.values())
    values = list(options.keys())
    selected = _current_origin_choice()
    index = values.index(selected) if selected in values else None

    choice_label = st.radio('Origem dos dados', labels, index=index, key='frontpage_origin_radio_universal', label_visibility='collapsed')
    if choice_label is None:
        return

    origin = values[labels.index(choice_label)]
    _sync_flow_state(origin)
    _render_origin_explanation(origin)

    target = wizard_next_target(STEP_ORIGEM, UNIVERSAL_INTERNAL_OPERATION)
    if target != STEP_ORIGEM:
        add_audit_event(
            'origin_selected_forced_auto_next',
            area='WIZARD',
            step=STEP_ORIGEM,
            details={'origin': origin, 'target': target, 'operation_step_removed': REMOVED_OPERATION_STEP, 'responsible_file': RESPONSIBLE_FILE},
        )
        _clear_manual_pause(STEP_ORIGEM)
        _go_to_step(target, reason='origin_selected_forced_auto_next')


def _render_cadastro_entrada() -> None:
    origin = _current_origin_choice()
    add_audit_event('universal_entry_rendered', area='UNIVERSAL', step=STEP_ENTRADA, details={'origin': origin, 'operation_step_removed': REMOVED_OPERATION_STEP, 'responsible_file': RESPONSIBLE_FILE})
    if origin == 'site':
        from bling_app_zero.ui.site_panel import render_site_panel

        render_site_panel()
    render_cadastro_entrada_step()


def _render_cadastro_mapeamento() -> None:
    render_cadastro_mapeamento_step()


def _render_cadastro_preview() -> None:
    render_cadastro_preview_step()


def _render_reset_only_footer(key: str) -> None:
    st.caption('Use os botões de navegação acima para voltar ou avançar sem perder o que já foi informado.')
    if st.button('Recomeçar fluxo', use_container_width=True, key=key):
        _reset_wizard()


def _render_cadastro_download() -> None:
    render_cadastro_download_step()
    _render_reset_only_footer('wizard_download_reset')


def render_home_wizard() -> None:
    _ensure_universal_operation_state()
    st.session_state[BOTTOM_NAV_RENDERED_KEY] = False
    nav = _render_step_header()
    step = _current_step()
    operation = _selected_operation()
    add_audit_event('wizard_step_rendered', area='WIZARD', step=step, details={'operation': operation or 'nao_escolhida', 'index': nav.index, 'total': nav.total, 'steps': nav.steps, 'bottom_navigation': True, 'back_always_clickable': True, 'linear_index_navigation': True, 'manual_navigation_pauses_autoflow': True, 'operation_step_removed': REMOVED_OPERATION_STEP, 'responsible_file': RESPONSIBLE_FILE})

    if step == STEP_MODELO:
        _render_model_step()
    elif step == STEP_PRECIFICACAO:
        _render_pricing_step()
    elif step == STEP_ORIGEM:
        _render_origin_step()
    elif step == STEP_ENTRADA:
        _render_cadastro_entrada()
    elif step == STEP_MAPEAMENTO:
        _render_cadastro_mapeamento()
    elif step == STEP_PREVIEW:
        _render_cadastro_preview()
    elif step == STEP_DOWNLOAD:
        _render_cadastro_download()
    else:
        add_audit_event('wizard_invalid_step', area='WIZARD', step=step, status='ERRO', details={'operation': operation, 'operation_step_removed': REMOVED_OPERATION_STEP, 'responsible_file': RESPONSIBLE_FILE})
        st.warning('Etapa inválida. O fluxo foi ajustado para continuar sem a escolha Cadastro/Estoque.')
        render_pending_notice('Volte uma etapa ou recomece o fluxo para sincronizar a navegação.')

    _render_bottom_navigation_for_current_step()
