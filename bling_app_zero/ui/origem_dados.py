from __future__ import annotations

import streamlit as st

from bling_app_zero.ui.origem_dados_helpers import (
    log_debug,
    ler_planilha_segura,
)
from bling_app_zero.ui.origem_dados_site import render_origem_site


def _safe_df_dados(df):
    try:
        if df is None:
            return None
        if len(df.columns) == 0:
            return None
        if df.empty:
            return None
        return df
    except Exception:
        return None


def _safe_df_modelo(df):
    try:
        if df is None:
            return None
        if len(df.columns) == 0:
            return None
        return df
    except Exception:
        return None


def _normalizar_texto(valor: str) -> str:
    try:
        return str(valor or "").strip().lower()
    except Exception:
        return ""


def _detectar_coluna_deposito(df):
    try:
        if df is None or len(df.columns) == 0:
            return None

        candidatos_exatos = {
            "depósito",
            "deposito",
            "nome do depósito",
            "nome do deposito",
            "depósito padrão",
            "deposito padrao",
            "depósito padrão",
            "depósito estoque",
            "deposito estoque",
        }

        for col in df.columns:
            nome = _normalizar_texto(col)
            if nome in candidatos_exatos:
                return col

        for col in df.columns:
            nome = _normalizar_texto(col)
            if "deposit" in nome or "depós" in nome:
                return col

        return None
    except Exception:
        return None


def _aplicar_deposito_manual(df, deposito_nome):
    try:
        if df is None:
            return df

        deposito_nome = str(deposito_nome or "").strip()
        if not deposito_nome:
            return df

        df_saida = df.copy()

        coluna_deposito = _detectar_coluna_deposito(df_saida)
        if coluna_deposito:
            df_saida[coluna_deposito] = deposito_nome
        else:
            # cria uma coluna padrão já pronta para o fluxo seguinte
            df_saida["Depósito"] = deposito_nome

        return df_saida
    except Exception as e:
        log_debug(f"Erro ao aplicar depósito manual: {e}")
        return df


def _obter_df_modelo_ativo(tipo: str):
    if tipo == "cadastro":
        return st.session_state.get("df_modelo_cadastro")
    return st.session_state.get("df_modelo_estoque")


def render_origem_dados() -> None:
    if st.session_state.get("etapa_origem") == "mapeamento":
        return

    st.subheader("Origem dos dados")

    origem = st.selectbox(
        "Selecione a origem",
        ["Planilha", "XML", "Site"],
        key="origem_tipo",
    )

    df_origem = None

    if origem == "Planilha":
        arquivo = st.file_uploader(
            "Envie a planilha",
            type=["xlsx", "xls", "csv", "xlsm", "xlsb"],
            key="upload_planilha_origem",
        )

        if arquivo:
            try:
                df_origem = ler_planilha_segura(arquivo)
            except Exception as e:
                log_debug(f"Erro ao ler planilha de origem: {e}")
                st.error("Erro ao ler planilha.")
                return

            if _safe_df_dados(df_origem) is None:
                st.error("Erro ao ler planilha.")
                return

    elif origem == "XML":
        st.info("Envio por XML ainda depende do fluxo complementar do projeto.")
        return

    elif origem == "Site":
        try:
            df_origem = render_origem_site()
        except Exception as e:
            log_debug(f"Erro em render_origem_site: {e}")
            st.error("Erro ao buscar dados do site.")
            return

    if _safe_df_dados(df_origem) is None:
        return

    st.session_state["df_origem"] = df_origem

    with st.expander("👁️ Pré-visualização dos dados", expanded=False):
        try:
            st.dataframe(df_origem.head(10), width="stretch")
        except Exception:
            st.dataframe(df_origem.head(10))

    op = st.radio(
        "Operação",
        ["Cadastro", "Estoque"],
        horizontal=True,
        key="operacao_origem_dados",
    )

    tipo = "cadastro" if op == "Cadastro" else "estoque"
    st.session_state["tipo_operacao_bling"] = tipo

    modelo_valido = None
    deposito_nome = ""

    if tipo == "cadastro":
        modelo = st.file_uploader(
            "Modelo Cadastro",
            type=["xlsx", "xls", "csv", "xlsm", "xlsb"],
            key="modelo_cadastro",
        )

        if modelo:
            try:
                df_modelo = ler_planilha_segura(modelo)
                if _safe_df_modelo(df_modelo) is None:
                    st.error("Modelo de cadastro inválido.")
                    return
                st.session_state["df_modelo_cadastro"] = df_modelo
            except Exception as e:
                log_debug(f"Erro ao ler modelo de cadastro: {e}")
                st.error("Erro ao ler modelo de cadastro.")
                return

        modelo_valido = _safe_df_modelo(_obter_df_modelo_ativo("cadastro"))

    else:
        modelo = st.file_uploader(
            "Modelo Estoque",
            type=["xlsx", "xls", "csv", "xlsm", "xlsb"],
            key="modelo_estoque",
        )

        if modelo:
            try:
                df_modelo = ler_planilha_segura(modelo)
                if _safe_df_modelo(df_modelo) is None:
                    st.error("Modelo de estoque inválido.")
                    return
                st.session_state["df_modelo_estoque"] = df_modelo
            except Exception as e:
                log_debug(f"Erro ao ler modelo de estoque: {e}")
                st.error("Erro ao ler modelo de estoque.")
                return

        deposito_nome = st.text_input(
            "Nome do depósito",
            key="deposito_nome_manual",
            placeholder="Ex.: ifood",
        ).strip()

        st.session_state["deposito_nome_manual"] = deposito_nome
        modelo_valido = _safe_df_modelo(_obter_df_modelo_ativo("estoque"))

    pode_avancar = _safe_df_dados(df_origem) is not None and modelo_valido is not None

    if tipo == "estoque" and pode_avancar and not deposito_nome:
        st.warning("Informe o nome do depósito para continuar no fluxo de estoque.")
        return

    if pode_avancar:
        try:
            df_saida = df_origem.copy()

            if tipo == "estoque":
                df_saida = _aplicar_deposito_manual(df_saida, deposito_nome)

            st.session_state["df_saida"] = df_saida
            st.session_state["etapa_origem"] = "mapeamento"

            log_debug(
                f"Fluxo origem -> mapeamento | origem={origem} | tipo={tipo} | "
                f"linhas={len(df_saida)} | colunas={len(df_saida.columns)}"
            )

            st.rerun()

        except Exception as e:
            log_debug(f"Erro ao preparar df_saida para mapeamento: {e}")
            st.error("Erro ao preparar os dados para o mapeamento.")
            return
