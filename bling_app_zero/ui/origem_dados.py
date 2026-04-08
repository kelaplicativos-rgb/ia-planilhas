from __future__ import annotations

import pandas as pd
import streamlit as st

from bling_app_zero.ui.app_helpers import log_debug
from bling_app_zero.ui.origem_dados_estado import (
    controlar_troca_operacao,
    controlar_troca_origem,
    safe_df_dados,
    sincronizar_estado_com_origem,
)
from bling_app_zero.ui.origem_dados_precificacao import render_precificacao
from bling_app_zero.ui.origem_dados_uploads import (
    render_modelo_bling,
    render_origem_entrada,
)
from bling_app_zero.ui.origem_dados_validacao import (
    obter_modelo_ativo,
    validar_antes_mapeamento,
)


def _obter_origem_atual() -> str:
    try:
        for key in ["origem_dados", "origem_selecionada", "tipo_origem", "origem"]:
            val = str(st.session_state.get(key) or "").strip().lower()
            if val:
                return val
        return ""
    except Exception:
        return ""


def _sincronizar_df_saida_base(df_origem: pd.DataFrame) -> pd.DataFrame:
    try:
        df_saida = st.session_state.get("df_saida")

        if not safe_df_dados(df_saida):
            df_saida = df_origem.copy()
            st.session_state["df_saida"] = df_saida.copy()

        st.session_state["df_final"] = df_saida.copy()
        return df_saida
    except Exception:
        df_saida = df_origem.copy()
        st.session_state["df_saida"] = df_saida.copy()
        st.session_state["df_final"] = df_saida.copy()
        return df_saida


def render_origem_dados() -> None:
    etapa = st.session_state.get("etapa_origem")
    if etapa in ["mapeamento", "final"]:
        return

    st.subheader("📦 Origem dos dados")

    # =========================================================
    # 1) ORIGEM
    # =========================================================
    df_origem = render_origem_entrada(
        lambda origem: controlar_troca_origem(origem, log_debug)
    )

    origem_atual = _obter_origem_atual()

    # 🔒 TRAVA PARA SITE
    if "site" in origem_atual:
        if not st.session_state.get("site_processado"):
            st.info("🔎 Execute a busca do site para continuar.")
            return

    if not safe_df_dados(df_origem):
        st.info("Selecione a origem e carregue os dados para continuar.")
        return

    sincronizar_estado_com_origem(df_origem, log_debug)

    # =========================================================
    # PREVIEW COMPACTA
    # =========================================================
    if "site" not in origem_atual:
        with st.expander("👁 Prévia do fornecedor", expanded=False):
            try:
                st.dataframe(df_origem.head(5), use_container_width=True)
            except Exception:
                pass

    # =========================================================
    # 2 + 3) OPERAÇÃO + MODELO (LADO A LADO)
    # =========================================================
    col1, col2 = st.columns(2)

    with col1:
        st.markdown("### Tipo de envio")

        operacao = st.radio(
            "Selecione",
            ["Cadastro de Produtos", "Atualização de Estoque"],
            key="tipo_operacao",
            label_visibility="collapsed",
        )

        controlar_troca_operacao(operacao, log_debug)

        st.session_state["tipo_operacao_bling"] = (
            "cadastro" if operacao == "Cadastro de Produtos" else "estoque"
        )

    with col2:
        st.markdown("### Modelo Bling")
        render_modelo_bling(operacao)

    df_saida = _sincronizar_df_saida_base(df_origem)

    # =========================================================
    # 4) DEPÓSITO (SÓ ESTOQUE)
    # =========================================================
    if st.session_state["tipo_operacao_bling"] == "estoque":
        st.markdown("### 🏬 Estoque")

        col1, col2 = st.columns(2)

        with col1:
            deposito = st.text_input(
                "Depósito",
                value=st.session_state.get("deposito_nome", ""),
                key="deposito_nome",
            )

            if deposito:
                df_saida["Depósito"] = deposito

        with col2:
            if "site" in origem_atual:
                qtd = st.number_input(
                    "Qtd padrão",
                    min_value=0,
                    value=st.session_state.get("quantidade_fallback", 0),
                    step=1,
                    key="quantidade_fallback",
                )

                df_saida["Quantidade"] = df_saida.get(
                    "Quantidade", pd.Series()
                ).replace("", qtd)

    # =========================================================
    # 5) PRECIFICAÇÃO (MANTIDO NO LUGAR CORRETO)
    # =========================================================
    st.markdown("### 💰 Precificação")
    render_precificacao(df_origem)

    st.session_state["df_saida"] = df_saida.copy()
    st.session_state["df_final"] = df_saida.copy()

    # =========================================================
    # 6) VALIDAÇÃO + AVANÇO
    # =========================================================
    modelo_ok = safe_df_dados(obter_modelo_ativo())

    if not modelo_ok:
        st.warning("⚠️ Anexe o modelo do Bling antes de continuar.")

    st.markdown("---")

    if st.button(
        "➡️ Continuar para mapeamento",
        use_container_width=True,
        disabled=not modelo_ok,
    ):
        valido, erros = validar_antes_mapeamento()

        if not valido:
            for e in erros:
                st.warning(e)
            return

        st.session_state["etapa_origem"] = "mapeamento"
        st.rerun()
