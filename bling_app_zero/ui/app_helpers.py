
import streamlit as st
from datetime import datetime
from pathlib import Path

# ===============================
# CONFIG
# ===============================

LOG_PATH = Path("bling_app_zero/output/debug_log.txt")
LOG_PATH.parent.mkdir(parents=True, exist_ok=True)


# ===============================
# LOG GLOBAL (MEMÓRIA + ARQUIVO)
# ===============================

def log_debug(msg, nivel="INFO"):
    """Registra log na memória e no arquivo"""

    if "logs_debug" not in st.session_state:
        st.session_state["logs_debug"] = []

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    linha = f"[{timestamp}] [{nivel}] {msg}"

    # memória
    st.session_state["logs_debug"].append(linha)

    # arquivo persistente
    try:
        with open(LOG_PATH, "a", encoding="utf-8") as f:
            f.write(linha + "\n")
    except Exception as e:
        st.session_state["logs_debug"].append(f"[ERRO LOG] {e}")


def obter_logs():
    """Prioriza arquivo persistente"""
    try:
        if LOG_PATH.exists():
            return LOG_PATH.read_text(encoding="utf-8")
    except:
        pass

    if "logs_debug" in st.session_state:
        return "\n".join(st.session_state["logs_debug"])

    return ""


# ===============================
# BOTÃO FIXO (FLOAT)
# ===============================

def render_botao_download_logs():
    """Botão fixo no canto da tela"""

    logs_txt = obter_logs()

    if not logs_txt.strip():
        return

    # CSS botão flutuante
    st.markdown(
        """
        <style>
        .botao-log-fixo {
            position: fixed;
            bottom: 20px;
            right: 20px;
            z-index: 9999;
        }
        </style>
        """,
        unsafe_allow_html=True
    )

    # container fixo
    with st.container():
        st.markdown('<div class="botao-log-fixo">', unsafe_allow_html=True)

        st.download_button(
            label="📥 Log",
            data=logs_txt,
            file_name="debug_log.txt",
            mime="text/plain",
            use_container_width=False
        )

        st.markdown("</div>", unsafe_allow_html=True)


# ===============================
# LIMPAR LOG
# ===============================

def limpar_logs():
    """Limpa logs memória + arquivo"""
    st.session_state["logs_debug"] = []

    try:
        if LOG_PATH.exists():
            LOG_PATH.unlink()
    except:
        pass
