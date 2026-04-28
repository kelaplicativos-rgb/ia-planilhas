from __future__ import annotations

from typing import List
from urllib.parse import urljoin, urlparse, parse_qs, urlencode, urlunparse

from bs4 import BeautifulSoup


class PaginationDetector:
    def __init__(self, base_url: str, html: str):
        self.base_url = self._normalize_url(base_url)
        self.html = html or ""
        self.soup = BeautifulSoup(self.html, "lxml")

    def detect_next_urls(self, max_pages: int = 10) -> List[str]:
        urls = []

        urls.extend(self._detect_links_next())
        urls.extend(self._generate_query_pages(max_pages=max_pages))
        urls.extend(self._generate_path_pages(max_pages=max_pages))

        final = []
        seen = set()

        for url in urls:
            url = self._normalize_url(url)
            if not url:
                continue
            if url == self.base_url:
                continue
            if url in seen:
                continue
            seen.add(url)
            final.append(url)

        return final[:max_pages]

    def _detect_links_next(self) -> List[str]:
        candidates = []

        words = [
            "próxima",
            "proxima",
            "next",
            "seguinte",
            "mais",
            ">",
            "›",
            "»",
        ]

        for a in self.soup.find_all("a", href=True):
            text = a.get_text(" ", strip=True).lower()
            rel = " ".join(a.get("rel", [])).lower()
            aria = str(a.get("aria-label", "")).lower()
            cls = " ".join(a.get("class", [])).lower()

            combined = f"{text} {rel} {aria} {cls}"

            if any(word in combined for word in words):
                candidates.append(urljoin(self.base_url, a["href"]))

        return candidates

    def _generate_query_pages(self, max_pages: int = 10) -> List[str]:
        parsed = urlparse(self.base_url)
        query = parse_qs(parsed.query)

        urls = []

        possible_keys = ["page", "pagina", "p", "pg"]

        for key in possible_keys:
            for page in range(2, max_pages + 1):
                new_query = dict(query)
                new_query[key] = [str(page)]

                query_string = urlencode(new_query, doseq=True)

                new_url = urlunparse(
                    (
                        parsed.scheme,
                        parsed.netloc,
                        parsed.path,
                        parsed.params,
                        query_string,
                        parsed.fragment,
                    )
                )

                urls.append(new_url)

        return urls

    def _generate_path_pages(self, max_pages: int = 10) -> List[str]:
        base = self.base_url.rstrip("/")
        urls = []

        for page in range(2, max_pages + 1):
            urls.append(f"{base}/page/{page}")
            urls.append(f"{base}/pagina/{page}")
            urls.append(f"{base}/p/{page}")

        return urls

    def _normalize_url(self, url: str) -> str:
        url = str(url or "").strip()

        if not url:
            return ""

        if url.startswith("//"):
            url = "https:" + url

        if not url.startswith(("http://", "https://")):
            url = "https://" + url

        return url
