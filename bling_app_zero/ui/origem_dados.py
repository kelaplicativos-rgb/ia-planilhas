from __future__ import annotations

import streamlit as st

from bling_app_zero.core.mapeamento_auto import sugestao_automatica

from bling_app_zero.ui.origem_dados_helpers import (
    log_debug,
    ler_planilha_segura,
)

from bling_app_zero.ui.origem_dados_site import render_origem_site


# ==========================================================
# MAIN UI
# ==========================================================
def render_origem_dados() -> None:
    st.subheader("Origem dos dados")

    # 🔥 CONTROLE DE ETAPA
    etapa = st.session_state.get("etapa_origem", "upload")

    # ==========================================================
    # ETAPA: UPLOAD
    # ==========================================================
    if etapa == "upload":

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
            df_origem = render_origem_site()

        if df_origem is None or df_origem.empty:
            return

        # mantém compatibilidade com o resto do sistema
        st.session_state["df_origem"] = df_origem

        # ==========================================================
        # PREVIEW
        # ==========================================================
        st.divider()

        st.subheader("Pré-visualização dos dados")

        try:
            st.dataframe(
                df_origem.head(10),
                use_container_width=True
            )

            st.success(f"{len(df_origem)} registros carregados")

        except Exception:
            st.error("Erro ao gerar preview")

        # ==========================================================
        # BOTÃO PRÓXIMA ETAPA
        # ==========================================================
        if st.button("➡️ Continuar para mapeamento", use_container_width=True):
            st.session_state["etapa_origem"] = "mapeamento"
            st.rerun()

    # ==========================================================
    # ETAPA: MAPEAMENTO
    # ==========================================================
    elif etapa == "mapeamento":

        st.subheader("Mapeamento de colunas")

        df = st.session_state.get("df_origem")

        if df is None or df.empty:
            st.warning("Nenhum dado encontrado")
            return

        st.success("Você está na etapa de mapeamento")

        # 🔥 AQUI VAI ENTRAR SEU SISTEMA DE MAPEAMENTO REAL
        st.dataframe(df.head(5), use_container_width=True)

        # BOTÃO VOLTAR (IMPORTANTE)
        if st.button("⬅️ Voltar"):
            st.session_state["etapa_origem"] = "upload"
            st.rerun()
