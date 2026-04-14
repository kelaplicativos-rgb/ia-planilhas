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
    texto = safe_str(valor).strip().lower()

    if not texto:
        return "Ativo"

    mapa_inativo_para_ativo = {
        "inativo",
        "inactive",
        "0",
        "false",
        "nao",
        "não",
    }

    if texto in mapa_inativo_para_ativo:
        return "Ativo"

    if texto in {"ativo", "active", "1", "true", "sim", "yes"}:
        return "Ativo"

    return "Ativo"


def normalizar_urls_imagem(valor) -> str:
    texto = safe_str(valor)
    if not texto:
        return ""

    texto = (
        texto.replace("\n", "|")
        .replace("\r", "|")
        .replace(";", "|")
        .replace(",", "|")
    )

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

        if (
            "preco" in nome
            or "preço" in str(col).lower()
            or "valor" in nome
            or "custo" in nome
        ):
            return str(col)

    return ""


def _coluna_preco_destino(col_modelo: str) -> bool:
    nome = normalizar_coluna(col_modelo)
    return "preco de venda" in nome or "preco unitario" in nome


def aplicar_mapeamento_automatico_preco(
    mapping: dict,
    df_modelo: pd.DataFrame,
    df_fonte: pd.DataFrame,
) -> dict:
    try:
        mapping_out = dict(mapping or {})

        coluna_preco = safe_str(st.session_state.get("coluna_precificacao_resultado"))
        if not coluna_preco:
            coluna_preco = inferir_coluna_preco(df_fonte)

        if not coluna_preco or coluna_preco not in df_fonte.columns:
            return mapping_out

        for col_modelo in df_modelo.columns:
            if not _coluna_preco_destino(str(col_modelo)):
                continue

            valor_atual = safe_str(mapping_out.get(col_modelo))
            if valor_atual and valor_atual in df_fonte.columns:
                continue

            mapping_out[col_modelo] = coluna_preco

        return mapping_out

    except Exception:
        return dict(mapping or {})


def _nova_base_saida(df_fonte: pd.DataFrame, df_modelo: pd.DataFrame) -> pd.DataFrame:
    colunas_modelo = [str(col) for col in df_modelo.columns]
    return pd.DataFrame("", index=range(len(df_fonte)), columns=colunas_modelo)


def _reaproveitar_base_saida_se_compativel(
    df_fonte: pd.DataFrame,
    df_modelo: pd.DataFrame,
) -> pd.DataFrame:
    df_saida_base = st.session_state.get("df_saida")

    if not isinstance(df_saida_base, pd.DataFrame):
        return _nova_base_saida(df_fonte, df_modelo)

    if len(df_saida_base) != len(df_fonte):
        return _nova_base_saida(df_fonte, df_modelo)

    try:
        df_out = df_saida_base.copy()
    except Exception:
        return _nova_base_saida(df_fonte, df_modelo)

    for col in df_modelo.columns:
        if col not in df_out.columns:
            df_out[col] = ""

    df_out = df_out[[str(col) for col in df_modelo.columns]].copy()
    return df_out.fillna("")


def _serie_origem(df_fonte: pd.DataFrame, origem: str) -> pd.Series:
    serie = df_fonte[origem].reset_index(drop=True)
    return serie.apply(sanitizar_valor)


def _aplicar_coluna_mapeada(
    df_saida: pd.DataFrame,
    df_fonte: pd.DataFrame,
    col_modelo: str,
    origem: str,
) -> None:
    if not origem or origem not in df_fonte.columns:
        if col_modelo not in df_saida.columns:
            df_saida[col_modelo] = ""
        else:
            df_saida[col_modelo] = df_saida[col_modelo].fillna("")
        return

    serie = _serie_origem(df_fonte, origem)

    if is_coluna_imagem(col_modelo):
        serie = serie.apply(normalizar_urls_imagem)

    df_saida[col_modelo] = serie


def _aplicar_defaults_sistema(df_saida: pd.DataFrame, df_modelo: pd.DataFrame) -> pd.DataFrame:
    deposito = safe_str(st.session_state.get("deposito_nome"))

    for col in df_modelo.columns:
        if is_coluna_id(col):
            df_saida[col] = ""
            continue

        if is_coluna_deposito(col):
            df_saida[col] = deposito
            continue

        if "situa" in str(col).lower():
            df_saida[col] = df_saida[col].apply(normalizar_situacao)

    return df_saida


def montar_df_saida_mapeado(
    df_fonte: pd.DataFrame,
    df_modelo: pd.DataFrame,
    mapping: dict,
) -> pd.DataFrame:
    if not safe_df_com_linhas(df_fonte) or not safe_df(df_modelo):
        return pd.DataFrame()

    mapping_limpo = {
        str(k): safe_str(v)
        for k, v in dict(mapping or {}).items()
    }

    df_saida = _reaproveitar_base_saida_se_compativel(df_fonte, df_modelo)

    for col in df_modelo.columns:
        col_modelo = str(col)

        if is_coluna_id(col_modelo):
            df_saida[col_modelo] = ""
            continue

        if is_coluna_deposito(col_modelo):
            continue

        origem = mapping_limpo.get(col_modelo, "")
        _aplicar_coluna_mapeada(df_saida, df_fonte, col_modelo, origem)

    df_saida = _aplicar_defaults_sistema(df_saida, df_modelo)

    for col in df_modelo.columns:
        if col not in df_saida.columns:
            df_saida[col] = ""

    df_saida = df_saida[[str(col) for col in df_modelo.columns]].copy()
    df_saida = df_saida.fillna("")

    try:
        st.session_state["df_preview_mapeamento"] = df_saida.copy()
    except Exception:
        st.session_state["df_preview_mapeamento"] = df_saida

    return df_saida
