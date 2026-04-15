
from __future__ import annotations

import streamlit as st


def render_send_panel(*args, **kwargs) -> None:
    st.info("O envio para o Bling foi removido do fluxo principal desta versão.")


def render_bling_primeiro_acesso(*args, **kwargs) -> None:
    st.info("A conexão com o Bling foi removida deste projeto nesta versão.")
