from __future__ import annotations

import pandas as pd
import streamlit as st

from bling_app_zero.ui.origem_site_config import PRESETS
from bling_app_zero.ui.origem_site_execution import executar_busca
from bling_app_zero.ui.origem_site_state import limpar_busca_site, guardar_resultado
from bling_app_zero.ui.origem_site_utils import extrair_urls, url_valida
from bling_app_zero.ui.origem_site_visual import render_origem_site_visual_preview


def _obter_df_atual_site() -> pd.DataFrame | None:
    df_saida = st.session_state.get("df_saida")
    df_origem = st.session_state.get("df_origem")

    if isinstance(df_saida, pd.DataFrame) and not df_saida.empty:
        return df_saida

    if isinstance(df_origem, pd.DataFrame) and not df_origem.empty:
        return df_origem

    return None


def render_origem_site_panel() -> None:
    with st.container(border=True):
        st.markdown("#### 🚀 Captura por site (modo automático)")

        urls_texto = st.text_area("URLs", height=100)
        urls = extrair_urls(urls_texto)

        preset_nome = st.selectbox("Modo", list(PRESETS.keys()))
        preset = PRESETS[preset_nome]

        col1, col2 = st.columns(2)
        with col1:
            executar = st.button("🚀 Buscar automaticamente")
        with col2:
            limpar = st.button("🧹 Limpar")

        if limpar:
            limpar_busca_site()
            st.rerun()

        if executar:
            if not urls:
                st.error("Informe URLs")
                return

            invalidas = [u for u in urls if not url_valida(u)]
            if invalidas:
                st.error("URLs inválidas")
                return

            df = executar_busca(urls, preset, "AUTO_TODOS")

            if df.empty:
                st.warning("Nada encontrado")
                return

            guardar_resultado(df, urls, preset, "AUTO_TODOS")
            st.success(f"{len(df)} produtos encontrados (modo automático)")
            st.rerun()

    df_atual = _obter_df_atual_site()
    if df_atual is not None:
        render_origem_site_visual_preview(df_atual)
