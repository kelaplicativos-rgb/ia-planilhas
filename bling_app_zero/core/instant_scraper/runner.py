from __future__ import annotations

from typing import List, Tuple

import pandas as pd

from .browser_fetcher import fetch_html_browser
from .html_fetcher import fetch_html
from .jsonld_extractor import JsonLdExtractor
from .pagination import PaginationDetector
from .product_extractor import ProductExtractor
from .structure_detector import StructureDetector


class InstantScraper:
    """
    Motor completo nível produção:
    1. HTTP normal
    2. JSON-LD
    3. Structure scraping
    4. Playwright fallback quando HTTP não renderizar produto útil
    5. Paginação
    """

    def __init__(
        self,
        base_url: str,
        max_pages: int = 10,
        stop_when_empty: bool = True,
        min_rows_without_browser: int = 1,
    ):
        self.base_url = self._normalize_url(base_url)
        self.max_pages = max(1, int(max_pages or 1))
        self.stop_when_empty = bool(stop_when_empty)
        self.min_rows_without_browser = max(1, int(min_rows_without_browser or 1))

    def run(self) -> pd.DataFrame:
        all_frames: List[pd.DataFrame] = []
        visited = set()

        if not self.base_url:
            return pd.DataFrame()

        html = self._fetch_http(self.base_url)
        df_first = self._extract_all(html, self.base_url)

        if self._needs_browser(df_first):
            html_js = self._fetch_browser(self.base_url)
            df_js = self._extract_all(html_js, self.base_url)

            if len(df_js) > len(df_first):
                html = html_js
                df_first = df_js

        if isinstance(df_first, pd.DataFrame) and not df_first.empty:
            all_frames.append(df_first)

        visited.add(self.base_url)

        pagination = PaginationDetector(self.base_url, html)
        next_urls = pagination.detect_next_urls(max_pages=self.max_pages)

        for url in next_urls:
            if len(visited) >= self.max_pages:
                break

            url = self._normalize_url(url)

            if not url or url in visited:
                continue

            visited.add(url)

            html_page = self._fetch_http(url)
            df_page = self._extract_all(html_page, url)

            if self._needs_browser(df_page):
                html_js = self._fetch_browser(url)
                df_js = self._extract_all(html_js, url)

                if len(df_js) > len(df_page):
                    df_page = df_js

            if isinstance(df_page, pd.DataFrame) and not df_page.empty:
                all_frames.append(df_page)
            elif self.stop_when_empty:
                break

        if not all_frames:
            return pd.DataFrame()

        df = pd.concat(all_frames, ignore_index=True)
        return self._normalize(df)

    def _fetch_http(self, url: str) -> str:
        try:
            return fetch_html(url)
        except Exception:
            return ""

    def _fetch_browser(self, url: str) -> str:
        try:
            return fetch_html_browser(url)
        except Exception:
            return ""

    def _extract_all(self, html: str, url: str) -> pd.DataFrame:
        frames: List[pd.DataFrame] = []

        df_json = self._extract_jsonld(html, url)
        if isinstance(df_json, pd.DataFrame) and not df_json.empty:
            frames.append(df_json)

        df_struct = self._extract_structure(html, url)
        if isinstance(df_struct, pd.DataFrame) and not df_struct.empty:
            frames.append(df_struct)

        if not frames:
            return pd.DataFrame()

        return self._normalize(pd.concat(frames, ignore_index=True))

    def _needs_browser(self, df: pd.DataFrame) -> bool:
        if not isinstance(df, pd.DataFrame) or df.empty:
            return True

        return len(df) < self.min_rows_without_browser

    def _extract_jsonld(self, html: str, url: str) -> pd.DataFrame:
        if not html:
            return pd.DataFrame()

        try:
            extractor = JsonLdExtractor(html, url)
            return extractor.extract_dataframe()
        except Exception:
            return pd.DataFrame()

    def _extract_structure(self, html: str, url: str) -> pd.DataFrame:
        if not html:
            return pd.DataFrame()

        try:
            detector = StructureDetector(html)
            candidates = detector.detect()

            if not candidates:
                return pd.DataFrame()

            frames: List[pd.DataFrame] = []

            for candidate in candidates[:3]:
                elements = candidate.get("elements", [])
                extractor = ProductExtractor(base_url=url)
                produtos = extractor.extract(elements)

                if produtos:
                    frames.append(pd.DataFrame(produtos))

            if not frames:
                return pd.DataFrame()

            return pd.concat(frames, ignore_index=True)

        except Exception:
            return pd.DataFrame()

    def _normalize(self, df: pd.DataFrame) -> pd.DataFrame:
        if not isinstance(df, pd.DataFrame) or df.empty:
            return pd.DataFrame()

        df = df.copy().fillna("")

        cols = [
            "nome",
            "preco",
            "url_produto",
            "imagens",
            "sku",
            "estoque",
            "descricao",
            "gtin",
            "marca",
            "categoria",
        ]

        for col in cols:
            if col not in df.columns:
                df[col] = ""

        for col in cols:
            df[col] = (
                df[col]
                .astype(str)
                .replace(
                    {
                        "nan": "",
                        "None": "",
                        "none": "",
                        "NaN": "",
                    }
                )
            )

        df = df[
            (df["nome"].astype(str).str.strip() != "")
            | (df["url_produto"].astype(str).str.strip() != "")
        ]

        if df.empty:
            return pd.DataFrame(columns=cols)

        df["_score"] = df.apply(self._quality_score, axis=1)
        df = df.sort_values("_score", ascending=False)

        df["_dedupe"] = df.apply(self._dedupe_key, axis=1)
        df = df[df["_dedupe"].astype(str).str.strip() != ""]
        df = df.drop_duplicates(subset=["_dedupe"], keep="first")
        df = df.drop(columns=["_dedupe", "_score"], errors="ignore")

        return df[cols].reset_index(drop=True)

    def _quality_score(self, row) -> int:
        score = 0

        if str(row.get("nome", "")).strip():
            score += 3

        if str(row.get("preco", "")).strip():
            score += 3

        if str(row.get("url_produto", "")).strip():
            score += 2

        if str(row.get("imagens", "")).strip():
            score += 2

        if str(row.get("sku", "")).strip():
            score += 1

        if str(row.get("descricao", "")).strip():
            score += 1

        if str(row.get("gtin", "")).strip():
            score += 1

        return score

    def _dedupe_key(self, row) -> str:
        url = str(row.get("url_produto", "")).strip().lower()
        sku = str(row.get("sku", "")).strip().lower()
        gtin = str(row.get("gtin", "")).strip().lower()
        nome = str(row.get("nome", "")).strip().lower()

        return url or sku or gtin or nome

    def _normalize_url(self, url: str) -> str:
        url = str(url or "").strip()

        if not url:
            return ""

        if url.startswith("//"):
            url = "https:" + url

        if not url.startswith(("http://", "https://")):
            url = "https://" + url

        return url


def run_scraper(url: str, max_pages: int = 10) -> pd.DataFrame:
    scraper = InstantScraper(url, max_pages=max_pages)
    return scraper.run()


