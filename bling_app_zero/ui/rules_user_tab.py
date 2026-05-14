from __future__ import annotations

import streamlit as st


def render_user_rules_tab() -> None:
    """A edição de regras foi centralizada no fluxo principal.

    BLINGFIX: regras não devem ficar duplicadas na sidebar. A Central de Regras
    e Padrões é a única tela de criação, edição, exclusão e desligamento geral.
    """
    st.markdown('##### Regras centralizadas')
    st.info(
        'As regras agora ficam na etapa **Regras e Padrões** do fluxo principal. '
        'Criação, edição, exclusão e o botão de desligar geral foram centralizados lá para evitar conflito com a sidebar.'
    )
