
from __future__ import annotations

import time
from typing import Any
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


# ============================================================
# SESSÃO / AUTH
# ============================================================

def _auth_context_valido(auth_context: dict[str, Any] | None) -> bool:
    if not isinstance(auth_context, dict):
        return False
    return bool(auth_context.get("session_ready", False))


def _normalizar_headers_auth(headers: dict[str, Any] | None) -> dict[str, str]:
    if not isinstance(headers, dict):
        return {}

    saida: dict[str, str] = {}
    for chave, valor in headers.items():
        k = safe_str(chave)
        v = safe_str(valor)
        if k and v:
            saida[k] = v
    return saida


def get_session(auth_context: dict[str, Any] | None = None) -> requests.Session:
    sess = requests.Session()
    sess.headers.update(HEADERS)

    if not _auth_context_valido(auth_context):
        return sess

    headers = _normalizar_headers_auth(auth_context.get("headers"))
    if headers:
        sess.headers.update(headers)

    cookies = auth_context.get("cookies", [])
    if isinstance(cookies, list):
        for cookie in cookies:
            if not isinstance(cookie, dict):
                continue

            nome = safe_str(cookie.get("name"))
            valor = safe_str(cookie.get("value"))
            dominio = safe_str(cookie.get("domain"))
            path = safe_str(cookie.get("path")) or "/"

            if not nome:
                continue

            try:
                sess.cookies.set(
                    nome,
                    valor,
                    domain=dominio or None,
                    path=path,
                )
            except Exception:
                continue

    return sess


def _parece_login_ou_bloqueio(html: str, final_url: str = "") -> bool:
    page = safe_str(html).lower()
    final_url_n = safe_str(final_url).lower()

    sinais = [
        "/login",
        "acesse sua conta",
        "fazer login",
        "insira seus dados",
        "type=\"password\"",
        "name=\"password\"",
        "g-recaptcha",
        "recaptcha",
        "não sou um robô",
        "nao sou um robo",
    ]

    if any(sinal in final_url_n for sinal in ["/login", "/auth", "/signin"]):
        return True

    if any(sinal in page for sinal in sinais):
        return True

    return False


def _headers_navegacao(url: str) -> dict[str, str]:
    parsed = urlparse(url)
    origem = f"{parsed.scheme}://{parsed.netloc}" if parsed.scheme and parsed.netloc else ""
    headers = {
        "Referer": origem or url,
        "Cache-Control": "no-cache",
        "Pragma": "no-cache",
    }
    if origem:
        headers["Origin"] = origem
    return headers


# ============================================================
# FETCH
# ============================================================

def fetch_html_retry(
    url: str,
    timeout: int = 20,
    tentativas: int = 3,
    backoff: float = 1.2,
    auth_context: dict[str, Any] | None = None,
    accept_login_page: bool = False,
) -> str:
    sess = get_session(auth_context=auth_context)
    ultimo_erro = None
    url = safe_str(url)

    if not url:
        raise RuntimeError("URL vazia para busca de HTML")

    for tentativa in range(1, tentativas + 1):
        try:
            resp = sess.get(
                url,
                timeout=timeout,
                allow_redirects=True,
                headers=_headers_navegacao(url),
            )
            resp.raise_for_status()

            html = safe_str(resp.text)
            final_url = safe_str(resp.url)

            if not html:
                raise RuntimeError("Resposta HTML vazia")

            if not accept_login_page and _parece_login_ou_bloqueio(html, final_url=final_url):
                raise RuntimeError(f"Página de login/bloqueio detectada em {final_url}")

            return html

        except Exception as exc:
            ultimo_erro = exc
            if tentativa < tentativas:
                time.sleep(backoff * tentativa)

    raise ultimo_erro if ultimo_erro else RuntimeError("Falha ao buscar HTML")


# ============================================================
# NORMALIZAÇÃO DE LINKS
# ============================================================

def normalizar_link_crawl(base_url: str, href: str) -> str:
    href = safe_str(href)
    if not href:
        return ""

    if href.startswith(("mailto:", "tel:", "javascript:", "#")):
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
                "phpessid",
                "_token",
            }:
                continue

            query_items.append((chave, valor))

    path = parsed.path.rstrip("/") or "/"

    url = urlunparse(
        (
            parsed.scheme,
            parsed.netloc,
            path,
            parsed.params,
            urlencode(query_items, doseq=True),
            "",
        )
    )

    return url.rstrip("/") if url != f"{parsed.scheme}://{parsed.netloc}/" else url


# ============================================================
# VALIDAÇÃO DE URL
# ============================================================

def url_valida_para_crawl(base_url: str, url: str) -> bool:
    url = safe_str(url)
    if not url:
        return False

    if url.startswith(("mailto:", "tel:", "javascript:", "#")):
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

    bloqueios_extras = [
        "/logout",
        "/sair",
        "/signin",
        "/auth",
        "/register",
        "/cadastro",
        "/forgot",
        "/reset-password",
        "mailto:",
        "tel:",
        "javascript:",
    ]
    if any(h in url_l for h in bloqueios_extras):
        return False

    return True
