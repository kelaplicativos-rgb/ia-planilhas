from typing import Dict, List

import pandas as pd
import streamlit as st


def _to_text(valor) -> str:
    if valor is None:
        return ""
    try:
        if pd.isna(valor):
            return ""
    except Exception:
        pass
    texto = str(valor).strip()
    return "" if texto.lower() == "nan" else texto


def _to_float(valor) -> float:
    if valor is None:
        return 0.0

    try:
        if pd.isna(valor):
            return 0.0
    except Exception:
        pass

    texto = str(valor).strip()
    if not texto:
        return 0.0

    texto = (
        texto.replace("R$", "")
        .replace("r$", "")
        .replace("\u00a0", "")
        .replace(" ", "")
    )

    if "," in texto and "." in texto:
        if texto.rfind(",") > texto.rfind("."):
            texto = texto.replace(".", "").replace(",", ".")
        else:
            texto = texto.replace(",", "")
    elif "," in texto:
        texto = texto.replace(".", "").replace(",", ".")

    try:
        return float(texto)
    except Exception:
        return 0.0


def _normalizar_texto(texto: str) -> str:
    import re
    import unicodedata

    texto = str(texto or "").strip().lower()
    texto = unicodedata.normalize("NFKD", texto)
    texto = texto.encode("ascii", "ignore").decode("utf-8")
    texto = re.sub(r"[^a-z0-9]+", " ", texto)
    return re.sub(r"\s+", " ", texto).strip()


def _mapa_colunas_normalizadas(colunas: List[str]) -> Dict[str, str]:
    return {_normalizar_texto(col): col for col in colunas}


def _serie_texto(df: pd.DataFrame, coluna: str) -> pd.Series:
    if coluna not in df.columns:
        return pd.Series([""] * len(df), index=df.index, dtype="string")

    return (
        df[coluna]
        .apply(_to_text)
        .astype("string")
        .fillna("")
        .str.strip()
    )


def _serie_float(df: pd.DataFrame, coluna: str, default: float = 0.0) -> pd.Series:
    if coluna not in df.columns:
        return pd.Series([default] * len(df), index=df.index, dtype="float64")

    serie = df[coluna].apply(_to_float)
    serie = pd.to_numeric(serie, errors="coerce").fillna(default).astype("float64")
    return serie


def detectar_coluna_deposito(colunas_modelo: List[str]) -> str:
    mapa = _mapa_colunas_normalizadas(colunas_modelo)

    for chave in ["deposito", "depósito", "deposito obrigatorio", "depósito obrigatório"]:
        chave_norm = _normalizar_texto(chave)
        if chave_norm in mapa:
            return mapa[chave_norm]

    for col in colunas_modelo:
        cl = _normalizar_texto(col)
        if "deposito" in cl or "depósito" in cl:
            return col

    return ""


def detectar_coluna_estoque(colunas_modelo: List[str]) -> str:
    mapa = _mapa_colunas_normalizadas(colunas_modelo)

    prioridades = [
        "balanco",
        "balanço",
        "estoque",
        "saldo",
        "quantidade",
        "qtd",
    ]

    for chave in prioridades:
        chave_norm = _normalizar_texto(chave)
        if chave_norm in mapa:
            return mapa[chave_norm]

    for col in colunas_modelo:
        cl = _normalizar_texto(col)
        if any(token in cl for token in ["balanco", "balanço", "estoque", "saldo", "quantidade", "qtd"]):
            return col

    return ""


def render_campos_fixos_estoque(colunas_modelo: List[str]) -> Dict[str, object]:
    st.divider()
    st.subheader("Campos fixos do estoque")

    coluna_deposito = detectar_coluna_deposito(colunas_modelo)
    coluna_estoque = detectar_coluna_estoque(colunas_modelo)

    c1, c2 = st.columns(2)

    with c1:
        if coluna_deposito:
            deposito_nome = st.text_input(
                f"Nome do depósito para preencher a coluna '{coluna_deposito}'",
                value=st.session_state.get("deposito_nome_widget", ""),
                key="deposito_nome_widget",
                placeholder="Ex.: Geral, Loja 1, Principal...",
            )
        else:
            deposito_nome = ""

    with c2:
        quantidade_padrao_site = st.number_input(
            f"Quantidade padrão para '{coluna_estoque or 'estoque'}' quando o site só indicar disponível",
            min_value=0,
            value=int(st.session_state.get("estoque_site_padrao_widget", 0)),
            step=1,
            key="estoque_site_padrao_widget",
            help=(
                "Usado apenas na busca por site quando o scraper não identificar a quantidade real. "
                "Se o site indicar esgotado/indisponível, o sistema grava 0. "
                "Se indicar disponível, grava a quantidade informada aqui."
            ),
        )

    return {
        "coluna_deposito": coluna_deposito,
        "deposito_nome": deposito_nome,
        "coluna_estoque": coluna_estoque,
        "quantidade_padrao_site": int(quantidade_padrao_site),
    }


def _status_site_indica_indisponivel(texto: str) -> bool:
    t = _normalizar_texto(texto)

    termos = [
        "indisponivel",
        "indisponível",
        "esgotado",
        "fora de estoque",
        "sem estoque",
        "sold out",
        "out of stock",
        "unavailable",
        "nao disponivel",
        "não disponível",
    ]
    return any(_normalizar_texto(termo) in t for termo in termos)


def _status_site_indica_disponivel(texto: str) -> bool:
    t = _normalizar_texto(texto)

    termos = [
        "disponivel",
        "disponível",
        "em estoque",
        "available",
        "in stock",
        "comprar",
        "adicionar ao carrinho",
    ]
    return any(_normalizar_texto(termo) in t for termo in termos)


def aplicar_regra_estoque_site_na_saida(
    df_saida: pd.DataFrame,
    df_origem: pd.DataFrame,
    estoque_cfg: Dict[str, object] | None,
) -> pd.DataFrame:
    if not estoque_cfg:
        return df_saida

    if "disponibilidade_site" not in df_origem.columns:
        return df_saida

    coluna_estoque = str(estoque_cfg.get("coluna_estoque", "") or "").strip()
    if not coluna_estoque or coluna_estoque not in df_saida.columns:
        return df_saida

    try:
        quantidade_padrao = int(float(estoque_cfg.get("quantidade_padrao_site", 0) or 0))
    except Exception:
        quantidade_padrao = 0

    quantidade_padrao = max(0, quantidade_padrao)

    serie_saida = _serie_texto(df_saida, coluna_estoque)
    serie_disp = _serie_texto(df_origem, "disponibilidade_site")

    novos_valores = []

    for valor_atual, disponibilidade in zip(serie_saida.tolist(), serie_disp.tolist()):
        atual = str(valor_atual or "").strip()

        if atual and atual.lower() not in {"nan", "none"}:
            novos_valores.append(atual)
            continue

        if _status_site_indica_indisponivel(disponibilidade):
            novos_valores.append("0")
            continue

        if _status_site_indica_disponivel(disponibilidade):
            novos_valores.append(str(quantidade_padrao))
            continue

        novos_valores.append(atual)

    df_saida = df_saida.copy()
    df_saida[coluna_estoque] = pd.Series(novos_valores, index=df_saida.index, dtype="string")
    return df_saida


def aplicar_campos_fixos_estoque(
    df_saida: pd.DataFrame,
    df_origem: pd.DataFrame,
    estoque_cfg: Dict[str, object] | None,
) -> pd.DataFrame:
    if not estoque_cfg:
        return df_saida

    df_saida = df_saida.copy()

    coluna_deposito = str(estoque_cfg.get("coluna_deposito", "") or "").strip()
    deposito_nome = str(estoque_cfg.get("deposito_nome", "") or "").strip()

    if coluna_deposito:
        if not deposito_nome:
            deposito_nome = "Geral"
        df_saida[coluna_deposito] = deposito_nome

    df_saida = aplicar_regra_estoque_site_na_saida(
        df_saida=df_saida,
        df_origem=df_origem,
        estoque_cfg=estoque_cfg,
    )

    return df_saida
