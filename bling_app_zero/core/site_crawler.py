from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any
from urllib.parse import urljoin, urlparse

import pandas as pd
import streamlit as st
from bs4 import BeautifulSoup

from bling_app_zero.core.fetch_router import fetch_payload_router
from bling_app_zero.core.site_crawler_extractors import extrair_produto_crawler
from bling_app_zero.core.site_crawler_helpers import (
    MAX_PAGINAS,
    MAX_PRODUTOS,
    MAX_THREADS,
    extrair_links_paginacao_crawler,
    extrair_links_produtos_crawler,
    link_parece_produto_crawler,
)

# ==========================================================
# VERSION
# ==========================================================
SITE_CRAWLER_VERSION = "V2_MODULAR_IMG_FIX"


# ==========================================================
# LOG
# ==========================================================
try:
    from bling_app_zero.utils.excel_logs import log_debug
except Exception:
    def log_debug(*args, **kwargs):
        return None


# ==========================================================
# SAFE
# ==========================================================
def _safe_list(v: Any) -> list[Any]:
    return v if isinstance(v, list) else []


def _safe_int(valor: Any, padrao: int) -> int:
    try:
        n = int(valor)
        return n if n >= 0 else padrao
    except Exception:
        return padrao


def _safe_str(valor: Any) -> str:
    try:
        return str(valor or "").strip()
    except Exception:
        return ""


def _normalizar_estoque_df(valor: Any) -> int:
    try:
        if valor is None:
            return 0

        if isinstance(valor, bool):
            return 0

        texto = _safe_str(valor)
        if not texto:
            return 0

        numero = int(float(texto.replace(",", ".")))
        if numero < 0:
            return 0

        return numero
    except Exception:
        return 0


# ==========================================================
# IMAGENS
# ==========================================================
def _eh_url_imagem_invalida(url: str) -> bool:
    try:
        u = _safe_str(url).lower()
        if not u:
            return True

        tokens_ruins = [
            "facebook.com/tr",
            "facebook.net",
            "doubleclick.net",
            "google-analytics.com",
            "googletagmanager.com",
            "/pixel",
            "/track",
            "/tracking",
            "/collect",
            "fbclid=",
            "gclid=",
            "utm_",
            "sprite",
            "icon",
            "logo",
            "banner",
            "avatar",
            "placeholder",
            "spacer",
            "blank.",
            "loader",
            "loading",
            "favicon",
            "lazyload",
            "thumb",
            "thumbnail",
            "mini",
            "small",
        ]

        if any(token in u for token in tokens_ruins):
            return True

        if not u.startswith(("http://", "https://")):
            return True

        return False
    except Exception:
        return True


def _normalizar_url_imagem(url: str, base_url: str = "") -> str:
    try:
        txt = _safe_str(url)
        if not txt:
            return ""

        if txt.startswith("data:image"):
            return ""

        if "," in txt:
            partes = [p.strip() for p in txt.split(",") if p.strip()]
            for parte in partes:
                primeira = parte.split(" ")[0].strip()
                if primeira:
                    txt = primeira
                    break

        absoluto = urljoin(base_url, txt).strip() if base_url else txt.strip()
        if not absoluto.startswith(("http://", "https://")):
            return ""

        if _eh_url_imagem_invalida(absoluto):
            return ""

        return absoluto
    except Exception:
        return ""
