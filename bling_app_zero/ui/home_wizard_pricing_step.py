from __future__ import annotations

import pandas as pd
import streamlit as st

from bling_app_zero.ui.cadastro_pricing import apply_cadastro_pricing, clear_cadastro_pricing_state
from bling_app_zero.ui.home_pricing_config import (
    disable_home_pricing,
    get_home_pricing_config,
    render_home_pricing_config_form,
    set_home_pricing_config,
)
from bling_app_zero.ui.home_wizard_scroll import render_step_anchor
from bling_app_zero.ui.home_wizard_ui import render_pending_notice
from bling_app_zero.ui.universal_wizard_state import UNIVERSAL_ORIGEM_KEY, UNIVERSAL_ORIGEM_PRICED_KEY, universal_context_ready

RESPONSIBLE_FILE = 'bling_app_zero/ui/home_wizard_pricing_step.py'


def source_dataframe_for_pricing() -> pd.DataFrame | None:
    df_origem = st.session_state.get(UNIVERSAL_ORIGEM_KEY)
    return df_origem if isinstance(df_origem, pd.DataFrame) else None


def apply_pricing_step_result() -> None:
    df_origem = source_dataframe_for_pricing()
    if not isinstance(df_origem, pd.DataFrame) or df_origem.empty:
        clear_cadastro_pricing_state()
        render_pending_notice('Carregue os dados primeiro.')
        return
    df_precificado = apply_cadastro_pricing(df_origem, channel='home_price_step')
    if isinstance(df_precificado, pd.DataFrame):
        st.session_state[UNIVERSAL_ORIGEM_PRICED_KEY] = df_precificado
    selected_cost_column = str(st.session_state.get('global_price_source_cost_column') or '').strip()
    if bool(st.session_state.get('cadastro_preco_calculado_ativo', False)):
        suffix = f' usando a coluna de custo "{selected_cost_column}"' if selected_cost_column else ''
        st.success(f'Preço calculado linha a linha{suffix}. O campo Preço de venda será usado no mapeamento e no preview.')
    else:
        st.warning('Calcule um preço para aplicar a referência de precificação aos dados carregados.')


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
    if is_price_update and not is_api_direct and not is_universal_entry:
        section_title(section_number, 'Preço')
        render_price_update_notice()
        st.caption('A planilha de atualização de preços já contém a estrutura e a origem. Use a calculadora somente se quiser recalcular os valores antes do mapeamento.')
    else:
        section_title(section_number, 'Preço')
    if not model_available:
        render_pending_notice('Liberado após escolher o caminho do fluxo.')
        return
    if not universal_context_ready():
        render_pending_notice('Carregue os dados primeiro.')
        return
    df_origem = source_dataframe_for_pricing()
    current_config = get_home_pricing_config()
    use_pricing = st.toggle('Usar calculadora', value=bool(current_config.get('enabled', False)), key='home_pricing_enabled_toggle')
    if use_pricing:
        with st.container(border=True):
            config = render_home_pricing_config_form(source_df=df_origem)
            set_home_pricing_config(config)
            apply_pricing_step_result()
    else:
        disable_home_pricing()
        if not is_price_update:
            clear_cadastro_pricing_state()
        st.caption('Opcional. Se desligada, mantém o preço da origem ou do mapeamento.')


__all__ = ['apply_pricing_step_result', 'render_pricing_step', 'source_dataframe_for_pricing']
