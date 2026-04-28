from __future__ import annotations

import random
import time
from typing import Optional

import httpx


DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Connection": "keep-alive",
}


class HTMLFetcher:
    """
    Responsável por buscar o HTML da página (igual extensão Chrome faria).
    """

    def __init__(
        self,
        timeout: int = 20,
        max_retries: int = 3,
        delay_range: tuple = (0.5, 1.5),
    ):
        self.timeout = timeout
        self.max_retries = max_retries
        self.delay_range = delay_range

    def fetch(self, url: str) -> str:
        """
        Faz download do HTML da página.
        """

        url = self._normalize_url(url)

        last_error: Optional[Exception] = None

        for attempt in range(self.max_retries):
            try:
                response = httpx.get(
                    url,
                    headers=self._random_headers(),
                    timeout=self.timeout,
                    follow_redirects=True,
                )

                if response.status_code == 200:
                    return response.text

                last_error = Exception(f"Status code: {response.status_code}")

            except Exception as e:
                last_error = e

            time.sleep(random.uniform(*self.delay_range))

        raise Exception(f"Erro ao buscar HTML: {last_error}")

    def _normalize_url(self, url: str) -> str:
        url = str(url or "").strip()

        if not url:
            raise ValueError("URL vazia")

        if url.startswith("//"):
            url = "https:" + url

        if not url.startswith(("http://", "https://")):
            url = "https://" + url

        return url

    def _random_headers(self) -> dict:
        """
        Gera headers variáveis para evitar bloqueio
        """

        headers = DEFAULT_HEADERS.copy()

        user_agents = [
            DEFAULT_HEADERS["User-Agent"],
            "Mozilla/5.0 (Linux; Android 10)",
            "Mozilla/5.0 (iPhone; CPU iPhone OS 14_0 like Mac OS X)",
        ]

        headers["User-Agent"] = random.choice(user_agents)

        return headers


# função simples para uso direto
def fetch_html(url: str) -> str:
    fetcher = HTMLFetcher()
    return fetcher.fetch(url)
