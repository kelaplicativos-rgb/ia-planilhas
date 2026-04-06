from __future__ import annotations

import streamlit as st

from bling_app_zero.core.mapeamento_auto import sugestao_automatica
from bling_app_zero.ui.origem_dados_helpers import (
    log_debug,
    ler_planilha_segura,
)
from bling_app_zero.ui.origem_dados_site import render_origem_site


# ==========================================================
# HELPERS
# ==========================================================
def _obter_df_origem():
    df = st.session_state.get("df_origem")
    if df is None:
        return None
    try:
        if df.empty:
            return None
    except Exception:
        return None
    return df


def _obter_colunas_modelo_ativo(df_origem=None) -> list[str]:
    """
    🔥 AGORA COM FALLBACK INTELIGENTE
    """
    candidatos = [
        st.session_state.get("colunas_modelo_ativo"),
        st.session_state.get("colunas_modelo"),
        st.session_state.get("modelo_ativo_colunas"),
        st.session_state.get("colunas_bling_modelo"),
    ]

    for item in candidatos:
        if isinstance(item, list) and item:
            return [str(x) for x in item if str(x).strip()]

    dfs_candidatos = [
        st.session_state.get("df_modelo_ativo"),
        st.session_state.get("df_modelo_cadastro"),
        st.session_state.get("df_modelo_estoque"),
        st.session_state.get("modelo_ativo_df"),
    ]

    for df in dfs_candidatos:
        try:
            if df is not None and not df.empty:
                return [str(c) for c in df.columns]
        except Exception:
            continue

    # 🔥 FALLBACK FINAL — NÃO TRAVA MAIS
    if df_origem is not None:
        return list(df_origem.columns)

    return []


def _obter_mapeamento_inicial(df_origem, colunas_alvo: list[str]) -> dict[str, str]:
    mapeamento: dict[str, str] = {}

    if df_origem is None or df_origem.empty:
        return mapeamento

    if not colunas_alvo:
        return mapeamento

    try:
        sugestoes = sugestao_automatica(df_origem, colunas_alvo)

        if isinstance(sugestoes, dict):
            for k, v in sugestoes.items():
                if k and v:
                    if k in df_origem.columns:
                        mapeamento[k] = v

    except Exception as e:
        log_debug(f"Erro IA mapeamento: {e}", "WARNING")

    return mapeamento


def _render_preview_compacto(df_origem) -> None:
    st.dataframe(df_origem.head(10), use_container_width=True, height=260)


# ==========================================================
# MAPEAMENTO
# ==========================================================
def _render_mapeamento(df_origem) -> None:
    st.subheader("Mapeamento de colunas")

    colunas_alvo = _obter_colunas_modelo_ativo(df_origem)

    # 🔥 NÃO TRAVA MAIS
    if not colunas_alvo:
        st.warning("Modo automático ativado (sem modelo)")

    mapeamento = _obter_mapeamento_inicial(df_origem, colunas_alvo)

    st.markdown("### Preview")
    _render_preview_compacto(df_origem)

    st.markdown("### Mapeamento")

    resultado = {}

    for col in df_origem.columns:
        escolha = st.selectbox(
            f"{col}",
            [""] + colunas_alvo,
            key=f"map_{col}",
        )
        if escolha:
            resultado[col] = escolha

    st.session_state["mapeamento_origem"] = resultado

    if st.button("✅ Confirmar mapeamento", use_container_width=True):
        st.session_state["mapeamento_origem_confirmado"] = True

        # 🔥 CRIA DF FINAL AQUI
        st.session_state["df_final"] = df_origem.copy()

        st.success("Mapeamento confirmado")


# ==========================================================
# MAIN
# ==========================================================
def render_origem_dados() -> None:
    st.subheader("Origem dos dados")

    etapa = st.session_state.get("etapa_origem", "upload")

    # =========================
    # UPLOAD
    # =========================
    if etapa == "upload":

        origem = st.selectbox(
            "Selecione a origem",
            ["Planilha", "XML", "Site"],
        )

        df_origem = None

        if origem == "Planilha":
            arquivo = st.file_uploader(
                "Envie a planilha",
                type=["xlsx", "xls", "csv"],
            )

            if arquivo:
                df_origem = ler_planilha_segura(arquivo)

        elif origem == "Site":
            df_origem = render_origem_site()

        if df_origem is None or df_origem.empty:
            return

        st.session_state["df_origem"] = df_origem

        st.subheader("Pré-visualização")
        _render_preview_compacto(df_origem)

        if st.button("➡️ Continuar para mapeamento", use_container_width=True):

            # 🔥 ESSENCIAL
            st.session_state["df_final"] = df_origem.copy()

            st.session_state["etapa_origem"] = "mapeamento"
            st.rerun()

    # =========================
    # MAPEAMENTO
    # =========================
    elif etapa == "mapeamento":

        df_origem = _obter_df_origem()

        if df_origem is None:
            st.warning("Sem dados")
            return

        _render_mapeamento(df_origem)
