# bling_app_zero/ui/debug_panel.py

from __future__ import annotations

from datetime import datetime
from typing import Any

import pandas as pd
import streamlit as st


LOG_KEY = "logs"
DEBUG_ENABLED_KEY = "debug_panel_enabled"
DEBUG_INLINE_ENABLED_KEY = "debug_panel_inline_enabled"


def add_debug_log(message: Any, payload: Any | None = None, *, origem: str = "APP") -> None:
    """Adiciona uma linha segura no log interno do Streamlit."""
    try:
        if LOG_KEY not in st.session_state or not isinstance(st.session_state.get(LOG_KEY), list):
            st.session_state[LOG_KEY] = []

        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        texto = str(message or "").strip()
        if payload is not None:
            texto = f"{texto} | {payload}"
        if not texto:
            return

        st.session_state[LOG_KEY].append(f"[{timestamp}] [{origem}] {texto}")

        # Evita deixar a sessão pesada em capturas grandes.
        if len(st.session_state[LOG_KEY]) > 1200:
            st.session_state[LOG_KEY] = st.session_state[LOG_KEY][-1200:]
    except Exception:
        pass


def _logs_text() -> str:
    logs = st.session_state.get(LOG_KEY, [])
    if not isinstance(logs, list):
        return str(logs or "")
    return "\n".join(str(item) for item in logs)


def _session_summary() -> str:
    linhas: list[str] = []
    try:
        for key in sorted(st.session_state.keys()):
            value = st.session_state.get(key)
            if key == LOG_KEY:
                linhas.append(f"{key}: {len(value) if isinstance(value, list) else 0} linhas")
            elif isinstance(value, pd.DataFrame):
                linhas.append(f"{key}: DataFrame {len(value)} linhas × {len(value.columns)} colunas")
            elif isinstance(value, (list, tuple, set, dict)):
                linhas.append(f"{key}: {type(value).__name__} tamanho={len(value)}")
            else:
                preview = str(value)
                if len(preview) > 120:
                    preview = preview[:120] + "..."
                linhas.append(f"{key}: {type(value).__name__} = {preview}")
    except Exception as exc:
        linhas.append(f"Erro ao montar resumo da sessão: {exc}")
    return "\n".join(linhas)


def _render_debug_content(prefix: str, *, use_expanders: bool = True) -> None:
    logs_text = _logs_text()
    st.caption(f"Logs registrados: {len(st.session_state.get(LOG_KEY, []))}")

    col_down, col_note = st.columns([1, 1])
    with col_down:
        st.download_button(
            "📥 Baixar log debug",
            data=logs_text.encode("utf-8-sig"),
            file_name=f"debug_ia_planilhas_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
            mime="text/plain",
            use_container_width=True,
            key=f"{prefix}_download_debug_log",
        )
    with col_note:
        if st.button("🧹 Limpar log", use_container_width=True, key=f"{prefix}_clear_debug_log"):
            st.session_state[LOG_KEY] = []
            add_debug_log("Log limpo pelo usuário.", origem="DEBUG")
            st.rerun()

    if use_expanders:
        with st.expander("📋 Log interno", expanded=True):
            if logs_text.strip():
                st.code(logs_text[-20000:], language="text")
            else:
                st.info("Nenhum log interno registrado ainda.")

        with st.expander("🧠 Estado da sessão", expanded=False):
            st.code(_session_summary(), language="text")

        with st.expander("➕ Adicionar anotação manual", expanded=False):
            nota = st.text_input("Anotação", key=f"{prefix}_debug_manual_note")
            if st.button("Adicionar ao log", use_container_width=True, key=f"{prefix}_btn_add_manual_debug_note"):
                add_debug_log(nota, origem="MANUAL")
                st.rerun()
        return

    st.markdown("**📋 Log interno**")
    if logs_text.strip():
        st.code(logs_text[-20000:], language="text")
    else:
        st.info("Nenhum log interno registrado ainda.")

    st.markdown("**🧠 Estado da sessão**")
    st.code(_session_summary(), language="text")

    st.markdown("**➕ Adicionar anotação manual**")
    nota = st.text_input("Anotação", key=f"{prefix}_debug_manual_note")
    if st.button("Adicionar ao log", use_container_width=True, key=f"{prefix}_btn_add_manual_debug_note"):
        add_debug_log(nota, origem="MANUAL")
        st.rerun()


def render_debug_panel() -> None:
    """Renderiza o botão/painel de debug na sidebar."""
    if LOG_KEY not in st.session_state:
        st.session_state[LOG_KEY] = []

    with st.sidebar:
        st.divider()
        st.caption("🧪 Debug")

        if st.button("🐞 Abrir/fechar log", use_container_width=True, key="btn_toggle_debug_log"):
            st.session_state[DEBUG_ENABLED_KEY] = not bool(st.session_state.get(DEBUG_ENABLED_KEY, False))

        if not bool(st.session_state.get(DEBUG_ENABLED_KEY, False)):
            st.caption("Clique em 🐞 para abrir o painel.")
            return

        _render_debug_content("sidebar", use_expanders=True)


def render_debug_panel_inline() -> None:
    """Renderiza um botão de debug visível no corpo da página."""
    if LOG_KEY not in st.session_state:
        st.session_state[LOG_KEY] = []

    with st.container():
        col_a, col_b = st.columns([2, 1])
        with col_a:
            st.caption("🧪 Debug ativo no sistema — se esta faixa apareceu, o deploy já está usando o código novo.")
        with col_b:
            if st.button("🐞 Abrir log debug", use_container_width=True, key="btn_toggle_inline_debug_log"):
                st.session_state[DEBUG_INLINE_ENABLED_KEY] = not bool(st.session_state.get(DEBUG_INLINE_ENABLED_KEY, False))

    if bool(st.session_state.get(DEBUG_INLINE_ENABLED_KEY, False)):
        st.markdown("### 🐞 Painel de debug")
        _render_debug_content("inline", use_expanders=False)
