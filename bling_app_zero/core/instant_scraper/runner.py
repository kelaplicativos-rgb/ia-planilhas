# bling_app_zero/core/instant_scraper/runner.py

from __future__ import annotations

from typing import List
import pandas as pd
import time
from urllib.parse import urlparse, urlunparse

from .browser_fetcher import fetch_html_browser
from .html_fetcher import fetch_html
from .jsonld_extractor import JsonLdExtractor
from .pagination import PaginationDetector
from .product_extractor import ProductExtractor
from .structure_detector import StructureDetector


MAX_TOTAL_PRODUCTS = 300
MAX_RUNTIME_SECONDS = 25


class InstantScraper:

    def __init__(
        self,
        base_url: str,
        max_pages: int = 5,
        stop_when_empty: bool = False,
        min_rows_without_browser: int = 3,
    ):
        self.base_url = self._normalize_url(base_url)
        self.max_pages = max(1, int(max_pages or 1))
        self.stop_when_empty = bool(stop_when_empty)
        self.min_rows_without_browser = max(1, int(min_rows_without_browser or 1))

    # =========================
    # 🚀 EXECUÇÃO PRINCIPAL
    # =========================
    def run(self) -> pd.DataFrame:
        all_frames: List[pd.DataFrame] = []
        visited = set()

        start_time = time.time()

        if not self.base_url:
            return pd.DataFrame()

        html = self._safe_fetch_http(self.base_url)
        df_first = self._extract_all(html, self.base_url)

        if self._needs_browser(df_first):
            html_js = self._safe_fetch_browser(self.base_url)
            df_js = self._extract_all(html_js, self.base_url)

            if len(df_js) > len(df_first):
                html = html_js
                df_first = df_js

        if not df_first.empty:
            all_frames.append(df_first)

        visited.add(self._clean_url(self.base_url))

        pagination = PaginationDetector(self.base_url, html)
        next_urls = pagination.detect_next_urls(max_pages=self.max_pages)

        for url in next_urls:

            # 🔥 LIMITES GLOBAIS
            if len(visited) >= self.max_pages:
                break

            if self._total_rows(all_frames) >= MAX_TOTAL_PRODUCTS:
                break

            if (time.time() - start_time) > MAX_RUNTIME_SECONDS:
                break

            url = self._normalize_url(url)
            url_clean = self._clean_url(url)

            if not url or url_clean in visited:
                continue

            visited.add(url_clean)

            html_page = self._safe_fetch_http(url)
            df_page = self._extract_all(html_page, url)

            if self._needs_browser(df_page):
                html_js = self._safe_fetch_browser(url)
                df_js = self._extract_all(html_js, url)

                if len(df_js) > len(df_page):
                    df_page = df_js

            if not df_page.empty:
                all_frames.append(df_page)
            elif self.stop_when_empty:
                break

        if not all_frames:
            return pd.DataFrame()

        df = pd.concat(all_frames, ignore_index=True)

        return self._normalize(df)

    # =========================
    # 🌐 FETCH
    # =========================
    def _safe_fetch_http(self, url: str) -> str:
        try:
            return fetch_html(url)
        except Exception:
            return ""

    def _safe_fetch_browser(self, url: str) -> str:
        try:
            return fetch_html_browser(url)
        except Exception:
            return ""

    # =========================
    # 🔍 EXTRAÇÃO
    # =========================
    def _extract_all(self, html: str, url: str) -> pd.DataFrame:
        if not html:
            return pd.DataFrame()

        frames: List[pd.DataFrame] = []

        df_json = self._extract_jsonld(html, url)
        if not df_json.empty:
            frames.append(df_json)

        df_struct = self._extract_structure(html, url)
        if not df_struct.empty:
            frames.append(df_struct)

        if not frames:
            return pd.DataFrame()

        return self._normalize(pd.concat(frames, ignore_index=True))

    def _extract_jsonld(self, html: str, url: str) -> pd.DataFrame:
        try:
            return JsonLdExtractor(html, url).extract_dataframe()
        except Exception:
            return pd.DataFrame()

    def _extract_structure(self, html: str, url: str) -> pd.DataFrame:
        try:
            detector = StructureDetector(html)
            candidates = detector.detect()

            frames: List[pd.DataFrame] = []

            for candidate in candidates[:5]:
                elements = candidate.get("elements", [])
                if not elements:
                    continue

                extractor = ProductExtractor(base_url=url)
                produtos = extractor.extract(elements)

                if produtos:
                    frames.append(pd.DataFrame(produtos))

            if not frames:
                return pd.DataFrame()

            return pd.concat(frames, ignore_index=True)

        except Exception:
            return pd.DataFrame()

    # =========================
    # 🧠 DECISÃO
    # =========================
    def _needs_browser(self, df: pd.DataFrame) -> bool:
        if not isinstance(df, pd.DataFrame) or df.empty:
            return True

        preenchidos = (
            df["nome"].astype(str).str.strip() != ""
        ).sum()

        return len(df) < self.min_rows_without_browser or preenchidos < 2

    # =========================
    # 📊 NORMALIZAÇÃO
    # =========================
    def _normalize(self, df: pd.DataFrame) -> pd.DataFrame:
        if df.empty:
            return pd.DataFrame()

        df = df.copy().fillna("")

        cols = [
            "nome", "preco", "url_produto", "imagens",
            "sku", "estoque", "descricao", "gtin", "marca", "categoria",
        ]

        for col in cols:
            if col not in df.columns:
                df[col] = ""

        df = df[
            (df["nome"].astype(str).str.strip() != "")
            | (df["url_produto"].astype(str).str.strip() != "")
        ]

        return df.reset_index(drop=True)

    # =========================
    # 🔧 UTIL
    # =========================
    def _normalize_url(self, url: str) -> str:
        url = str(url or "").strip()

        if not url:
            return ""

        if url.startswith("//"):
            url = "https:" + url

        if not url.startswith(("http://", "https://")):
            url = "https://" + url

        return url

    def _clean_url(self, url: str) -> str:
        try:
            parsed = urlparse(url)
            return urlunparse((parsed.scheme, parsed.netloc, parsed.path, "", "", ""))
        except Exception:
            return url

    def _total_rows(self, frames: List[pd.DataFrame]) -> int:
        return sum(len(df) for df in frames)


# =========================
# ENTRYPOINT
# =========================
def run_scraper(url: str, max_pages: int = 5) -> pd.DataFrame:
    scraper = InstantScraper(url, max_pages=max_pages)
    return scraper.run()
