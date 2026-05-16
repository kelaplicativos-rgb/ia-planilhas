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
from bling_app_zero.ui.estoque_wizard_steps import (
    estoque_context_ready,
    estoque_output_ready,
    render_estoque_download_step,
    render_estoque_entrada_step,
    render_estoque_gerar_step,
    render_estoque_preview_step,
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
    STEP_GERAR_ESTOQUE,
    STEP_MAPEAMENTO,
    STEP_MODELO,
    STEP_OPERACAO,
    STEP_ORIGEM,
    STEP_PRECIFICACAO,
    STEP_PREVIEW,
    STEP_REGRAS,
    WIZARD_STEP_KEY,
    WizardNav,
)
from bling_app_zero.ui.home_wizard_ui import render_pending_notice, render_section_card, render_step_header
from bling_app_zero.ui.rules_center_step import render_rules_center_step, rules_center_ready

RESPONSIBLE_FILE = 'bling_app_zero/ui/home_wizard.py'
ORIGIN_AUTO_FORWARDED_KEY = 'wizard_origin_auto_forwarded_signature'
BOTTOM_NAV_RENDERED_KEY = 'wizard_bottom_nav_rendered_current_cycle'
HOME_ACTIVE_OPERATION_KEY = 'home_active_operation_v2'
HOME_ALLOW_OPERATION_KEY = 'home_allow_operation_v2_session'
HOME_CHOICE_TARGET = '__home_choice__'


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


def _available_operations() -> list[str]:
    operations: list[str] = []
    if _has_cadastro_model():
        operations.append('cadastro')
    if _has_estoque_model():
        operations.append('estoque')
    return operations


def _selected_operation() -> str:
    available = _available_operations()
    if not available:
        return ''

    operation = str(st.session_state.get(FLOW_OPERATION_KEY) or '').strip().lower()
    if operation not in available:
        operation = available[0]
        st.session_state[FLOW_OPERATION_KEY] = operation
        st.session_state['operacao_final'] = operation
        st.session_state['tipo_operacao_final'] = operation
        add_audit_event(
            'operation_auto_selected',
            area='WIZARD',
            step=st.session_state.get(WIZARD_STEP_KEY),
            details={'operation': operation, 'available': available, 'responsible_file': RESPONSIBLE_FILE},
        )
    return operation


def wizard_steps_for_operation(operation: str) -> list[str]:
    """Fluxograma oficial da operação para os botões Voltar/Avançar."""
    return list(ESTOQUE_STEPS if str(operation or '').strip().lower() == 'estoque' else CADASTRO_STEPS)


def _target_by_delta(current_step: str, operation: str, delta: int) -> str:
    steps = wizard_steps_for_operation(operation)
    current = str(current_step or '').strip().lower()
    if current not in steps:
        return STEP_MODELO
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
    elif step not in steps:
        step = STEP_MODELO
    st.session_state[WIZARD_STEP_KEY] = step
    return step


def _go_to_step(step: str, *, reason: str = 'navigation') -> None:
    steps = _active_steps()
    previous = str(st.session_state.get(WIZARD_STEP_KEY) or '').strip().lower()
    requested = step
    if step not in steps:
        step = STEP_MODELO

    if step == previous:
        add_audit_event(
            'wizard_step_kept',
            area='WIZARD',
            step=step,
            details={'from': previous, 'to': step, 'requested': requested, 'reason': reason, 'operation': _selected_operation(), 'state_preserved': True, 'responsible_file': RESPONSIBLE_FILE},
        )
        return

    st.session_state[WIZARD_STEP_KEY] = step
    add_audit_event(
        'wizard_step_changed',
        area='WIZARD',
        step=step,
        details={'from': previous, 'to': step, 'requested': requested, 'reason': reason, 'operation': _selected_operation(), 'state_preserved': True, 'responsible_file': RESPONSIBLE_FILE},
    )
    try:
        st.query_params['step'] = step
    except Exception:
        pass
    st.rerun()


def _back_to_home_choice() -> None:
    st.session_state.pop(HOME_ACTIVE_OPERATION_KEY, None)
    st.session_state.pop(HOME_ALLOW_OPERATION_KEY, None)
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
    add_audit_event('wizard_outputs_reset', area='WIZARD', step=st.session_state.get(WIZARD_STEP_KEY), details={'removed_keys': removed, 'responsible_file': RESPONSIBLE_FILE})


def _reset_wizard() -> None:
    _reset_outputs_for_operation_change()
    for key in (FLOW_OPERATION_KEY, FLOW_ORIGIN_KEY, 'operacao_final', 'tipo_operacao_final', 'origem_final'):
        st.session_state.pop(key, None)
    add_audit_event('wizard_reset', area='WIZARD', step=_current_step(), details={'responsible_file': RESPONSIBLE_FILE})
    _go_to_step(STEP_MODELO, reason='reset_wizard')


def _render_step_header() -> WizardNav:
    return render_step_header(steps=_active_steps(), current=_current_step())


def _audit_step_blocked(current: str, pending_message: str | None) -> None:
    marker_key = f'audit_blocked_notice_{current}_{hash(str(pending_message))}'
    if st.session_state.get(marker_key):
        return
    st.session_state[marker_key] = True
    add_audit_event('wizard_next_blocked', area='WIZARD', step=current, status='BLOQUEADO', details={'message': pending_message, 'operation': _selected_operation(), 'responsible_file': RESPONSIBLE_FILE})


def _sync_flow_state(origin: str, operation: str) -> None:
    origin = 'arquivo' if origin == 'arquivo' else 'site'
    operation = 'estoque' if operation == 'estoque' else 'cadastro'
    previous_origin = st.session_state.get(FLOW_ORIGIN_KEY)
    previous_operation = st.session_state.get(FLOW_OPERATION_KEY)

    st.session_state[FLOW_ORIGIN_KEY] = origin
    st.session_state[FLOW_OPERATION_KEY] = operation
    st.session_state.pop(FLOW_ACTIVE_KEY, None)
    st.session_state['operacao_final'] = operation
    st.session_state['tipo_operacao_final'] = operation
    st.session_state['origem_final'] = origin
    st.session_state['tipo_operacao_site'] = operation if origin == 'site' else ''

    if previous_origin != origin or previous_operation != operation:
        st.session_state.pop(ORIGIN_AUTO_FORWARDED_KEY, None)
        add_audit_event('flow_state_synced', area='WIZARD', step=_current_step(), details={'origin': origin, 'operation': operation, 'previous_origin': previous_origin, 'previous_operation': previous_operation, 'state_preserved': True, 'responsible_file': RESPONSIBLE_FILE})
    try:
        st.query_params['origem'] = origin
        st.query_params['operacao'] = operation
        st.query_params['flow'] = 'site' if origin == 'site' else 'planilha'
    except Exception:
        pass


def _origin_from_radio_state(operation: str) -> str:
    value = str(st.session_state.get(f'frontpage_origin_radio_{operation}') or '').strip().lower()
    if 'arquivo' in value:
        return 'arquivo'
    if 'site' in value:
        return 'site'
    return ''


def _current_origin_choice() -> str:
    current = str(st.session_state.get(FLOW_ORIGIN_KEY) or '').strip().lower()
    if current in {'arquivo', 'site'}:
        return current
    radio_origin = _origin_from_radio_state(_selected_operation())
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
    operation = _selected_operation()

    if step == STEP_MODELO:
        return _has_home_models(), 'Avançar →', 'Envie ou mantenha um modelo do Bling para continuar.'
    if step == STEP_OPERACAO:
        return operation in {'cadastro', 'estoque'}, 'Avançar →', 'Escolha Cadastro ou Estoque.'
    if step == STEP_PRECIFICACAO:
        return True, 'Avançar →', None
    if step == STEP_ORIGEM:
        return _current_origin_choice() in {'arquivo', 'site'}, 'Avançar →', 'Escolha Arquivo ou Site.'
    if step == STEP_REGRAS:
        return rules_center_ready(), 'Avançar →', 'Confirme as regras antes de continuar.'
    if step == STEP_ENTRADA:
        ready = estoque_context_ready() if operation == 'estoque' else cadastro_context_ready()
        return ready, 'Avançar →', 'Carregue ou capture os dados desta etapa.'
    if step == STEP_MAPEAMENTO:
        return cadastro_mapping_ready(), 'Avançar →', 'Confirme o mapeamento obrigatório.'
    if step == STEP_GERAR_ESTOQUE:
        return estoque_output_ready(), 'Avançar →', 'Gere/confira o estoque antes do preview.'
    if step == STEP_PREVIEW:
        ready = estoque_output_ready() if operation == 'estoque' else cadastro_mapping_ready()
        return ready, 'Avançar →', 'O preview ainda depende da etapa anterior.'
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
                add_audit_event('wizard_next_clicked', area='WIZARD', step=current, details={'label': next_label, 'responsible_file': RESPONSIBLE_FILE})
                _next_step()
        else:
            _audit_step_blocked(current, pending_message)
            render_pending_notice(pending_message)

    st.session_state[BOTTOM_NAV_RENDERED_KEY] = True


def _render_bottom_navigation_for_current_step() -> None:
    allow_next, next_label, pending_message = _nav_state_for_current_step()
    _render_bottom_navigation(allow_next=allow_next, next_label=next_label, pending_message=pending_message)


def _clear_legacy_origin_widget_state(operation: str) -> None:
    st.session_state.pop(LEGACY_ORIGIN_RADIO_KEY, None)
    valid_keys = {f'frontpage_origin_radio_{operation}', 'home_pricing_enabled_toggle'}
    for key in list(st.session_state.keys()):
        text = str(key)
        if text.startswith('frontpage_origin_radio') and text not in valid_keys:
            st.session_state.pop(key, None)


def _render_model_step() -> None:
    from bling_app_zero.ui.home_models import render_home_bling_models

    with st.container(border=True):
        render_home_bling_models()
        if not _has_home_models():
            add_audit_event('wizard_model_waiting_for_upload', area='WIZARD', step=STEP_MODELO, status='INFO', details={'responsible_file': RESPONSIBLE_FILE})


def _render_operation_step() -> None:
    available = _available_operations()
    if not available:
        return

    labels_by_value = {'cadastro': '🧾 Cadastro', 'estoque': '📦 Estoque'}
    if len(available) == 1:
        selected = available[0]
        st.session_state[FLOW_OPERATION_KEY] = selected
        st.session_state['operacao_final'] = selected
        st.session_state['tipo_operacao_final'] = selected
        st.success(f'Operação: {labels_by_value[selected]}')
        return

    current = _selected_operation()
    labels = [labels_by_value[value] for value in available]
    index = available.index(current) if current in available else 0
    choice_label = st.radio('Operação', labels, index=index, key='wizard_operation_radio', label_visibility='collapsed')
    selected = available[labels.index(choice_label)] if choice_label else current

    if selected != st.session_state.get(FLOW_OPERATION_KEY):
        _reset_outputs_for_operation_change()
    st.session_state[FLOW_OPERATION_KEY] = selected
    st.session_state['operacao_final'] = selected
    st.session_state['tipo_operacao_final'] = selected


def _render_pricing_step() -> None:
    current_config = get_home_pricing_config()
    render_section_card(
        'Preço',
        'Calculadora compartilhada de preços',
        'Use a mesma calculadora do Atualizar Preços Multiloja para calcular preço antes do mapeamento.',
    )
    use_pricing = st.toggle(
        'Usar calculadora compartilhada',
        value=bool(current_config.get('enabled', False)),
        key='home_pricing_enabled_toggle',
        help='Quando ativada, o cadastro por site ou anexo usa o motor compartilhado de preço antes do mapeamento.',
    )
    if use_pricing:
        with st.container(border=True):
            st.success('Calculadora compartilhada ativa para este fluxo.')
            config = render_home_pricing_config_form()
            set_home_pricing_config(config)
    else:
        disable_home_pricing()
        st.info('Calculadora desativada. O sistema manterá o preço da origem ou o valor definido no mapeamento.')


def _render_origin_step() -> None:
    operation = _selected_operation()
    _clear_legacy_origin_widget_state(operation)

    st.markdown('### Origem')
    options = {'arquivo': '📎 Arquivo', 'site': '🌐 Site'}
    labels = list(options.values())
    values = list(options.keys())
    selected = _current_origin_choice()
    index = values.index(selected) if selected in values else None

    choice_label = st.radio('Origem dos dados', labels, index=index, key=f'frontpage_origin_radio_{operation}', label_visibility='collapsed')
    if choice_label is None:
        return

    origin = values[labels.index(choice_label)]
    _sync_flow_state(origin, operation)
    st.success('Origem definida. Avançando para a próxima etapa.')

    signature = f'{operation}:{origin}'
    if st.session_state.get(ORIGIN_AUTO_FORWARDED_KEY) != signature:
        st.session_state[ORIGIN_AUTO_FORWARDED_KEY] = signature
        _go_to_step(wizard_next_target(STEP_ORIGEM, operation), reason='origin_selected_auto_next')


def _render_rules_step() -> None:
    render_rules_center_step()


def _render_cadastro_entrada() -> None:
    origin = _current_origin_choice()
    add_audit_event('cadastro_entry_rendered', area='CADASTRO', step=STEP_ENTRADA, details={'origin': origin, 'responsible_file': RESPONSIBLE_FILE})
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


def _render_estoque_entrada() -> None:
    origin = _current_origin_choice()
    add_audit_event('estoque_entry_rendered', area='ESTOQUE', step=STEP_ENTRADA, details={'origin': origin, 'responsible_file': RESPONSIBLE_FILE})
    if origin == 'site':
        from bling_app_zero.ui.site_panel import render_site_panel

        render_site_panel()
    render_estoque_entrada_step()


def _render_estoque_gerar() -> None:
    render_estoque_gerar_step()


def _render_estoque_preview() -> None:
    render_estoque_preview_step()


def _render_estoque_download() -> None:
    render_estoque_download_step()
    _render_reset_only_footer('wizard_estoque_download_reset')


def render_home_wizard() -> None:
    st.session_state[BOTTOM_NAV_RENDERED_KEY] = False
    nav = _render_step_header()
    step = _current_step()
    operation = _selected_operation()
    add_audit_event('wizard_step_rendered', area='WIZARD', step=step, details={'operation': operation, 'index': nav.index, 'total': nav.total, 'steps': nav.steps, 'bottom_navigation': True, 'back_always_clickable': True, 'linear_index_navigation': True, 'responsible_file': RESPONSIBLE_FILE})

    if step == STEP_MODELO:
        _render_model_step()
    elif step == STEP_OPERACAO:
        _render_operation_step()
    elif step == STEP_PRECIFICACAO:
        _render_pricing_step()
    elif step == STEP_ORIGEM:
        _render_origin_step()
    elif step == STEP_REGRAS:
        _render_rules_step()
    elif operation == 'cadastro' and step == STEP_ENTRADA:
        _render_cadastro_entrada()
    elif operation == 'cadastro' and step == STEP_MAPEAMENTO:
        _render_cadastro_mapeamento()
    elif operation == 'cadastro' and step == STEP_PREVIEW:
        _render_cadastro_preview()
    elif operation == 'cadastro' and step == STEP_DOWNLOAD:
        _render_cadastro_download()
    elif operation == 'estoque' and step == STEP_ENTRADA:
        _render_estoque_entrada()
    elif operation == 'estoque' and step == STEP_GERAR_ESTOQUE:
        _render_estoque_gerar()
    elif operation == 'estoque' and step == STEP_PREVIEW:
        _render_estoque_preview()
    elif operation == 'estoque' and step == STEP_DOWNLOAD:
        _render_estoque_download()
    else:
        add_audit_event('wizard_invalid_step', area='WIZARD', step=step, status='ERRO', details={'operation': operation, 'responsible_file': RESPONSIBLE_FILE})
        st.warning('Etapa inválida. Recomece o fluxo.')
        render_pending_notice('Fluxo inválido.')

    _render_bottom_navigation_for_current_step()
