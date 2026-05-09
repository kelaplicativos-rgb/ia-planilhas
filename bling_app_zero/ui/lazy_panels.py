from __future__ import annotations

import streamlit as st


VALID_OPERATIONS = {'site', 'cadastro', 'estoque'}


def normalize_panel_operation(operation: str | None) -> str:
    text = str(operation or '').strip().lower()
    if text in {'site', 'scraper', 'fornecedores', 'cadastro_site', 'estoque_site'}:
        return 'site'
    if text in {'estoque', 'stock', 'atualizacao_estoque', 'atualização de estoque'}:
        return 'estoque'
    if text in {'cadastro', 'produtos', 'produto', 'planilha', 'arquivo'}:
        return 'cadastro'
    return 'site'


def render_lazy_panel(operation: str | None) -> None:
    """Carrega cada fluxo somente quando ele for solicitado pela tela inicial."""
    normalized = normalize_panel_operation(operation)

    if normalized == 'site':
        st.session_state['origem_final'] = 'site'
        from bling_app_zero.ui.site_panel import render_site_panel

        render_site_panel()
        return

    if normalized == 'estoque':
        st.session_state['tipo_operacao'] = 'estoque'
        st.session_state['operacao_final'] = 'estoque'
        st.session_state['tipo_operacao_final'] = 'estoque'
        st.session_state['origem_final'] = st.session_state.get('origem_final') or 'arquivo'
        from bling_app_zero.ui.estoque_panel import render_estoque_panel

        render_estoque_panel()
        return

    st.session_state['tipo_operacao'] = 'cadastro'
    st.session_state['operacao_final'] = 'cadastro'
    st.session_state['tipo_operacao_final'] = 'cadastro'
    st.session_state['origem_final'] = st.session_state.get('origem_final') or 'arquivo'
    from bling_app_zero.ui.cadastro_panel_modular import render_cadastro_panel

    render_cadastro_panel()
