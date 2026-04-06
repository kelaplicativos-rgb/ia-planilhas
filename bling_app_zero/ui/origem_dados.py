from __future__ import annotations

import streamlit as st

from bling_app_zero.ui.origem_dados_helpers import (
    log_debug,
    ler_planilha_segura,
)
from bling_app_zero.ui.origem_dados_site import render_origem_site


def _safe_df(df):
    try:
        if df is None or df.empty:
            return None
        return df
    except Exception:
        return None


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
            df_origem = ler_planilha_segura(arquivo)

            if _safe_df(df_origem) is None:
                st.error("Erro ao ler planilha")
                return

    elif origem == "XML":
        st.warning("XML ainda em construção")
        return

    elif origem == "Site":
        try:
            df_origem = render_origem_site()
        except Exception:
            st.error("Erro ao buscar dados do site")
            return

    if _safe_df(df_origem) is None:
        return

    # 🔥 PADRÃO REAL DO SISTEMA
    st.session_state["df_origem"] = df_origem

    # ==========================================================
    # PREVIEW
    # ==========================================================
    st.divider()
    st.subheader("Pré-visualização dos dados")

    st.dataframe(df_origem.head(10), use_container_width=True)
    st.success(f"{len(df_origem)} registros carregados")

    # ==========================================================
    # 🔥 RESTAURA FLUXO ORIGINAL
    # ==========================================================
    st.divider()
    st.subheader("Selecione a operação")

    valor_atual = st.session_state.get("tipo_operacao_bling", "cadastro")

    opcoes = {
        "Cadastro / atualização de produtos": "cadastro",
        "Atualização de estoque": "estoque",
    }

    labels = list(opcoes.keys())
    indice = 0 if valor_atual != "estoque" else 1

    escolha_label = st.radio(
        "O que será feito?",
        options=labels,
        index=indice,
        key="radio_operacao_bling",
    )

    escolha_valor = opcoes[escolha_label]

    # 🔥 PADRÃO DO STATE.PY
    st.session_state["tipo_operacao_bling"] = escolha_valor

    if escolha_valor == "cadastro":
        st.info("Modo: Cadastro de produtos")
    else:
        st.info("Modo: Atualização de estoque")

    # ==========================================================
    # BOTÃO CONTINUAR (CORRIGIDO)
    # ==========================================================
    if st.button("➡️ Continuar para mapeamento", use_container_width=True):
        try:
            # 🔥 IMPORTANTE: usar df_saida (não df_final)
            st.session_state["df_saida"] = df_origem.copy()

            # 🔥 AQUI ESTÁ O PONTO QUE FALTAVA
            st.session_state["etapa_origem"] = "mapeamento"

            st.rerun()

        except Exception as e:
            log_debug(f"Erro ao ir para mapeamento: {e}", "ERROR")
            st.error("Erro ao avançar")
