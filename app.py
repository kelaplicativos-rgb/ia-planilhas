
from __future__ import annotations

import pandas as pd
import streamlit as st

from bling_app_zero.agent.agent_memory import get_agent_snapshot, get_agent_state
from bling_app_zero.ui.app_helpers import (
    inicializar_debug,
    render_debug_panel,
    safe_df_dados,
    sincronizar_etapa_global,
)
from bling_app_zero.ui.ia_panel import render_ia_panel
from bling_app_zero.ui.preview_final import render_preview_final
from bling_app_zero.utils.init_app import init_app_state

try:
    from bling_app_zero.ui.origem_mapeamento import render_origem_mapeamento
except Exception:
    render_origem_mapeamento = None

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
# HELPERS BASE
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
        if isinstance(df, pd.DataFrame):
            return len(df)
        if df is not None and hasattr(df, "__len__"):
            return len(df)
    except Exception:
        pass
    return 0


def _get_etapa_atual() -> str:
    state = get_agent_state()

    for valor in [
        st.session_state.get("etapa"),
        st.session_state.get("etapa_fluxo"),
        st.session_state.get("etapa_origem"),
        getattr(state, "etapa_atual", ""),
    ]:
        etapa = _safe_str(valor).lower()
        if etapa:
            return etapa

    return "ia_orquestrador"


def _tem_base_para_mapear() -> bool:
    for chave in [
        "df_mapeado",
        "df_precificado",
        "df_calc_precificado",
        "df_normalizado",
        "df_origem",
    ]:
        if safe_df_dados(st.session_state.get(chave)):
            return True
    return False


def _tem_base_final() -> bool:
    for chave in ["df_final", "df_saida"]:
        if safe_df_dados(st.session_state.get(chave)):
            return True
    return False


def _limpar_estado_fluxo_manual_legado() -> None:
    """
    Blindagem do app principal:
    - mantém o modo_execucao no fluxo novo
    - elimina desvios para telas antigas que não são mais rota principal
    - preserva apenas as etapas úteis do fluxo novo
    """
    st.session_state["modo_execucao"] = "ia_orquestrador"

    etapas_validas = {
        "ia_orquestrador",
        "mapeamento",
        "final",
        "validacao",
    }

    for chave in ["etapa", "etapa_origem", "etapa_fluxo"]:
        valor = _safe_str(st.session_state.get(chave)).lower()
        if valor and valor not in etapas_validas:
            st.session_state[chave] = "ia_orquestrador"

    state = get_agent_state()
    etapa_state = _safe_str(getattr(state, "etapa_atual", "")).lower()
    if etapa_state and etapa_state not in etapas_validas:
        state.etapa_atual = "ia_orquestrador"


def _sincronizar_com_agente() -> None:
    """
    Garante coerência entre sessão visual e estado do agente.
    """
    etapa = _get_etapa_atual()

    if etapa == "mapeamento" and not _tem_base_para_mapear():
        sincronizar_etapa_global("ia_orquestrador")
        return

    if etapa in {"final", "validacao"} and not (_tem_base_para_mapear() or _tem_base_final()):
        sincronizar_etapa_global("ia_orquestrador")
        return

    sincronizar_etapa_global(etapa)


# ============================================================
# HEADER / STATUS
# ============================================================

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


def _render_status_cards() -> None:
    etapa = _get_etapa_atual()
    state = get_agent_state()

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Etapa atual", etapa if etapa else "-")
    with col2:
        st.metric("Status do agente", _safe_str(getattr(state, "status_execucao", "")) or "-")
    with col3:
        st.metric("Operação", _safe_str(getattr(state, "operacao", "")) or "-")
    with col4:
        st.metric(
            "Simulação",
            "Aprovada" if bool(getattr(state, "simulacao_aprovada", False)) else "Pendente",
        )


def _render_resumo_agente() -> None:
    state = get_agent_state()
    snapshot = get_agent_snapshot()

    with st.expander("Estado do agente", expanded=False):
        col1, col2, col3, col4 = st.columns(4)

        with col1:
            st.metric("Etapa", _safe_str(getattr(state, "etapa_atual", "")) or "-")
        with col2:
            st.metric("Status", _safe_str(getattr(state, "status_execucao", "")) or "-")
        with col3:
            st.metric("Operação", _safe_str(getattr(state, "operacao", "")) or "-")
        with col4:
            st.metric(
                "Simulação",
                "Aprovada" if bool(getattr(state, "simulacao_aprovada", False)) else "Pendente",
            )

        erros = snapshot.get("erros") or []
        avisos = snapshot.get("avisos") or []
        pendencias = snapshot.get("pendencias") or []

        if erros:
            st.markdown("**Erros**")
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


# ============================================================
# NAVEGAÇÃO
# ============================================================

def _render_navegacao_fluxo() -> None:
    etapa = _get_etapa_atual()

    st.markdown("### Fluxo principal")
    st.success("Modo ativo: ETL completo + Bling output")

    col1, col2, col3 = st.columns(3)

    with col1:
        if st.button(
            "1. IA Orquestrador",
            use_container_width=True,
            type="primary" if etapa == "ia_orquestrador" else "secondary",
            key="nav_ia_orquestrador",
        ):
            sincronizar_etapa_global("ia_orquestrador")
            st.rerun()

    with col2:
        if st.button(
            "2. Mapeamento",
            use_container_width=True,
            type="primary" if etapa == "mapeamento" else "secondary",
            disabled=not _tem_base_para_mapear(),
            key="nav_mapeamento",
        ):
            sincronizar_etapa_global("mapeamento")
            st.rerun()

    with col3:
        if st.button(
            "3. Preview final",
            use_container_width=True,
            type="primary" if etapa in {"final", "validacao"} else "secondary",
            disabled=not (_tem_base_para_mapear() or _tem_base_final()),
            key="nav_preview_final",
        ):
            sincronizar_etapa_global("final")
            st.rerun()

    with st.expander("Etapas do fluxo", expanded=False):
        st.markdown("1. IA Orquestrador")
        st.markdown("2. Mapeamento")
        st.markdown("3. Preview final")
        st.caption(
            "O fluxo antigo não é mais rota principal. "
            "A IA deve ler a origem, transformar no modelo interno do Bling e só então liberar o preview final."
        )


def _render_etapa_atual() -> None:
    etapa = _get_etapa_atual()

    if etapa == "mapeamento":
        if render_origem_mapeamento is None:
            st.warning(
                "O módulo de mapeamento não está disponível neste ambiente. "
                "O fluxo continuará pelo orquestrador da IA."
            )
            render_ia_panel()
            return

        render_origem_mapeamento()
        return

    if etapa in {"final", "validacao"}:
        render_preview_final()
        return

    render_ia_panel()


# ============================================================
# RENDER PRINCIPAL
# ============================================================

st.session_state["app_version"] = APP_VERSION

_limpar_estado_fluxo_manual_legado()
_sincronizar_com_agente()

_render_header()
_render_status_cards()
_render_navegacao_fluxo()
_render_etapa_atual()
_render_resumo_agente()
render_debug_panel("🐞 Debug do sistema")


