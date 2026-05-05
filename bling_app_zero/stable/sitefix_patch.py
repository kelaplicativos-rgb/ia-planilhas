from __future__ import annotations

from typing import Any

import pandas as pd
import streamlit as st

from bling_app_zero.stable import stable_app as base_app
from bling_app_zero.stable.product_flash_crawler import crawl_product_flash_dataframe
from bling_app_zero.stable.session_vault import guardar_df, restaurar_df
from bling_app_zero.stable.stock_flash_crawler import crawl_stock_flash_dataframe


OLD_SITE_INFO = "Captura por site está liberada neste núcleo para atualização de estoque."
NEW_SITE_INFO = (
    "Captura por site em modo flash. "
    "Cadastro busca dados de cadastro sem consultar estoque. "
    "Atualização de estoque busca somente SKU/código, disponibilidade e quantidade."
)

ESTOQUE_DISPONIVEL_PADRAO_UI = 1000


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


def _crawl_site_df(raw_urls: str, estoque_padrao: int) -> pd.DataFrame:
    tipo = _tipo_operacao_atual()
    estoque_padrao = _normalizar_estoque_input(estoque_padrao)

    if tipo == "estoque":
        with st.spinner("Modo flash estoque: buscando só SKU/código, disponibilidade e quantidade..."):
            df = crawl_stock_flash_dataframe(raw_urls, estoque_disponivel=estoque_padrao)
        if df is None or df.empty:
            st.warning("Nenhum estoque foi capturado. Tente colar links de categorias ou produtos específicos.")
            return pd.DataFrame()
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


def _render_busca_site_independente() -> None:
    modelo = restaurar_df("stable_df_modelo")
    origem = restaurar_df("stable_df_origem")
    if not isinstance(modelo, pd.DataFrame) or modelo.empty:
        return
    if isinstance(origem, pd.DataFrame) and not origem.empty:
        return

    _inicializar_estoque_padrao_ui()
    tipo = _tipo_operacao_atual()
    is_estoque = tipo == "estoque"

    with st.container(border=True):
        titulo = "### ⚡ Buscar estoque flash por site" if is_estoque else "### ⚡ Buscar cadastro flash por site"
        st.markdown(titulo)
        if is_estoque:
            st.caption("Atualização de estoque: busca rápida só de SKU/código, disponibilidade, quantidade e origem do estoque.")
        else:
            st.caption("Cadastro de produtos: busca rápida de dados cadastrais sem consultar estoque/quantidade.")

        raw_urls = st.text_area("Links do fornecedor", key="stable_site_urls_fallback", height=120)

        estoque_padrao = ESTOQUE_DISPONIVEL_PADRAO_UI
        if is_estoque:
            st.info(
                "📦 Estoque automático: se encontrar número real, usa o real. "
                "Se detectar disponível sem quantidade, usa o valor abaixo. "
                "Se detectar indisponível/sem estoque, usa 0."
            )
            estoque_padrao = st.number_input(
                "Estoque para disponível sem quantidade real",
                min_value=0,
                value=_normalizar_estoque_input(st.session_state.get("stable_estoque_padrao_fallback", ESTOQUE_DISPONIVEL_PADRAO_UI)),
                step=1,
                key="stable_estoque_padrao_fallback",
                help="Padrão automático: 1000. Se você trocar, o valor digitado substitui o 1000 apenas quando o produto estiver disponível sem quantidade real.",
            )
        else:
            st.info("🧾 Cadastro flash: este modo não busca estoque nem quantidade. Use Atualização de estoque para essa operação.")

        tem_url = bool(str(raw_urls or "").strip())
        label_botao = "⚡ Buscar estoque flash" if is_estoque else "⚡ Buscar cadastro flash"
        if st.button(label_botao, disabled=not tem_url, use_container_width=True, key="btn_site_fallback_modelo"):
            df = _crawl_site_df(raw_urls, int(estoque_padrao))
            if isinstance(df, pd.DataFrame) and not df.empty:
                st.rerun()


def run_stable_app() -> None:
    _inicializar_estoque_padrao_ui()

    original_button = st.button
    original_info = st.info
    original_site_df = base_app._site_df
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
    try:
        base_app.run_stable_app()
        _render_busca_site_independente()
    finally:
        st.button = original_button
        st.info = original_info
        st.number_input = original_number_input
        base_app._site_df = original_site_df
