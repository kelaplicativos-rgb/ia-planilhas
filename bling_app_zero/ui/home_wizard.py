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
    render_home_pricing_config_form,
    set_home_pricing_config,
)
from bling_app_zero.ui.home_wizard_constants import (
    ALL_STEPS,
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
from bling_app_zero.ui.home_wizard_ui import (
    render_pending_notice,
    render_section_card,
    render_step_header,
)
from bling_app_zero.ui.rules_center_step import render_rules_center_step, rules_center_ready

RESPONSIBLE_FILE = 'bling_app_zero/ui/home_wizard.py'


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
    return _has_any_model([HOME_CADASTRO_MODEL_KEY] + GLOBAL_CADASTRO_MODEL_KEYS)


def _has_estoque_model() -> bool:
    return _has_any_model([HOME_ESTOQUE_MODEL_KEY] + GLOBAL_ESTOQUE_MODEL_KEYS)


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
    operation = str(st.session_state.get(FLOW_OPERATION_KEY) or '').strip().lower()
    available = _available_operations()
    if not available:
        return ''
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


def _active_steps() -> list[str]:
    return ESTOQUE_STEPS if _selected_operation() == 'estoque' else CADASTRO_STEPS


def _current_step() -> str:
    steps = _active_steps()
    step = str(st.session_state.get(WIZARD_STEP_KEY) or STEP_MODELO).strip().lower()
    if not _has_home_models():
        step = STEP_MODELO
    elif step not in steps:
        original_step = step
        step = STEP_OPERACAO if step in ALL_STEPS and STEP_OPERACAO in steps else STEP_MODELO
        add_audit_event(
            'wizard_step_normalized',
            area='WIZARD',
            step=step,
            details={
                'original_step': original_step,
                'normalized_step': step,
                'steps': steps,
                'responsible_file': RESPONSIBLE_FILE,
            },
        )
    st.session_state[WIZARD_STEP_KEY] = step
    return step


def _go_to_step(step: str, *, reason: str = 'navigation') -> None:
    steps = _active_steps()
    previous = str(st.session_state.get(WIZARD_STEP_KEY) or '').strip().lower()
    requested = step
    if step not in steps:
        step = STEP_MODELO
    st.session_state[WIZARD_STEP_KEY] = step
    add_audit_event(
        'wizard_step_changed',
        area='WIZARD',
        step=step,
        details={
            'from': previous,
            'to': step,
            'requested': requested,
            'reason': reason,
            'operation': _selected_operation(),
            'responsible_file': RESPONSIBLE_FILE,
        },
    )
    try:
        st.query_params['step'] = step
    except Exception:
        pass
    st.rerun()


def _next_step() -> None:
    steps = _active_steps()
    step = _current_step()
    index = steps.index(step)
    if index < len(steps) - 1:
        _go_to_step(steps[index + 1], reason='next_button')


def _previous_step() -> None:
    steps = _active_steps()
    step = _current_step()
    index = steps.index(step)
    if index > 0:
        _go_to_step(steps[index - 1], reason='back_button')


def _reset_outputs_for_operation_change() -> None:
    removed: list[str] = []
    for key in RESET_OUTPUT_KEYS:
        if key in st.session_state:
            removed.append(key)
        st.session_state.pop(key, None)
    add_audit_event(
        'wizard_outputs_reset',
        area='WIZARD',
        step=st.session_state.get(WIZARD_STEP_KEY),
        details={'removed_keys': removed, 'responsible_file': RESPONSIBLE_FILE},
    )


def _reset_wizard() -> None:
    _reset_outputs_for_operation_change()
    st.session_state.pop(FLOW_OPERATION_KEY, None)
    st.session_state.pop('operacao_final', None)
    st.session_state.pop('tipo_operacao_final', None)
    add_audit_event('wizard_reset', area='WIZARD', step=_current_step(), details={'responsible_file': RESPONSIBLE_FILE})
    _go_to_step(STEP_MODELO, reason='reset_wizard')


def _render_step_header() -> WizardNav:
    return render_step_header(steps=_active_steps(), current=_current_step())


def _debug_state_keys(keys: list[str]) -> dict[str, object]:
    debug: dict[str, object] = {}
    for key in keys:
        value = st.session_state.get(key)
        if value is None:
            debug[key] = {'present': False, 'loaded_dataframe': False}
            continue
        summary: dict[str, object] = {
            'present': True,
            'type': type(value).__name__,
            'loaded_dataframe': _looks_like_loaded_df(value),
        }
        if hasattr(value, 'shape'):
            try:
                summary['shape'] = tuple(value.shape)
            except Exception:
                pass
        if isinstance(value, (list, tuple, set, dict, str)):
            try:
                summary['length'] = len(value)
            except Exception:
                pass
        debug[key] = summary
    return debug


def _blocked_audit_details(current: str, pending_message: str | None) -> dict[str, object]:
    details: dict[str, object] = {
        'message': pending_message,
        'operation': _selected_operation(),
        'step': current,
        'wizard_step_key': WIZARD_STEP_KEY,
        'responsible_file': RESPONSIBLE_FILE,
    }
    if current == STEP_MODELO:
        required_keys = [
            HOME_CADASTRO_MODEL_KEY,
            *GLOBAL_CADASTRO_MODEL_KEYS,
            HOME_ESTOQUE_MODEL_KEY,
            *GLOBAL_ESTOQUE_MODEL_KEYS,
            'home_model_upload_bling',
        ]
        details.update(
            {
                'blocking_reason': 'missing_bling_model',
                'blocking_key': 'home_model_upload_bling',
                'required_any_of': [
                    HOME_CADASTRO_MODEL_KEY,
                    *GLOBAL_CADASTRO_MODEL_KEYS,
                    HOME_ESTOQUE_MODEL_KEY,
                    *GLOBAL_ESTOQUE_MODEL_KEYS,
                ],
                'state_keys': _debug_state_keys(required_keys),
            }
        )
    elif current == STEP_OPERACAO:
        details.update(
            {
                'blocking_reason': 'operation_not_selected_or_model_not_detected',
                'blocking_key': FLOW_OPERATION_KEY,
                'state_keys': _debug_state_keys([FLOW_OPERATION_KEY, 'operacao_final', 'tipo_operacao_final']),
            }
        )
    elif current == STEP_ORIGEM:
        details.update(
            {
                'blocking_reason': 'origin_not_selected',
                'blocking_key': FLOW_ORIGIN_KEY,
                'state_keys': _debug_state_keys([FLOW_ORIGIN_KEY, 'origem_final', 'origem_dados', 'origem_tipo']),
            }
        )
    elif current == STEP_REGRAS:
        details.update(
            {
                'blocking_reason': 'rules_center_not_confirmed',
                'blocking_key': 'rules_center_reviewed',
                'state_keys': _debug_state_keys(['rules_center_reviewed', 'bling_user_rules']),
            }
        )
    elif current == STEP_ENTRADA:
        details.update(
            {
                'blocking_reason': 'input_data_not_ready',
                'state_keys': _debug_state_keys([
                    'cadastro_wizard_df_origem',
                    'cadastro_wizard_df_para_mapear',
                    'estoque_wizard_upload',
                    'estoque_wizard_df_origem_site',
                ]),
            }
        )
    elif current == STEP_MAPEAMENTO:
        details.update(
            {
                'blocking_reason': 'mapping_not_confirmed',
                'blocking_key': 'cadastro_mapping_confirmed',
                'state_keys': _debug_state_keys(['cadastro_mapping_confirmed', 'mapping_cadastro', 'mapping_confidence_cadastro']),
            }
        )
    elif current == STEP_GERAR_ESTOQUE:
        details.update(
            {
                'blocking_reason': 'stock_output_not_generated',
                'blocking_key': 'df_final_estoque',
                'state_keys': _debug_state_keys(['estoque_multi_outputs', 'df_final_estoque', 'mapping_estoque']),
            }
        )
    elif current == STEP_PREVIEW:
        details.update(
            {
                'blocking_reason': 'preview_source_not_ready',
                'state_keys': _debug_state_keys(['df_final_cadastro', 'df_final_estoque', 'cadastro_mapping_confirmed']),
            }
        )
    else:
        details.update({'blocking_reason': 'step_prerequisite_not_ready'})
    return details


def _audit_step_blocked(current: str, pending_message: str | None) -> None:
    marker_key = f'audit_blocked_notice_{current}_{hash(str(pending_message))}'
    if st.session_state.get(marker_key):
        return
    st.session_state[marker_key] = True
    add_audit_event(
        'wizard_next_blocked',
        area='WIZARD',
        step=current,
        status='BLOQUEADO',
        details=_blocked_audit_details(current, pending_message),
    )


def _audit_model_waiting_for_upload() -> None:
    marker_key = 'audit_model_waiting_for_upload_notice'
    if st.session_state.get(marker_key):
        return
    st.session_state[marker_key] = True
    add_audit_event(
        'wizard_model_waiting_for_upload',
        area='WIZARD',
        step=STEP_MODELO,
        status='INFO',
        details={
            'message': 'Aguardando envio do modelo do Bling.',
            'has_model': False,
            'visual_block_removed': True,
            'responsible_file': RESPONSIBLE_FILE,
        },
    )


def _render_nav_buttons(
    *,
    allow_next: bool = True,
    next_label: str = 'Continuar',
    pending_message: str | None = None,
) -> None:
    steps = _active_steps()
    current = _current_step()
    current_index = steps.index(current)
    is_last = current_index == len(steps) - 1

    if not allow_next and not is_last:
        _audit_step_blocked(current, pending_message)
        render_pending_notice(pending_message)

    col_back, col_next = st.columns(2)
    with col_back:
        disabled = current_index == 0
        if st.button('Voltar', use_container_width=True, disabled=disabled, key=f'wizard_back_{current}'):
            add_audit_event('wizard_back_clicked', area='WIZARD', step=current, details={'index': current_index, 'responsible_file': RESPONSIBLE_FILE})
            _previous_step()
    with col_next:
        if is_last:
            return
        if allow_next:
            if st.button(next_label, use_container_width=True, key=f'wizard_next_{current}'):
                add_audit_event(
                    'wizard_next_clicked',
                    area='WIZARD',
                    step=current,
                    details={'label': next_label, 'index': current_index, 'responsible_file': RESPONSIBLE_FILE},
                )
                _next_step()
        else:
            pass


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
        add_audit_event(
            'flow_state_synced',
            area='WIZARD',
            step=_current_step(),
            details={
                'origin': origin,
                'operation': operation,
                'previous_origin': previous_origin,
                'previous_operation': previous_operation,
                'responsible_file': RESPONSIBLE_FILE,
            },
        )
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
    if origem in {'arquivo', 'planilha', 'planilhas', 'xml', 'pdf'} or flow in {'arquivo', 'planilha', 'planilhas', 'xml', 'pdf'}:
        return 'arquivo'
    if origem == 'site' or flow == 'site':
        return 'site'
    return ''


def _clear_legacy_origin_widget_state(operation: str) -> None:
    st.session_state.pop(LEGACY_ORIGIN_RADIO_KEY, None)
    valid_keys = {f'frontpage_origin_radio_{operation}', 'home_pricing_enabled_toggle'}
    removed: list[str] = []
    for key in list(st.session_state.keys()):
        text = str(key)
        if text.startswith('frontpage_origin_radio') and text not in valid_keys:
            removed.append(text)
            st.session_state.pop(key, None)
    if removed:
        add_audit_event('legacy_origin_state_cleared', area='WIZARD', step=_current_step(), details={'removed_keys': removed, 'responsible_file': RESPONSIBLE_FILE})


def _render_model_step() -> None:
    from bling_app_zero.ui.home_models import render_home_bling_models

    with st.container(border=True):
        render_home_bling_models()
        has_model = _has_home_models()
        add_audit_event(
            'wizard_model_step_status',
            area='WIZARD',
            step=STEP_MODELO,
            details={
                'has_model': has_model,
                'has_cadastro_model': _has_cadastro_model(),
                'has_estoque_model': _has_estoque_model(),
                'model_keys': _debug_state_keys([
                    HOME_CADASTRO_MODEL_KEY,
                    *GLOBAL_CADASTRO_MODEL_KEYS,
                    HOME_ESTOQUE_MODEL_KEY,
                    *GLOBAL_ESTOQUE_MODEL_KEYS,
                    'home_model_upload_bling',
                ]),
                'responsible_file': RESPONSIBLE_FILE,
            },
        )

        if not has_model:
            _audit_model_waiting_for_upload()
            return

        st.markdown('<div class="bling-primary-cta-anchor"></div>', unsafe_allow_html=True)
        if st.button('Continuar', use_container_width=True, key='wizard_model_continue'):
            add_audit_event('wizard_next_clicked', area='WIZARD', step=STEP_MODELO, details={'label': 'Continuar', 'responsible_file': RESPONSIBLE_FILE})
            _next_step()


def _render_operation_step() -> None:
    available = _available_operations()
    labels_by_value = {
        'cadastro': '🧾 Cadastrar produtos no Bling',
        'estoque': '📦 Atualizar estoque no Bling',
    }
    render_section_card(
        'Etapa 2',
        'Operação reconhecida pelo modelo',
        'Quando o modelo enviado for oficial de estoque, o sistema seleciona automaticamente Atualizar estoque. Se houver os dois modelos, você ainda pode escolher manualmente.',
    )
    if not available:
        _render_nav_buttons(allow_next=False, pending_message='Envie o modelo do Bling para liberar a escolha da operação.')
        return

    current = _selected_operation()
    if len(available) == 1:
        selected = available[0]
        if current != selected:
            st.session_state[FLOW_OPERATION_KEY] = selected
            st.session_state['operacao_final'] = selected
            st.session_state['tipo_operacao_final'] = selected
            add_audit_event('operation_auto_recognized', area='WIZARD', step=STEP_OPERACAO, details={'operation': selected, 'responsible_file': RESPONSIBLE_FILE})
        st.success(f'Fluxo reconhecido automaticamente: {labels_by_value[selected]}')
        st.caption('Modelo de saldo/estoque detectado: o próximo fluxo será de atualização de estoque.' if selected == 'estoque' else 'Modelo de cadastro detectado: o próximo fluxo será de cadastro de produtos.')
        try:
            st.query_params['operacao'] = selected
        except Exception:
            pass
        _render_nav_buttons(allow_next=True, next_label='Continuar no fluxo reconhecido')
        return

    labels = [labels_by_value[value] for value in available]
    index = available.index(current) if current in available else 0
    choice_label = st.radio('Operação', labels, index=index, key='wizard_operation_radio', label_visibility='collapsed')
    selected = available[labels.index(choice_label)] if choice_label else current
    previous = st.session_state.get(FLOW_OPERATION_KEY)
    if selected != previous:
        add_audit_event('operation_changed', area='WIZARD', step=STEP_OPERACAO, details={'previous': previous, 'selected': selected, 'available': available, 'responsible_file': RESPONSIBLE_FILE})
        _reset_outputs_for_operation_change()
    st.session_state[FLOW_OPERATION_KEY] = selected
    st.session_state['operacao_final'] = selected
    st.session_state['tipo_operacao_final'] = selected
    try:
        st.query_params['operacao'] = selected
    except Exception:
        pass
    _render_nav_buttons(allow_next=bool(selected), pending_message='Selecione se o fluxo é Cadastro de produtos ou Atualização de estoque.')


def _render_pricing_step() -> None:
    render_section_card('Etapa 3', 'Precificação opcional', 'Ative somente se quiser calcular preço de venda antes do mapeamento. Esta etapa vale para cadastro e estoque. Se não precisar, pule esta etapa.')
    previous = bool(st.session_state.get('home_precificacao_inicial', False))
    use_pricing = st.toggle('Usar calculadora de preço', value=previous, key='home_pricing_enabled_toggle')
    if use_pricing != previous:
        add_audit_event('pricing_toggle_changed', area='WIZARD', step=STEP_PRECIFICACAO, details={'previous': previous, 'selected': use_pricing, 'responsible_file': RESPONSIBLE_FILE})
    if use_pricing:
        config = render_home_pricing_config_form()
        set_home_pricing_config(config)
        add_audit_event('pricing_config_updated', area='PRECIFICACAO', step=STEP_PRECIFICACAO, details={'config': config, 'responsible_file': RESPONSIBLE_FILE})
    else:
        disable_home_pricing()
    _render_nav_buttons(allow_next=True, next_label='Continuar')


def _render_origin_step() -> None:
    operation = _selected_operation()
    _clear_legacy_origin_widget_state(operation)
    operation_label = 'atualização de estoque' if operation == 'estoque' else 'cadastro de produtos'
    render_section_card('Etapa 4', 'Origem dos dados', f'Escolha como os produtos entram no fluxo de {operation_label}. A próxima tela carrega somente o módulo necessário.')
    selected = _current_origin_choice()
    options = {'arquivo': '📎 Anexar planilha/XML/PDF do fornecedor', 'site': '🌐 Buscar por site/link'}
    labels = list(options.values())
    values = list(options.keys())
    index = values.index(selected) if selected in values else None
    choice_label = st.radio('Origem dos dados', labels, index=index, key=f'frontpage_origin_radio_{operation}', label_visibility='collapsed')
    if choice_label is not None:
        _sync_flow_state(values[labels.index(choice_label)], operation)
    _render_nav_buttons(allow_next=bool(_current_origin_choice()), pending_message='Escolha a origem dos dados para liberar a próxima etapa.')


def _render_rules_step() -> None:
    add_audit_event('rules_center_rendered', area='REGRAS', step=STEP_REGRAS, details={'operation': _selected_operation(), 'responsible_file': RESPONSIBLE_FILE})
    render_rules_center_step()
    _render_nav_buttons(allow_next=rules_center_ready(), pending_message='Confirme a Central de Regras e Padrões antes de continuar.')


def _render_cadastro_entrada() -> None:
    origin = _current_origin_choice()
    add_audit_event('cadastro_entry_rendered', area='CADASTRO', step=STEP_ENTRADA, details={'origin': origin, 'responsible_file': RESPONSIBLE_FILE})
    if origin == 'site':
        from bling_app_zero.ui.site_panel import render_site_panel

        render_site_panel()
    render_cadastro_entrada_step()
    _render_nav_buttons(allow_next=cadastro_context_ready(), pending_message='Carregue ou capture os dados dos produtos antes de continuar para o mapeamento.')


def _render_cadastro_mapeamento() -> None:
    ready = cadastro_mapping_ready()
    add_audit_event('cadastro_mapping_rendered', area='CADASTRO', step=STEP_MAPEAMENTO, details={'ready': ready, 'responsible_file': RESPONSIBLE_FILE})
    render_cadastro_mapeamento_step()
    _render_nav_buttons(allow_next=cadastro_mapping_ready(), pending_message='Revise e confirme o mapeamento obrigatório antes de abrir o preview final.')


def _render_cadastro_preview() -> None:
    ready = cadastro_mapping_ready()
    add_audit_event('cadastro_preview_rendered', area='CADASTRO', step=STEP_PREVIEW, details={'ready': ready, 'responsible_file': RESPONSIBLE_FILE})
    render_cadastro_preview_step()
    _render_nav_buttons(allow_next=cadastro_mapping_ready(), pending_message='O preview depende de um mapeamento confirmado e válido.')


def _render_cadastro_download() -> None:
    add_audit_event('cadastro_download_step_rendered', area='CADASTRO', step=STEP_DOWNLOAD, details={'responsible_file': RESPONSIBLE_FILE})
    render_cadastro_download_step()
    col_back, col_reset = st.columns(2)
    with col_back:
        if st.button('Voltar para preview', use_container_width=True, key='wizard_download_back'):
            add_audit_event('download_back_to_preview_clicked', area='CADASTRO', step=STEP_DOWNLOAD, details={'responsible_file': RESPONSIBLE_FILE})
            _go_to_step(STEP_PREVIEW, reason='download_back_to_preview')
    with col_reset:
        if st.button('Recomeçar fluxo', use_container_width=True, key='wizard_download_reset'):
            add_audit_event('download_reset_clicked', area='CADASTRO', step=STEP_DOWNLOAD, details={'responsible_file': RESPONSIBLE_FILE})
            _reset_wizard()


def _render_estoque_entrada() -> None:
    origin = _current_origin_choice()
    add_audit_event('estoque_entry_rendered', area='ESTOQUE', step=STEP_ENTRADA, details={'origin': origin, 'responsible_file': RESPONSIBLE_FILE})
    if origin == 'site':
        from bling_app_zero.ui.site_panel import render_site_panel

        render_site_panel()
    render_estoque_entrada_step()
    _render_nav_buttons(allow_next=estoque_context_ready(), pending_message='Informe a entrada necessária do estoque antes de gerar o resultado.')


def _render_estoque_gerar() -> None:
    ready = estoque_output_ready()
    add_audit_event('estoque_generate_rendered', area='ESTOQUE', step=STEP_GERAR_ESTOQUE, details={'ready': ready, 'responsible_file': RESPONSIBLE_FILE})
    render_estoque_gerar_step()
    _render_nav_buttons(allow_next=estoque_output_ready(), pending_message='Gere o arquivo de estoque antes de ir para o preview.')


def _render_estoque_preview() -> None:
    ready = estoque_output_ready()
    add_audit_event('estoque_preview_rendered', area='ESTOQUE', step=STEP_PREVIEW, details={'ready': ready, 'responsible_file': RESPONSIBLE_FILE})
    render_estoque_preview_step()
    _render_nav_buttons(allow_next=estoque_output_ready(), pending_message='O preview de estoque depende de um resultado gerado com sucesso.')


def _render_estoque_download() -> None:
    add_audit_event('estoque_download_step_rendered', area='ESTOQUE', step=STEP_DOWNLOAD, details={'responsible_file': RESPONSIBLE_FILE})
    render_estoque_download_step()
    col_back, col_reset = st.columns(2)
    with col_back:
        if st.button('Voltar para preview', use_container_width=True, key='wizard_estoque_download_back'):
            add_audit_event('download_back_to_preview_clicked', area='ESTOQUE', step=STEP_DOWNLOAD, details={'responsible_file': RESPONSIBLE_FILE})
            _go_to_step(STEP_PREVIEW, reason='download_back_to_preview')
    with col_reset:
        if st.button('Recomeçar fluxo', use_container_width=True, key='wizard_estoque_download_reset'):
            add_audit_event('download_reset_clicked', area='ESTOQUE', step=STEP_DOWNLOAD, details={'responsible_file': RESPONSIBLE_FILE})
            _reset_wizard()


def render_home_wizard() -> None:
    nav = _render_step_header()
    step = _current_step()
    operation = _selected_operation()
    add_audit_event('wizard_step_rendered', area='WIZARD', step=step, details={'operation': operation, 'index': nav.index, 'total': nav.total, 'steps': nav.steps, 'responsible_file': RESPONSIBLE_FILE})
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
        st.warning('Etapa inválida. Volte para o início do fluxo.')
        _render_nav_buttons(allow_next=False, pending_message='Volte para ajustar o fluxo antes de continuar.')
