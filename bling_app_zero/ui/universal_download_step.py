from __future__ import annotations

import streamlit as st

from bling_app_zero.ui.cadastro_download_step_v2 import render_cadastro_download_step


def _api_flow_active() -> bool:
    return bool(
        st.session_state.get('home_bling_connected_same_flow_api_send')
        or st.session_state.get('bling_connected_api_flow_active')
        or st.session_state.get('direct_bling_api_contract_active')
        or str(st.session_state.get('bling_finish_mode') or '').strip() == 'api_direct'
    )


def _api_operation() -> str:
    for key in ('source_first_selected_operation', 'direct_bling_operation_applied', 'api_operation', 'bling_api_operation', 'operacao_final', 'tipo_operacao_final'):
        value = str(st.session_state.get(key) or '').strip()
        if value in {'cadastro', 'estoque', 'atualizacao_preco'}:
            return value
    return 'cadastro'


def render_universal_download_step() -> None:
    if _api_flow_active():
        try:
            from bling_app_zero.ui.bling_api_nuclei_panel import render_api_nuclei_panel
            render_api_nuclei_panel(_api_operation(), compact=True)
        except Exception as exc:
            st.caption(f'Núcleos API ativos; painel indisponível agora: {exc}')
    render_cadastro_download_step()


__all__ = ['render_universal_download_step']
