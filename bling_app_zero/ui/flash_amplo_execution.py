from __future__ import annotations

"""Executor de UI para o Flash Amplo página por página.

Executa a captura rápida paralela, normaliza dados reais, salva os DataFrames
nas chaves esperadas pelo app e retorna o resultado.

Regra:
- Nenhum limite manual exposto na tela.
- Limite interno alto herdado do motor Flash Amplo.
- Sitemap entra por último apenas para completar URLs não detectadas.
- Se imagens vierem vazias, faz backfill usando Link Externo antes do mapeamento.
"""

from typing import Iterable

import pandas as pd
import streamlit as st

from bling_app_zero.core.flash_page_crawler import DEFAULT_MAX_PRODUCTS, DEFAULT_MAX_WORKERS
from bling_app_zero.core.instant_scraper import run_flash_amplo_page_mode
from bling_app_zero.core.product_data_quality import normalize_product_dataframe
from bling_app_zero.core.product_image_backfill import backfill_images_by_product_url
from bling_app_zero.ui.mapeamento.value_guard import clean_invalid_preview_mappings


def _normalize_urls(urls: Iterable[str] | str) -> list[str]:
    if isinstance(urls, str):
        raw_items = urls.replace("\r", "\n").split("\n")
    else:
        raw_items = list(urls)

    normalized: list[str] = []
    seen: set[str] = set()
    for item in raw_items:
        url = str(item or "").strip()
        if not url or url in seen:
            continue
        seen.add(url)
        normalized.append(url)
    return normalized


def preparar_dataframe_flash_amplo(df: pd.DataFrame) -> pd.DataFrame:
    """Aplica normalização, backfill de imagens e blindagem no resultado."""
    if not isinstance(df, pd.DataFrame):
        df = pd.DataFrame()
    if df.empty:
        return df.copy()

    normalized = normalize_product_dataframe(df.copy())
    with_images = backfill_images_by_product_url(normalized.copy())
    cleaned = clean_invalid_preview_mappings(with_images.copy())
    cleaned = backfill_images_by_product_url(cleaned.copy())
    return cleaned


def salvar_resultado_flash_amplo(df: pd.DataFrame) -> pd.DataFrame:
    """Salva o resultado nas chaves usadas pelo fluxo de origem/mapeamento."""
    cleaned = preparar_dataframe_flash_amplo(df)

    st.session_state["df_origem"] = cleaned.copy()
    st.session_state["df_origem_site"] = cleaned.copy()
    st.session_state["df_capturado_site"] = cleaned.copy()
    st.session_state.pop("df_preview_origem", None)
    st.session_state.pop("origem_preview_key", None)
    st.session_state["flash_amplo_page_by_page"] = True
    st.session_state["flash_amplo_total_produtos"] = int(len(cleaned))
    return cleaned


def executar_flash_amplo_pagina_por_pagina(
    urls: Iterable[str] | str,
    *,
    max_products: int = DEFAULT_MAX_PRODUCTS,
    max_workers: int = DEFAULT_MAX_WORKERS,
    show_progress: bool = True,
) -> pd.DataFrame:
    """Executa Flash Amplo com entrada em cada página de produto.

    A listagem/categoria descobre links primeiro. Sitemap complementa por último.
    A linha final vem da página real de cada produto.
    """
    seed_urls = _normalize_urls(urls)
    if not seed_urls:
        st.warning("Informe pelo menos uma URL de categoria, busca ou produto.")
        return pd.DataFrame()

    progress_bar = st.progress(0) if show_progress else None
    status = st.empty() if show_progress else None

    def progress_callback(done: int, total: int, url: str) -> None:
        if not show_progress:
            return
        progress = min(1.0, done / max(total, 1))
        if progress_bar is not None:
            progress_bar.progress(progress)
        if status is not None:
            status.caption(f"Flash Amplo: {done}/{total} páginas de produto lidas")

    df = run_flash_amplo_page_mode(
        seed_urls,
        max_products=max_products,
        max_workers=max_workers,
        progress_callback=progress_callback,
    )

    cleaned = salvar_resultado_flash_amplo(df)

    if show_progress:
        if progress_bar is not None:
            progress_bar.progress(1.0)
        if status is not None:
            total_com_imagem = 0
            if "URL Imagens Externas" in cleaned.columns:
                total_com_imagem = int(cleaned["URL Imagens Externas"].astype(str).str.strip().ne("").sum())
            status.success(
                f"Flash Amplo concluído: {len(cleaned)} produto(s), {total_com_imagem} com imagem."
            )

    return cleaned


executar_flash_amplo = executar_flash_amplo_pagina_por_pagina
run_flash_amplo_ui = executar_flash_amplo_pagina_por_pagina
