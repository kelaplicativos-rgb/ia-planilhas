from __future__ import annotations

from typing import Any

import pandas as pd
import streamlit as st

from bling_app_zero.stable import stable_app as base_app
from bling_app_zero.stable.megacenter_crawler import crawl_site_to_bling_dataframe
from bling_app_zero.stable.session_vault import guardar_df, restaurar_df


OLD_SITE_INFO = "Captura por site está liberada neste núcleo para atualização de estoque."
NEW_SITE_INFO = (
    "Captura por site real liberada para cadastro e atualização de estoque. "
    "Cole o domínio, categoria ou links de produtos. O sistema procura produtos, entra em cada página "
    "e tenta capturar descrição, código, preço, imagens e disponibilidade/estoque."
)


def _crawl_site_df(raw_urls: str, estoque_padrao: int) -> pd.DataFrame:
    with st.spinner("Buscando produtos no site, entrando nas páginas e capturando dados..."):
        df = crawl_site_to_bling_dataframe(raw_urls, estoque_padrao=estoque_padrao)
    if df is None or df.empty:
        st.warning("Nenhum produto foi capturado. Tente colar links de categorias ou produtos específicos.")
        return pd.DataFrame()
    df = guardar_df("stable_df_origem", df)
    st.success(f"Captura real finalizada e travada: {len(df)} produto(s) encontrado(s).")
    return df


def _render_busca_site_independente() -> None:
    """Fallback para quando o modelo Bling foi anexado e a origem ainda não existe.

    Isso evita a sensação de que o modelo travou a busca: o usuário pode iniciar
    a captura por site fora da aba, e o resultado cai na mesma chave stable_df_origem.
    """
    modelo = restaurar_df("stable_df_modelo")
    origem = restaurar_df("stable_df_origem")
    if not isinstance(modelo, pd.DataFrame) or modelo.empty:
        return
    if isinstance(origem, pd.DataFrame) and not origem.empty:
        return

    with st.container(border=True):
        st.markdown("### 🌐 Busca por site liberada após anexar o modelo")
        st.caption("O modelo Bling está preservado. Agora cole os links do fornecedor e busque os produtos.")
        raw_urls = st.text_area("Links do fornecedor", key="stable_site_urls_fallback", height=120)
        estoque_padrao = st.number_input(
            "Estoque padrão",
            min_value=0,
            value=int(st.session_state.get("stable_estoque_padrao_fallback", 0) or 0),
            step=1,
            key="stable_estoque_padrao_fallback",
        )
        tem_url = bool(str(raw_urls or "").strip())
        if st.button("🚀 Buscar produtos por site", disabled=not tem_url, use_container_width=True, key="btn_site_fallback_modelo"):
            df = _crawl_site_df(raw_urls, int(estoque_padrao))
            if isinstance(df, pd.DataFrame) and not df.empty:
                st.rerun()


def run_stable_app() -> None:
    original_button = st.button
    original_info = st.info
    original_site_df = base_app._site_df

    def patched_button(label: str, *args: Any, **kwargs: Any):
        if label == "Gerar base por site":
            kwargs["disabled"] = False
        return original_button(label, *args, **kwargs)

    def patched_info(body: Any, *args: Any, **kwargs: Any):
        if str(body) == OLD_SITE_INFO:
            body = NEW_SITE_INFO
        return original_info(body, *args, **kwargs)

    st.button = patched_button
    st.info = patched_info
    base_app._site_df = _crawl_site_df
    try:
        base_app.run_stable_app()
        _render_busca_site_independente()
    finally:
        st.button = original_button
        st.info = original_info
        base_app._site_df = original_site_df
