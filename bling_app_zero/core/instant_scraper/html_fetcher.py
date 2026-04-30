from __future__ import annotations

import random
import re
import time
from functools import lru_cache
from typing import Optional
from urllib.parse import urlparse, urlunparse

import httpx


MAX_HTML_CHARS = 800_000

DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/123.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
    "Cache-Control": "no-cache",
    "Pragma": "no-cache",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
}


LAST_FETCH_INFO = {
    "url": "",
    "url_final": "",
    "status_code": "",
    "content_type": "",
    "html_chars": 0,
    "erro": "",
    "motivo": "",
    "parece_bloqueio": False,
    "parece_javascript": False,
    "cache": "",
}


def _txt(valor) -> str:
    return str(valor or "").strip()


def _registrar_fetch_info(**kwargs) -> None:
    for chave in list(LAST_FETCH_INFO.keys()):
        if chave in kwargs:
            LAST_FETCH_INFO[chave] = kwargs[chave]


def obter_ultimo_fetch_info() -> dict:
    return dict(LAST_FETCH_INFO)


class HTMLFetcher:
    def __init__(
        self,
        timeout: int = 20,
        max_retries: int = 2,
        delay_range: tuple[float, float] = (0.25, 0.8),
    ):
        self.timeout = timeout
        self.max_retries = max_retries
        self.delay_range = delay_range
        self.last_error: str = ""
        self.last_info: dict = {}

    def fetch(self, url: str) -> str:
        url = self._normalize_url(url)

        self.last_info = {
            "url": url,
            "url_final": "",
            "status_code": "",
            "content_type": "",
            "html_chars": 0,
            "erro": "",
            "motivo": "",
            "parece_bloqueio": False,
            "parece_javascript": False,
            "cache": "fresh",
        }
        _registrar_fetch_info(**self.last_info)

        if not url:
            self.last_error = "URL vazia"
            self._set_last_info(erro=self.last_error, motivo="url_vazia")
            return ""

        urls_tentativa = self._gerar_variacoes_url(url)
        last_error: Optional[Exception] = None

        with httpx.Client(timeout=self.timeout, follow_redirects=True) as client:
            for tentativa_url in urls_tentativa:
                for _attempt in range(self.max_retries):
                    try:
                        response = client.get(
                            tentativa_url,
                            headers=self._random_headers(referer=tentativa_url),
                        )

                        html = self._extrair_html_response(response)

                        if html:
                            self.last_error = ""
                            self._set_last_info(
                                url_final=str(response.url),
                                status_code=str(response.status_code),
                                content_type=str(response.headers.get("content-type", "")),
                                html_chars=len(html),
                                erro="",
                                motivo=self.last_info.get("motivo") or "ok",
                            )
                            return html[:MAX_HTML_CHARS]

                        motivo = self.last_info.get("motivo") or "sem_html_util"
                        last_error = Exception(
                            f"Resposta sem HTML útil | status={response.status_code} | motivo={motivo} | url={tentativa_url}"
                        )

                    except Exception as exc:
                        last_error = exc
                        self._set_last_info(
                            url_final=tentativa_url,
                            erro=str(exc),
                            motivo="erro_requisicao",
                        )

                    time.sleep(random.uniform(*self.delay_range))

        self.last_error = f"Erro ao buscar HTML: {last_error}"
        self._set_last_info(erro=self.last_error)
        return ""

    def _set_last_info(self, **kwargs) -> None:
        self.last_info.update(kwargs)
        _registrar_fetch_info(**self.last_info)

    def _extrair_html_response(self, response: httpx.Response) -> str:
        status = int(getattr(response, "status_code", 0) or 0)
        content_type = str(response.headers.get("content-type", "")).lower()
        texto = response.text or ""

        self._set_last_info(
            url_final=str(getattr(response, "url", "") or ""),
            status_code=str(status),
            content_type=content_type,
            html_chars=len(texto),
        )

        if status >= 400:
            self._set_last_info(motivo=f"http_{status}")
            return ""

        if not texto.strip():
            self._set_last_info(motivo="resposta_vazia")
            return ""

        if "text/html" not in content_type and "<html" not in texto.lower():
            self._set_last_info(motivo="conteudo_nao_html")
            return ""

        if self._parece_bloqueio(texto):
            if len(texto) > 200_000:
                self._set_last_info(
                    motivo="possivel_falso_antibot_html_grande",
                    parece_bloqueio=False,
                    parece_javascript=self._parece_dependente_js(texto),
                )
                return texto[:MAX_HTML_CHARS]

            self._set_last_info(
                motivo="bloqueio_ou_antibot",
                parece_bloqueio=True,
                parece_javascript=self._parece_dependente_js(texto),
            )
            return ""

        if self._parece_dependente_js(texto):
            self._set_last_info(
                motivo="pagina_possivelmente_dependente_de_javascript",
                parece_javascript=True,
            )

        return texto[:MAX_HTML_CHARS]

    def _parece_bloqueio(self, html: str) -> bool:
        texto = re.sub(r"\s+", " ", str(html or "").lower())

        sinais_bloqueio = [
            "access denied",
            "forbidden",
            "captcha",
            "cloudflare",
            "checking your browser",
            "verificando seu navegador",
            "enable javascript",
            "ative o javascript",
            "blocked",
            "bot detection",
            "unusual traffic",
            "request blocked",
            "security check",
            "cf-browser-verification",
        ]

        return any(sinal in texto for sinal in sinais_bloqueio)

    def _parece_dependente_js(self, html: str) -> bool:
        texto = re.sub(r"\s+", " ", str(html or "").lower())

        sinais_js = [
            "enable javascript",
            "ative o javascript",
            "noscript",
            "__next_data__",
            "window.__nuxt__",
            "id=\"__next\"",
            "id='__next'",
            "data-reactroot",
        ]

        tem_sinal_js = any(sinal in texto for sinal in sinais_js)
        poucos_produtos = not any(
            sinal in texto
            for sinal in ["produto", "preço", "preco", "comprar", "r$", "add to cart"]
        )

        return bool(tem_sinal_js and poucos_produtos)

    def _normalize_url(self, url: str) -> str:
        url = str(url or "").strip()

        if not url:
            return ""

        if url.startswith("//"):
            url = "https:" + url

        if not url.startswith(("http://", "https://")):
            url = "https://" + url

        parsed = urlparse(url)

        scheme = parsed.scheme or "https"
        netloc = parsed.netloc.strip()
        path = parsed.path or "/"

        if not netloc:
            return ""

        return urlunparse((scheme, netloc, path, "", parsed.query, ""))

    def _gerar_variacoes_url(self, url: str) -> list[str]:
        parsed = urlparse(url)
        host = parsed.netloc

        urls = [url]

        if host.startswith("www."):
            urls.append(urlunparse(parsed._replace(netloc=host[4:])))
        else:
            urls.append(urlunparse(parsed._replace(netloc=f"www.{host}")))

        if parsed.scheme == "https":
            urls.append(urlunparse(parsed._replace(scheme="http")))
        elif parsed.scheme == "http":
            urls.append(urlunparse(parsed._replace(scheme="https")))

        vistos = set()
        final = []

        for item in urls:
            if item and item not in vistos:
                vistos.add(item)
                final.append(item)

        return final

    def _random_headers(self, referer: str = "") -> dict:
        headers = DEFAULT_HEADERS.copy()

        user_agents = [
            DEFAULT_HEADERS["User-Agent"],
            (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            (
                "Mozilla/5.0 (X11; Linux x86_64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/123.0.0.0 Safari/537.36"
            ),
        ]

        headers["User-Agent"] = random.choice(user_agents)

        if referer:
            headers["Referer"] = referer

        return headers


@lru_cache(maxsize=32)
def _fetch_html_cached(url: str) -> str:
    fetcher = HTMLFetcher()
    html = fetcher.fetch(url)
    info = fetcher.last_info.copy()
    info["cache"] = "cached_or_fresh"
    _registrar_fetch_info(**info)
    return html


def fetch_html(url: str, force_refresh: bool = False) -> str:
    url = _txt(url)
    if force_refresh:
        limpar_cache_html()
        fetcher = HTMLFetcher()
        html = fetcher.fetch(url)
        info = fetcher.last_info.copy()
        info["cache"] = "fresh_forced"
        _registrar_fetch_info(**info)
        return html

    return _fetch_html_cached(url)


def fetch_html_sem_cache(url: str) -> str:
    return fetch_html(url, force_refresh=True)


def limpar_cache_html() -> None:
    _fetch_html_cached.cache_clear()
    _registrar_fetch_info(cache="cleared")
