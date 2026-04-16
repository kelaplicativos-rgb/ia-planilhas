
from __future__ import annotations

import streamlit as st

from bling_app_zero.ui.origem_dados import render_origem_dados
from bling_app_zero.ui.origem_precificacao import render_origem_precificacao
from bling_app_zero.ui.origem_mapeamento import render_origem_mapeamento
from bling_app_zero.ui.preview_final import render_preview_final
from bling_app_zero.ui.ia_panel import render_ia_panel
from bling_app_zero.ui.app_helpers import (
    inicializar_debug,
    log_debug,
    render_debug_panel,
)
from bling_app_zero.utils.init_app import init_app_state

APP_VERSION = "2.1.0"


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
        if df is not None and hasattr(df, "__len__"):
            return len(df)
    except Exception:
        pass
    return 0


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


def _render_menu_superior() -> None:
    modo_atual = _safe_str(st.session_state.get("modo_execucao") or "fluxo_manual")

    st.markdown("### Como deseja usar o sistema?")
    col1, col2 = st.columns(2)

    with col1:
        if st.button(
            "Fluxo Manual",
            use_container_width=True,
            type="primary" if modo_atual == "fluxo_manual" else "secondary",
            key="btn_modo_fluxo_manual",
        ):
            st.session_state["modo_execucao"] = "fluxo_manual"
            log_debug("Modo alterado para fluxo manual", "INFO")
            st.rerun()

    with col2:
        if st.button(
            "Executar com IA",
            use_container_width=True,
            type="primary" if modo_atual == "ia_orquestrador" else "secondary",
            key="btn_modo_ia_orquestrador",
        ):
            st.session_state["modo_execucao"] = "ia_orquestrador"
            log_debug("Modo alterado para IA Orquestrador", "INFO")
            st.rerun()


def _render_etapas_fluxo() -> None:
    etapa = _safe_str(st.session_state.get("etapa") or "origem")

    st.markdown("### Etapas do fluxo")
    col1, col2, col3, col4 = st.columns(4)

    def _etapa_label(nome: str, titulo: str) -> str:
        return f"**{titulo}**" if etapa == nome else titulo

    with col1:
        st.markdown(_etapa_label("origem", "1. Origem"))
    with col2:
        st.markdown(_etapa_label("precificacao", "2. Precificação"))
    with col3:
        st.markdown(_etapa_label("mapeamento", "3. Mapeamento"))
    with col4:
        st.markdown(_etapa_label("final", "4. Final"))


def _render_fluxo_manual() -> None:
    _render_etapas_fluxo()

    etapa = _safe_str(st.session_state.get("etapa") or "origem")

    if etapa == "origem":
        render_origem_dados()
        return

    if etapa == "precificacao":
        render_origem_precificacao()
        return

    if etapa == "mapeamento":
        render_origem_mapeamento()
        return

    if etapa == "final":
        render_preview_final()
        return

    st.warning("Etapa inválida. O fluxo foi retornado para a origem.")
    st.session_state["etapa"] = "origem"
    st.session_state["etapa_origem"] = "origem"


def _render_modo_ia() -> None:
    render_ia_panel()

    if _contar_linhas_df("df_origem") > 0:
        st.markdown("---")
        st.info(
            "A base foi preparada pela IA. Revise o mapeamento e conclua no fluxo principal."
        )

        col1, col2 = st.columns(2)
        with col1:
            if st.button(
                "Ir para mapeamento",
                use_container_width=True,
                key="btn_ir_mapeamento_pos_ia",
            ):
                st.session_state["etapa"] = "mapeamento"
                st.session_state["etapa_origem"] = "mapeamento"
                st.rerun()

        with col2:
            if st.button(
                "Ir para preview final",
                use_container_width=True,
                key="btn_ir_preview_final_pos_ia",
            ):
                st.session_state["etapa"] = "final"
                st.session_state["etapa_origem"] = "final"
                st.rerun()


# ============================================================
# RENDER PRINCIPAL
# ============================================================

_render_header()
_render_menu_superior()

modo_execucao = _safe_str(st.session_state.get("modo_execucao") or "fluxo_manual")

if modo_execucao == "ia_orquestrador":
    _render_modo_ia()
else:
    _render_fluxo_manual()

render_debug_panel("🧠 Debug do sistema")
