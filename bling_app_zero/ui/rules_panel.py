from __future__ import annotations

import streamlit as st

from bling_app_zero.ui.rules_resources_tab import render_resources_tab
from bling_app_zero.ui.rules_user_tab import render_user_rules_tab


def render_rules_panel() -> None:
    """Orquestra as abas de Regras e Recursos do CSV final.

    Responsabilidade deste arquivo:
    - abrir o painel lateral;
    - criar as abas;
    - chamar os módulos independentes.

    Não colocar aqui:
    - lógica de edição de regra;
    - lógica de recursos;
    - logs;
    - IA;
    - diagnóstico técnico.
    """
    with st.sidebar:
        with st.expander('Regras e recursos do CSV final', expanded=False):
            tab_rules, tab_resources = st.tabs(['Regras', 'Recursos'])

            with tab_rules:
                render_user_rules_tab()

            with tab_resources:
                render_resources_tab()
