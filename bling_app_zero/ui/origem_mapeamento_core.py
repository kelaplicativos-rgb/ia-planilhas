from __future__ import annotations

import pandas as pd
import streamlit as st

from bling_app_zero.ui.origem_mapeamento_validacao import (
    is_coluna_deposito,
    is_coluna_id,
    is_coluna_imagem,
    normalizar_coluna,
    safe_df,
    safe_df_com_linhas,
    safe_str,
)


def sanitizar_valor(valor):
    try:
        if valor is None:
            return ""
        if pd.isna(valor):
            return ""
    except Exception:
        pass
    return valor


def normalizar_situacao(valor) -> str:
    texto = safe_str(valor).lower()
    if not texto:
        return "Ativo"
    if texto in {"inativo", "inactive", "0"}:
        return "Ativo"
    return "Ativo"


def normalizar_urls_imagem(valor) -> str:
    texto = safe_str(valor)
    if not texto:
        return ""

    texto = texto.replace("\n", "|").replace(";", "|").replace(",", "|")
    partes = [p.strip() for p in texto.split("|") if p.strip()]

    unicos: list[str] = []
    vistos: set[str] = set()

    for item in partes:
        if item not in vistos:
            vistos.add(item)
            unicos.append(item)

    return "|".join(unicos)


def obter_df_fonte_mapeamento():
    candidatos = [
        st.session_state.get("df_precificado"),
        st.session_state.get("df_calc_precificado"),
        st.session_state.get("df_origem"),
    ]

    for df in candidatos:
        if safe_df_com_linhas(df):
            return df

    return None


def obter_df_modelo_mapeamento():
    candidatos = [
        st.session_state.get("df_modelo_mapeamento"),
        st.session_state.get("df_modelo_cadastro"),
        st.session_state.get("df_modelo_estoque"),
        st.session_state.get("df_saida"),
        st.session_state.get("df_final"),
    ]

    for df in candidatos:
        if safe_df(df):
            return df

    return None


def inferir_coluna_preco(df_fonte: pd.DataFrame) -> str:
    for col in df_fonte.columns:
        nome = normalizar_coluna(col)
        if "preco" in nome or "preço" in str(col).lower():
            return str(col)
    return ""


def aplicar_mapeamento_automatico_preco(mapping: dict, df_modelo: pd.DataFrame, df_fonte: pd.DataFrame) -> dict:
    try:
        coluna_preco = safe_str(st.session_state.get("coluna_precificacao_resultado"))

        if not coluna_preco:
            coluna_preco = inferir_coluna_preco(df_fonte)

        if not coluna_preco or coluna_preco not in df_fonte.columns:
            return dict(mapping)

        mapping_out = dict(mapping)

        for col_modelo in df_modelo.columns:
            nome = normalizar_coluna(col_modelo)
            if "preco de venda" in nome or "preco unitario" in nome:
                mapping_out[col_modelo] = coluna_preco

        return mapping_out
    except Exception:
        return dict(mapping)


def montar_df_saida_mapeado(df_fonte: pd.DataFrame, df_modelo: pd.DataFrame, mapping: dict) -> pd.DataFrame:
    df_saida_base = st.session_state.get("df_saida")

    if isinstance(df_saida_base, pd.DataFrame) and len(df_saida_base) == len(df_fonte):
        df_saida = df_saida_base.copy()
    else:
        df_saida = pd.DataFrame(index=range(len(df_fonte)))

    deposito = str(st.session_state.get("deposito_nome", "") or "").strip()

    for col in df_modelo.columns:
        if is_coluna_id(col):
            df_saida[col] = ""
            continue

        if is_coluna_deposito(col):
            df_saida[col] = deposito
            continue

        origem = str(mapping.get(col, "") or "").strip()

        if origem and origem in df_fonte.columns:
            serie = df_fonte[origem].reset_index(drop=True)
            serie = serie.apply(sanitizar_valor)

            if is_coluna_imagem(col):
                serie = serie.apply(normalizar_urls_imagem)

            df_saida[col] = serie
        else:
            if col not in df_saida.columns:
                df_saida[col] = ""
            else:
                df_saida[col] = df_saida[col].fillna("")

        if "situa" in str(col).lower():
            df_saida[col] = df_saida[col].apply(normalizar_situacao)

    return df_saida
