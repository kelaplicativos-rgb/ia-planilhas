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


def _detectar_coluna_preco_base(colunas_origem: List[str]) -> str:
    prioridades = [
        "custo",
        "preco custo",
        "preço custo",
        "preco de custo",
        "valor custo",
        "valor",
        "preco",
        "preço",
        "vuncom",
        "vprod",
    ]
    mapa = _mapa_colunas_normalizadas(colunas_origem)

    for chave in prioridades:
        chave_norm = _normalizar_texto(chave)
        if chave_norm in mapa:
            return mapa[chave_norm]

    for col in colunas_origem:
        cl = _normalizar_texto(col)
        if "custo" in cl or "preco" in cl or "valor" in cl:
            return col

    return ""


def _detectar_coluna_preco_destino(colunas_destino: List[str], modo: str) -> str:
    prioridades_estoque = [
        "preco unitario",
        "preço unitário",
        "preco unitário",
        "preço unitario",
    ]
    prioridades_gerais = [
        "preco",
        "preço",
        "preco venda",
        "preço venda",
        "preco de venda",
        "preço de venda",
        "valor de venda",
    ]

    mapa = _mapa_colunas_normalizadas(colunas_destino)

    if modo == "estoque":
        for chave in prioridades_estoque + prioridades_gerais:
            chave_norm = _normalizar_texto(chave)
            if chave_norm in mapa:
                return mapa[chave_norm]

    for chave in prioridades_gerais + prioridades_estoque:
        chave_norm = _normalizar_texto(chave)
        if chave_norm in mapa:
            return mapa[chave_norm]

    for col in colunas_destino:
        cl = _normalizar_texto(col)
        if "preco" in cl or "preço" in cl:
            return col

    return ""


def calcular_preco_venda_unitario(
    preco_compra: float,
    percentual_impostos: float,
    margem_lucro: float,
    custo_fixo: float,
    taxa_extra: float,
) -> float:
    base = float(preco_compra or 0.0) + float(custo_fixo or 0.0)
    impostos = float(percentual_impostos or 0.0) / 100.0
    lucro = float(margem_lucro or 0.0) / 100.0
    taxa = float(taxa_extra or 0.0) / 100.0

    denominador = 1.0 - impostos - lucro - taxa
    if denominador <= 0:
        return 0.0

    resultado = base / denominador
    return round(resultado if resultado > 0 else 0.0, 2)


def render_calculadora(
    df_origem: pd.DataFrame,
    colunas_destino_ativas: List[str],
    modo: str,
) -> Dict[str, object]:
    st.divider()
    st.subheader("Calculadora de preço")
    st.caption("O preço gerado será gravado na coluna real de preço do modelo final.")

    colunas_origem = list(df_origem.columns)

    base_default = st.session_state.get("coluna_preco_base_widget", "")
    if not base_default or base_default not in colunas_origem:
        base_default = _detectar_coluna_preco_base(colunas_origem)

    destino_default = st.session_state.get("coluna_preco_destino_widget", "")
    if not destino_default or destino_default not in colunas_destino_ativas:
        destino_default = _detectar_coluna_preco_destino(colunas_destino_ativas, modo)

    csel1, csel2 = st.columns(2)

    with csel1:
        opcoes_origem = [""] + colunas_origem
        idx_origem = opcoes_origem.index(base_default) if base_default in opcoes_origem else 0
        coluna_preco_base = st.selectbox(
            "Coluna da fornecedora usada como preço base",
            options=opcoes_origem,
            index=idx_origem,
            key="coluna_preco_base_widget",
        )

    with csel2:
        opcoes_destino = [""] + colunas_destino_ativas
        idx_destino = opcoes_destino.index(destino_default) if destino_default in opcoes_destino else 0
        coluna_preco_destino = st.selectbox(
            "Coluna do modelo final que receberá o preço gerado",
            options=opcoes_destino,
            index=idx_destino,
            key="coluna_preco_destino_widget",
        )

    preco_base_medio = 0.0
    exemplo_base = ""

    if coluna_preco_base and coluna_preco_base in df_origem.columns:
        serie_exemplo = _serie_texto(df_origem, coluna_preco_base)
        serie_exemplo = serie_exemplo[serie_exemplo != ""]
        exemplo_base = serie_exemplo.iloc[0] if not serie_exemplo.empty else ""

        precos = _serie_float(df_origem, coluna_preco_base, default=0.0)
        precos = precos[precos > 0]
        preco_base_medio = float(precos.mean()) if not precos.empty else 0.0

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        margem = st.number_input(
            "Lucro (%)",
            min_value=0.0,
            max_value=100.0,
            value=float(st.session_state.get("calc_margem_lucro", 30.0)),
            step=1.0,
            key="calc_margem_lucro",
        )
    with c2:
        impostos = st.number_input(
            "Impostos (%)",
            min_value=0.0,
            max_value=100.0,
            value=float(st.session_state.get("calc_impostos", 0.0)),
            step=1.0,
            key="calc_impostos",
        )
    with c3:
        taxa_extra = st.number_input(
            "Taxas extras (%)",
            min_value=0.0,
            max_value=100.0,
            value=float(st.session_state.get("calc_taxa_extra", 15.0)),
            step=1.0,
            key="calc_taxa_extra",
        )
    with c4:
        custo_fixo = st.number_input(
            "Custo fixo (R$)",
            min_value=0.0,
            value=float(st.session_state.get("calc_custo_fixo", 0.0)),
            step=1.0,
            key="calc_custo_fixo",
        )

    preco_sugerido = calcular_preco_venda_unitario(
        preco_compra=preco_base_medio,
        percentual_impostos=impostos,
        margem_lucro=margem,
        custo_fixo=custo_fixo,
        taxa_extra=taxa_extra,
    )

    m1, m2, m3 = st.columns(3)
    with m1:
        st.metric("Preço base médio detectado", f"R$ {preco_base_medio:.2f}")
    with m2:
        st.metric("Preço gerado", f"R$ {preco_sugerido:.2f}")
    with m3:
        st.metric("Exemplo da coluna base", str(exemplo_base) if exemplo_base else "—")

    if margem + impostos + taxa_extra >= 100:
        st.warning("A soma de lucro + impostos + taxas extras precisa ser menor que 100%.")

    return {
        "coluna_preco_base": coluna_preco_base,
        "coluna_preco_destino": coluna_preco_destino,
        "margem": margem,
        "impostos": impostos,
        "taxa_extra": taxa_extra,
        "custo_fixo": custo_fixo,
    }
