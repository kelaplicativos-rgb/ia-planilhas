
from __future__ import annotations

import streamlit as st

from bling_app_zero.agent.agent_memory import get_agent_snapshot, get_agent_state
from bling_app_zero.ui.app_helpers import in0o.ui.ia_panel import render_ia_panel
from bling_app_zero.utils.init_app import init_app_state

APP_VERSION = "2.2.0"


# ============================================================
# CONFIG GERAL
# ============================================================
st.set_page_config(
    page_title="IA Planilhas → Bling",
    layout="wide",
)

init_app_state()
inicializar_debug()


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


def _limpar_estado_fluxo_manual_legado() -> None:
    """
    Mantém o app travado no fluxo do agente, sem deixar chaves antigas
    reativarem o pipeline manual por engano.
    """
    st.session_state["modo_execucao"] = "ia_orquestrador"

    etapas_legadas = {"origem", "precificacao", "mapeamento", "final"}

    etapa = _safe_str(st.session_state.get("etapa"))
    etapa_origem = _safe_str(st.session_state.get("etapa_origem"))
    etapa_fluxo = _safe_str(st.session_state.get("etapa_fluxo"))

    if etapa in etapas_legadas:
        st.session_state["etapa"] = "ia_orquestrador"

    if etapa_origem in etapas_legadas:
        st.session_state["etapa_origem"] = "ia_orquestrador"

    if etapa_fluxo in etapas_legadas:
        st.session_state["etapa_fluxo"] = "ia_orquestrador"


def _render_header() -> None:
    st.title("🚀 IA Planilhas → Bling")
    st.caption(f"Versão: {APP_VERSION}")

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric("Origem", _contar_linhas_df("df_origem"))

    with col2:
        st.metric("Precisificado", _contar_linhas_df("df_precificado"))

    with col3:
        st.metric("Mapeado", _contar_linhas_df("df_mapeado"))

    with col4:
        st.metric("Final", _contar_linhas_df("df_final"))


def _render_resumo_agente() -> None:
    state = get_agent_state()
    snapshot = get_agent_snapshot()

    with st.expander("Estado do agente", expanded=False):
        col1, col2, col3, col4 = st.columns(4)

        with col1:
            st.metric("Etapa", _safe_str(state.etapa_atual) or "-")
        with col2:
            st.metric("Status", _safe_str(state.status_execucao) or "-")
        with col3:
            st.metric("Operação", _safe_str(state.operacao) or "-")
        with col4:
            st.metric("Simulação", "Aprovada" if state.simulacao_aprovada else "Pendente")

        erros = snapshot.get("erros") or []
        avisos = snapshot.get("avisos") or []
        pendencias = snapshot.get("pendencias") or []

        if erros:
            for erro in erros:
                st.error(erro)

        if avisos:
            st.markdown("**Avisos**")
            for aviso in avisos:
                st.warning(aviso)

        if pendencias:
            st.markdown("**Pendências**")
            for pendencia in pendencias:
                st.info(pendencia)


def _render_fluxo_principal() -> None:
    st.markdown("### Como deseja usar o sistema?")
    st.success("Fluxo principal unificado com IA ativo.")

    with st.expander("Etapas do fluxo", expanded=True):
        st.markdown("1. Origem")
        st.markdown("2. Precisão")
        st.markdown("3. Mapeamento")
        st.markdown("4. Final")

    render_ia_panel()
    _render_resumo_agente()


# ============================================================
# BLINDAGEM DE ESTADO
# ============================================================
st.session_state["app_version"] = APP_VERSION
_limpar_estado_fluxo_manual_legado()


# ============================================================
# RENDER PRINCIPAL
# ============================================================
_render_header()
_render_fluxo_principal()
render_debug_panel("🐞 Debug do sistema")

