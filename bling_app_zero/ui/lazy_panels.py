from __future__ import annotations

import streamlit as st


VALID_OPERATIONS = {'site', 'cadastro', 'estoque'}


def normalize_panel_operation(operation: str | None) -> str:
    text = str(operation or '').strip().lower()
    if text in {'site', 'scraper', 'fornecedores', 'cadastro_site', 'estoque_site'}:
        return 'site'
    if text in {'estoque', 'stock', 'atualizacao_estoque', 'atualização de estoque'}:
        return 'estoque'
    if text in {'cadastro', 'produtos', 'produto', 'planilha'}:
        return 'cadastro'
    return 'site'


def render_lazy_panel(operation: str | None) -> None:
    """Carrega cada fluxo somente quando ele for solicitado pela tela inicial.

    A home fica leve para internet lenta/notebook antigo e cada motor permanece
    isolado no seu próprio módulo: site/scraper, cadastro e estoque.
    """
    normalized = normalize_panel_operation(operation)
    st.session_state['tipo_operacao'] = normalized

    if normalized == 'site':
        from bling_app_zero.ui.site_panel import render_site_panel

        render_site_panel()
        return

    if normalized == 'estoque':
        from bling_app_zero.ui.estoque_panel import render_estoque_panel

        render_estoque_panel()
        return

    from bling_app_zero.ui.cadastro_panel_modular import render_cadastro_panel

    render_cadastro_panel()
