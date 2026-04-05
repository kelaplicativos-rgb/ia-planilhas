from __future__ import annotations

from typing import Dict, List, Optional
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
    return url


def _trocar_scheme(url: str, scheme: str) -> str:
    p = urlparse(url)
    return urlunparse((scheme, p.netloc, p.path or "/", p.params, p.query, p.fragment))


def _trocar_www(url: str, usar_www: bool) -> str:
    p = urlparse(url)
    host = (p.netloc or "").strip()

    if not host:
        return url

    if usar_www:
        if host.startswith("www."):
            novo_host = host
        else:
            novo_host = f"www.{host}"
    else:
        novo_host = host[4:] if host.startswith("www.") else host

    return urlunparse((p.scheme, novo_host, p.path or "/", p.params, p.query, p.fragment))


def _gerar_urls_tentativa(url: str) -> List[str]:
    base = _normalizar_url(url)
    if not base:
        return []

    candidatos: List[str] = []
    vistos = set()

    def add(u: str) -> None:
        u = (u or "").strip()
        if u and u not in vistos:
            vistos.add(u)
            candidatos.append(u)

    add(base)

    https_sem_www = _trocar_www(_trocar_scheme(base, "https"), usar_www=False)
    https_com_www = _trocar_www(_trocar_scheme(base, "https"), usar_www=True)
    http_sem_www = _trocar_www(_trocar_scheme(base, "http"), usar_www=False)
    http_com_www = _trocar_www(_trocar_scheme(base, "http"), usar_www=True)

    add(https_sem_www)
    add(https_com_www)
    add(http_sem_www)
    add(http_com_www)

    return candidatos


def _criar_sessao() -> requests.Session:
    sessao = requests.Session()
    sessao.headers.update(DEFAULT_HEADERS)
    return sessao


def baixar_html(
    url: str,
    timeout: int = 20,
    verify_ssl: bool = True,
    max_redirects: int = 8,
) -> Dict:
    """
    Baixa HTML com fallback robusto para:
    - https/http
    - host com e sem www
    - retry com verify=False quando SSL falhar
    """
    url = _normalizar_url(url)
    if not url:
        return {
            "ok": False,
            "erro": "URL vazia.",
            "url": "",
            "html": "",
            "status_code": None,
            "content_type": "",
            "tentativas": [],
        }

    sessao = _criar_sessao()
    tentativas_log: List[Dict[str, object]] = []
    candidatos = _gerar_urls_tentativa(url)

    # ordem de tentativa:
    # 1) verify_ssl padrão
    # 2) fallback verify=False
    politicas_ssl = [verify_ssl]
    if verify_ssl:
        politicas_ssl.append(False)

    for verify in politicas_ssl:
        for candidata in candidatos:
            try:
                resposta = sessao.get(
                    candidata,
                    timeout=timeout,
                    allow_redirects=True,
                    verify=verify,
                )
                if len(resposta.history) > max_redirects:
                    raise requests.TooManyRedirects(
                        f"Redirecionamentos demais: {len(resposta.history)}"
                    )

                resposta.raise_for_status()

                content_type = resposta.headers.get("Content-Type", "")
                html = resposta.text or ""

                tentativas_log.append(
                    {
                        "url": candidata,
                        "ok": True,
                        "verify_ssl": verify,
                        "status_code": resposta.status_code,
                        "erro": "",
                    }
                )

                return {
                    "ok": True,
                    "erro": "",
                    "url": resposta.url,
                    "html": html,
                    "status_code": resposta.status_code,
                    "content_type": content_type,
                    "tentativas": tentativas_log,
                }

            except Exception as e:
                tentativas_log.append(
                    {
                        "url": candidata,
                        "ok": False,
                        "verify_ssl": verify,
                        "status_code": None,
                        "erro": str(e),
                    }
                )

    ultimo_erro = tentativas_log[-1]["erro"] if tentativas_log else "Falha desconhecida."
    return {
        "ok": False,
        "erro": str(ultimo_erro),
        "url": url,
        "html": "",
        "status_code": None,
        "content_type": "",
        "tentativas": tentativas_log,
    }
