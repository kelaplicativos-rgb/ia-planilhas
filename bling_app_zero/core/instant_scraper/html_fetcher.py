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
    "Cache-Control": "no-cache",
    "Pragma": "no-cache",
}


class HTMLFetcher:
    """
    Busca HTML sem derrubar o Streamlit.

    Regra:
    - tenta buscar com retries;
    - se falhar, retorna string vazia;
    - não lança Exception para a tela principal.
    """

    def __init__(
        self,
        timeout: int = 20,
        max_retries: int = 3,
        delay_range: tuple[float, float] = (0.5, 1.5),
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

        last_error: Optional[Exception] = None

        for _attempt in range(self.max_retries):
            try:
                response = httpx.get(
                    url,
                    headers=self._random_headers(),
                    timeout=self.timeout,
                    follow_redirects=True,
                )

                if response.status_code == 200 and response.text:
                    return response.text

                last_error = Exception(f"Status code: {response.status_code}")

            except Exception as e:
                last_error = e

            time.sleep(random.uniform(*self.delay_range))

        self.last_error = f"Erro ao buscar HTML: {last_error}"
        return ""

    def _normalize_url(self, url: str) -> str:
        url = str(url or "").strip()

        if not url:
            return ""

        if url.startswith("//"):
            url = "https:" + url

        if not url.startswith(("http://", "https://")):
            url = "https://" + url

        return url

    def _random_headers(self) -> dict:
        headers = DEFAULT_HEADERS.copy()

        user_agents = [
            DEFAULT_HEADERS["User-Agent"],
            (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/121.0.0.0 Safari/537.36"
            ),
            (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/121.0.0.0 Safari/537.36"
            ),
            (
                "Mozilla/5.0 (X11; Linux x86_64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
        ]

        headers["User-Agent"] = random.choice(user_agents)
        return headers


def fetch_html(url: str) -> str:
    fetcher = HTMLFetcher()
    return fetcher.fetch(url)
