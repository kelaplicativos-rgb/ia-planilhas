from __future__ import annotations

import pandas as pd
import streamlit as st

from bling_app_zero.core.flow_spine_output import output_diagnostics, output_plan
from bling_app_zero.core.product_pricing_center import PRICE_OUTPUT_COLUMN, PROMO_PRICE_OUTPUT_COLUMN, promotional_price_columns
from bling_app_zero.ui.cadastro_pricing import apply_cadastro_pricing, clear_cadastro_pricing_state
from bling_app_zero.ui.home_pricing_config import (
    disable_home_pricing,
    get_home_pricing_config,
    render_home_pricing_config_form,
    set_home_pricing_config,
)
from bling_app_zero.ui.home_wizard_scroll import render_step_anchor
from bling_app_zero.ui.home_wizard_ui import render_pending_notice
from bling_app_zero.ui.universal_wizard_state import (
    UNIVERSAL_MODELO_KEY,
    UNIVERSAL_ORIGEM_KEY,
    UNIVERSAL_ORIGEM_PRICED_KEY,
    universal_context_ready,
)

RESPONSIBLE_FILE = 'bling_app_zero/ui/home_wizard_pricing_step.py'
LIVE_PREVIEW_ROWS = 20


def _pricing_plan():
    try:
        return output_plan()
    except Exception:
        return None


def _pricing_enabled_by_spine() -> bool:
    plan = _pricing_plan()
    if plan is None:
        return True
    return bool(plan.needs_pricing)


def _stock_label(value: object) -> bool:
    text = str(value or '').strip().lower()
    return bool('estoque' in text or 'stock' in text or 'saldo' in text)


def _api_stock_pricing_optional(plan=None) -> bool:
    """Libera a calculadora no fluxo api_estoque mesmo quando a Flow Spine diz needs_pricing=False."""
    if plan is None:
        plan = _pricing_plan()
    if plan is not None:
        operation = str(getattr(plan, 'operation', '') or '').strip().lower()
        destination = str(getattr(plan, 'final_destination', '') or '').strip().lower()
        contract_key = str(getattr(plan, 'contract_key', '') or '').strip().lower()
        if (contract_key == 'api_estoque' or _stock_label(operation)) and destination == 'api_bling':
            return True
    operation_values = [
        st.session_state.get('flow_spine_operation'),
        st.session_state.get('flow_spine_sender_operation'),
        st.session_state.get('flow_spine_api_batch_operation'),
        st.session_state.get('flow_spine_operation_resolved_for_api'),
        st.session_state.get('home_slim_flow_operation'),
        st.session_state.get('home_detected_operation'),
        st.session_state.get('operacao_final'),
        st.session_state.get('tipo_operacao_final'),
        st.session_state.get('active_feature_operation'),
        st.session_state.get('api_operation'),
        st.session_state.get('bling_api_operation'),
        st.session_state.get('site_capture_operation'),
    ]
    is_stock = any(_stock_label(value) for value in operation_values)
    is_api = bool(
        str(st.session_state.get('flow_spine_final_destination') or '').strip().lower() == 'api_bling'
        or st.session_state.get('home_bling_connected_same_flow_api_send')
        or st.session_state.get('bling_connected_api_flow_active')
        or st.session_state.get('direct_bling_api_contract_active')
    )
    return bool(is_stock and is_api)


def _store_pricing_spine_state() -> None:
    try:
        plan = output_plan()
        st.session_state['flow_spine_pricing_ready'] = bool(plan.needs_pricing)
        st.session_state['flow_spine_pricing_diagnostics'] = output_diagnostics()
    except Exception:
        pass


def source_dataframe_for_pricing() -> pd.DataFrame | None:
    df_origem = st.session_state.get(UNIVERSAL_ORIGEM_KEY)
    return df_origem if isinstance(df_origem, pd.DataFrame) else None


def _model_dataframe_for_pricing() -> pd.DataFrame | None:
    for key in (
        UNIVERSAL_MODELO_KEY,
        'home_modelo_universal_df',
        'df_modelo_universal',
        'modelo_universal_df',
        'home_modelo_atualizacao_preco_df',
        'df_modelo_atualizacao_preco',
        'modelo_atualizacao_preco_df',
    ):
        value = st.session_state.get(key)
        if isinstance(value, pd.DataFrame) and len(value.columns) > 0:
            return value
    return None


def _detected_promotional_columns(source_df: pd.DataFrame | None, model_df: pd.DataFrame | None) -> list[str]:
    detected: list[str] = []
    for df in (source_df, model_df):
        if not isinstance(df, pd.DataFrame):
            continue
        for column in promotional_price_columns(df.columns):
            if column not in detected:
                detected.append(column)
    return detected


def _live_preview_columns(df: pd.DataFrame, selected_cost_column: str, detected_promo_columns: list[str]) -> list[str]:
    columns: list[str] = []
    if selected_cost_column and selected_cost_column in df.columns:
        columns.append(selected_cost_column)
    for column in (PRICE_OUTPUT_COLUMN, 'Preco', PROMO_PRICE_OUTPUT_COLUMN, 'Preco Promocional', *detected_promo_columns, *promotional_price_columns(df.columns)):
        if column in df.columns and column not in columns:
            columns.append(column)
    return columns


def _render_live_pricing_preview(df_precificado: pd.DataFrame, selected_cost_column: str, detected_promo_columns: list[str]) -> None:
    if not isinstance(df_precificado, pd.DataFrame) or df_precificado.empty:
        return
    columns = _live_preview_columns(df_precificado, selected_cost_column, detected_promo_columns)
    if not columns:
        return
    preview = df_precificado.loc[:, columns].head(LIVE_PREVIEW_ROWS).copy().fillna('')
    price_columns = [column for column in columns if column != selected_cost_column]

    st.markdown('##### Resultado ao vivo')
    st.success(
        f'Prévia atualizada: {len(df_precificado)} produto(s). '
        'As colunas de preço normal e promocional detectadas seguirão para as próximas etapas do fluxo.'
    )
    try:
        styled = preview.style.set_properties(
            subset=price_columns,
            **{'background-color': '#dcfce7', 'color': '#166534', 'font-weight': '700'},
        )
        st.dataframe(styled, use_container_width=True, hide_index=True, height=min(520, 72 + (len(preview) * 35)))
    except Exception:
        st.dataframe(preview, use_container_width=True, hide_index=True)
    if len(df_precificado) > LIVE_PREVIEW_ROWS:
        st.caption(f'Mostrando {LIVE_PREVIEW_ROWS} de {len(df_precificado)} produtos. O cálculo foi aplicado em todas as linhas.')


def apply_pricing_step_result() -> None:
    df_origem = source_dataframe_for_pricing()
    if not isinstance(df_origem, pd.DataFrame) or df_origem.empty:
        clear_cadastro_pricing_state()
        render_pending_notice('Carregue os dados primeiro.')
        return
    model_df = _model_dataframe_for_pricing()
    detected_promo_columns = _detected_promotional_columns(df_origem, model_df)
    df_precificado = apply_cadastro_pricing(df_origem, channel='home_price_step')
    if isinstance(df_precificado, pd.DataFrame):
        st.session_state[UNIVERSAL_ORIGEM_PRICED_KEY] = df_precificado
    selected_cost_column = str(st.session_state.get('global_price_source_cost_column') or '').strip()
    if bool(st.session_state.get('cadastro_preco_calculado_ativo', False)):
        suffix = f' usando a coluna base "{selected_cost_column}"' if selected_cost_column else ''
        st.success(f'Preço calculado linha a linha{suffix}.')
        _render_live_pricing_preview(df_precificado, selected_cost_column, detected_promo_columns)
        st.session_state['flow_spine_pricing_applied'] = True
    else:
        st.warning('Calcule um preço para aplicar a referência de precificação aos dados carregados.')
        st.session_state['flow_spine_pricing_applied'] = False


def render_pricing_step(
    *,
    section_number: int,
    step_key: str,
    section_title,
    model_available: bool,
    is_price_update: bool,
    is_api_direct: bool,
    is_universal_entry: bool,
    render_price_update_notice,
) -> None:
    render_step_anchor(step_key)
    _store_pricing_spine_state()

    plan = _pricing_plan()
    optional_api_stock = _api_stock_pricing_optional(plan)
    title = 'Preço'
    if plan is not None and plan.operation == 'atualizacao_preco':
        title = 'Atualização de preços'

    if not _pricing_enabled_by_spine() and not optional_api_stock:
        section_title(section_number, title)
        disable_home_pricing()
        clear_cadastro_pricing_state()
        st.caption('A espinha dorsal deste fluxo não exige precificação. Esta etapa foi mantida apenas por compatibilidade visual e não altera os dados.')
        return

    section_title(section_number, title)
    if optional_api_stock:
        st.info('Precificação opcional para estoque via API. Ligue a calculadora somente se quiser recalcular os preços antes das regras e da IA.')
    elif is_price_update and not is_api_direct and not is_universal_entry:
        render_price_update_notice()
        st.caption('Use a calculadora somente se quiser recalcular os valores antes do mapeamento.')

    if plan is not None:
        st.caption(f'Fluxo ativo: {plan.contract_key} · operação: {plan.operation} · destino: {plan.final_destination}')

    if not model_available:
        render_pending_notice('Liberado após escolher o caminho do fluxo.')
        return
    if not universal_context_ready():
        render_pending_notice('Carregue os dados primeiro.')
        return

    df_origem = source_dataframe_for_pricing()
    df_modelo = _model_dataframe_for_pricing()
    detected_promo_columns = _detected_promotional_columns(df_origem, df_modelo)
    if detected_promo_columns:
        st.info('Coluna promocional detectada no modelo/origem: ' + ', '.join(detected_promo_columns))
        st.session_state['pricing_detected_promotional_columns'] = detected_promo_columns
    else:
        st.session_state.pop('pricing_detected_promotional_columns', None)

    current_config = get_home_pricing_config()
    use_pricing = st.toggle('Usar calculadora', value=bool(current_config.get('enabled', False)), key='home_pricing_enabled_toggle')
    if use_pricing:
        config = render_home_pricing_config_form(source_df=df_origem)
        set_home_pricing_config(config)
        if detected_promo_columns and float(config.get('promo_discount_percent', 0.0) or 0.0) <= 0:
            st.warning('A coluna promocional foi detectada. Informe um desconto promocional maior que zero para preenchê-la.')
        apply_pricing_step_result()
    else:
        disable_home_pricing()
        if not is_price_update:
            clear_cadastro_pricing_state()
        st.session_state['flow_spine_pricing_applied'] = False
        st.caption('Opcional. Se desligada, mantém os valores captados na origem e segue para as regras.')


__all__ = ['apply_pricing_step_result', 'render_pricing_step', 'source_dataframe_for_pricing']
