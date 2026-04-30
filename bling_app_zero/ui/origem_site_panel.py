from __future__ import annotations

from urllib.parse import urlparse

import pandas as pd
import streamlit as st

from bling_app_zero.core.site_crawler import CrawlConfig, crawl_site


def _normalizar_url(url: str) -> str:
    valor = str(url or "").strip()
    if not valor:
        return ""
    if not valor.startswith(("http://", "https://")):
        valor = "https://" + valor
    return valor.rstrip("/")


def _url_valida(url: str) -> bool:
    try:
        parsed = urlparse(url)
        return parsed.scheme in {"http", "https"} and bool(parsed.netloc)
    except Exception:
        return False


def _normalizar_df_site(df: pd.DataFrame) -> pd.DataFrame:
    if not isinstance(df, pd.DataFrame) or df.empty:
        return pd.DataFrame()

    base = df.copy().fillna("")
    base.columns = [str(c).strip() for c in base.columns]

    return base


def _guardar_resultado_site(df: pd.DataFrame, url: str) -> None:
    st.session_state["df_origem"] = df
    st.session_state["origem_upload_nome"] = url
    st.session_state["origem_upload_tipo"] = "site"


def render_origem_site_panel() -> None:
    url = st.text_input("URL do fornecedor", key="origem_site_url")

    if st.button("Buscar produtos"):
        url = _normalizar_url(url)

        if not _url_valida(url):
            st.error("URL inválida")
            return

        progress = st.progress(0)

        def cb(p, msg, total):
            progress.progress(int(p))

        df = crawl_site(url, CrawlConfig(), cb)
        df = _normalizar_df_site(df)

        if df.empty:
            st.warning("Nenhum produto encontrado")
            return

        _guardar_resultado_site(df, url)

        st.success(f"{len(df)} produtos encontrados")
        st.dataframe(df.head(50), use_container_width=True)
