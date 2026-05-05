from __future__ import annotations

import re
from concurrent.futures import ThreadPoolExecutor
from typing import Any

import pandas as pd
import streamlit as st

from bling_app_zero.stable import stable_app as base_app
from bling_app_zero.stable import sitefix_patch
from bling_app_zero.stable.site_cadastro_normalizer import normalize_cadastro_site_dataframe
from bling_app_zero.stable.site_price_extractor import extract_price_from_url


def _tipo() -> str:
    return str(st.session_state.get("stable_tipo", "cadastro") or "cadastro").strip().lower()


def _norm(v: object) -> str:
    t = str(v or "").strip().lower()
    t = t.translate(str.maketrans("áàãâéêíóôõúç", "aaaaeeiooouc"))
    t = re.sub(r"[^a-z0-9]+", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def _unique(options: Any) -> list[Any]:
    out: list[Any] = []
    seen: set[str] = set()
    for item in list(options or []):
        key = "__blank__" if item == "" else _norm(item)
        if key in seen:
            continue
        seen.add(key)
        out.append(item)
    return out or [""]


def _is_deposito_label(label: object) -> bool:
    return "deposito" in _norm(label)


def _is_protected_cadastro_target(label: object) -> bool:
    n = _norm(label)
    return n == "id" or n.startswith("id produto") or n == "categoria" or n.startswith("categoria ")


def _clear_protected_cadastro_columns(df: pd.DataFrame) -> pd.DataFrame:
    if _tipo() != "cadastro" or not isinstance(df, pd.DataFrame) or df.empty:
        return df
    out = df.copy()
    for col in out.columns:
        if _is_protected_cadastro_target(col):
            out[col] = ""
    return out


def _safe_price(url: object) -> str:
    try:
        preco = extract_price_from_url(url)
        return preco if preco else "0,00"
    except Exception:
        return "0,00"


def _preco_from_urls_fast(urls: pd.Series) -> pd.Series:
    clean_urls = urls.astype(str).fillna("").tolist()
    if not clean_urls:
        return pd.Series([], index=urls.index)

    workers = min(8, max(1, len(clean_urls)))
    with ThreadPoolExecutor(max_workers=workers) as executor:
        valores = list(executor.map(_safe_price, clean_urls))

    return pd.Series(valores, index=urls.index)


def run_stable_app() -> None:
    original_selectbox = st.selectbox
    original_price = base_app._is_price_target
    original_suggest = base_app._suggest
    original_map_df = base_app._map_df
    original_preco_from_urls = getattr(sitefix_patch, "_preco_from_urls", None)
    original_product_crawler = getattr(sitefix_patch, "crawl_product_flash_dataframe", None)

    def selectbox(label: str, options, *args: Any, **kwargs: Any):
        if _tipo() == "cadastro" and _is_protected_cadastro_target(label):
            st.caption(f"{label}: mantido vazio. O Bling não aceita preencher este campo pela importação.")
            return ""

        if _tipo() == "estoque" and _is_deposito_label(label):
            key = str(kwargs.get("key") or f"stock_deposito_{_norm(label)}")
            return st.text_input(
                str(label),
                value=str(st.session_state.get(key, "")),
                key=key,
                placeholder="Ex.: Geral",
                help="Digite o depósito manualmente. O site não informa esse campo.",
            ).strip()

        old = list(options or [])
        new = _unique(old)
        idx = int(kwargs.get("index", 0) or 0)
        selected = old[idx] if 0 <= idx < len(old) else new[0]
        kwargs["index"] = new.index(selected) if selected in new else 0
        return original_selectbox(label, new, *args, **kwargs)

    def is_price(target: object) -> bool:
        if _tipo() == "estoque":
            return False
        return original_price(target)

    def suggest(target: str, source_columns: list[str]) -> str:
        if _tipo() == "cadastro" and _is_protected_cadastro_target(target):
            return ""
        return original_suggest(target, source_columns)

    def map_df(df, targets, mapping, deposito, calculated_price=None):
        mapped = original_map_df(df, targets, mapping, deposito, calculated_price=calculated_price)
        return _clear_protected_cadastro_columns(mapped)

    def cadastro_crawler(raw_urls: str):
        if original_product_crawler is None:
            return pd.DataFrame()
        df = original_product_crawler(raw_urls)
        return normalize_cadastro_site_dataframe(df, raw_urls=raw_urls)

    st.selectbox = selectbox
    base_app._is_price_target = is_price
    base_app._suggest = suggest
    base_app._map_df = map_df
    sitefix_patch._preco_from_urls = _preco_from_urls_fast
    if original_product_crawler is not None:
        sitefix_patch.crawl_product_flash_dataframe = cadastro_crawler
    try:
        sitefix_patch.run_stable_app()
    finally:
        st.selectbox = original_selectbox
        base_app._is_price_target = original_price
        base_app._suggest = original_suggest
        base_app._map_df = original_map_df
        if original_preco_from_urls is not None:
            sitefix_patch._preco_from_urls = original_preco_from_urls
        if original_product_crawler is not None:
            sitefix_patch.crawl_product_flash_dataframe = original_product_crawler
