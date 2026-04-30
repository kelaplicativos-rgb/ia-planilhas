from __future__ import annotations

import pandas as pd
import streamlit as st

from bling_app_zero.ui.origem_site_config import PRESETS, MOTORES_SITE
from bling_app_zero.ui.origem_site_execution import executar_busca
from bling_app_zero.ui.origem_site_state import limpar_busca_site, guardar_resultado
from bling_app_zero.ui.origem_site_utils import extrair_urls, url_valida
from bling_app_zero.ui.origem_site_visual import render_origem_site_visual_preview


def _obter_df_atual_site() -> pd.DataFrame | None:
    """
    Retorna o DataFrame atual da captura por site sem usar avaliação booleana
    direta de DataFrame.

    Pandas não permite expressões como `df_saida or df_origem`, porque um
    DataFrame não tem valor booleano único. Essa função evita o erro:
    ValueError: The truth value of a DataFrame is ambiguous.
    """
    df_saida = st.session_state.get("df_saida")
    df_origem = st.session_state.get("df_origem")

    if isinstance(df_saida, pd.DataFrame) and not df_saida.empty:
        return df_saida

    if isinstance(df_origem, pd.DataFrame) and not df_origem.empty:
        return df_origem

    return None


def render_origem_site_panel() -> None:
    with st.container(border=True):
        st.markdown("#### 🚀 Captura por site")

        urls_texto = st.text_area("URLs", height=100)
        urls = extrair_urls(urls_texto)

        col1, col2 = st.columns(2)
        with col1:
            preset_nome = st.selectbox("Modo", list(PRESETS.keys()))
        with col2:
            motor = st.selectbox("Motor", MOTORES_SITE)

        preset = PRESETS[preset_nome]

        c1, c2 = st.columns(2)
        with c1:
            executar = st.button("Buscar")
        with c2:
            limpar = st.button("Limpar")

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

            df = executar_busca(urls, preset, motor)

            if df.empty:
                st.warning("Nada encontrado")
                return

            guardar_resultado(df, urls, preset, motor)
            st.success(f"{len(df)} produtos encontrados")
            st.rerun()

    df_atual = _obter_df_atual_site()
    if df_atual is not None:
        render_origem_site_visual_preview(df_atual)
