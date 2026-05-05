from __future__ import annotations

import re
from urllib.parse import urlparse

import pandas as pd
import streamlit as st

from bling_app_zero.ui.debug_panel import add_debug_log


def _split_urls(raw: str) -> list[str]:
    urls: list[str] = []
    seen: set[str] = set()
    for part in re.split(r"[\n,;\s]+", str(raw or "")):
        url = part.strip()
        if not url:
            continue
        if not url.startswith(("http://", "https://")):
            url = "https://" + url
        if url not in seen:
            seen.add(url)
            urls.append(url)
    return urls


def _codigo_from_url(url: str, index: int) -> str:
    parsed = urlparse(url)
    bits = [b for b in parsed.path.split("/") if b.strip()]
    candidate = bits[-1] if bits else parsed.netloc
    candidate = re.sub(r"[^A-Za-z0-9_-]+", "-", candidate).strip("-")
    return candidate[:60] or f"SITE-{index:04d}"


def _descricao_from_url(url: str, index: int) -> str:
    parsed = urlparse(url)
    bits = [b for b in parsed.path.split("/") if b.strip()]
    candidate = bits[-1] if bits else parsed.netloc
    candidate = re.sub(r"[-_]+", " ", candidate).strip()
    return candidate.title() if candidate else f"Produto capturado do site {index}"


def build_site_stock_dataframe(urls: list[str], deposito: str, estoque_padrao: int = 0) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for idx, url in enumerate(urls, start=1):
        titulo_produto = _descricao_from_url(url, idx)
        rows.append(
            {
                "Título do produto": titulo_produto,
                "Código": _codigo_from_url(url, idx),
                "Descrição": titulo_produto,
                "URL do produto": url,
                "Depósito": deposito,
                "Estoque": int(estoque_padrao),
                "Quantidade": int(estoque_padrao),
                "Origem": "site",
            }
        )
    return pd.DataFrame(rows).fillna("")


def render_site_stock_capture(*, deposito: str) -> pd.DataFrame | None:
    with st.expander("🌐 Captura por site", expanded=False):
        st.caption(
            "Use quando a atualização de estoque vier de links do fornecedor. "
            "O sistema cria uma base inicial e libera o próximo fluxo."
        )

        raw_urls = st.text_area(
            "Cole os links do site do fornecedor",
            value=str(st.session_state.get("site_urls_raw", "")),
            height=130,
            placeholder="https://fornecedor.com/produto-1\nhttps://fornecedor.com/produto-2",
            key="site_urls_raw_widget",
        )
        st.session_state["site_urls_raw"] = raw_urls

        estoque_padrao = st.number_input(
            "Estoque padrão quando o site não informar quantidade",
            min_value=0,
            value=int(st.session_state.get("site_estoque_padrao", 0) or 0),
            step=1,
            key="site_estoque_padrao_widget",
        )
        st.session_state["site_estoque_padrao"] = int(estoque_padrao)

        urls = _split_urls(raw_urls)
        if urls:
            st.caption(f"Links detectados: {len(urls)}")

        if st.button("🌐 Gerar base de estoque pelo site", use_container_width=True, disabled=not bool(urls)):
            if not str(deposito or "").strip():
                st.error("Informe o nome do depósito antes de gerar a base por site.")
                return None

            df = build_site_stock_dataframe(urls, deposito=str(deposito).strip(), estoque_padrao=int(estoque_padrao))
            st.session_state["df_origem"] = df
            st.session_state["tipo_origem"] = "site"
            st.session_state["tipo_operacao"] = "estoque"
            st.session_state["deposito_nome"] = str(deposito).strip()
            st.session_state["wizard_etapa_maxima"] = "mapeamento"
            add_debug_log("Captura por site", f"urls={len(urls)} deposito={deposito}")
            st.success("Base por site criada. O mapeamento já foi liberado.")
            return df

    return st.session_state.get("df_origem") if st.session_state.get("tipo_origem") == "site" else None
