from __future__ import annotations

import html
from dataclasses import dataclass

import streamlit as st

from bling_app_zero.flows.site_as_source import get_site_source_for_operation
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
    render_estoque_entrada_step,
    render_estoque_gerar_step,
    render_estoque_preview_step,
)
from bling_app_zero.ui.home_pricing_config import (
    disable_home_pricing,
    render_home_pricing_config_form,
    set_home_pricing_config,
)

HOME_CADASTRO_MODEL_KEY = 'home_modelo_cadastro_df'
HOME_ESTOQUE_MODEL_KEY = 'home_modelo_estoque_df'
GLOBAL_CADASTRO_MODEL_KEYS = ['df_modelo_cadastro', 'modelo_cadastro_df']
GLOBAL_ESTOQUE_MODEL_KEYS = ['df_modelo_estoque', 'modelo_estoque_df']
FLOW_ORIGIN_KEY = 'home_slim_flow_origin'
FLOW_OPERATION_KEY = 'home_slim_flow_operation'
FLOW_ACTIVE_KEY = 'home_slim_active_panel'
LEGACY_ORIGIN_RADIO_KEY = 'frontpage_origin_radio'
WIZARD_STEP_KEY = 'bling_wizard_step'

STEP_MODELO = 'modelo'
STEP_PRECIFICACAO = 'precificacao'
STEP_ORIGEM = 'origem'
STEP_ENTRADA = 'entrada'
STEP_MAPEAMENTO = 'mapeamento'
STEP_GERAR_ESTOQUE = 'gerar_estoque'
STEP_PREVIEW = 'preview'
STEP_DOWNLOAD = 'download'
STEP_PROCESSAR = 'processar'

CADASTRO_STEPS = [
    STEP_MODELO,
    STEP_PRECIFICACAO,
    STEP_ORIGEM,
    STEP_ENTRADA,
    STEP_MAPEAMENTO,
    STEP_PREVIEW,
    STEP_DOWNLOAD,
]
ESTOQUE_STEPS = [
    STEP_MODELO,
    STEP_PRECIFICACAO,
    STEP_ORIGEM,
    STEP_ENTRADA,
    STEP_GERAR_ESTOQUE,
    STEP_PREVIEW,
]

STEP_LABELS = {
    STEP_MODELO: 'Modelo',
    STEP_PRECIFICACAO: 'Preço',
    STEP_ORIGEM: 'Origem',
    STEP_ENTRADA: 'Entrada',
    STEP_MAPEAMENTO: 'Mapeamento',
    STEP_GERAR_ESTOQUE: 'Gerar',
    STEP_PREVIEW: 'Preview',
    STEP_DOWNLOAD: 'Download',
    STEP_PROCESSAR: 'Processar',
}


@dataclass(frozen=True)
class WizardNav:
    current: str
    index: int
    total: int
    steps: list[str]


def _looks_like_loaded_df(value: object) -> bool:
    if value is None or not hasattr(value, 'columns'):
        return False
    try:
        return len(getattr(value, 'columns', [])) > 0
    except Exception:
        return False


def _has_any_model(keys: list[str]) -> bool:
    return any(_looks_like_loaded_df(st.session_state.get(key)) for key in keys)


def _has_home_models() -> bool:
    return _has_any_model([HOME_CADASTRO_MODEL_KEY] + GLOBAL_CADASTRO_MODEL_KEYS + [HOME_ESTOQUE_MODEL_KEY] + GLOBAL_ESTOQUE_MODEL_KEYS)


def _preferred_operation_from_models() -> str:
    has_cadastro = _has_any_model([HOME_CADASTRO_MODEL_KEY] + GLOBAL_CADASTRO_MODEL_KEYS)
    has_estoque = _has_any_model([HOME_ESTOQUE_MODEL_KEY] + GLOBAL_ESTOQUE_MODEL_KEYS)
    if has_estoque and not has_cadastro:
        return 'estoque'
    return 'cadastro'


def _active_steps() -> list[str]:
    return CADASTRO_STEPS if _preferred_operation_from_models() == 'cadastro' else ESTOQUE_STEPS


def _current_step() -> str:
    steps = _active_steps()
    step = str(st.session_state.get(WIZARD_STEP_KEY) or STEP_MODELO).strip().lower()
    if step not in steps:
        step = STEP_ORIGEM if step in set(CADASTRO_STEPS + ESTOQUE_STEPS) and STEP_ORIGEM in steps else STEP_MODELO
    st.session_state[WIZARD_STEP_KEY] = step
    return step


def _go_to_step(step: str) -> None:
    steps = _active_steps()
    if step not in steps:
        step = STEP_MODELO
    st.session_state[WIZARD_STEP_KEY] = step
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
        _go_to_step(steps[index + 1])


def _previous_step() -> None:
    steps = _active_steps()
    step = _current_step()
    index = steps.index(step)
    if index > 0:
        _go_to_step(steps[index - 1])


def _reset_wizard() -> None:
    for key in [
        FLOW_ORIGIN_KEY,
        FLOW_OPERATION_KEY,
        FLOW_ACTIVE_KEY,
        'origem_final',
        'origem_dados',
        'origem_tipo',
        'tipo_operacao_site',
        'operation_site',
        'cadastro_wizard_df_origem',
        'cadastro_wizard_df_para_mapear',
        'cadastro_wizard_df_modelo',
        'cadastro_wizard_df_modelo_estoque',
        'estoque_wizard_upload',
        'estoque_wizard_df_origem_site',
        'estoque_wizard_df_modelo',
        'df_final_cadastro',
        'mapping_cadastro',
        'estoque_multi_outputs',
        'df_final_estoque',
        'mapping_estoque',
    ]:
        st.session_state.pop(key, None)
    _go_to_step(STEP_MODELO)


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


def _render_step_header() -> WizardNav:
    steps = _active_steps()
    current = _current_step()
    index = steps.index(current)
    total = len(steps)
    percent = int(((index + 1) / total) * 100)
    labels = []
    for i, step in enumerate(steps):
        prefix = '●' if i == index else '✓' if i < index else '○'
        labels.append(f'{prefix} {STEP_LABELS[step]}')
    st.progress((index + 1) / total, text=f'Etapa {index + 1} de {total} · {STEP_LABELS[current]} · {percent}%')
    st.caption('  ·  '.join(labels))
    return WizardNav(current=current, index=index, total=total, steps=steps)


def _render_nav_buttons(*, allow_next: bool = True, next_label: str = 'Continuar') -> None:
    steps = _active_steps()
    col_back, col_next = st.columns(2)
    with col_back:
        disabled = steps.index(_current_step()) == 0
        if st.button('Voltar', use_container_width=True, disabled=disabled, key=f'wizard_back_{_current_step()}'):
            _previous_step()
    with col_next:
        is_last = steps.index(_current_step()) == len(steps) - 1
        if not is_last and st.button(next_label, use_container_width=True, disabled=not allow_next, key=f'wizard_next_{_current_step()}'):
            _next_step()


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


def _clear_legacy_origin_widget_state(operation: str) -> None:
    st.session_state.pop(LEGACY_ORIGIN_RADIO_KEY, None)
    valid_keys = {f'frontpage_origin_radio_{operation}', 'home_pricing_enabled_toggle'}
    for key in list(st.session_state.keys()):
        text = str(key)
        if text.startswith('frontpage_origin_radio') and text not in valid_keys:
            st.session_state.pop(key, None)


def _render_model_step() -> None:
    from bling_app_zero.ui.home_models import render_home_bling_models

    _render_section_card(
        'Etapa 1',
        'Modelo do Bling',
        'Envie o modelo de cadastro, estoque ou ambos. O sistema usa esse modelo como contrato das colunas que podem ser preenchidas.',
    )
    render_home_bling_models()
    _render_nav_buttons(allow_next=_has_home_models())
    if not _has_home_models():
        st.info('Envie pelo menos um modelo do Bling para continuar com segurança.')


def _render_pricing_step() -> None:
    _render_section_card(
        'Etapa 2',
        'Precificação opcional',
        'Ative somente se quiser calcular preço de venda antes do mapeamento. Se não precisar, pule esta etapa.',
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
    _render_nav_buttons(allow_next=True, next_label='Continuar')


def _render_origin_step() -> None:
    operation = _preferred_operation_from_models()
    _clear_legacy_origin_widget_state(operation)
    operation_label = 'atualização de estoque' if operation == 'estoque' else 'cadastro de produtos'
    _render_section_card(
        'Etapa 3',
        'Origem dos dados',
        f'Escolha como os produtos entram no fluxo de {operation_label}. A próxima tela carrega somente o módulo necessário.',
    )

    selected = _current_origin_choice()
    options = {
        'arquivo': '📎 Anexar planilha/XML/PDF do fornecedor',
        'site': '🌐 Buscar por site/link',
    }
    labels = list(options.values())
    values = list(options.keys())
    index = values.index(selected) if selected in values else None

    choice_label = st.radio(
        'Origem dos dados',
        labels,
        index=index,
        key=f'frontpage_origin_radio_{operation}',
        label_visibility='collapsed',
    )
    if choice_label is not None:
        choice = values[labels.index(choice_label)]
        _sync_flow_state(choice, operation)
    _render_nav_buttons(allow_next=bool(_current_origin_choice()))


def _render_operation_panel(operation: str) -> None:
    if operation == 'estoque':
        from bling_app_zero.ui.estoque_panel import render_estoque_panel

        render_estoque_panel()
        return

    from bling_app_zero.ui.cadastro_panel_modular import render_cadastro_panel

    render_cadastro_panel()


def _render_process_step() -> None:
    origin = _current_origin_choice()
    operation = _preferred_operation_from_models()
    if not origin:
        st.warning('Escolha a origem dos dados antes de processar.')
        _render_nav_buttons(allow_next=False)
        return

    operation_label = 'Estoque' if operation == 'estoque' else 'Cadastro'
    origin_label = 'site/link' if origin == 'site' else 'planilha/arquivo'
    _render_section_card('Etapa', f'{operation_label} por {origin_label}', 'Nesta fase o sistema carrega apenas o módulo escolhido.')

    if origin == 'site':
        from bling_app_zero.ui.site_panel import render_site_panel

        render_site_panel()
        df_site_source = get_site_source_for_operation(operation)
        if df_site_source is not None:
            _render_operation_panel(operation)
    else:
        _render_operation_panel(operation)


def _render_cadastro_entrada() -> None:
    origin = _current_origin_choice()
    if origin == 'site':
        from bling_app_zero.ui.site_panel import render_site_panel

        render_site_panel()
    render_cadastro_entrada_step()
    _render_nav_buttons(allow_next=cadastro_context_ready())


def _render_cadastro_mapeamento() -> None:
    render_cadastro_mapeamento_step()
    _render_nav_buttons(allow_next=cadastro_mapping_ready())


def _render_cadastro_preview() -> None:
    render_cadastro_preview_step()
    _render_nav_buttons(allow_next=cadastro_mapping_ready())


def _render_cadastro_download() -> None:
    render_cadastro_download_step()
    col_back, col_reset = st.columns(2)
    with col_back:
        if st.button('Voltar para preview', use_container_width=True, key='wizard_download_back'):
            _go_to_step(STEP_PREVIEW)
    with col_reset:
        if st.button('Recomeçar fluxo', use_container_width=True, key='wizard_download_reset'):
            _reset_wizard()


def _render_estoque_entrada() -> None:
    origin = _current_origin_choice()
    if origin == 'site':
        from bling_app_zero.ui.site_panel import render_site_panel

        render_site_panel()
    render_estoque_entrada_step()
    _render_nav_buttons(allow_next=estoque_context_ready())


def _render_estoque_gerar() -> None:
    render_estoque_gerar_step()
    _render_nav_buttons(allow_next=estoque_output_ready())


def _render_estoque_preview() -> None:
    render_estoque_preview_step()
    col_back, col_reset = st.columns(2)
    with col_back:
        if st.button('Voltar para gerar estoque', use_container_width=True, key='wizard_estoque_preview_back'):
            _go_to_step(STEP_GERAR_ESTOQUE)
    with col_reset:
        if st.button('Recomeçar fluxo', use_container_width=True, key='wizard_estoque_preview_reset'):
            _reset_wizard()


def render_home_wizard() -> None:
    operation = _preferred_operation_from_models()
    _render_step_header()
    step = _current_step()
    if step == STEP_MODELO:
        _render_model_step()
    elif step == STEP_PRECIFICACAO:
        _render_pricing_step()
    elif step == STEP_ORIGEM:
        _render_origin_step()
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
    else:
        _render_process_step()
