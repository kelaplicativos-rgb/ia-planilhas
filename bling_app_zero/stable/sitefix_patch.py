from __future__ import annotations

import re
from typing import Any
from urllib.parse import urlparse

import pandas as pd
import streamlit as st

from bling_app_zero.stable import stable_app as base_app
from bling_app_zero.stable.product_flash_crawler import crawl_product_flash_dataframe
from bling_app_zero.stable.session_vault import guardar_df
from bling_app_zero.stable.site_price_extractor import extract_price_from_url
from bling_app_zero.stable.stock_flash_crawler import crawl_stock_flash_dataframe


OLD_SITE_INFO = "Captura por site está liberada neste núcleo para atualização de estoque."
NEW_SITE_INFO = (
    "Captura por site em modo flash. "
    "Cadastro busca dados de cadastro sem consultar estoque. "
    "Atualização de estoque busca SKU, nome do produto, preço e valor/saldo, "
    "mantendo o preview no espelho do modelo Bling anexado."
)

ESTOQUE_DISPONIVEL_PADRAO_UI = 1000

ESTOQUE_SITE_COLUMNS = [
    "Codigo produto *",
    "GTIN **",
    "Descrição Produto",
    "Balanço (OBRIGATÓRIO)",
    "Preço unitário (OBRIGATÓRIO)",
]

_GENERIC_SITE_TITLES = {
    "mega center eletrônicos",
    "mega center eletronicos",
    "mega center",
    "produto",
    "produtos",
    "loja",
}

_URL_ALIASES = [
    "URL do produto",
    "Url do produto",
    "url_produto",
    "url",
    "URL",
    "Link",
    "link",
    "Link do produto",
    "Produto URL",
]


def _tipo_operacao_atual() -> str:
    return str(st.session_state.get("stable_tipo", "cadastro") or "cadastro").strip().lower()


def _inicializar_estoque_padrao_ui() -> None:
    for key in ["stable_estoque_padrao", "stable_estoque_padrao_fallback"]:
        flag = f"{key}_inicializado_auto_1000"
        if not st.session_state.get(flag):
            valor_atual = st.session_state.get(key, None)
            if valor_atual in (None, "", 0, "0"):
                st.session_state[key] = ESTOQUE_DISPONIVEL_PADRAO_UI
            st.session_state[flag] = True


def _normalizar_estoque_input(valor: object) -> int:
    try:
        return max(0, int(valor))
    except Exception:
        return ESTOQUE_DISPONIVEL_PADRAO_UI


def _split_urls_local(raw: str) -> list[str]:
    urls: list[str] = []
    seen: set[str] = set()
    for item in re.split(r"[\n,;\s]+", str(raw or "")):
        url = item.strip()
        if not url:
            continue
        if not url.startswith(("http://", "https://")):
            url = "https://" + url
        if url not in seen:
            seen.add(url)
            urls.append(url)
    return urls


def _serie(df: pd.DataFrame, coluna: str, padrao: object = "") -> pd.Series:
    if isinstance(df, pd.DataFrame) and coluna in df.columns:
        return df[coluna].astype(str).fillna("")
    return pd.Series([padrao] * len(df), index=df.index)


def _url_series(df: pd.DataFrame, raw_urls: str = "") -> pd.Series:
    for coluna in _URL_ALIASES:
        if isinstance(df, pd.DataFrame) and coluna in df.columns:
            serie = df[coluna].astype(str).fillna("")
            if serie.astype(str).str.strip().any():
                return serie

    urls = _split_urls_local(raw_urls)
    if urls and len(urls) == len(df):
        return pd.Series(urls, index=df.index)

    return pd.Series([""] * len(df), index=df.index)


def _clean_text(value: object) -> str:
    return re.sub(r"\s+", " ", str(value or "").replace("\xa0", " ")).strip()


def _is_generic_product_name(value: object) -> bool:
    text = _clean_text(value).lower()
    if not text:
        return True
    text = text.replace("|", " ").replace("-", " ")
    text = re.sub(r"\s+", " ", text).strip()
    return text in _GENERIC_SITE_TITLES or text.endswith(" mega center eletrônicos") or text.endswith(" mega center eletronicos")


def _nome_produto_from_url(url: object, fallback: object = "") -> str:
    raw = str(url or "").strip()
    if raw:
        parsed = urlparse(raw)
        parts = [p for p in parsed.path.split("/") if p.strip()]
        if parts:
            slug = parts[-1]
            slug = re.sub(r"\.(html?|php|aspx?)$", "", slug, flags=re.IGNORECASE)
            slug = re.sub(r"^[0-9]+[-_ ]+", "", slug)
            slug = re.sub(r"[-_]+", " ", slug)
            slug = re.sub(r"\s+", " ", slug).strip()
            if slug:
                return slug.title()
    fallback_text = _clean_text(fallback)
    return fallback_text or "Produto capturado do site"


def _preco_from_urls(urls: pd.Series) -> pd.Series:
    valores: list[str] = []
    for url in urls.astype(str).fillna("").tolist():
        preco = extract_price_from_url(url)
        valores.append(preco if preco else "0,00")
    return pd.Series(valores, index=urls.index)


def _limpar_df_estoque_site(df: pd.DataFrame, raw_urls: str = "") -> pd.DataFrame:
    if not isinstance(df, pd.DataFrame) or df.empty:
        return pd.DataFrame(columns=ESTOQUE_SITE_COLUMNS)

    codigo = _serie(df, "Código")
    if not codigo.astype(str).str.strip().any():
        codigo = _serie(df, "SKU site")

    nome = _serie(df, "Descrição")
    if not nome.astype(str).str.strip().any():
        nome = _serie(df, "Produto")

    url_produto = _url_series(df, raw_urls=raw_urls)
    nome = pd.Series(
        [
            _nome_produto_from_url(url, fallback=codigo.iloc[pos]) if _is_generic_product_name(value) else _clean_text(value)
            for pos, (value, url) in enumerate(zip(nome.tolist(), url_produto.tolist()))
        ],
        index=df.index,
    )

    preco_unitario = _preco_from_urls(url_produto) if url_produto.astype(str).str.strip().any() else pd.Series(["0,00"] * len(df), index=df.index)

    if "Valor" in df.columns:
        valor = df["Valor"]
    elif "Estoque" in df.columns:
        valor = df["Estoque"]
    elif "Quantidade" in df.columns:
        valor = df["Quantidade"]
    else:
        valor = pd.Series([0] * len(df), index=df.index)

    if "Estoque" in df.columns:
        estoque = df["Estoque"]
    elif "Quantidade" in df.columns:
        estoque = df["Quantidade"]
    else:
        estoque = valor

    if "Quantidade" in df.columns:
        quantidade = df["Quantidade"]
    else:
        quantidade = estoque

    out = pd.DataFrame(index=df.index)

    out["Código"] = codigo
    out["Codigo"] = codigo
    out["Codigo produto *"] = codigo
    out["SKU"] = codigo
    out["SKU site"] = codigo
    out["GTIN"] = codigo
    out["GTIN **"] = codigo
    out["GTIN/EAN"] = codigo
    out["Descrição"] = nome
    out["Descrição Produto"] = nome
    out["Produto"] = nome
    out["Nome"] = nome
    out["Nome do produto"] = nome
    out["Valor"] = valor
    out["Balanço (OBRIGATÓRIO)"] = valor
    out["Balanco (OBRIGATORIO)"] = valor
    out["Estoque"] = estoque
    out["Quantidade"] = quantidade
    out["Preço unitário (OBRIGATÓRIO)"] = preco_unitario
    out["Preço de Custo"] = ""

    out["ID"] = ""
    out["ID Produto"] = ""
    out["Data"] = ""
    out["Depósito"] = ""
    out["Deposito"] = ""
    out["Deposito (OBRIGATÓRIO)"] = ""
    out["Observação"] = ""
    out["Observações"] = ""
    out["Observacao"] = ""
    out["Observacoes"] = ""
    out["URL do produto"] = url_produto

    return out.fillna("")


def _remover_colunas_estoque_do_cadastro(df: pd.DataFrame) -> pd.DataFrame:
    if not isinstance(df, pd.DataFrame) or df.empty:
        return pd.DataFrame()
    remover = {
        "estoque",
        "quantidade",
        "disponibilidade",
        "origem do estoque",
        "sku site",
    }
    colunas = [c for c in df.columns if str(c).strip().lower() not in remover]
    return df[colunas].copy().fillna("")


def _colunas_do_modelo(modelo: pd.DataFrame | None) -> list[str]:
    if isinstance(modelo, pd.DataFrame) and not modelo.empty and len(modelo.columns) > 0:
        return [str(c).strip() for c in modelo.columns if str(c).strip()]
    return []


def _target_columns_corrigido(tipo: str, modelo: pd.DataFrame | None) -> list[str]:
    colunas_modelo = _colunas_do_modelo(modelo)
    if colunas_modelo:
        return colunas_modelo
    if str(tipo or "").strip().lower() == "estoque":
        return ESTOQUE_SITE_COLUMNS.copy()
    return base_app.CADASTRO_DEFAULT_COLUMNS.copy()


def _crawl_site_df(raw_urls: str, estoque_padrao: int) -> pd.DataFrame:
    tipo = _tipo_operacao_atual()
    estoque_padrao = _normalizar_estoque_input(estoque_padrao)

    if tipo == "estoque":
        with st.spinner("Modo flash estoque: buscando nome do produto, SKU, preço e valor/saldo..."):
            df = crawl_stock_flash_dataframe(raw_urls, estoque_disponivel=estoque_padrao)
        if df is None or df.empty:
            st.warning("Nenhum estoque foi capturado. Tente colar links de categorias ou produtos específicos.")
            return pd.DataFrame(columns=ESTOQUE_SITE_COLUMNS)
        df = _limpar_df_estoque_site(df, raw_urls=raw_urls)
        df = guardar_df("stable_df_origem", df)
        st.success(f"Busca flash de estoque finalizada e travada: {len(df)} produto(s) encontrado(s).")
        return df

    with st.spinner("Modo flash cadastro: buscando dados de produto sem consultar estoque..."):
        df = crawl_product_flash_dataframe(raw_urls)

    if df is None or df.empty:
        st.warning("Nenhum produto foi capturado. Tente colar links de categorias ou produtos específicos.")
        return pd.DataFrame()

    df = _remover_colunas_estoque_do_cadastro(df)
    df = guardar_df("stable_df_origem", df)
    st.success(f"Busca flash de cadastro finalizada e travada: {len(df)} produto(s) encontrado(s).")
    return df


def run_stable_app() -> None:
    _inicializar_estoque_padrao_ui()

    original_button = st.button
    original_info = st.info
    original_site_df = base_app._site_df
    original_target_columns = base_app._target_columns
    original_number_input = st.number_input

    def patched_button(label: str, *args: Any, **kwargs: Any):
        if label == "Gerar base por site":
            kwargs["disabled"] = False
        return original_button(label, *args, **kwargs)

    def patched_info(body: Any, *args: Any, **kwargs: Any):
        if str(body) == OLD_SITE_INFO:
            body = NEW_SITE_INFO
        return original_info(body, *args, **kwargs)

    def patched_number_input(label: str, *args: Any, **kwargs: Any):
        tipo = _tipo_operacao_atual()
        if str(label) == "Estoque padrão":
            if tipo != "estoque":
                return ESTOQUE_DISPONIVEL_PADRAO_UI
            label = "Valor/saldo para disponível sem quantidade real"
            kwargs["value"] = _normalizar_estoque_input(st.session_state.get("stable_estoque_padrao", ESTOQUE_DISPONIVEL_PADRAO_UI))
            kwargs.setdefault(
                "help",
                "Padrão automático: 1000. Se você trocar, o valor digitado substitui o 1000 apenas quando o produto estiver disponível sem quantidade real.",
            )
        return original_number_input(label, *args, **kwargs)

    st.button = patched_button
    st.info = patched_info
    st.number_input = patched_number_input
    base_app._site_df = _crawl_site_df
    base_app._target_columns = _target_columns_corrigido
    try:
        base_app.run_stable_app()
    finally:
        st.button = original_button
        st.info = original_info
        st.number_input = original_number_input
        base_app._site_df = original_site_df
        base_app._target_columns = original_target_columns
