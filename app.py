from __future__ import annotations

import streamlit as st
from datetime import datetime

# =========================
# 🔥 VERSIONAMENTO
# =========================
APP_VERSION = "1.0.5"


# =========================
# 🔥 LOG GLOBAL
# =========================
if "logs" not in st.session_state:
    st.session_state["logs"] = []


def log_debug(msg: str, nivel: str = "INFO") -> None:
    """
    Logger global do sistema
    """
    try:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        linha = f"[{timestamp}] [{nivel}] {msg}"
        st.session_state["logs"].append(linha)
    except Exception:
        pass


# =========================
# 🔥 PROTEÇÃO GLOBAL
# =========================
def executar_com_log(func, nome: str):
    try:
        log_debug(f"Iniciando: {nome}")
        func()
        log_debug(f"Finalizado: {nome}", "SUCCESS")
    except Exception as e:
        erro = f"Erro em {nome}: {str(e)}"
        log_debug(erro, "ERROR")
        st.error(erro)


# =========================
# 🔥 IMPORTS DO SISTEMA
# =========================
try:
    from bling_app_zero.ui.origem_dados import render_origem_dados
    log_debug("Import origem_dados OK")
except Exception as e:
    log_debug(f"Erro import origem_dados: {e}", "ERROR")

try:
    from bling_app_zero.ui.origem_mapeamento import render_origem_mapeamento
    log_debug("Import origem_mapeamento OK")
except Exception as e:
    log_debug(f"Erro import origem_mapeamento: {e}", "ERROR")

try:
    from bling_app_zero.ui.bling_panel import render_bling_panel
    log_debug("Import bling_panel OK")
except Exception as e:
    log_debug(f"Erro import bling_panel: {e}", "ERROR")


# =========================
# 🔥 CONFIG PAGE
# =========================
st.set_page_config(
    page_title="IA Planilhas Bling",
    layout="wide"
)


# =========================
# 🔥 HEADER
# =========================
st.title("IA Planilhas → Bling")
st.caption(f"Versão: {APP_VERSION}")


# =========================
# 🔥 FLUXO PRINCIPAL
# =========================
try:
    executar_com_log(render_origem_dados, "Origem dos Dados")
except:
    pass


# =========================
# 🔥 DEBUG (OCULTO)
# =========================
with st.expander("🔍 Debug do sistema", expanded=False):

    st.markdown("### Logs em tempo real")

    logs = st.session_state.get("logs", [])

    if logs:
        for l in reversed(logs[-50:]):
            st.text(l)
    else:
        st.info("Nenhum log ainda.")

    st.markdown("---")

    # 🔥 DOWNLOAD DO LOG DIRETO DO APP (EXTRA)
    log_texto = "\n".join(logs) if logs else "Sem logs disponíveis"

    st.download_button(
        label="📥 Baixar log completo",
        data=log_texto.encode("utf-8"),
        file_name="debug_sistema.txt",
        mime="text/plain",
        use_container_width=True,
    )
