# bling_app_zero/ui/origem_site_panel.py

from __future__ import annotations

import time
from typing import Any

import pandas as pd
import streamlit as st

from bling_app_zero.core.site_agent import buscar_produtos_site_df


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
    return isinstance(df, pd.DataFrame) and not df.empty and len(df.columns) > 0


def _registrar_origem_site(df: pd.DataFrame, url: str) -> None:
    df = df.copy().fillna("")
    st.session_state["df_origem"] = df
    st.session_state["site_url_origem"] = url
    st.session_state["site_busca_status"] = "concluido"
    st.session_state["site_busca_total"] = len(df)


def _limpar_resultado_site() -> None:
    for chave in [
        "df_origem",
        "site_url_origem",
        "site_busca_status",
        "site_busca_total",
        "site_busca_fonte_descoberta",
        "site_busca_diagnostico_df",
        "site_busca_diagnostico_total_descobertos",
        "site_busca_diagnostico_total_validos",
        "site_busca_diagnostico_total_rejeitados",
    ]:
        st.session_state.pop(chave, None)


def _preview_qualidade(df: pd.DataFrame) -> None:
    if not _df_ok(df):
        return

    colunas = list(df.columns)

    nome_ok = "nome" in colunas and df["nome"].astype(str).str.strip().ne("").mean()
    preco_ok = "preco" in colunas and df["preco"].astype(str).str.strip().ne("").mean()
    url_ok = "url_produto" in colunas and df["url_produto"].astype(str).str.strip().ne("").mean()
    img_ok = "imagens" in colunas and df["imagens"].astype(str).str.strip().ne("").mean()

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Nome", f"{nome_ok:.0%}" if isinstance(nome_ok, float) else "0%")
    c2.metric("Preço", f"{preco_ok:.0%}" if isinstance(preco_ok, float) else "0%")
    c3.metric("URL", f"{url_ok:.0%}" if isinstance(url_ok, float) else "0%")
    c4.metric("Imagem", f"{img_ok:.0%}" if isinstance(img_ok, float) else "0%")


def render_origem_site_panel() -> None:
    st.markdown("#### Ultra Scraper IA")
    st.caption("Modo Instant Data Scraper: detecta tabelas, cards, listas e produtos sem crawler infinito.")

    url_digitada = st.text_input(
        "URL do fornecedor ou categoria",
        value=_txt(st.session_state.get("site_url_input", "")),
        placeholder="Ex.: https://www.megacentereletronicos.com.br",
        key="site_url_input",
    )

    c1, c2 = st.columns([2, 1])

    with c1:
        max_pages = st.slider(
            "Quantidade máxima de páginas",
            min_value=1,
            max_value=10,
            value=int(st.session_state.get("site_max_pages", 5) or 5),
            key="site_max_pages",
            help="Limite anti-loop. O scraper trabalha na página atual e em poucas paginações.",
        )

    with c2:
        modo_fluxo = st.selectbox(
            "Motor",
            ["instant", "inteligente"],
            index=0,
            key="site_modo_fluxo_ui",
            help="Instant = só Ultra Scraper. Inteligente = Ultra Scraper + fallbacks.",
        )

    b1, b2 = st.columns(2)

    with b1:
        executar = st.button(
            "🚀 Buscar produtos",
            key="btn_site_ultra_scraper",
            use_container_width=True,
            type="primary",
        )

    with b2:
        if st.button("🧹 Limpar busca", key="btn_limpar_site_ultra", use_container_width=True):
            _limpar_resultado_site()
            st.rerun()

    if executar:
        url = _normalizar_url(url_digitada)

        if not url:
            st.error("Informe uma URL válida para buscar.")
            return

        _limpar_resultado_site()
        st.session_state["site_busca_status"] = "executando"

        barra = st.progress(0)
        status = st.empty()

        inicio = time.time()

        try:
            status.info("🔎 Lendo página e detectando estrutura de produtos...")
            barra.progress(15)

            df = buscar_produtos_site_df(
                url,
                modo_fluxo_site=modo_fluxo,
                usar_instant_scraper=True,
                instant_max_pages=max_pages,
                limite_paginas=max_pages,
                varrer_site_completo=False,
                sitemap_completo=False,
                preferir_playwright=False,
            )

            barra.progress(75)
            status.info("🧠 Normalizando resultado e removendo duplicados...")

            if not _df_ok(df):
                barra.progress(100)
                st.session_state["site_busca_status"] = "vazio"
                status.error("Nenhum produto útil foi encontrado nessa página.")
                return

            _registrar_origem_site(df, url)

            tempo = int(time.time() - inicio)
            barra.progress(100)
            status.success(f"Busca concluída em {tempo}s com {len(df)} produto(s).")

        except Exception as exc:
            barra.progress(100)
            st.session_state["site_busca_status"] = "erro"
            status.error(f"Erro na busca por site: {exc}")
            return

    df_atual = st.session_state.get("df_origem")

    if _df_ok(df_atual):
        st.success(f"✅ Origem por site pronta: {len(df_atual)} produto(s).")

        fonte = _txt(st.session_state.get("site_busca_fonte_descoberta"))
        if fonte:
            st.caption(f"Motor usado: {fonte}")

        _preview_qualidade(df_atual)

        with st.expander("Preview dos produtos capturados", expanded=True):
            st.dataframe(df_atual.head(50), use_container_width=True)

        csv = df_atual.to_csv(index=False, sep=";", encoding="utf-8-sig").encode("utf-8-sig")

        st.download_button(
            "⬇️ Baixar preview CSV",
            data=csv,
            file_name="preview_site_ultra_scraper.csv",
            mime="text/csv",
            use_container_width=True,
            key="download_preview_site_ultra",
        )
