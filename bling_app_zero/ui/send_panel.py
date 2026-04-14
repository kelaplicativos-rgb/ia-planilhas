from __future__ import annotations

import streamlit as st

from bling_app_zero.ui.app_helpers import log_debug


def render_bling_primeiro_acesso(on_skip=None, on_continue=None) -> None:
    """
    Módulo neutralizado.
    A conexão com o Bling foi removida do fluxo principal.
    """
    log_debug("[SEND_PANEL] módulo de conexão neutralizado.", "INFO")
    st.info("A conexão com o Bling foi removida deste projeto.")


def render_send_panel() -> None:
    """
    Módulo neutralizado.
    O envio para o Bling foi removido do fluxo principal.
    """
    log_debug("[SEND_PANEL] módulo de envio neutralizado.", "INFO")
    st.info("O envio para o Bling foi removido deste projeto.")
