from __future__ import annotations

from datetime import datetime
import pandas as pd
import streamlit as st

# =========================
# CONFIG (TEM QUE SER O PRIMEIRO)
# =========================
st.set_page_config(page_title="IA Planilhas Bling", layout="wide")

# =========================
# VERSIONAMENTO
# =========================
APP_VERSION = "1.0.13"


# =========================
# LOG GLOBAL
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
# IA DEBUG
# =========================
def analisar_logs_com_ia(logs: list[str]) -> dict:
    if not logs:
        return {
            "tipo": "Sem logs",
            "problema": "Nenhum evento registrado ainda.",
            "solucao": "-"
        }

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

    if "excel" in texto and "erro" in texto:
        return {
            "tipo": "Erro Excel",
            "problema": "Falha ao ler modelo",
            "solucao": "Verifique formato XLSX"
        }

    return {
        "tipo": "Não identificado",
        "problema": "Verifique manualmente",
        "solucao": "-"
    }


# =========================
# HELPERS DE ESTADO
# =========================
def _safe_df_from_state(key: str) -> pd.DataFrame | None:
    try:
        valor = st.session_state.get(key)
        if isinstance(valor, pd.DataFrame) and not valor.empty:
            return valor
    except Exception:
        pass
    return None


def _get_df_origem() -> pd.DataFrame | None:
    return _safe_df_from_state("df_origem")


def _get_df_final() -> pd.DataFrame | None:
    return _safe_df_from_state("df_final")


# =========================
# IMPORTS SEGUROS
# =========================
render_origem_dados = None
render_origem_mapeamento = None
render_bling_panel = None

try:
    from bling_app_zero.ui.origem_dados import render_origem_dados
    log_debug("Import origem_dados OK")
except Exception as e:
    log_debug(f"Erro origem_dados: {e}", "ERROR")

try:
    from bling_app_zero.ui.origem_mapeamento import render_origem_mapeamento
    log_debug("Import origem_mapeamento OK")
except Exception as e:
    log_debug(f"Erro origem_mapeamento: {e}", "ERROR")

try:
    from bling_app_zero.ui.bling_panel import render_bling_panel
    log_debug("Import bling_panel OK")
except Exception as e:
    log_debug(f"Erro bling_panel: {e}", "ERROR")


# =========================
# UI
# =========================
st.title("IA Planilhas → Bling")
st.caption(f"Versão: {APP_VERSION}")


# =========================
# FLUXO PRINCIPAL
# =========================
etapa_origem = st.session_state.get("etapa_origem", "upload")
df_origem = _get_df_origem()
df_final = _get_df_final()

# 1) ORIGEM
if render_origem_dados:
    try:
        log_debug("Iniciando: Origem dos Dados")
        render_origem_dados()
        log_debug("Finalizado: Origem dos Dados", "SUCCESS")
    except Exception as e:
        log_debug(f"Erro execução origem_dados: {e}", "ERROR")
        st.error("Erro na origem dos dados")
else:
    st.error("Erro ao carregar módulo origem_dados")

# Recarrega após origem
etapa_origem = st.session_state.get("etapa_origem", "upload")
df_origem = _get_df_origem()
df_final = _get_df_final()

# 2) MAPEAMENTO
if etapa_origem == "mapeamento":
    st.divider()
    st.subheader("Mapeamento e validação")

    if render_origem_mapeamento:
        try:
            render_origem_mapeamento()
        except Exception as e:
            log_debug(f"Erro mapeamento: {e}", "ERROR")
            st.error("Erro no mapeamento")
    else:
        st.warning("Módulo de mapeamento não carregado")

# 3) BLING
if df_final is not None and etapa_origem != "upload":
    st.divider()
    st.subheader("Integração com Bling")

    if render_bling_panel:
        try:
            render_bling_panel()
        except Exception as e:
            log_debug(f"Erro bling panel: {e}", "ERROR")
            st.error("Erro na integração Bling")
    else:
        st.warning("Módulo Bling não carregado")


# =========================
# DEBUG
# =========================
with st.expander("🔍 Debug do sistema"):
    logs = st.session_state.get("logs", [])

    for l in reversed(logs[-50:]):
        st.text(l)

    log_texto = "\n".join(logs)

    st.download_button(
        "Baixar log",
        log_texto,
        "debug.txt",
        key="download_debug_log",
    )

    st.markdown("### 🧠 IA Debug")

    diag = analisar_logs_com_ia(logs)

    st.warning(diag.get("tipo", "Não identificado"))
    st.write(diag.get("problema", "-"))
    st.success(diag.get("solucao", "-"))
