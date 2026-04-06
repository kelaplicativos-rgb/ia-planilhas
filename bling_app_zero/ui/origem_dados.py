from __future__ import annotations

import streamlit as st

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


def _render_preview_compacto(df_origem) -> None:
    try:
        st.dataframe(
            df_origem.head(10),
            use_container_width=True,
            height=260,
        )
    except Exception as e:
        log_debug(f"Erro no preview compacto: {e}", "ERROR")
        st.dataframe(df_origem.head(10), use_container_width=True)


def _reset_fluxo_origem() -> None:
    for chave in [
        "df_origem",
        "etapa_origem",
        "mapeamento_origem",
        "mapeamento_origem_confirmado",
        "mapeamento_origem_hash",
    ]:
        if chave in st.session_state:
            del st.session_state[chave]


# ==========================================================
# MAIN UI
# ==========================================================
def render_origem_dados() -> None:
    st.subheader("Origem dos dados")

    origem = st.selectbox(
        "Selecione a origem",
        ["Planilha", "XML", "Site"],
        key="origem_tipo",
    )

    df_origem = None

    # =========================
    # PLANILHA
    # =========================
    if origem == "Planilha":
        arquivo = st.file_uploader(
            "Envie a planilha",
            type=["xlsx", "xls", "csv", "xlsm", "xlsb"],
            key="upload_planilha_origem",
        )

        if arquivo:
            log_debug("Iniciando leitura da planilha")
            df_origem = ler_planilha_segura(arquivo)

            if df_origem is None or df_origem.empty:
                log_debug("Erro planilha", "ERROR")
                st.error("Erro ao ler planilha")
                return

    # =========================
    # XML
    # =========================
    elif origem == "XML":
        st.warning("XML ainda em construção")
        return

    # =========================
    # SITE
    # =========================
    elif origem == "Site":
        try:
            df_origem = render_origem_site()
        except Exception as e:
            log_debug(f"Erro na origem por site: {e}", "ERROR")
            st.error("Erro ao buscar dados do site")
            return

    if df_origem is None or df_origem.empty:
        return

    # mantém compatibilidade com o resto do sistema
    st.session_state["df_origem"] = df_origem

    st.divider()
    st.subheader("Pré-visualização dos dados")

    try:
        _render_preview_compacto(df_origem)
        st.success(f"{len(df_origem)} registros carregados")
    except Exception as e:
        log_debug(f"Erro ao gerar preview: {e}", "ERROR")
        st.error("Erro ao gerar preview")
        return

    col1, col2 = st.columns(2)

    with col1:
        if st.button("➡️ Continuar para mapeamento", use_container_width=True, key="btn_continuar_mapeamento"):
            try:
                # libera o fluxo original do app.py
                st.session_state["df_final"] = df_origem.copy()
                st.session_state["etapa_origem"] = "mapeamento"
                log_debug("Fluxo liberado para mapeamento", "SUCCESS")
                st.rerun()
            except Exception as e:
                log_debug(f"Erro ao preparar mapeamento: {e}", "ERROR")
                st.error("Erro ao avançar para o mapeamento")

    with col2:
        if st.button("🧹 Limpar dados carregados", use_container_width=True, key="btn_limpar_origem"):
            _reset_fluxo_origem()
            log_debug("Fluxo de origem resetado", "INFO")
            st.rerun()
