from __future__ import annotations

import streamlit as st


def limpar_cache_se_necessario():
    """
    Limpa cache automaticamente UMA VEZ por sessão.
    Evita bugs de leitura de planilha, estado antigo e processamento preso.
    """

    try:
        if not st.session_state.get("_cache_limpo_auto", False):
            st.cache_data.clear()
            st.cache_resource.clear()

            # marca que já limpou
            st.session_state["_cache_limpo_auto"] = True

            # opcional: log visual
            st.session_state["_cache_log"] = "Cache limpo automaticamente na inicialização."

    except Exception:
        pass


def inicializar_app():
    """
    Ponto único de inicialização do app.
    Pode crescer depois (logs, configs, etc).
    """

    limpar_cache_se_necessario()
