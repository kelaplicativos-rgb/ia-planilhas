from __future__ import annotations

from datetime import datetime

import pandas as pd
import streamlit as st

from bling_app_zero.ui.origem_dados_helpers import (
    exportar_excel_bytes,
    limpar_gtin_invalido,
    validar_campos_obrigatorios,
)
from bling_app_zero.utils.init_app import inicializar_app

# tenta usar exportador mais robusto, sem quebrar se não existir
try:
    from bling_app_zero.utils.excel import (
        exportar_dataframe_para_excel as _exportar_excel_robusto,
    )
except Exception:
    _exportar_excel_robusto = None

from bling_app_zero.ui.bling_panel import render_bling_panel
from bling_app_zero.ui.fornecedores_panel import render_fornecedores_panel
from bling_app_zero.ui.origem_dados import render_origem_dados
from bling_app_zero.ui.origem_mapeamento import render_origem_mapeamento


# =========================
# CONFIG
# =========================
st.set_page_config(page_title="IA Planilhas Bling", layout="wide")

APP_VERSION = "1.0.20"


# =========================
# INICIALIZAÇÃO
# =========================
inicializar_app()


# =========================
# LOG
# =========================
if "logs" not in st.session_state:
    st.session_state["logs"] = []

if "etapa_origem" not in st.session_state or not st.session_state.get("etapa_origem"):
    st.session_state["etapa_origem"] = "upload"

if "area_app" not in st.session_state:
    st.session_state["area_app"] = "Fluxo principal"


def log_debug(msg: str, nivel: str = "INFO") -> None:
    try:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        linha = f"[{timestamp}] [{nivel}] {msg}"
        st.session_state["logs"].append(linha)
    except Exception:
        pass


# =========================
# HELPERS
# =========================
def _safe_df(key: str) -> pd.DataFrame | None:
    df = st.session_state.get(key)
    if isinstance(df, pd.DataFrame) and not df.empty and len(df.columns) > 0:
        return df.copy()
    return None


def _get_df_fluxo() -> pd.DataFrame | None:
    """
    Ordem de prioridade do fluxo final:
    1) df_saida        -> normalmente o mais próximo do arquivo final
    2) df_final        -> consolidado do fluxo
    3) df_precificado  -> fallback quando a precificação já foi gerada
    4) df_origem       -> último recurso para não quebrar a UI
    """
    for key in ["df_saida", "df_final", "df_precificado", "df_origem"]:
        df = _safe_df(key)
        if df is not None:
            return df
    return None


def _sincronizar_df_final() -> None:
    """
    Mantém um espelho estável em df_final sem sobrescrever incorretamente
    o melhor DataFrame do fluxo.
    """
    df_fluxo = _get_df_fluxo()
    if df_fluxo is not None:
        st.session_state["df_final"] = df_fluxo.copy()


def _normalizar_validacao_obrigatorios(resultado_validacao) -> bool:
    """
    Aceita bool direto ou estruturas mais complexas retornadas pelo helper.
    """
    try:
        if isinstance(resultado_validacao, bool):
            return resultado_validacao

        if resultado_validacao is None:
            return True

        if isinstance(resultado_validacao, dict):
            return len(resultado_validacao) == 0

        if isinstance(resultado_validacao, (list, tuple, set)):
            return len(resultado_validacao) == 0

        return bool(resultado_validacao)
    except Exception:
        return True


def _exportar_download_bytes(df: pd.DataFrame) -> bytes:
    """
    Tenta primeiro um exportador robusto. Se não existir ou falhar,
    cai no exportador atual do projeto.
    """
    if _exportar_excel_robusto is not None:
        try:
            retorno = _exportar_excel_robusto(df)

            if isinstance(retorno, bytes):
                return retorno

            if hasattr(retorno, "getvalue"):
                return retorno.getvalue()
        except Exception as e:
            log_debug(f"Falha no exportador robusto: {e}", "ERRO")

    return exportar_excel_bytes(df)


def _render_preview_final() -> None:
    _sincronizar_df_final()
    df_fluxo = _get_df_fluxo()

    if df_fluxo is None:
        st.warning("Nenhum dado disponível para o preview final.")
        log_debug("Etapa final sem DataFrame disponível", "ERRO")
        return

    try:
        log_debug(
            f"Preview final carregado com {len(df_fluxo)} linha(s) e "
            f"{len(df_fluxo.columns)} coluna(s)"
        )
    except Exception:
        pass

    st.divider()
    st.subheader("Preview final")

    with st.expander("📦 Ver dados finais", expanded=False):
        st.dataframe(df_fluxo.head(20), use_container_width=True)

    col1, col2 = st.columns(2)

    with col1:
        if st.button(
            "⬅️ Voltar para mapeamento",
            use_container_width=True,
            key="btn_voltar_para_mapeamento_final",
        ):
            st.session_state["etapa_origem"] = "mapeamento"
            st.rerun()

    with col2:
        if st.button(
            "🔄 Atualizar preview",
            use_container_width=True,
            key="btn_atualizar_preview_final",
        ):
            st.session_state["df_final"] = df_fluxo.copy()
            st.rerun()

    try:
        df_download = limpar_gtin_invalido(df_fluxo.copy())
    except Exception as e:
        log_debug(f"Erro ao limpar GTIN inválido: {e}", "ERRO")
        df_download = df_fluxo.copy()

    validacao_ok = True
    excel_bytes = None

    try:
        validacao_ok = _normalizar_validacao_obrigatorios(
            validar_campos_obrigatorios(df_download)
        )
    except Exception as e:
        log_debug(f"Erro na validação de campos obrigatórios: {e}", "ERRO")
        validacao_ok = True

    if not validacao_ok:
        st.error("Preencha os campos obrigatórios antes do download.")
    else:
        try:
            excel_bytes = _exportar_download_bytes(df_download)
        except Exception as e:
            log_debug(f"Erro ao gerar Excel final: {e}", "ERRO")
            st.error("Não foi possível gerar a planilha final.")

    if excel_bytes:
        st.download_button(
            "⬇️ Baixar planilha final",
            excel_bytes,
            "bling_final.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
            key="btn_baixar_planilha_final",
        )

    st.divider()
    st.subheader("Integração com Bling")
    render_bling_panel()


# =========================
# UI
# =========================
st.title("IA Planilhas → Bling")
st.caption(f"Versão: {APP_VERSION}")

if st.session_state.get("_cache_log"):
    st.info(st.session_state.get("_cache_log"))

area_app = st.radio(
    "Área do sistema",
    ["Fluxo principal", "Fornecedores adaptativos"],
    horizontal=True,
    key="area_app",
)

if area_app == "Fornecedores adaptativos":
    render_fornecedores_panel()

    with st.expander("🔍 Debug", expanded=False):
        logs = st.session_state.get("logs", [])

        for linha in reversed(logs[-100:]):
            st.text(linha)

        st.download_button(
            "📥 Baixar log",
            "\n".join(logs),
            "debug.txt",
            use_container_width=True,
            key="btn_baixar_log_debug_fornecedores",
        )

    st.stop()


# =========================
# CONTROLE DE ETAPA
# =========================
etapa = st.session_state.get("etapa_origem")

if not etapa:
    etapa = "upload"
    st.session_state["etapa_origem"] = "upload"


# =========================
# ETAPA 1 — ORIGEM
# =========================
if etapa in ["upload", "origem"]:
    render_origem_dados()
    _sincronizar_df_final()


# =========================
# ETAPA 2 — MAPEAMENTO
# =========================
elif etapa == "mapeamento":
    st.divider()
    st.subheader("Mapeamento")
    render_origem_mapeamento()
    _sincronizar_df_final()


# =========================
# ETAPA 3 — FINAL
# =========================
elif etapa == "final":
    _render_preview_final()


# =========================
# FALLBACK DE ETAPA DESCONHECIDA
# =========================
else:
    log_debug(f"Etapa desconhecida recebida: {etapa}", "ERRO")
    st.warning("Etapa do fluxo inválida. Retornando para a origem.")
    st.session_state["etapa_origem"] = "upload"
    st.rerun()


# =========================
# DEBUG
# =========================
with st.expander("🔍 Debug", expanded=False):
    logs = st.session_state.get("logs", [])

    for linha in reversed(logs[-100:]):
        st.text(linha)

    st.download_button(
        "📥 Baixar log",
        "\n".join(logs),
        "debug.txt",
        use_container_width=True,
        key="btn_baixar_log_debug",
    )
