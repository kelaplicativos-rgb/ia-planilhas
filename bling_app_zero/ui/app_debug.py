
from __future__ import annotations

from datetime import datetime

import streamlit as st


def _agora_str() -> str:
    return datetime.now().strftime("%d/%m/%Y %H:%M:%S")


def inicializar_debug() -> None:
    if "debug_logs" not in st.session_state:
        st.session_state["debug_logs"] = []


def log_debug(mensagem: str, nivel: str = "INFO") -> None:
    inicializar_debug()
    linha = f"[{_agora_str()}] [{str(nivel).upper()}] {mensagem}"
    st.session_state["debug_logs"].append(linha)


def obter_logs_texto() -> str:
    inicializar_debug()
    return "\n".join(st.session_state.get("debug_logs", []))


def limpar_logs() -> None:
    st.session_state["debug_logs"] = []


def render_debug_panel(titulo: str = "Debug do sistema") -> None:
    inicializar_debug()

    with st.expander(titulo, expanded=False):
        logs = st.session_state.get("debug_logs", [])

        if logs:
            st.text_area(
                "Logs",
                value="\n".join(logs[-500:]),
                height=250,
                key="debug_logs_area",
            )

            col1, col2 = st.columns(2)

            with col1:
                st.download_button(
                    "⬇️ Baixar log TXT",
                    data=obter_logs_texto().encode("utf-8"),
                    file_name="debug_ia_planilhas.txt",
                    mime="text/plain",
                    use_container_width=True,
                )

            with col2:
                if st.button("Limpar log", use_container_width=True):
                    limpar_logs()
                    st.rerun()
        else:
            st.caption("Nenhum log registrado até agora.")
