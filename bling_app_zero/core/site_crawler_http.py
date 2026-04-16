from __future__ import annotations

import time
from urllib.parse import parse_qsl, urlencode, urljoin, urlparse, urlunparse

import requests

from bling_app_zero.core.site_crawler_cleaners import (
    mesmo_dominio,
    normalizar_texto,
    safe_str,
)
from bling_app_zero.core.site_crawler_config import (
    HEADERS,
    STOP_EXTENSIONS,
    STOP_URL_HINTS,
)


def get_session() -> requests.Session:
    sess = requests.Session()
    sess.headers.update(HEADERS)
    return sess


def fetch_html_retry(
    url: str,
    timeout: int = 20,
    tentativas: int = 3,
    backoff: float = 1.2,
) -> str:
    sess = get_session()
    ultimo_erro = None

    for tentativa in range(1, tentativas + 1):
        try:
            resp = sess.get(url, timeout=timeout, allow_redirects=True)
            resp.raise_for_status()
            return resp.text
        except Exception as exc:
            ultimo_erro = exc
            if tentativa < tentativas:
                time.sleep(backoff * tentativa)

    raise ultimo_erro if ultimo_erro else RuntimeError("Falha ao buscar HTML")


def normalizar_link_crawl(base_url: str, href: str) -> str:
    href = safe_str(href)
    if not href:
        return ""

    url = urljoin(base_url, href)
    url = url.split("#")[0].strip()

    parsed = urlparse(url)
    query_items = []

    if parsed.query:
        for chave, valor in parse_qsl(parsed.query, keep_blank_values=True):
            chave_l = safe_str(chave).lower()
            if chave_l.startswith("utm_"):
                continue
            if chave_l in {
                "fbclid",
                "gclid",
                "sort",
                "order",
                "dir",
                "variant",
                "view",
                "sessionid",
                "sid",
            }:
                continue
            query_items.append((chave, valor))

    url = urlunparse(
        (
            parsed.scheme,
            parsed.netloc,
            parsed.path.rstrip("/"),
            parsed.params,
            urlencode(query_items, doseq=True),
            "",
        )
    )

    return url.rstrip("/")


def url_valida_para_crawl(base_url: str, url: str) -> bool:
    url = safe_str(url)
    if not url:
        return False
    if not url.startswith(("http://", "https://")):
        return False
    if not mesmo_dominio(base_url, url):
        return False

    url_l = normalizar_texto(url)
    if any(ext in url_l for ext in STOP_EXTENSIONS):
        return False
    if any(h in url_l for h in STOP_URL_HINTS):
        return False
    if url_l.startswith(("mailto:", "tel:", "javascript:", "#")):
        return False

    return True
