from __future__ import annotations

from typing import Dict, List, Optional, Tuple
from urllib.parse import urlparse, urlunparse

import requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept": (
        "text/html,application/xhtml+xml,application/xml;q=0.9,"
        "image/avif,image/webp,*/*;q=0.8"
    ),
    "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8",
    "Cache-Control": "no-cache",
    "Pragma": "no-cache",
}


def _normalizar_url(url: str) -> str:
    url = (url or "").strip()
    if not url:
        return ""

    if not url.startswith(("http://", "https://")):
        url = f"https://{url}"

    parsed = urlparse(url)
    scheme = (parsed.scheme or "https").lower()
    netloc = (parsed.netloc or "").strip().lower()
    path = parsed.path or "/"

    return urlunparse((scheme, netloc, path, "", parsed.query, ""))


def _variantes_url(url: str) -> List[str]:
    url = _normalizar_url(url)
    if not url:
        return []

    parsed = urlparse(url)
    netloc = parsed.netloc or ""
    path = parsed.path or "/"

    variantes: List[str] = []

    candidatos_host = [netloc]
    if netloc.startswith("www."):
        candidatos_host.append(netloc[4:])
    else:
        candidatos_host.append(f"www.{netloc}")

    candidatos_scheme = ["https", "http"]
    vistos = set()

    for scheme in candidatos_scheme:
        for host in candidatos_host:
            if not host:
                continue
            candidato = urlunparse((scheme, host, path, "", parsed.query, ""))
            if candidato not in vistos:
                vistos.add(candidato)
                variantes.append(candidato)

    return variantes


def _is_html_content_type(content_type: str) -> bool:
    valor = (content_type or "").lower()
    if not valor:
        return True
    return (
        "text/html" in valor
        or "application/xhtml+xml" in valor
        or "xml" in valor
        or "text/plain" in valor
    )


def _build_session() -> requests.Session:
    session = requests.Session()
    session.headers.update(DEFAULT_HEADERS)
    return session


def _tentar_request(
    session: requests.Session,
    url: str,
    timeout: int,
    verify_ssl: bool,
) -> Tuple[bool, Dict]:
    try:
        resposta = session.get(
            url,
            timeout=timeout,
            allow_redirects=True,
            verify=verify_ssl,
        )
        resposta.raise_for_status()

        content_type = resposta.headers.get("Content-Type", "")
        html = resposta.text or ""

        if not html.strip():
            return False, {
                "ok": False,
                "erro": "Resposta vazia.",
                "url": resposta.url or url,
                "status_code": resposta.status_code,
                "content_type": content_type,
                "html": "",
            }

        if not _is_html_content_type(content_type):
            return False, {
                "ok": False,
                "erro": f"Conteúdo não HTML: {content_type}",
                "url": resposta.url or url,
                "status_code": resposta.status_code,
                "content_type": content_type,
                "html": "",
            }

        return True, {
            "ok": True,
            "erro": "",
            "url": resposta.url or url,
            "status_code": resposta.status_code,
            "content_type": content_type,
            "html": html,
        }

    except Exception as e:
        return False, {
            "ok": False,
            "erro": str(e),
            "url": url,
            "status_code": None,
            "content_type": "",
            "html": "",
        }


def baixar_html(url: str, timeout: int = 20) -> Dict:
    """
    Faz download de HTML com fallback para:
    - normalização de URL
    - https/http
    - www/sem www
    - SSL verify on/off

    Mantém a interface pública já usada no projeto.
    """
    url = _normalizar_url(url)
    if not url:
        return {
            "ok": False,
            "erro": "URL vazia.",
            "url": "",
            "status_code": None,
            "content_type": "",
            "html": "",
        }

    session = _build_session()
    ultima_resposta: Optional[Dict] = None

    for variante in _variantes_url(url):
        for verify_ssl in (True, False):
            ok, resultado = _tentar_request(
                session=session,
                url=variante,
                timeout=timeout,
                verify_ssl=verify_ssl,
            )
            ultima_resposta = resultado
            if ok:
                return resultado

    return ultima_resposta or {
        "ok": False,
        "erro": "Falha desconhecida ao baixar HTML.",
        "url": url,
        "status_code": None,
        "content_type": "",
        "html": "",
    }
