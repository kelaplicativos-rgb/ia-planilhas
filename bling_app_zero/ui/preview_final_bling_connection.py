from __future__ import annotations

import streamlit as st

from bling_app_zero.ui.app_helpers import log_debug
from bling_app_zero.ui.preview_final_state import safe_import_bling_auth


def render_conexao_bling(liberado: bool) -> None:
    if not liberado:
        st.warning(
            "A conexão com o Bling só é liberada depois que o resultado final estiver validado, "
            "o download for confirmado e, quando for origem por site, a varredura estiver concluída."
        )
        return

    bling_auth = safe_import_bling_auth()
    if bling_auth is None:
        st.error("Módulo de autenticação do Bling não disponível nesta execução.")
        return

    render_conectar_bling = bling_auth.get("render_conectar_bling")
    if callable(render_conectar_bling):
        try:
            render_conectar_bling()
            return
        except Exception as exc:
            st.error(f"Falha ao renderizar conexão com o Bling: {exc}")
            log_debug(f"Falha ao renderizar conexão com o Bling: {exc}", nivel="ERRO")
            return

    st.error("Função de conexão OAuth do Bling não encontrada.")
