from __future__ import annotations

from urllib.parse import urlparse


def normalizar_url(url: str) -> str:
    valor = str(url or "").strip()
    if not valor:
        return ""
    if not valor.startswith(("http://", "https://")):
        valor = "https://" + valor
    return valor.rstrip("/")


def url_valida(url: str) -> bool:
    try:
        parsed = urlparse(normalizar_url(url))
        return parsed.scheme in {"http", "https"} and bool(parsed.netloc)
    except Exception:
        return False


def extrair_urls(texto: str) -> list[str]:
    urls: list[str] = []
    vistos: set[str] = set()

    conteudo = str(texto or "").replace(",", "\n").replace(";", "\n")
    for linha in conteudo.splitlines():
        url = normalizar_url(linha)
        if not url or url in vistos:
            continue
        vistos.add(url)
        urls.append(url)

    return urls
