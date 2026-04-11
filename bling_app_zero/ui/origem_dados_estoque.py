from __future__ import annotations

import pandas as pd
import streamlit as st

from bling_app_zero.ui.app_helpers import log_debug


def _normalizar_texto(valor) -> str:
    try:
        if valor is None:
            return ""
        return str(valor).strip().lower()
    except Exception:
        return ""


def _normalizar_quantidade(valor, fallback: int) -> int:
    try:
        texto = str(valor or "").strip().lower()

        if texto in {"", "nan", "none"}:
            return int(fallback)

        if texto in {"sem estoque", "indisponível", "indisponivel", "zerado"}:
            return 0

        numero = int(float(str(valor).replace(",", ".")))
        return max(numero, 0)
    except Exception:
        return int(fallback)


def garantir_coluna(df: pd.DataFrame, nome: str, valor_padrao="") -> pd.DataFrame:
    try:
        if not isinstance(df, pd.DataFrame):
            return df

        if nome not in df.columns:
            df[nome] = valor_padrao

        return df
    except Exception:
        return df


def obter_colunas_estoque(df: pd.DataFrame) -> list[str]:
    try:
        if not isinstance(df, pd.DataFrame) or len(df.columns) == 0:
            return []

        candidatos = []
        aliases = [
            "quantidade",
            "qtd",
            "estoque",
            "saldo",
            "saldo estoque",
            "saldo em estoque",
            "estoque atual",
        ]

        for col in df.columns:
            nome = _normalizar_texto(col)
            if any(alias in nome for alias in aliases):
                candidatos.append(col)

        vistos = set()
        saida = []
        for col in candidatos:
            if col not in vistos:
                vistos.add(col)
                saida.append(col)

        return saida
    except Exception:
        return []


def aplicar_quantidade_em_df(
    df: pd.DataFrame | None,
    quantidade: int,
    origem_atual: str,
) -> pd.DataFrame | None:
    try:
        if not isinstance(df, pd.DataFrame):
            return df

        out = df.copy()
        colunas_estoque = obter_colunas_estoque(out)

        if not colunas_estoque:
            out = garantir_coluna(out, "Quantidade", quantidade)
            colunas_estoque = ["Quantidade"]

        for col in colunas_estoque:
            out[col] = out[col].apply(
                lambda v: _normalizar_quantidade(v, quantidade)
            )

        return out
    except Exception:
        return df


def persistir_estoque_em_todas_etapas(origem_atual: str) -> None:
    try:
        if str(st.session_state.get("tipo_operacao_bling") or "").strip().lower() != "estoque":
            return

        quantidade = int(st.session_state.get("quantidade_fallback", 0) or 0)

        chaves_df = [
            "df_origem",
            "df_saida",
            "df_final",
            "df_precificado",
            "df_calc_precificado",
            "df_xml_mapeado_modelo",
        ]

        for chave in chaves_df:
            df_ref = st.session_state.get(chave)
            if isinstance(df_ref, pd.DataFrame):
                st.session_state[chave] = aplicar_quantidade_em_df(
                    df_ref,
                    quantidade=quantidade,
                    origem_atual=origem_atual,
                )

        log_debug(
            f"[ESTOQUE] quantidade manual persistida em todas as etapas: {quantidade}",
            "INFO",
        )
    except Exception as e:
        log_debug(f"[ESTOQUE] erro ao persistir quantidade global: {e}", "ERROR")


def aplicar_bloco_estoque(df_saida: pd.DataFrame, origem_atual: str) -> pd.DataFrame:
    try:
        df_saida = df_saida.copy()

        st.markdown("### Dados de estoque")

        deposito = st.text_input(
            "Nome do depósito",
            value=str(st.session_state.get("deposito_nome", "") or ""),
            key="deposito_nome",
            placeholder="Ex.: ifood",
        )

        qtd = st.number_input(
            "Quantidade padrão",
            min_value=0,
            value=int(st.session_state.get("quantidade_fallback", 0) or 0),
            step=1,
            key="quantidade_fallback",
            help="Usado como fallback quando não houver quantidade válida.",
        )

        st.session_state["quantidade_fallback"] = int(qtd)

        if deposito:
            for nome_col in ["Depósito", "deposito", "Depósito padrão"]:
                if nome_col in df_saida.columns:
                    df_saida[nome_col] = deposito

            if "Depósito" not in df_saida.columns:
                df_saida = garantir_coluna(df_saida, "Depósito", deposito)
                df_saida["Depósito"] = deposito

        df_saida = aplicar_quantidade_em_df(
            df_saida,
            quantidade=int(qtd),
            origem_atual=origem_atual,
        )

        return df_saida

    except Exception as e:
        log_debug(f"[ORIGEM_DADOS_ESTOQUE] erro bloco estoque: {e}", "ERROR")
        return df_saida
