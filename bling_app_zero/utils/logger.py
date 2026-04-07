from __future__ import annotations

from datetime import datetime

import streamlit as st


# =========================
# 🧠 INICIALIZA LOG
# =========================
def iniciar_log() -> None:
    try:
        if "logs" not in st.session_state:
            st.session_state["logs"] = []
    except Exception:
        pass


# =========================
# 📝 ADICIONAR LOG
# =========================
def log(msg: str) -> None:
    try:
        iniciar_log()

        agora = datetime.now().strftime("%H:%M:%S")
        linha = f"[{agora}] {str(msg)}"

        st.session_state["logs"].append(linha)
    except Exception:
        pass


# =========================
# 📥 DOWNLOAD LOG
# =========================
def botao_download_log() -> None:
    try:
        iniciar_log()

        if not st.session_state.get("logs"):
            return

        conteudo = "\n".join(st.session_state["logs"])

        st.download_button(
            label="⬇️ Baixar LOG",
            data=conteudo,
            file_name="log_processamento.txt",
            mime="text/plain",
        )
    except Exception:
        pass


# =========================
# 👁️ MOSTRAR LOG (OPCIONAL)
# =========================
def mostrar_log(height: int = 200) -> None:
    try:
        iniciar_log()

        if st.session_state.get("logs"):
            st.text_area(
                "📜 Log do processamento",
                "\n".join(st.session_state["logs"]),
                height=height,
            )
    except Exception:
        pass


# =========================
# 🔄 COMPATIBILIDADE
# =========================
def adicionar_log(msg: str) -> None:
    """
    Alias de compatibilidade para usos antigos.
    """
    log(msg)


def limpar_log() -> None:
    try:
        st.session_state["logs"] = []
    except Exception:
        pass


__all__ = [
    "iniciar_log",
    "log",
    "adicionar_log",
    "botao_download_log",
    "mostrar_log",
    "limpar_log",
]
