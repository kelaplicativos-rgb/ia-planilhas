# bling_app_zero/ui/origem_site_panel.py

from __future__ import annotations

import time
from typing import Any

import pandas as pd
import streamlit as st

from bling_app_zero.core.instant_scraper.click_selector import (
    gerar_opcoes_click_scraper,
    extrair_por_opcao_click,
)
from bling_app_zero.core.instant_scraper.runner import run_scraper
from bling_app_zero.core.instant_scraper.html_fetcher import fetch_html


def _txt(v: Any) -> str:
    return str(v or "").strip()


def _normalizar_url(url: str) -> str:
    url = _txt(url)
    if not url:
        return ""
    if url.startswith("//"):
        url = "https:" + url
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    return url


def _df_ok(df: Any) -> bool:
    return isinstance(df, pd.DataFrame) and not df.empty


def render_origem_site_panel() -> None:
    st.markdown("#### 🔥 Ultra Scraper (Click Mode)")
    st.caption("Escolha a estrutura igual extensão Chrome")

    url_input = st.text_input("URL do fornecedor")

    if st.button("🔍 Detectar estruturas"):
        url = _normalizar_url(url_input)

        if not url:
            st.error("Informe uma URL válida")
            return

        html = fetch_html(url)

        opcoes = gerar_opcoes_click_scraper(html, url)

        if not opcoes:
            st.error("Nenhuma estrutura detectada")
            return

        st.session_state["click_opcoes"] = opcoes
        st.session_state["click_url"] = url

    opcoes = st.session_state.get("click_opcoes", [])

    if opcoes:
        st.markdown("### 🧠 Estruturas detectadas")

        for opcao in opcoes:
            with st.container():
                st.markdown(f"### 🔹 Opção {opcao['id']} (score: {opcao['score']})")

                df = opcao["dataframe"]

                if _df_ok(df):
                    st.dataframe(df.head(10), use_container_width=True)

                col1, col2 = st.columns(2)

                with col1:
                    if st.button(f"Usar opção {opcao['id']}", key=f"use_{opcao['id']}"):
                        df_final = extrair_por_opcao_click(
                            html=fetch_html(st.session_state["click_url"]),
                            base_url=st.session_state["click_url"],
                            opcao_id=opcao["id"],
                        )

                        if _df_ok(df_final):
                            st.session_state["df_origem"] = df_final
                            st.success(f"{len(df_final)} produtos carregados")
                        else:
                            st.error("Falha ao extrair produtos")

                with col2:
                    if st.button(f"Auto (AI) {opcao['id']}", key=f"auto_{opcao['id']}"):
                        df_auto = run_scraper(st.session_state["click_url"])

                        if _df_ok(df_auto):
                            st.session_state["df_origem"] = df_auto
                            st.success(f"{len(df_auto)} produtos (modo automático)")
                        else:
                            st.error("Modo automático falhou")

    df_final = st.session_state.get("df_origem")

    if _df_ok(df_final):
        st.markdown("## ✅ Resultado final")

        st.dataframe(df_final.head(50), use_container_width=True)

        csv = df_final.to_csv(index=False, sep=";", encoding="utf-8-sig").encode("utf-8-sig")

        st.download_button(
            "⬇️ Baixar CSV",
            data=csv,
            file_name="produtos_click_scraper.csv",
            mime="text/csv",
        )
