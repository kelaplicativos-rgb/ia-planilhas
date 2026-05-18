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
)
from bling_app_zero.ui.home_wizard_ui import render_pending_notice, render_section_card
from bling_app_zero.ui.scroll_guard import inject_scroll_guard

RESPONSIBLE_FILE = 'bling_app_zero/ui/home_wizard.py'
UNIVERSAL_INTERNAL_OPERATION = 'cadastro'
REMOVED_OPERATION_STEP = True
SINGLE_PAGE_FLOW = True
HOME_ACTIVE_OPERATION_KEY = 'home_active_operation_v2'
HOME_ALLOW_OPERATION_KEY = 'home_allow_operation_v2_session'
HOME_CHOICE_TARGET = '__home_choice__'
BOTTOM_NAV_RENDERED_KEY = 'wizard_bottom_nav_rendered_current_cycle'
ORIGIN_AUTO_FORWARDED_KEY = 'wizard_origin_auto_forwarded_signature'
AUTOFLOW_PAUSE_STEP_KEY = 'bling_autofluxo_pause_step'
AUTOFLOW_MANUAL_LOCK_KEY = 'bling_autofluxo_manual_navigation_lock'
AUTOFLOW_LAST_STEP_KEY = 'bling_autofluxo_last_step'
AUTOFLOW_LAST_MOVE_KEY = 'bling_autofluxo_last_move'
MANUAL_NAVIGATION_REASONS = {'next_button', 'back_button_previous_index'}
VALID_OPERATIONS = {'cadastro', 'estoque'}

UNIVERSAL_STEPS = [step for step in CADASTRO_STEPS if step != STEP_OPERACAO]
ORIGIN_RADIO_KEY = 'frontpage_origin_radio_universal'
ORIGIN_OPTIONS = {'arquivo': '📎 Arquivo do fornecedor', 'site': '🌐 Site do fornecedor'}


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


def _query_param(name: str) -> str:
    try:
        value = st.query_params.get(name, '')
        if isinstance(value, list):
            return str(value[0] if value else '')
        return str(value or '')
    except Exception:
        return ''


def _normalize_operation(value: object) -> str:
    text = str(value or '').strip().lower()
    if text in {'cadastro', 'cadastro_site'}:
        return 'cadastro'
    if text in {'estoque', 'estoque_site', 'atualizacao_estoque', 'atualização de estoque'}:
        return 'estoque'
    if 'estoque' in text:
        return 'estoque'
    if 'cadastro' in text:
        return 'cadastro'
    return ''


def _operation_from_runtime() -> str:
    for value in (
        _query_param('operacao'),
        _query_param('operation'),
        _query_param('operation_v2'),
        st.session_state.get('home_detected_operation'),
        st.session_state.get(FLOW_OPERATION_KEY),
        st.session_state.get('operacao_final'),
        st.session_state.get('tipo_operacao_final'),
        st.session_state.get('tipo_operacao_site'),
        st.session_state.get('home_slim_flow_operation'),
    ):
        operation = _normalize_operation(value)
        if operation in VALID_OPERATIONS:
            return operation
    if _has_estoque_model() and not _has_cadastro_model():
        return 'estoque'
    return UNIVERSAL_INTERNAL_OPERATION


def _ensure_universal_operation_state() -> str:
    if not _has_home_models():
        return ''
    operation = _operation_from_runtime()
    st.session_state[FLOW_OPERATION_KEY] = operation
    st.session_state['operacao_final'] = operation
    st.session_state['tipo_operacao_final'] = operation
    st.session_state['home_detected_operation'] = operation
    st.session_state['home_operation_choice_removed'] = True
    return operation


def _selected_operation() -> str:
    return _ensure_universal_operation_state()


def wizard_steps_for_operation(operation: str | None = None) -> list[str]:
    _ = operation
    return list(UNIVERSAL_STEPS) if _has_home_models() else [STEP_MODELO]


def _target_by_delta(current_step: str, operation: str, delta: int) -> str:
    steps = wizard_steps_for_operation(operation)
    current = str(current_step or '').strip().lower()
    if current == STEP_OPERACAO:
        current = STEP_ORIGEM
    if current not in steps:
        return steps[0]
    index = steps.index(current)
    target_index = max(0, min(len(steps) - 1, index + delta))
    return steps[target_index]


def wizard_previous_target(current_step: str, operation: str) -> str:
    return _target_by_delta(current_step, operation, -1)


def wizard_next_target(current_step: str, operation: str) -> str:
    return _target_by_delta(current_step, operation, 1)


def _active_steps() -> list[str]:
    return wizard_steps_for_operation(_selected_operation())


def _current_step() -> str:
    step = str(st.session_state.get(WIZARD_STEP_KEY) or STEP_MODELO).strip().lower()
    if step == STEP_OPERACAO:
        step = STEP_ORIGEM
    if step not in _active_steps():
        step = STEP_MODELO if not _has_home_models() else STEP_ORIGEM
    st.session_state[WIZARD_STEP_KEY] = step
    return step


def _clear_manual_pause(step: str | None = None) -> None:
    _ = step
    for key in (AUTOFLOW_PAUSE_STEP_KEY, AUTOFLOW_MANUAL_LOCK_KEY, AUTOFLOW_LAST_MOVE_KEY):
        st.session_state.pop(key, None)


def _go_to_step(step: str, *, reason: str = 'navigation') -> None:
    if step == STEP_OPERACAO:
        step = STEP_ORIGEM
    if step not in _active_steps():
        step = STEP_ORIGEM if _has_home_models() else STEP_MODELO
    previous = st.session_state.get(WIZARD_STEP_KEY)
    st.session_state[WIZARD_STEP_KEY] = step
    add_audit_event('wizard_single_page_step_marker_changed', area='WIZARD', step=step, details={'from': previous, 'to': step, 'reason': reason, 'operation': _selected_operation(), 'single_page_flow': SINGLE_PAGE_FLOW, 'responsible_file': RESPONSIBLE_FILE})


def _back_to_home_choice() -> None:
    st.session_state.pop(HOME_ACTIVE_OPERATION_KEY, None)
    st.session_state.pop(HOME_ALLOW_OPERATION_KEY, None)
    _clear_manual_pause()
    for key in ('operation_v2', 'step'):
        try:
            st.query_params.pop(key, None)
        except Exception:
            pass
    add_audit_event('wizard_back_to_home_choice', area='WIZARD', step=_current_step(), details={'single_page_flow': SINGLE_PAGE_FLOW, 'state_preserved': True, 'responsible_file': RESPONSIBLE_FILE})
    st.rerun()


def _next_step() -> None:
    _go_to_step(wizard_next_target(_current_step(), _selected_operation()), reason='next_button')


def _previous_step() -> None:
    _go_to_step(wizard_previous_target(_current_step(), _selected_operation()), reason='back_button_previous_index')


def _reset_outputs_for_operation_change() -> None:
    removed: list[str] = []
    for key in RESET_OUTPUT_KEYS:
        if key in st.session_state:
            removed.append(key)
        st.session_state.pop(key, None)
    _clear_manual_pause()
    add_audit_event('wizard_outputs_reset', area='WIZARD', step=st.session_state.get(WIZARD_STEP_KEY), details={'removed_keys': removed, 'single_page_flow': SINGLE_PAGE_FLOW, 'responsible_file': RESPONSIBLE_FILE})


def _reset_wizard() -> None:
    _reset_outputs_for_operation_change()
    for key in (FLOW_ORIGIN_KEY, 'origem_final'):
        st.session_state.pop(key, None)
    _ensure_universal_operation_state()
    add_audit_event('wizard_reset', area='WIZARD', step=_current_step(), details={'single_page_flow': SINGLE_PAGE_FLOW, 'responsible_file': RESPONSIBLE_FILE})
    st.rerun()


def _force_model_first_when_missing() -> None:
    st.session_state[WIZARD_STEP_KEY] = STEP_MODELO
    for key in (
        FLOW_ORIGIN_KEY,
        FLOW_OPERATION_KEY,
        'origem_final',
        'tipo_operacao_site',
        'home_slim_flow_origin',
        'home_slim_flow_operation',
    ):
        st.session_state.pop(key, None)
    try:
        st.query_params['step'] = STEP_MODELO
        st.query_params.pop('origem', None)
        st.query_params.pop('flow', None)
        st.query_params.pop('operacao', None)
    except Exception:
        pass


def _render_step_header():
    st.caption('Fluxo em tela única: siga rolando para baixo.')
    return None


def _audit_step_blocked(current: str, pending_message: str | None) -> None:
    add_audit_event('wizard_single_page_notice', area='WIZARD', step=current, status='INFO', details={'message': pending_message, 'single_page_flow': SINGLE_PAGE_FLOW, 'responsible_file': RESPONSIBLE_FILE})


def _sync_flow_state(origin: str, operation: str | None = None) -> None:
    operation = _normalize_operation(operation) or _operation_from_runtime()
    origin = 'arquivo' if origin == 'arquivo' else 'site'
    previous_origin = st.session_state.get(FLOW_ORIGIN_KEY)
    st.session_state[FLOW_ORIGIN_KEY] = origin
    st.session_state[FLOW_OPERATION_KEY] = operation
    st.session_state.pop(FLOW_ACTIVE_KEY, None)
    st.session_state['operacao_final'] = operation
    st.session_state['tipo_operacao_final'] = operation
    st.session_state['origem_final'] = origin
    st.session_state['tipo_operacao_site'] = operation if origin == 'site' else ''
    st.session_state['home_slim_flow_operation'] = operation
    st.session_state['home_operation_choice_removed'] = True
    st.session_state[WIZARD_STEP_KEY] = STEP_ENTRADA
    if previous_origin != origin:
        add_audit_event('single_page_origin_selected', area='WIZARD', step=STEP_ORIGEM, details={'origin': origin, 'operation': operation, 'previous_origin': previous_origin, 'single_page_flow': SINGLE_PAGE_FLOW, 'responsible_file': RESPONSIBLE_FILE})
    try:
        st.query_params['origem'] = origin
        st.query_params['flow'] = 'site' if origin == 'site' else 'planilha'
        st.query_params['step'] = STEP_ENTRADA
        st.query_params['operacao'] = operation
    except Exception:
        pass


def _select_origin(origin: str) -> None:
    origin = _normalize_origin_value(origin)
    if origin not in {'arquivo', 'site'}:
        return
    st.session_state[ORIGIN_RADIO_KEY] = origin
    _sync_flow_state(origin, _selected_operation())
    st.rerun()


def _normalize_origin_value(value: object) -> str:
    text = str(value or '').strip().lower()
    if text in {'arquivo', 'site'}:
        return text
    if 'arquivo' in text or 'planilha' in text or 'xml' in text or 'pdf' in text:
        return 'arquivo'
    if 'site' in text:
        return 'site'
    return ''


def _origin_from_radio_state(operation: str | None = None) -> str:
    _ = operation
    for key in (ORIGIN_RADIO_KEY, f'frontpage_origin_radio_{UNIVERSAL_INTERNAL_OPERATION}', LEGACY_ORIGIN_RADIO_KEY):
        origin = _normalize_origin_value(st.session_state.get(key))
        if origin:
            return origin
    return ''


def _current_origin_choice() -> str:
    current = _normalize_origin_value(st.session_state.get(FLOW_ORIGIN_KEY))
    if current:
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
    if step == STEP_ORIGEM:
        return _current_origin_choice() in {'arquivo', 'site'}, 'Avançar →', 'Escolha se os dados virão de um arquivo ou de um site.'
    if step == STEP_ENTRADA:
        return cadastro_context_ready(), 'Avançar →', 'Carregue ou capture os dados desta etapa.'
    if step == STEP_MAPEAMENTO:
        return cadastro_mapping_ready(), 'Avançar →', 'Confirme o mapeamento obrigatório.'
    if step == STEP_PREVIEW:
        return cadastro_mapping_ready(), 'Avançar →', 'O preview ainda depende da etapa anterior.'
    return True, 'Avançar →', None


def _render_nav_buttons(*, allow_next: bool = True, next_label: str = 'Continuar', pending_message: str | None = None) -> None:
    _ = (allow_next, next_label, pending_message)


def _render_bottom_navigation(*, allow_next: bool, next_label: str, pending_message: str | None) -> None:
    _ = (allow_next, next_label, pending_message)


def _render_bottom_navigation_for_current_step() -> None:
    st.session_state[BOTTOM_NAV_RENDERED_KEY] = True


def _clear_legacy_origin_widget_state() -> None:
    valid_keys = {ORIGIN_RADIO_KEY, f'frontpage_origin_radio_{UNIVERSAL_INTERNAL_OPERATION}', 'home_pricing_enabled_toggle'}
    for key in list(st.session_state.keys()):
        text = str(key)
        if (text == LEGACY_ORIGIN_RADIO_KEY or text.startswith('frontpage_origin_radio')) and text not in valid_keys:
            st.session_state.pop(key, None)


def _section_title(number: int, title: str, caption: str = '') -> None:
    st.markdown('---')
    st.markdown(f'### {number}. {title}')
    if caption:
        st.caption(caption)


def _render_model_step() -> None:
    from bling_app_zero.ui.home_models import render_home_bling_models
    _section_title(
        1,
        'Anexe a planilha modelo preenchida',
        'Envie o arquivo modelo que será usado como base para gerar o resultado final.',
    )
    with st.container(border=True):
        render_home_bling_models()
    _ensure_universal_operation_state()
    if not _has_home_models():
        render_pending_notice('Atenção: anexe a planilha modelo preenchida para liberar as próximas seções.')


def _render_origin_explanation(origin: str) -> None:
    if origin == 'arquivo':
        st.success('Arquivo selecionado. Role para baixo e anexe a planilha, CSV, XML ou PDF com os dados de origem.')
    elif origin == 'site':
        st.success('Site selecionado. Role para baixo e cole os links do fornecedor.')


def _render_origin_step() -> None:
    _section_title(2, 'Origem dos dados', 'Escolha de onde vêm os dados que preencherão o modelo.')
    if not _has_home_models():
        render_pending_notice('A origem dos dados será liberada depois que o modelo de destino for anexado.')
        return
    _ensure_universal_operation_state()
    _clear_legacy_origin_widget_state()
    selected = _current_origin_choice()

    col1, col2 = st.columns(2)
    with col1:
        if st.button('📎 Usar arquivo do fornecedor', use_container_width=True, key='origin_choose_file'):
            _select_origin('arquivo')
    with col2:
        if st.button('🌐 Usar site do fornecedor', use_container_width=True, key='origin_choose_site'):
            _select_origin('site')

    if selected in {'arquivo', 'site'}:
        _render_origin_explanation(selected)
        return

    render_pending_notice('Escolha Arquivo ou Site para liberar a seção Dados de origem logo abaixo.')


def _render_cadastro_entrada() -> None:
    origin = _current_origin_choice()
    _section_title(3, 'Dados de origem', 'Aqui entram os dados reais: arquivo do fornecedor ou links do site.')
    if not _has_home_models():
        render_pending_notice('Os dados de origem serão liberados depois que o modelo de destino for anexado.')
        return
    if origin not in {'arquivo', 'site'}:
        render_pending_notice('Escolha a origem dos dados acima para liberar esta seção.')
        return
    add_audit_event('single_page_origin_data_rendered', area='UNIVERSAL', step=STEP_ENTRADA, details={'origin': origin, 'operation': _selected_operation(), 'single_page_flow': SINGLE_PAGE_FLOW, 'responsible_file': RESPONSIBLE_FILE})
    if origin == 'site':
        from bling_app_zero.ui.site_panel import render_site_panel
        render_site_panel()
    render_cadastro_entrada_step()


def _render_pricing_step() -> None:
    _section_title(4, 'Calculadora de preço', 'Opcional. Use depois de escolher a origem e carregar os dados.')
    if not _has_home_models():
        render_pending_notice('A calculadora será liberada depois que o modelo de destino for anexado.')
        return
    if not cadastro_context_ready():
        render_pending_notice('Carregue ou capture os dados de origem antes de usar a calculadora.')
        return
    current_config = get_home_pricing_config()
    use_pricing = st.toggle('Usar calculadora compartilhada', value=bool(current_config.get('enabled', False)), key='home_pricing_enabled_toggle', help='Quando ativada, o preço calculado pode ser usado antes do mapeamento final.')
    if use_pricing:
        with st.container(border=True):
            st.success('Calculadora compartilhada ativa para este fluxo.')
            config = render_home_pricing_config_form()
            set_home_pricing_config(config)
    else:
        disable_home_pricing()
        st.info('Calculadora desativada. O sistema manterá o preço da origem ou o valor definido no mapeamento.')


def _render_cadastro_mapeamento() -> None:
    _section_title(5, 'Mapeamento + IA', 'Ligue as colunas da origem nas colunas do modelo final.')
    if not _has_home_models():
        render_pending_notice('O mapeamento será liberado depois que o modelo e os dados de origem forem carregados.')
        return
    if not cadastro_context_ready():
        render_pending_notice('Carregue ou capture os dados de origem na seção anterior para liberar o mapeamento.')
        return
    render_cadastro_mapeamento_step()


def _render_cadastro_preview() -> None:
    _section_title(6, 'Preview', 'Confira o arquivo final antes de baixar.')
    if not _has_home_models():
        render_pending_notice('O preview será liberado depois que o modelo, a origem e o mapeamento forem concluídos.')
        return
    if not cadastro_mapping_ready():
        render_pending_notice('Confirme o mapeamento para liberar o preview.')
        return
    render_cadastro_preview_step()


def _render_reset_only_footer(key: str) -> None:
    st.caption('O fluxo está em tela única. Você pode rolar para revisar qualquer seção acima.')
    if st.button('Recomeçar fluxo', use_container_width=True, key=key):
        _reset_wizard()


def _render_cadastro_download() -> None:
    _section_title(7, 'Download', 'Baixe o CSV final pronto para importar.')
    if not _has_home_models():
        render_pending_notice('O download será liberado depois que todas as etapas anteriores forem concluídas.')
        return
    if not cadastro_mapping_ready():
        render_pending_notice('O download será liberado depois do mapeamento confirmado e do preview.')
        return
    render_cadastro_download_step()
    _render_reset_only_footer('wizard_download_reset_single_page')


def render_home_wizard() -> None:
    inject_scroll_guard('home_wizard')
    has_model = _has_home_models()
    operation = _ensure_universal_operation_state()
    st.session_state[BOTTOM_NAV_RENDERED_KEY] = True
    st.session_state['home_single_page_flow_active'] = True

    if not has_model:
        _force_model_first_when_missing()
        add_audit_event('wizard_model_first_guard_active', area='WIZARD', step=STEP_MODELO, details={'reason': 'missing_destination_model', 'single_page_flow': SINGLE_PAGE_FLOW, 'responsible_file': RESPONSIBLE_FILE})
        st.info('Comece anexando a planilha modelo preenchida. Depois o sistema libera as próximas etapas automaticamente.')
        _render_model_step()
        return

    add_audit_event('wizard_single_page_rendered', area='WIZARD', step='single_page', details={'operation': operation or 'nao_escolhida', 'steps': UNIVERSAL_STEPS, 'single_page_flow': SINGLE_PAGE_FLOW, 'responsible_file': RESPONSIBLE_FILE})
    st.info('Fluxo em tela única: siga rolando para baixo. As seções abaixo ficam visíveis e mostram claramente o que falta liberar.')
    _render_model_step()
    _render_origin_step()
    _render_cadastro_entrada()
    _render_pricing_step()
    _render_cadastro_mapeamento()
    _render_cadastro_preview()
    _render_cadastro_download()


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
