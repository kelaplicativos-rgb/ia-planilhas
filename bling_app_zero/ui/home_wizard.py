from __future__ import annotations

from html import escape

import pandas as pd
import streamlit as st

from bling_app_zero.core.audit import add_audit_event
from bling_app_zero.core.bling_oauth import build_authorization_url, connection_status, disconnect
from bling_app_zero.ui.ai_real_advanced_panel import render_ai_real_advanced_panel
from bling_app_zero.ui.cadastro_pricing import apply_cadastro_pricing, clear_cadastro_pricing_state
from bling_app_zero.ui.cadastro_wizard_state import (
    CADASTRO_MODELO_KEY,
    CADASTRO_ORIGEM_KEY,
    CADASTRO_ORIGEM_PRICED_KEY,
    store_cadastro_context,
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
from bling_app_zero.universal.model_contract_detector import MODEL_CONTRACT_TYPE_KEY, normalize_contract_operation

RESPONSIBLE_FILE = 'bling_app_zero/ui/home_wizard.py'
PRICE_UPDATE_OPERATION = 'atualizacao_preco'
FINISH_MODE_KEY = 'bling_finish_mode'
FINISH_MODE_API = 'api_direct'
FINISH_MODE_CSV = 'csv_download'
SKIP_DIRECT_BLING_KEY = 'skip_direct_bling_connection_this_flow'
DIRECT_API_CONTRACT_KEY = 'direct_bling_api_contract_df'
DIRECT_API_CONTRACT_ACTIVE_KEY = 'direct_bling_api_contract_active'

DIRECT_OPERATION_LABELS = {
    'cadastro': 'Cadastrar produtos',
    'estoque': 'Atualizar estoque',
    'atualizacao_preco': 'Atualizar preços',
}

API_CONTRACT_COLUMNS = {
    'cadastro': [
        'Nome',
        'Código',
        'Preço',
        'Quantidade',
        'GTIN',
        'Descrição',
        'Marca',
        'Categoria',
        'Imagens',
        'Depósito',
    ],
    'estoque': ['ID produto', 'Código', 'Quantidade', 'Depósito'],
    'atualizacao_preco': ['ID produto', 'Código', 'Preço'],
}

DIRECT_CONTRACT_SESSION_KEYS = (
    DIRECT_API_CONTRACT_KEY,
    'home_modelo_universal_df',
    'df_modelo_universal',
    'modelo_universal_df',
    'cadastro_wizard_df_modelo',
    'home_modelo_cadastro_df',
    'df_modelo_cadastro',
    'modelo_cadastro_df',
    'home_modelo_estoque_df',
    'df_modelo_estoque',
    'modelo_estoque_df',
    'cadastro_wizard_df_modelo_estoque',
    'home_modelo_atualizacao_preco_df',
    'df_modelo_atualizacao_preco',
    'modelo_atualizacao_preco_df',
)

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


def _finish_mode() -> str:
    return str(st.session_state.get(FINISH_MODE_KEY) or '').strip()


def _is_api_direct_mode() -> bool:
    return _finish_mode() == FINISH_MODE_API and bool(connection_status().get('connected'))


def _direct_operation() -> str:
    choice = normalize_contract_operation(st.session_state.get('direct_bling_operation_choice'))
    if choice in DIRECT_OPERATION_LABELS:
        return choice
    op = normalize_contract_operation(st.session_state.get('home_slim_flow_operation'))
    if op in DIRECT_OPERATION_LABELS:
        return op
    return 'cadastro'


def _direct_api_contract_model(operation: str | None = None) -> pd.DataFrame:
    op = normalize_contract_operation(operation or _direct_operation()) or 'cadastro'
    columns = API_CONTRACT_COLUMNS.get(op, API_CONTRACT_COLUMNS['cadastro'])
    return pd.DataFrame(columns=columns)


def _clear_direct_api_contract() -> None:
    if not st.session_state.get(DIRECT_API_CONTRACT_ACTIVE_KEY):
        return
    for key in DIRECT_CONTRACT_SESSION_KEYS:
        st.session_state.pop(key, None)
    st.session_state.pop(DIRECT_API_CONTRACT_ACTIVE_KEY, None)
    st.session_state.pop(MODEL_CONTRACT_TYPE_KEY, None)


def _apply_direct_api_contract(operation: str | None = None) -> pd.DataFrame:
    op = normalize_contract_operation(operation or _direct_operation()) or 'cadastro'
    model = _direct_api_contract_model(op)
    st.session_state[DIRECT_API_CONTRACT_ACTIVE_KEY] = True
    st.session_state[DIRECT_API_CONTRACT_KEY] = model.copy()
    st.session_state[CADASTRO_MODELO_KEY] = model.copy()
    st.session_state['cadastro_wizard_df_modelo'] = model.copy()
    st.session_state['home_modelo_universal_df'] = model.copy()
    st.session_state['df_modelo_universal'] = model.copy()
    st.session_state['modelo_universal_df'] = model.copy()

    if op == 'cadastro':
        st.session_state['home_modelo_cadastro_df'] = model.copy()
        st.session_state['df_modelo_cadastro'] = model.copy()
        st.session_state['modelo_cadastro_df'] = model.copy()
    elif op == 'estoque':
        st.session_state['home_modelo_estoque_df'] = model.copy()
        st.session_state['df_modelo_estoque'] = model.copy()
        st.session_state['modelo_estoque_df'] = model.copy()
        st.session_state['cadastro_wizard_df_modelo_estoque'] = model.copy()
    elif op == PRICE_UPDATE_OPERATION:
        st.session_state['home_modelo_atualizacao_preco_df'] = model.copy()
        st.session_state['df_modelo_atualizacao_preco'] = model.copy()
        st.session_state['modelo_atualizacao_preco_df'] = model.copy()

    st.session_state['home_slim_flow_operation'] = op
    st.session_state['home_detected_operation'] = op
    st.session_state['operacao_final'] = op
    st.session_state['tipo_operacao_final'] = op
    st.session_state[MODEL_CONTRACT_TYPE_KEY] = op
    return model


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
    return _current_contract_operation() == PRICE_UPDATE_OPERATION


def _price_update_model_df() -> pd.DataFrame | None:
    for key in (
        'home_modelo_atualizacao_preco_df',
        'df_modelo_atualizacao_preco',
        'modelo_atualizacao_preco_df',
        CADASTRO_MODELO_KEY,
    ):
        df = st.session_state.get(key)
        if isinstance(df, pd.DataFrame) and len(df.columns):
            return df.copy().fillna('')
    return None


def _bind_price_update_single_sheet() -> bool:
    df_modelo = _price_update_model_df()
    if not isinstance(df_modelo, pd.DataFrame) or not len(df_modelo.columns):
        return False

    df_origem = df_modelo.copy().fillna('')
    store_cadastro_context(df_origem, df_modelo, None)
    st.session_state[CADASTRO_ORIGEM_PRICED_KEY] = df_origem.copy().fillna('')
    st.session_state['home_slim_flow_origin'] = 'arquivo'
    st.session_state['origem_final'] = 'arquivo'
    st.session_state['operacao_final'] = PRICE_UPDATE_OPERATION
    st.session_state['tipo_operacao_final'] = PRICE_UPDATE_OPERATION
    st.session_state['home_detected_operation'] = PRICE_UPDATE_OPERATION
    st.session_state['home_slim_flow_operation'] = PRICE_UPDATE_OPERATION
    st.session_state[MODEL_CONTRACT_TYPE_KEY] = PRICE_UPDATE_OPERATION
    add_audit_event(
        'price_update_single_sheet_bound',
        area='PRECOS',
        step='entrada',
        status='OK',
        details={
            'rows': len(df_origem),
            'columns': len(df_origem.columns),
            'mode': 'same_sheet_as_source_and_contract',
            'responsible_file': RESPONSIBLE_FILE,
        },
    )
    return True


def _render_price_update_single_sheet_notice() -> None:
    if _bind_price_update_single_sheet():
        st.success('Atualização de preços detectada: a planilha anexada será usada como origem e como modelo final. Não é necessário enviar outra planilha.')
        df = st.session_state.get(CADASTRO_ORIGEM_KEY)
        if isinstance(df, pd.DataFrame):
            st.caption(f'Planilha única vinculada · {len(df)} linha(s) · {len(df.columns)} coluna(s).')
    else:
        render_pending_notice('Anexe a planilha de atualização de preços para continuar.')


def _render_same_tab_connect_button(auth_url: str) -> None:
    safe_url = escape(str(auth_url or ''), quote=True)
    if not safe_url:
        st.warning('Não consegui gerar o link de conexão com o Bling agora.')
        return
    st.markdown(
        f'''
<a href="{safe_url}" target="_self" style="
    display:block;
    width:100%;
    box-sizing:border-box;
    text-align:center;
    text-decoration:none;
    font-weight:900;
    padding:0.78rem 1rem;
    border-radius:0.78rem;
    border:1px solid rgba(37,99,235,.28);
    color:#ffffff;
    background:#2563eb;
    box-shadow:0 10px 22px rgba(37,99,235,.18);
">
    Conectar ao Bling e enviar direto
</a>
''',
        unsafe_allow_html=True,
    )


def _render_bling_connection_step() -> None:
    _section_title(1, 'Como deseja finalizar?')
    with st.container(border=True):
        st.caption('Escolha o caminho do fluxo. Envio direto usa a API do Bling e não exige planilha modelo. CSV exige modelo para importação manual.')
        status = connection_status()
        connected = bool(status.get('connected'))

        if connected:
            st.success('Bling conectado. Escolha envio direto ou CSV manual.')
            operation = st.radio(
                'O que deseja fazer no Bling?',
                options=list(DIRECT_OPERATION_LABELS.keys()),
                format_func=lambda value: DIRECT_OPERATION_LABELS.get(value, value),
                horizontal=True,
                key='direct_bling_operation_choice',
            )
            if _finish_mode() == FINISH_MODE_API:
                _apply_direct_api_contract(operation)

            col1, col2 = st.columns(2)
            with col1:
                if st.button('Usar envio direto', use_container_width=True, key='use_direct_bling_mode'):
                    st.session_state[FINISH_MODE_KEY] = FINISH_MODE_API
                    st.session_state.pop(SKIP_DIRECT_BLING_KEY, None)
                    _apply_direct_api_contract(operation)
                    st.session_state[WIZARD_STEP_KEY] = STEP_ORIGEM
                    set_scroll_target(STEP_ORIGEM)
                    st.rerun()
            with col2:
                if st.button('Gerar CSV', use_container_width=True, key='use_csv_even_connected'):
                    st.session_state[FINISH_MODE_KEY] = FINISH_MODE_CSV
                    st.session_state[SKIP_DIRECT_BLING_KEY] = True
                    _clear_direct_api_contract()
                    st.session_state[WIZARD_STEP_KEY] = STEP_MODELO
                    set_scroll_target(STEP_MODELO)
                    st.rerun()
            if st.button('Desconectar Bling', use_container_width=True, key='entry_disconnect_bling'):
                disconnect()
                _clear_direct_api_contract()
                st.session_state.pop(FINISH_MODE_KEY, None)
                st.rerun()
            return

        st.warning('Bling não conectado. Conecte para envio direto ou gere CSV sem conexão.')
        try:
            auth_url = build_authorization_url({'return_to': 'start', 'source_step': 'bling_connection_entry'})
        except Exception:
            auth_url = ''
        _render_same_tab_connect_button(auth_url)
        st.markdown('<div style="height:.55rem"></div>', unsafe_allow_html=True)
        if st.button('Continuar sem conectar e gerar CSV', use_container_width=True, key='continue_without_bling_connection'):
            st.session_state[FINISH_MODE_KEY] = FINISH_MODE_CSV
            st.session_state[SKIP_DIRECT_BLING_KEY] = True
            _clear_direct_api_contract()
            st.session_state[WIZARD_STEP_KEY] = STEP_MODELO
            set_scroll_target(STEP_MODELO)
            st.rerun()

    if not _finish_mode():
        st.warning('Escolha uma das opções acima para liberar o fluxo.')


def _render_model_step(section_number: int = 2) -> None:
    if _is_api_direct_mode():
        return
    from bling_app_zero.ui.home_models import render_home_bling_models

    render_step_anchor(STEP_MODELO)
    _section_title(section_number, 'Modelos Universal')
    with st.container(border=True):
        render_home_bling_models()
    ensure_universal_operation_state()
    if _is_price_update_contract():
        _bind_price_update_single_sheet()


def _render_origin_step(section_number: int = 3) -> None:
    render_step_anchor(STEP_ORIGEM)
    if _is_price_update_contract() and not _is_api_direct_mode():
        _section_title(section_number, 'Planilha única de atualização de preços')
        _render_price_update_single_sheet_notice()
        return

    _section_title(section_number, 'Origem dos dados')
    if not _model_available():
        render_pending_notice('Liberado após escolher o caminho do fluxo.')
        return
    ensure_universal_operation_state()
    if _is_api_direct_mode():
        _apply_direct_api_contract()
        st.caption('Modo Envio direto: não é necessário anexar modelo. O sistema usará o contrato interno da API do Bling.')
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


def _render_universal_entrada(section_number: int = 4) -> None:
    origin = current_origin_choice()
    render_step_anchor(STEP_ENTRADA)
    if _is_price_update_contract() and not _is_api_direct_mode():
        _section_title(section_number, 'Dados da atualização de preços')
        _render_price_update_single_sheet_notice()
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
            'single_page_flow': SINGLE_PAGE_FLOW,
            'responsible_file': RESPONSIBLE_FILE,
        },
    )
    if origin == 'site':
        from bling_app_zero.ui.site_panel import render_site_panel

        render_site_panel()
    render_universal_entrada_step()


def _source_dataframe_for_pricing() -> pd.DataFrame | None:
    df_origem = st.session_state.get(CADASTRO_ORIGEM_KEY)
    return df_origem if isinstance(df_origem, pd.DataFrame) else None


def _apply_pricing_step_result() -> None:
    df_origem = _source_dataframe_for_pricing()
    if not isinstance(df_origem, pd.DataFrame) or df_origem.empty:
        clear_cadastro_pricing_state()
        render_pending_notice('Carregue os dados primeiro.')
        return
    df_precificado = apply_cadastro_pricing(df_origem, channel='home_price_step')
    if isinstance(df_precificado, pd.DataFrame):
        st.session_state[CADASTRO_ORIGEM_PRICED_KEY] = df_precificado
    if bool(st.session_state.get('cadastro_preco_calculado_ativo', False)):
        st.success('Preço calculado. O campo Preço de venda será usado no mapeamento e no preview.')
    else:
        st.warning('Calcule um preço para aplicar a referência de precificação aos dados carregados.')


def _render_pricing_step(section_number: int = 5) -> None:
    render_step_anchor(STEP_PRECIFICACAO)
    if _is_price_update_contract() and not _is_api_direct_mode():
        _section_title(section_number, 'Preço')
        _render_price_update_single_sheet_notice()
        st.caption('A planilha de atualização de preços já contém a estrutura e a origem. Use a calculadora somente se quiser recalcular os valores antes do mapeamento.')
    else:
        _section_title(section_number, 'Preço')
    if not _model_available():
        render_pending_notice('Liberado após escolher o caminho do fluxo.')
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
            _apply_pricing_step_result()
    else:
        disable_home_pricing()
        if not _is_price_update_contract():
            clear_cadastro_pricing_state()
        st.caption('Opcional. Se desligada, mantém o preço da origem ou do mapeamento.')


def _render_universal_mapeamento(section_number: int = 6) -> None:
    render_step_anchor(STEP_MAPEAMENTO)
    title = 'Mapear campos da API' if _is_api_direct_mode() else ('Conferir campos da atualização' if _is_price_update_contract() else 'Mapear campos')
    _section_title(section_number, title)
    if not _model_available():
        render_pending_notice('Liberado após escolher o caminho do fluxo e carregar os dados.')
        return
    if not universal_context_ready():
        render_pending_notice('Carregue os dados primeiro.')
        return
    if _is_api_direct_mode():
        _apply_direct_api_contract()
        st.caption('Modo Envio direto: confirme a ligação dos dados de origem com os campos da API do Bling.')
    elif _is_price_update_contract():
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


def _render_steps_from(start_step: str, *, skip_model: bool) -> None:
    steps = [step for step in ACTIVE_RENDER_STEPS if not (skip_model and step == STEP_MODELO)]
    if start_step not in steps:
        start_step = steps[0]
    start_index = steps.index(start_step)
    section_number = 2
    for step in steps[start_index:]:
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
        section_number += 1


def render_home_wizard() -> None:
    inject_scroll_guard('home_wizard')
    has_model = has_home_models()
    operation = ensure_universal_operation_state()
    st.session_state['wizard_bottom_nav_rendered_current_cycle'] = True
    st.session_state['home_single_page_flow_active'] = True

    _render_bling_connection_step()
    mode = _finish_mode()
    direct_mode = _is_api_direct_mode()

    if not mode:
        inject_scroll_to_target()
        return

    if direct_mode:
        _apply_direct_api_contract()
        has_model = True
    elif not has_model:
        st.session_state[WIZARD_STEP_KEY] = STEP_MODELO
        st.session_state.pop('home_slim_flow_origin', None)
        add_audit_event(
            'wizard_model_first_guard_active',
            area='WIZARD',
            step=STEP_MODELO,
            details={'reason': 'missing_destination_model', 'single_page_flow': SINGLE_PAGE_FLOW, 'finish_mode': mode, 'responsible_file': RESPONSIBLE_FILE},
        )
        _render_model_step(2)
        inject_scroll_to_target()
        return

    start_at_origin = came_from_bling_quick_model() or direct_mode
    active_step = _active_start_step()
    if start_at_origin and active_step == STEP_MODELO:
        active_step = STEP_ORIGEM

    add_audit_event(
        'wizard_single_page_rendered',
        area='WIZARD',
        step=active_step,
        details={'operation': operation or 'universal', 'steps': UNIVERSAL_STEPS, 'single_page_flow': SINGLE_PAGE_FLOW, 'skip_model_step': start_at_origin, 'active_start_step': active_step, 'finish_mode': mode, 'responsible_file': RESPONSIBLE_FILE},
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
