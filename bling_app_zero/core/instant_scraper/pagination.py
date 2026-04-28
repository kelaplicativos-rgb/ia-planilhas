from __future__ import annotations

from typing import List
from urllib.parse import parse_qs, urlencode, urljoin, urlparse, urlunparse

from bs4 import BeautifulSoup


class PaginationDetector:
    """
    Detecta paginação com menos chute:
    - links next
    - links numéricos reais
    - URLs geradas por query/path como fallback
    """

    def __init__(self, base_url: str, html: str):
        self.base_url = self._normalize_url(base_url)
        self.html = html or ""
        self.soup = BeautifulSoup(self.html, "lxml")

    def detect_next_urls(self, max_pages: int = 10) -> List[str]:
        max_pages = max(1, int(max_pages or 1))

        urls: List[str] = []

        urls.extend(self._detect_links_next())
        urls.extend(self._detect_numbered_links())

        if len(urls) < max_pages:
            urls.extend(self._generate_query_pages(max_pages=max_pages))

        if len(urls) < max_pages:
            urls.extend(self._generate_path_pages(max_pages=max_pages))

        final: List[str] = []
        seen = set()

        for url in urls:
            url = self._normalize_url(url)

            if not url:
                continue

            if url == self.base_url:
                continue

            if url in seen:
                continue

            if not self._same_domain(url):
                continue

            seen.add(url)
            final.append(url)

            if len(final) >= max_pages:
                break

        return final

    def _detect_links_next(self) -> List[str]:
        candidates: List[str] = []

        words = [
            "próxima",
            "proxima",
            "next",
            "seguinte",
            "mais",
            "›",
            "»",
        ]

        for a in self.soup.find_all("a", href=True):
            text = a.get_text(" ", strip=True).lower()
            rel = " ".join(a.get("rel", [])).lower()
            aria = str(a.get("aria-label", "")).lower()
            title = str(a.get("title", "")).lower()
            cls = " ".join(a.get("class", [])).lower()
            href = str(a.get("href", "")).lower()

            combined = f"{text} {rel} {aria} {title} {cls} {href}"

            if any(word in combined for word in words):
                candidates.append(urljoin(self.base_url, a["href"]))

        return candidates

    def _detect_numbered_links(self) -> List[str]:
        candidates: List[tuple[int, str]] = []

        for a in self.soup.find_all("a", href=True):
            text = a.get_text(" ", strip=True)

            if not text.isdigit():
                continue

            try:
                number = int(text)
            except Exception:
                continue

            if number <= 1:
                continue

            href = urljoin(self.base_url, a["href"])
            candidates.append((number, href))

        candidates = sorted(candidates, key=lambda x: x[0])
        return [url for _, url in candidates]

    def _generate_query_pages(self, max_pages: int = 10) -> List[str]:
        parsed = urlparse(self.base_url)
        query = parse_qs(parsed.query)

        urls: List[str] = []
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
        urls: List[str] = []

        for page in range(2, max_pages + 1):
            urls.append(f"{base}/page/{page}")
            urls.append(f"{base}/pagina/{page}")
            urls.append(f"{base}/p/{page}")

        return urls

    def _same_domain(self, url: str) -> bool:
        try:
            base = urlparse(self.base_url)
            other = urlparse(url)

            return base.netloc.replace("www.", "") == other.netloc.replace("www.", "")
        except Exception:
            return True

    def _normalize_url(self, url: str) -> str:
        url = str(url or "").strip()

        if not url:
            return ""

        if url.startswith("//"):
            url = "https:" + url

        if not url.startswith(("http://", "https://")):
            url = urljoin(self.base_url or "https://", url)

        return url
