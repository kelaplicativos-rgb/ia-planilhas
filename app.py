from __future__ import annotations

import streamlit as st
from datetime import datetime

# =========================
# 🔥 VERSIONAMENTO
# =========================
APP_VERSION = "1.0.7"


# =========================
# 🔥 LOG GLOBAL
# =========================
if "logs" not in st.session_state:
    st.session_state["logs"] = []


def log_debug(msg: str, nivel: str = "INFO") -> None:
    try:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        linha = f"[{timestamp}] [{nivel}] {msg}"
        st.session_state["logs"].append(linha)
    except Exception:
        pass


# =========================
# 🧠 IA DEBUG
# =========================
def analisar_logs_com_ia(logs: list[str]) -> dict:
    if not logs:
        return {}

    texto = "\n".join(logs[-50:]).lower()

    if "unicode" in texto:
        return {
            "tipo": "Erro CSV",
            "problema": "Encoding inválido",
            "solucao": "Salvar como UTF-8"
        }

    if "empty" in texto:
        return {
            "tipo": "Planilha vazia",
            "problema": "Sem dados",
            "solucao": "Verifique o arquivo"
        }

    if "gtin" in texto:
        return {
            "tipo": "GTIN inválido",
            "problema": "Código inválido",
            "solucao": "Sistema limpa automaticamente"
        }

    return {
        "tipo": "Não identificado",
        "problema": "Verifique manual",
        "solucao": "-"
    }


# =========================
# 🔥 IMPORTS
# =========================
try:
    from bling_app_zero.ui.origem_dados import render_origem_dados
except Exception as e:
    log_debug(f"Erro origem_dados: {e}", "ERROR")

try:
    from bling_app_zero.ui.origem_mapeamento import render_origem_mapeamento
except Exception as e:
    log_debug(f"Erro origem_mapeamento: {e}", "ERROR")

try:
    from bling_app_zero.ui.bling_panel import render_bling_panel
except Exception as e:
    log_debug(f"Erro bling_panel: {e}", "ERROR")


# =========================
# CONFIG
# =========================
st.set_page_config(page_title="IA Planilhas Bling", layout="wide")

st.title("IA Planilhas → Bling")
st.caption(f"Versão: {APP_VERSION}")

# =========================
# 🔥 FLUXO REAL CORRIGIDO
# =========================

# 1️⃣ ORIGEM
render_origem_dados()

# 2️⃣ MAPEAMENTO (SÓ SE EXISTIR DF)
if "df_final" in st.session_state and st.session_state["df_final"] is not None:
    st.divider()
    st.subheader("Mapeamento e validação")

    try:
        render_origem_mapeamento()
    except Exception as e:
        log_debug(f"Erro mapeamento: {e}", "ERROR")
        st.error("Erro no mapeamento")

# 3️⃣ BLING PANEL
if "df_final" in st.session_state and st.session_state["df_final"] is not None:
    st.divider()
    st.subheader("Integração com Bling")

    try:
        render_bling_panel()
    except Exception as e:
        log_debug(f"Erro bling panel: {e}", "ERROR")
        st.error("Erro na integração Bling")


# =========================
# 🔍 DEBUG
# =========================
with st.expander("🔍 Debug do sistema"):

    logs = st.session_state.get("logs", [])

    for l in reversed(logs[-50:]):
        st.text(l)

    log_texto = "\n".join(logs)

    st.download_button(
        "Baixar log",
        log_texto,
        "debug.txt"
    )

    st.markdown("### 🧠 IA Debug")

    diag = analisar_logs_com_ia(logs)

    st.warning(diag["tipo"])
    st.write(diag["problema"])
    st.success(diag["solucao"])
