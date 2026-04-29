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

    def fetch(self, url: str) -> str:
        url = self._normalize_url(url)

        if not url:
            self.last_error = "URL vazia"
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
                            return html[:MAX_HTML_CHARS]

                        last_error = Exception(
                            f"Resposta sem HTML útil | status={response.status_code} | url={tentativa_url}"
                        )

                    except Exception as exc:
                        last_error = exc

                    time.sleep(random.uniform(*self.delay_range))

        self.last_error = f"Erro ao buscar HTML: {last_error}"
        return ""

    def _extrair_html_response(self, response: httpx.Response) -> str:
        status = int(getattr(response, "status_code", 0) or 0)

        if status >= 400:
            return ""

        content_type = str(response.headers.get("content-type", "")).lower()
        texto = response.text or ""

        if not texto.strip():
            return ""

        if "text/html" not in content_type and "<html" not in texto.lower():
            return ""

        if self._parece_bloqueio(texto):
            return ""

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
        ]

        return any(sinal in texto for sinal in sinais_bloqueio)

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
def fetch_html(url: str) -> str:
    fetcher = HTMLFetcher()
    return fetcher.fetch(url)


def limpar_cache_html() -> None:
    fetch_html.cache_clear()
