from __future__ import annotations

from typing import Dict, List
from urllib.parse import urlparse, urlunparse

import requests
import urllib3


DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8",
    "Accept": (
        "text/html,application/xhtml+xml,application/xml;q=0.9,"
        "image/avif,image/webp,image/apng,*/*;q=0.8"
    ),
    "Cache-Control": "no-cache",
    "Pragma": "no-cache",
}


def _normalizar_url(url: str) -> str:
    url = (url or "").strip()
    if not url:
        return ""
    if not url.lower().startswith(("http://", "https://")):
        url = f"https://{url}"
    return url


def _trocar_www(url: str) -> str:
    try:
        parsed = urlparse(url)
        host = (parsed.netloc or "").strip()
        if not host:
            return url

        if host.startswith("www."):
            novo_host = host[4:]
        else:
            novo_host = f"www.{host}"

        return urlunparse(
            (
                parsed.scheme or "https",
                novo_host,
                parsed.path or "",
                parsed.params or "",
                parsed.query or "",
                parsed.fragment or "",
            )
        )
    except Exception:
        return url


def _urls_candidatas(url: str) -> List[str]:
    url = _normalizar_url(url)
    if not url:
        return []

    candidatos: List[str] = [url]

    alternada = _trocar_www(url)
    if alternada and alternada not in candidatos:
        candidatos.append(alternada)

    if url.startswith("https://"):
        http_url = "http://" + url[len("https://") :]
        if http_url not in candidatos:
            candidatos.append(http_url)

        alternada_http = _trocar_www(http_url)
        if alternada_http and alternada_http not in candidatos:
            candidatos.append(alternada_http)

    return candidatos


def _fazer_request(
    session: requests.Session,
    url: str,
    timeout: int,
    verify: bool = True,
) -> requests.Response:
    return session.get(
        url,
        headers=DEFAULT_HEADERS,
        timeout=timeout,
        allow_redirects=True,
        verify=verify,
    )


def baixar_html(url: str, timeout: int = 20) -> Dict:
    url = _normalizar_url(url)
    if not url:
        return {"ok": False, "erro": "URL vazia.", "url": url, "html": ""}

    session = requests.Session()
    erros: List[str] = []

    for candidata in _urls_candidatas(url):
        try:
            resposta = _fazer_request(session, candidata, timeout=timeout, verify=True)
            resposta.raise_for_status()

            content_type = resposta.headers.get("Content-Type", "")
            html = resposta.text or ""

            return {
                "ok": True,
                "erro": "",
                "url": resposta.url,
                "status_code": resposta.status_code,
                "content_type": content_type,
                "html": html,
                "ssl_verify": "on",
            }

        except requests.exceptions.SSLError as e:
            erros.append(f"{candidata} -> SSL: {e}")

            host_original = (urlparse(candidata).netloc or "").lower()
            host_alternativo = (urlparse(_trocar_www(candidata)).netloc or "").lower()

            if host_original != host_alternativo:
                try:
                    resposta = _fazer_request(
                        session,
                        _trocar_www(candidata),
                        timeout=timeout,
                        verify=True,
                    )
                    resposta.raise_for_status()

                    content_type = resposta.headers.get("Content-Type", "")
                    html = resposta.text or ""

                    return {
                        "ok": True,
                        "erro": "",
                        "url": resposta.url,
                        "status_code": resposta.status_code,
                        "content_type": content_type,
                        "html": html,
                        "ssl_verify": "on",
                    }
                except Exception as e2:
                    erros.append(f"{_trocar_www(candidata)} -> fallback host: {e2}")

            try:
                urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

                resposta = _fazer_request(
                    session,
                    candidata,
                    timeout=timeout,
                    verify=False,
                )
                resposta.raise_for_status()

                content_type = resposta.headers.get("Content-Type", "")
                html = resposta.text or ""

                return {
                    "ok": True,
                    "erro": "",
                    "url": resposta.url,
                    "status_code": resposta.status_code,
                    "content_type": content_type,
                    "html": html,
                    "ssl_verify": "off",
                }
            except Exception as e3:
                erros.append(f"{candidata} -> sem verificação SSL: {e3}")

        except Exception as e:
            erros.append(f"{candidata} -> {e}")

    return {
        "ok": False,
        "erro": " | ".join(erros) if erros else "Falha desconhecida ao acessar a URL.",
        "url": url,
        "html": "",
    }
