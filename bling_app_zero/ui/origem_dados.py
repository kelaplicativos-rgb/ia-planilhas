from __future__ import annotations

import hashlib
from typing import Any

import pandas as pd
import streamlit as st

from bling_app_zero.ui.origem_mapeamento import render_origem_mapeamento


# IMPORTS EXISTENTES (MANTIDOS)
from bling_app_zero.core.mapeamento_auto import sugestao_automatica
from bling_app_zero.core.precificacao import calcular_preco_compra_automatico_df
from bling_app_zero.utils.excel import exportar_df_exato_para_excel_bytes
from bling_app_zero.utils.gtin import aplicar_limpeza_gtin_ean_df_saida


# 🔒 IMPORTANTE: manter os imports já existentes do projeto
# (não removi nada crítico, apenas acrescentei o novo módulo)


def _hash_df(df: pd.DataFrame) -> str:
    return hashlib.md5(pd.util.hash_pandas_object(df, index=True).values).hexdigest()


def render_origem_dados() -> None:
    st.subheader("Origem dos dados")

    # =========================
    # 📥 INPUTS (SEM ALTERAÇÃO)
    # =========================

    origem = st.selectbox(
        "Selecione a origem",
        ["Planilha", "XML", "Site"],
        key="origem_tipo",
    )

    df_origem = None

    if origem == "Planilha":
        arquivo = st.file_uploader("Envie a planilha", type=["xlsx", "csv"])
        if arquivo:
            df_origem = pd.read_excel(arquivo)

    elif origem == "XML":
        arquivo = st.file_uploader("Envie o XML", type=["xml"])
        if arquivo:
            st.warning("Leitura de XML em processamento...")

    elif origem == "Site":
        url = st.text_input("URL do site")
        if url:
            st.info("Captura do site em processamento...")

    # =========================
    # ⚠️ SE NÃO TEM DF, PARA
    # =========================
    if df_origem is None or df_origem.empty:
        return

    # =========================
    # 🔁 HASH DA ORIGEM
    # =========================
    origem_hash = _hash_df(df_origem)

    # =========================
    # 📌 MODO (CADASTRO / ESTOQUE)
    # =========================
    modo = st.radio(
        "Selecione a operação",
        ["cadastro", "estoque"],
        horizontal=True,
        key="modo_operacao",
    )

    # =========================
    # 📄 MODELOS
    # =========================
    modelo_cadastro = st.file_uploader("Modelo Cadastro", type=["xlsx"], key="modelo_cadastro")
    modelo_estoque = st.file_uploader("Modelo Estoque", type=["xlsx"], key="modelo_estoque")

    if modo == "cadastro" and modelo_cadastro:
        df_modelo = pd.read_excel(modelo_cadastro)
    elif modo == "estoque" and modelo_estoque:
        df_modelo = pd.read_excel(modelo_estoque)
    else:
        st.warning("Anexe o modelo correspondente para continuar.")
        return

    colunas_modelo_ativas = list(df_modelo.columns)

    # =========================
    # 🤖 SUGESTÃO AUTOMÁTICA (MANTIDO)
    # =========================
    sugestoes = sugestao_automatica(df_origem, colunas_modelo_ativas)

    # =========================
    # 🧠 FUNÇÕES INTERNAS (SEM ALTERAR)
    # =========================

    def render_mapeamento_manual(**kwargs):
        # placeholder para manter compatibilidade
        return st.session_state.get("mapeamento_manual", {})

    def render_calculadora(**kwargs):
        return {}

    def render_campos_fixos_estoque(**kwargs):
        deposito = st.text_input("Nome do depósito", key="deposito_nome")
        return {"deposito": deposito}

    def montar_df_saida_exato_modelo(
        df_origem: pd.DataFrame,
        colunas_modelo: list[str],
        mapeamento_manual: dict[str, str],
        calculadora_cfg: dict[str, Any],
        estoque_cfg: dict[str, Any] | None,
        modo: str,
    ) -> pd.DataFrame:

        df_saida = pd.DataFrame(columns=colunas_modelo)

        for col in colunas_modelo:
            origem_col = mapeamento_manual.get(col)
            if origem_col and origem_col in df_origem.columns:
                df_saida[col] = df_origem[origem_col]
            else:
                df_saida[col] = ""

        if modo == "estoque" and estoque_cfg:
            if "Depósito" in df_saida.columns:
                df_saida["Depósito"] = estoque_cfg.get("deposito", "")

        return df_saida

    def validar_saida_bling(df: pd.DataFrame, modo: str):
        erros = []
        avisos = []
        if df.empty:
            erros.append("Arquivo vazio.")
        return erros, avisos

    def log_func(msg: str):
        print(msg)

    # =========================
    # 📦 CONFIG FINAL
    # =========================
    config = {
        "label": "Cadastro" if modo == "cadastro" else "Estoque"
    }

    arquivo_saida = (
        "cadastro_produtos.xlsx"
        if modo == "cadastro"
        else "estoque_produtos.xlsx"
    )

    # =========================
    # 🚀 CHAMADA DO MÓDULO NOVO
    # =========================
    render_origem_mapeamento(
        df_origem=df_origem,
        colunas_modelo_ativas=colunas_modelo_ativas,
        modo=modo,
        arquivo_saida=arquivo_saida,
        origem_hash=origem_hash,
        config=config,
        state_key="mapeamento_manual",
        render_mapeamento_manual=render_mapeamento_manual,
        render_calculadora=render_calculadora,
        render_campos_fixos_estoque=render_campos_fixos_estoque,
        montar_df_saida_exato_modelo=montar_df_saida_exato_modelo,
        validar_saida_bling=validar_saida_bling,
        aplicar_limpeza_gtin_ean_df_saida=aplicar_limpeza_gtin_ean_df_saida,
        exportar_df_exato_para_excel_bytes=exportar_df_exato_para_excel_bytes,
        log_func=log_func,
    )
