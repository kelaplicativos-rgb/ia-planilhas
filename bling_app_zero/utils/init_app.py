from __future__ import annotations

import streamlit as st


# ⚠️ MANTER IGUAL AO app.py
APP_VERSION = "1.0.20"


def limpar_cache_se_necessario() -> None:
    """
    Limpa cache automaticamente de forma inteligente:
    - 1x por sessão
    - OU quando a versão do app muda (deploy novo)
    """

    try:
        cache_ja_limpo = st.session_state.get("_cache_limpo_auto", False)
        versao_cache = st.session_state.get("_cache_version")

        precisa_limpar = (
            not cache_ja_limpo
            or versao_cache != APP_VERSION
        )

        if precisa_limpar:
            st.cache_data.clear()
            st.cache_resource.clear()

            st.session_state["_cache_limpo_auto"] = True
            st.session_state["_cache_version"] = APP_VERSION
            st.session_state["_cache_log"] = (
                f"Cache limpo automaticamente (versão {APP_VERSION})"
            )

    except Exception:
        pass


def inicializar_app() -> None:
    """
    Inicialização central do app.
    Aqui você pode evoluir depois (logs, configs, IA debug etc).
    """

    limpar_cache_se_necessario()
