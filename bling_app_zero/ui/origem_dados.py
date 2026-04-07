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


def _df_preview_seguro(df: pd.DataFrame | None) -> pd.DataFrame | None:
    try:
        if not safe_df_dados(df):
            return df

        df_preview = df.copy()

        for col in df_preview.columns:
            try:
                df_preview[col] = df_preview[col].apply(
                    lambda x: "" if pd.isna(x) else str(x)
                )
            except Exception:
                try:
                    df_preview[col] = df_preview[col].astype(str)
                except Exception:
                    pass

        return df_preview.replace(
            {"nan": "", "None": "", "<NA>": "", "NaT": ""}
        )
    except Exception:
        return df


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

    st.subheader("Origem dos dados")

    # =========================================================
    # 1) ORIGEM
    # =========================================================
    df_origem = render_origem_entrada(
        lambda origem: controlar_troca_origem(origem, log_debug)
    )

    if not safe_df_dados(df_origem):
        st.info("Selecione a origem e carregue os dados para continuar.")
        return

    sincronizar_estado_com_origem(df_origem, log_debug)

    with st.expander("Prévia da planilha do fornecedor", expanded=False):
        try:
            st.dataframe(df_origem.head(10), use_container_width=True)
        except Exception:
            pass

    # =========================================================
    # 2) OPERAÇÃO + MODELO (CORREÇÃO PRINCIPAL)
    # AGORA FICA LOGO ABAIXO DA ORIGEM
    # =========================================================
    st.markdown("### Tipo de envio")

    operacao = st.radio(
        "Selecione a operação",
        ["Cadastro de Produtos", "Atualização de Estoque"],
        key="tipo_operacao",
    )

    controlar_troca_operacao(operacao, log_debug)

    st.session_state["tipo_operacao_bling"] = (
        "cadastro" if operacao == "Cadastro de Produtos" else "estoque"
    )

    # MODELO VEM JUNTO (colado na operação)
    render_modelo_bling(operacao)

    # =========================================================
    # 3) PRECIFICAÇÃO
    # =========================================================
    render_precificacao(df_origem)

    df_saida = _sincronizar_df_saida_base(df_origem)

    # =========================================================
    # 4) ESTOQUE + DEPÓSITO
    # =========================================================
    origem_atual = _obter_origem_atual()
    tipo = st.session_state.get("tipo_operacao_bling")

    if tipo == "estoque":
        st.markdown("### Configurações de estoque")

        deposito = st.text_input(
            "Nome do depósito",
            value=st.session_state.get("deposito_nome", ""),
            key="deposito_nome",
        )

        if deposito:
            df_saida["Depósito"] = deposito

        if "site" in origem_atual:
            qtd = st.number_input(
                "Quantidade padrão (fallback)",
                min_value=0,
                value=st.session_state.get("quantidade_fallback", 0),
                step=1,
                key="quantidade_fallback",
            )

            df_saida["Quantidade"] = df_saida.get("Quantidade", pd.Series()).replace(
                "", qtd
            )

    st.session_state["df_saida"] = df_saida.copy()
    st.session_state["df_final"] = df_saida.copy()

    # =========================================================
    # 5) VALIDAÇÃO + AVANÇO
    # =========================================================
    modelo_ok = safe_df_dados(obter_modelo_ativo())

    if not modelo_ok:
        st.warning("Anexe o modelo do Bling antes de continuar.")

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
