from __future__ import annotations

import streamlit as st


# ⚠️ MANTER IGUAL AO app.py
APP_VERSION = "1.0.22"


def limpar_cache_se_necessario() -> None:
    """
    Limpa cache automaticamente de forma segura:
    - 1x por sessão
    - somente quando a versão muda
    - sem forçar comportamento agressivo a cada rerun
    """
    try:
        cache_ja_limpo = bool(st.session_state.get("_cache_limpo_auto", False))
        versao_cache = str(st.session_state.get("_cache_version", "") or "").strip()

        precisa_limpar = (not cache_ja_limpo) or (versao_cache != APP_VERSION)

        if not precisa_limpar:
            return

        try:
            st.cache_data.clear()
        except Exception:
            pass

        try:
            st.cache_resource.clear()
        except Exception:
            pass

        st.session_state["_cache_limpo_auto"] = True
        st.session_state["_cache_version"] = APP_VERSION
        st.session_state["_cache_log"] = (
            f"Cache limpo automaticamente (versão {APP_VERSION})"
        )

    except Exception:
        # não derrubar o app por causa de cache
        try:
            st.session_state["_cache_limpo_auto"] = True
            st.session_state["_cache_version"] = APP_VERSION
        except Exception:
            pass


def inicializar_app() -> None:
    """
    Inicialização central do app.
    """
    try:
        if "logs" not in st.session_state:
            st.session_state["logs"] = []
    except Exception:
        pass

    limpar_cache_se_necessario()
