from __future__ import annotations

from typing import Any

import pandas as pd
import streamlit as st

from bling_app_zero.stable import stable_app as base_app
from bling_app_zero.stable.product_flash_crawler import crawl_product_flash_dataframe
from bling_app_zero.stable.session_vault import guardar_df
from bling_app_zero.stable.stock_flash_crawler import crawl_stock_flash_dataframe


OLD_SITE_INFO = "Captura por site está liberada neste núcleo para atualização de estoque."
NEW_SITE_INFO = (
    "Captura por site em modo flash. "
    "Cadastro busca dados de cadastro sem consultar estoque. "
    "Atualização de estoque busca SKU, nome do produto e valor/saldo, "
    "mantendo o preview no espelho do modelo Bling anexado."
)

ESTOQUE_DISPONIVEL_PADRAO_UI = 1000

# Fallback usado somente quando nenhum modelo Bling foi anexado.
# O modelo saldo_estoque.xlsx, quando anexado, sempre prevalece.
ESTOQUE_SITE_COLUMNS = ["SKU", "Produto", "Valor", "Estoque", "Quantidade"]


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


def _serie(df: pd.DataFrame, coluna: str, padrao: object = "") -> pd.Series:
    if isinstance(df, pd.DataFrame) and coluna in df.columns:
        return df[coluna].astype(str).fillna("")
    return pd.Series([padrao] * len(df), index=df.index)


def _limpar_df_estoque_site(df: pd.DataFrame) -> pd.DataFrame:
    if not isinstance(df, pd.DataFrame) or df.empty:
        return pd.DataFrame(columns=ESTOQUE_SITE_COLUMNS)

    codigo = _serie(df, "Código")
    if not codigo.astype(str).str.strip().any():
        codigo = _serie(df, "SKU site")

    nome = _serie(df, "Descrição")
    if not nome.astype(str).str.strip().any():
        nome = _serie(df, "Produto")

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

    # Colunas técnicas capturadas do site.
    out["Código"] = codigo
    out["SKU"] = codigo
    out["SKU site"] = codigo
    out["Descrição"] = nome
    out["Produto"] = nome
    out["Nome"] = nome
    out["Nome do produto"] = nome
    out["Valor"] = valor
    out["Estoque"] = estoque
    out["Quantidade"] = quantidade

    # Colunas do modelo saldo_estoque.xlsx que não existem no site.
    # Elas ficam vazias, mas disponíveis para o espelho do modelo anexado.
    out["ID"] = ""
    out["Data"] = ""
    out["Depósito"] = ""
    out["Deposito"] = ""
    out["Observações"] = ""
    out["Observacoes"] = ""

    if "URL do produto" in df.columns:
        out["URL do produto"] = df["URL do produto"].astype(str).fillna("")

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
        with st.spinner("Modo flash estoque: buscando nome do produto, SKU e valor/saldo..."):
            df = crawl_stock_flash_dataframe(raw_urls, estoque_disponivel=estoque_padrao)
        if df is None or df.empty:
            st.warning("Nenhum estoque foi capturado. Tente colar links de categorias ou produtos específicos.")
            return pd.DataFrame(columns=ESTOQUE_SITE_COLUMNS)
        df = _limpar_df_estoque_site(df)
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
