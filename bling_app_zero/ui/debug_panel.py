from __future__ import annotations

from datetime import datetime
from typing import Any

import streamlit as st


def add_debug_log(message: str, payload: Any | None = None) -> None:
    logs = st.session_state.setdefault("logs", [])
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{timestamp}] {message}"
    if payload is not None:
        line += f" | {payload}"
    logs.append(line)
    st.session_state["logs"] = logs[-500:]


def render_debug_panel() -> None:
    with st.sidebar.expander("🧪 Debug", expanded=False):
        logs = st.session_state.get("logs", [])

        if not logs:
            st.caption("Nenhum log registrado ainda.")
        else:
            with st.expander("Ver logs da sessão", expanded=False):
                st.code("\n".join(logs[-80:]))

            st.download_button(
                "⬇️ Baixar log debug",
                data="\n".join(logs),
                file_name="debug_ia_planilhas.txt",
                mime="text/plain",
                use_container_width=True,
            )

        if st.button("🧹 Limpar debug", use_container_width=True):
            st.session_state["logs"] = []
            st.rerun()
