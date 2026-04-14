from __future__ import annotations

import re
from typing import Any
from urllib.parse import urljoin, urlparse, urlunparse

HELPERS_VERSION = "V2_MODULAR_OK"
MAX_THREADS = 12
MAX_PAGINAS = 12
MAX_PRODUTOS = 1200


def normalizar_url_crawler(base_url: str, href: str | None) -> str:
    if not href:
        return ""

    href = str(href).strip()
    if not href:
        return ""

    url = urljoin(base_url, href)

    try:
        parsed = urlparse(url)
        url = urlunparse((parsed.scheme, parsed.netloc, parsed.path, "", "", ""))
    except Exception:
        pass

    return url


def url_mesmo_dominio_crawler(url_base: str, url: str) -> bool:
    try:
        d1 = urlparse(str(url_base or "")).netloc.replace("www.", "").lower()
        d2 = urlparse(str(url or "")).netloc.replace("www.", "").lower()

        if not d1 or not d2:
            return False

        return d1 == d2 or d2.endswith("." + d1) or d1.endswith("." + d2)
    except Exception:
        return False


def texto_limpo_crawler(valor: Any) -> str:
    return re.sub(r"\s+", " ", str(valor or "")).strip()


def numero_texto_crawler(valor: Any) -> str:
    texto = texto_limpo_crawler(valor)
    texto = texto.replace("R$", "").replace("r$", "").strip()

    m = re.search(r"(\d{1,3}(?:[\.\,]\d{3})*(?:[\.\,]\d{2}))", texto)
    if m:
        return m.group(1)

    m2 = re.search(r"(\d+)", texto)
    return m2.group(1) if m2 else ""
