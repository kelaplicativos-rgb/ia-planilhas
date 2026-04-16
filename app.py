
from __future__ import annotations

import streamlit as st

from bling_app_zero.ui.ia_panel import render_ia_panel
from bling_app_zero.ui.origem_mapeamento import render_origem_mapeamento
from bling_app_zero.ui.preview_final import render_preview_final
from bling_app_zero.ui.app_helpers import (
    inicializar_debug,
    log_debug,
    render_debug_panel,
    safe_df_dados,
)
from bling_app_zero.utils.init_app import init_app_state

APP_VERSION = "3.0.0"
ETAPAS_VALIDAS = {"ia", "mapeamento", "final"}


# ============================================================
# CONFIG GERAL
# ============================================================

st.set_page_config(
    page_title="IA Planilhas → Bling",
    layout="wide",
)

init_app_state()
inicializar_debug()

if "app_version" not in st.session_state:
    st.session_state["app_version"] = APP_VERSION

if "modo_execucao" in st.session_state:
    st.session_state["modo_execucao"] = "ia_orquestrador"


# ============================================================
# HELPERS
# ============================================================

def _safe_str(valor) -> str:
    if valor is None:
        return ""
    texto = str(valor).strip()
    if texto.lower() in {"none", "nan", "nat"}:
        return ""
    return texto


def _contar_linhas_df(chave: str) -> int:
    df = st.session_state.get(chave)
    try:
        if safe_df_dados(df):
            return len(df)
    except Exception:
        pass
    return 0


def _normalizar_etapa(valor: str) -> str:
    etapa = _safe_str(valor).lower() or "ia"

    # compatibilidade com estados antigos do fluxo manual
    if etapa == "origem":
        return "ia"
    if etapa == "precificacao":
        return "ia"

    if etapa not in ETAPAS_VALIDAS:
        return "ia"
    return etapa


def _sincronizar_etapa(etapa: str) -> str:
    etapa_ok = _normalizar_etapa(etapa)
    st.session_state["etapa"] = etapa_ok
    st.session_state["etapa_origem"] = etapa_ok
    st.session_state["etapa_fluxo"] = etapa_ok
    return etapa_ok


def _obter_etapa() -> str:
    for chave in ["etapa", "etapa_origem", "etapa_fluxo"]:
        if chave in st.session_state:
            return _normalizar_etapa(st.session_state.get(chave))
    return "ia"


def _tem_base_origem() -> bool:
    return safe_df_dados(st.session_state.get("df_origem"))


def _tem_base_mapeada() -> bool:
    for chave in ["df_mapeado", "df_preview_mapeamento", "df_final", "df_saida"]:
        if safe_df_dados(st.session_state.get(chave)):
            return True
    return False


def _garantir_fluxo_valido() -> str:
    etapa = _obter_etapa()

    if etapa == "mapeamento" and not _tem_base_origem():
        log_debug("Sem base para mapeamento. Retornando para IA.", "WARNING")
        return _sincronizar_etapa("ia")

    if etapa == "final" and not _tem_base_mapeada():
        if _tem_base_origem():
            log_debug("Sem base final, mas com origem válida. Indo para mapeamento.", "WARNING")
            return _sincronizar_etapa("mapeamento")
        log_debug("Sem base para etapa final. Retornando para IA.", "WARNING")
        return _sincronizar_etapa("ia")

    return etapa


def _render_header() -> None:
    st.title("🚀 IA Planilhas → Bling")
    st.caption(f"Versão: {APP_VERSION}")

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Origem", _contar_linhas_df("df_origem"))
    with col2:
        st.metric("Precificado", _contar_linhas_df("df_precificado"))
    with col3:
        st.metric("Mapeado", _contar_linhas_df("df_mapeado"))
    with col4:
        st.metric("Final", _contar_linhas_df("df_final"))


def _render_topbar_fluxo() -> None:
    etapa_atual = _obter_etapa()

    st.markdown("### Fluxo novo com IA")

    col1, col2, col3 = st.columns(3)

    def _titulo(nome: str, label: str) -> str:
        return f"**{label}**" if etapa_atual == nome else label

    with col1:
        st.markdown(_titulo("ia", "1. IA Orquestrador"))
    with col2:
        st.markdown(_titulo("mapeamento", "2. Mapeamento"))
    with col3:
        st.markdown(_titulo("final", "3. Final"))


def _render_navegacao() -> None:
    etapa_atual = _obter_etapa()

    if etapa_atual == "ia":
        return

    if etapa_atual == "mapeamento":
        col1, col2 = st.columns(2)
        with col1:
            if st.button("⬅️ Voltar para IA", use_container_width=True, key="app_btn_voltar_ia"):
                _sincronizar_etapa("ia")
                st.rerun()
        with col2:
            if st.button("Ir para final ➜", use_container_width=True, key="app_btn_ir_final"):
                _sincronizar_etapa("final")
                st.rerun()
        return

    if etapa_atual == "final":
        col1, col2 = st.columns(2)
        with col1:
            if st.button("⬅️ Voltar para mapeamento", use_container_width=True, key="app_btn_voltar_mapeamento"):
                _sincronizar_etapa("mapeamento")
                st.rerun()
        with col2:
            if st.button("⬅️ Voltar para IA", use_container_width=True, key="app_btn_final_voltar_ia"):
                _sincronizar_etapa("ia")
                st.rerun()


def _render_etapa() -> None:
    etapa = _garantir_fluxo_valido()

    if etapa == "ia":
        render_ia_panel()
        return

    if etapa == "mapeamento":
        render_origem_mapeamento()
        return

    render_preview_final()


# ============================================================
# RENDER PRINCIPAL
# ============================================================

_sincronizar_etapa(_obter_etapa())
_render_header()
_render_topbar_fluxo()
_render_etapa()

st.markdown("---")
_render_navegacao()
render_debug_panel("🧠 Debug do sistema")


