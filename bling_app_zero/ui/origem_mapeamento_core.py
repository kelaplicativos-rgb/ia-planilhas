
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


# =========================================================
# HELPERS
# =========================================================
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


def is_coluna_balanco(nome) -> bool:
    nome_normalizado = normalizar_coluna(nome)
    return "balanco" in nome_normalizado or "balanço" in str(nome).lower()


def is_coluna_codigo_produto(nome) -> bool:
    nome_normalizado = normalizar_coluna(nome)
    return (
        "codigo produto" in nome_normalizado
        or nome_normalizado == "codigo"
        or nome_normalizado == "código"
    )


def is_coluna_gtin_destino(nome) -> bool:
    nome_normalizado = normalizar_coluna(nome)
    return "gtin" in nome_normalizado or "ean" in nome_normalizado


def is_coluna_descricao_destino(nome) -> bool:
    nome_normalizado = normalizar_coluna(nome)
    return "descricao produto" in nome_normalizado or nome_normalizado == "descricao"


def is_coluna_preco_destino(nome) -> bool:
    nome_normalizado = normalizar_coluna(nome)
    return (
        "preco de venda" in nome_normalizado
        or "preco unitario" in nome_normalizado
    )


# =========================================================
# RESOLUÇÃO DE DFS
# =========================================================
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
        st.session_state.get("df_modelo_estoque"),
        st.session_state.get("df_modelo"),
        st.session_state.get("df_modelo_cadastro"),
    ]

    for df in candidatos:
        if safe_df(df):
            return df

    return None


# =========================================================
# INFERÊNCIA DE COLUNAS
# =========================================================
def _colunas_existentes(df_fonte: pd.DataFrame) -> list[str]:
    return [str(c) for c in df_fonte.columns]


def _mapa_normalizado(df_fonte: pd.DataFrame) -> dict[str, str]:
    return {normalizar_coluna(c): c for c in _colunas_existentes(df_fonte)}


def inferir_coluna_codigo(df_fonte: pd.DataFrame) -> str:
    prioridades = [
        "codigo_produto",
        "codigo",
        "código",
        "sku",
        "ean",
        "gtin",
        "cProd",
    ]
    mapa = _mapa_normalizado(df_fonte)

    for item in prioridades:
        chave = normalizar_coluna(item)
        if chave in mapa:
            return mapa[chave]

    for col in _colunas_existentes(df_fonte):
        nome = normalizar_coluna(col)
        if "codigo" in nome or "código" in str(col).lower() or nome == "sku":
            return col

    return ""


def inferir_coluna_gtin(df_fonte: pd.DataFrame) -> str:
    prioridades = [
        "ean",
        "gtin",
        "codigo_barras_tributavel",
        "cEAN",
        "cEANTrib",
    ]
    mapa = _mapa_normalizado(df_fonte)

    for item in prioridades:
        chave = normalizar_coluna(item)
        if chave in mapa:
            return mapa[chave]

    for col in _colunas_existentes(df_fonte):
        nome = normalizar_coluna(col)
        if "ean" in nome or "gtin" in nome or "barra" in nome:
            return col

    return ""


def inferir_coluna_descricao(df_fonte: pd.DataFrame) -> str:
    prioridades = [
        "descricao",
        "descrição",
        "descricao_curta",
        "descrição curta",
        "xProd",
        "nome",
        "produto",
    ]
    mapa = _mapa_normalizado(df_fonte)

    for item in prioridades:
        chave = normalizar_coluna(item)
        if chave in mapa:
            return mapa[chave]

    for col in _colunas_existentes(df_fonte):
        nome = normalizar_coluna(col)
        if "descricao" in nome or "descrição" in str(col).lower() or "produto" in nome:
            return col

    return ""


def inferir_coluna_preco(df_fonte: pd.DataFrame) -> str:
    prioridades = [
        "Preço unitário (OBRIGATÓRIO)",
        "Preço de venda",
        "preco_unitario",
        "preco de venda",
        "valor_unitario",
        "valor unitario",
        "valor_total",
        "preco",
        "preço",
        "valor",
        "custo",
        "preco_unitario_tributavel",
    ]
    mapa = _mapa_normalizado(df_fonte)

    for item in prioridades:
        chave = normalizar_coluna(item)
        if chave in mapa:
            return mapa[chave]

    for col in _colunas_existentes(df_fonte):
        nome = normalizar_coluna(col)
        if "preco" in nome or "valor" in nome or "custo" in nome:
            return col

    return ""


def inferir_coluna_custo(df_fonte: pd.DataFrame) -> str:
    prioridades = [
        "preco de custo",
        "preco_custo",
        "custo",
        "valor_custo",
        "preco_unitario",
        "preco_unitario_tributavel",
    ]
    mapa = _mapa_normalizado(df_fonte)

    for item in prioridades:
        chave = normalizar_coluna(item)
        if chave in mapa:
            return mapa[chave]

    for col in _colunas_existentes(df_fonte):
        nome = normalizar_coluna(col)
        if "custo" in nome:
            return col

    return ""


def inferir_coluna_balanco(df_fonte: pd.DataFrame) -> str:
    prioridades = [
        "quantidade",
        "qCom",
        "qTrib",
        "quantidade_tributavel",
        "estoque",
        "saldo",
        "balanco",
        "balanço",
    ]
    mapa = _mapa_normalizado(df_fonte)

    for item in prioridades:
        chave = normalizar_coluna(item)
        if chave in mapa:
            return mapa[chave]

    for col in _colunas_existentes(df_fonte):
        nome = normalizar_coluna(col)
        if (
            "quantidade" in nome
            or nome in {"qcom", "qtrib"}
            or "estoque" in nome
            or "saldo" in nome
            or "balanco" in nome
        ):
            return col

    return ""


def aplicar_mapeamento_automatico(
    mapping: dict,
    df_modelo: pd.DataFrame,
    df_fonte: pd.DataFrame,
) -> dict:
    try:
        mapping_out = dict(mapping or {})

        col_codigo = inferir_coluna_codigo(df_fonte)
        col_gtin = inferir_coluna_gtin(df_fonte)
        col_desc = inferir_coluna_descricao(df_fonte)
        col_preco = inferir_coluna_preco(df_fonte)
        col_custo = inferir_coluna_custo(df_fonte)
        col_balanco = inferir_coluna_balanco(df_fonte)

        for col_modelo in [str(c) for c in df_modelo.columns]:
            atual = safe_str(mapping_out.get(col_modelo))
            if atual and atual in df_fonte.columns:
                continue

            if is_coluna_codigo_produto(col_modelo) and col_codigo:
                mapping_out[col_modelo] = col_codigo
            elif is_coluna_gtin_destino(col_modelo) and col_gtin:
                mapping_out[col_modelo] = col_gtin
            elif is_coluna_descricao_destino(col_modelo) and col_desc:
                mapping_out[col_modelo] = col_desc
            elif is_coluna_balanco(col_modelo) and col_balanco:
                mapping_out[col_modelo] = col_balanco
            elif is_coluna_preco_destino(col_modelo) and col_preco:
                mapping_out[col_modelo] = col_preco
            elif normalizar_coluna(col_modelo) == "preco de custo" and col_custo:
                mapping_out[col_modelo] = col_custo

        return mapping_out
    except Exception:
        return dict(mapping or {})


# =========================================================
# MONTAGEM DE SAÍDA
# =========================================================
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
        col_nome = str(col)

        if is_coluna_id(col_nome):
            df_saida[col_nome] = ""
            continue

        if is_coluna_deposito(col_nome):
            df_saida[col_nome] = deposito
            continue

        if "situa" in str(col_nome).lower():
            df_saida[col_nome] = df_saida[col_nome].apply(normalizar_situacao)

        if normalizar_coluna(col_nome) in {"observacao", "data"}:
            if col_nome not in df_saida.columns:
                df_saida[col_nome] = ""

    return df_saida


def montar_df_saida_mapeado(
    df_fonte: pd.DataFrame,
    df_modelo: pd.DataFrame,
    mapping: dict,
) -> pd.DataFrame:
    if not safe_df_com_linhas(df_fonte) or not safe_df(df_modelo):
        return pd.DataFrame()

    mapping_limpo = {str(k): safe_str(v) for k, v in dict(mapping or {}).items()}
    mapping_limpo = aplicar_mapeamento_automatico(mapping_limpo, df_modelo, df_fonte)

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
