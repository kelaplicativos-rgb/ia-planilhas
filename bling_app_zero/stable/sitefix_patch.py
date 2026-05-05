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
    "Atualização de estoque busca SKU/código, nome do produto e quantidade, "
    "mantendo o preview final no mesmo espelho do modelo Bling anexado."
)

ESTOQUE_DISPONIVEL_PADRAO_UI = 1000

# Colunas mínimas usadas quando nenhum modelo Bling foi anexado.
ESTOQUE_SITE_COLUMNS = ["Código", "Descrição", "Depósito", "Estoque", "Quantidade"]


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


def _limpar_df_estoque_site(df: pd.DataFrame, deposito: str = "") -> pd.DataFrame:
    if not isinstance(df, pd.DataFrame) or df.empty:
        return pd.DataFrame(columns=ESTOQUE_SITE_COLUMNS)

    out = pd.DataFrame(index=df.index)
    out["Código"] = df["Código"].astype(str).fillna("") if "Código" in df.columns else ""
    out["Descrição"] = df["Descrição"].astype(str).fillna("") if "Descrição" in df.columns else ""

    if "Depósito" in df.columns:
        out["Depósito"] = df["Depósito"].astype(str).fillna("")
    else:
        out["Depósito"] = str(deposito or st.session_state.get("stable_deposito_mapeamento", "") or "")

    if "Estoque" in df.columns:
        out["Estoque"] = df["Estoque"]
    elif "Quantidade" in df.columns:
        out["Estoque"] = df["Quantidade"]
    else:
        out["Estoque"] = 0

    if "Quantidade" in df.columns:
        out["Quantidade"] = df["Quantidade"]
    else:
        out["Quantidade"] = out["Estoque"]

    return out[ESTOQUE_SITE_COLUMNS].fillna("")


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
        with st.spinner("Modo flash estoque: buscando SKU/código, nome do produto e quantidade..."):
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
            label = "Estoque para disponível sem quantidade real"
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
