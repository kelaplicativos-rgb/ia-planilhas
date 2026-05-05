from __future__ import annotations

from typing import Any

import pandas as pd
import streamlit as st

from bling_app_zero.stable import stable_app as base_app
from bling_app_zero.stable.megacenter_crawler import crawl_site_to_bling_dataframe
from bling_app_zero.stable.session_vault import guardar_df, restaurar_df
from bling_app_zero.stable.stock_flash_crawler import crawl_stock_flash_dataframe


OLD_SITE_INFO = "Captura por site está liberada neste núcleo para atualização de estoque."
NEW_SITE_INFO = (
    "Captura por site real liberada para cadastro e atualização de estoque. "
    "No cadastro, o sistema busca dados completos do produto. "
    "Na atualização de estoque, o sistema usa modo flash focado em SKU/código, disponibilidade e quantidade."
)


def _tipo_operacao_atual() -> str:
    return str(st.session_state.get("stable_tipo", "cadastro") or "cadastro").strip().lower()


def _crawl_site_df(raw_urls: str, estoque_padrao: int) -> pd.DataFrame:
    tipo = _tipo_operacao_atual()

    if tipo == "estoque":
        with st.spinner("Modo flash: buscando SKU/código e disponibilidade de estoque..."):
            df = crawl_stock_flash_dataframe(raw_urls, estoque_disponivel=estoque_padrao)
        if df is None or df.empty:
            st.warning("Nenhum estoque foi capturado. Tente colar links de categorias ou produtos específicos.")
            return pd.DataFrame()
        df = guardar_df("stable_df_origem", df)
        st.success(f"Busca flash de estoque finalizada e travada: {len(df)} produto(s) encontrado(s).")
        return df

    with st.spinner("Buscando produtos no site, entrando nas páginas e capturando dados completos..."):
        df = crawl_site_to_bling_dataframe(raw_urls, estoque_padrao=estoque_padrao)

    if df is None or df.empty:
        st.warning("Nenhum produto foi capturado. Tente colar links de categorias ou produtos específicos.")
        return pd.DataFrame()

    df = guardar_df("stable_df_origem", df)
    st.success(f"Captura completa finalizada e travada: {len(df)} produto(s) encontrado(s).")
    return df


def _render_busca_site_independente() -> None:
    """Fallback para quando o modelo Bling foi anexado e a origem ainda não existe."""
    modelo = restaurar_df("stable_df_modelo")
    origem = restaurar_df("stable_df_origem")
    if not isinstance(modelo, pd.DataFrame) or modelo.empty:
        return
    if isinstance(origem, pd.DataFrame) and not origem.empty:
        return

    tipo = _tipo_operacao_atual()
    with st.container(border=True):
        titulo = "### ⚡ Buscar estoque flash por site" if tipo == "estoque" else "### 🌐 Busca por site liberada após anexar o modelo"
        st.markdown(titulo)
        if tipo == "estoque":
            st.caption("Modo atualização de estoque: busca rápida só de SKU/código, disponibilidade, quantidade e origem do estoque.")
        else:
            st.caption("O modelo Bling está preservado. Agora cole os links do fornecedor e busque os produtos.")
        raw_urls = st.text_area("Links do fornecedor", key="stable_site_urls_fallback", height=120)
        st.info(
            "📦 Estoque automático: se encontrar número real, usa o real. "
            "Se detectar disponível sem quantidade, usa o valor abaixo. "
            "Se detectar indisponível/sem estoque, usa 0."
        )
        estoque_padrao = st.number_input(
            "Estoque para disponível sem quantidade real",
            min_value=0,
            value=int(st.session_state.get("stable_estoque_padrao_fallback", 1000) or 1000),
            step=1,
            key="stable_estoque_padrao_fallback",
            help="Padrão automático: 1000. Se você trocar, o valor digitado substitui o 1000 apenas quando o produto estiver disponível sem quantidade real.",
        )
        tem_url = bool(str(raw_urls or "").strip())
        label_botao = "⚡ Buscar estoque flash" if tipo == "estoque" else "🚀 Buscar produtos por site"
        if st.button(label_botao, disabled=not tem_url, use_container_width=True, key="btn_site_fallback_modelo"):
            df = _crawl_site_df(raw_urls, int(estoque_padrao))
            if isinstance(df, pd.DataFrame) and not df.empty:
                st.rerun()


def run_stable_app() -> None:
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
        if str(label) == "Estoque padrão":
            label = "Estoque para disponível sem quantidade real"
            kwargs.setdefault(
                "help",
                "Padrão automático: 1000. Se você trocar, o valor digitado substitui o 1000 apenas quando o produto estiver disponível sem quantidade real.",
            )
            kwargs.setdefault("value", 1000)
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
