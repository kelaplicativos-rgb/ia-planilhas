from __future__ import annotations

from typing import List

import pandas as pd

from .html_fetcher import fetch_html
from .pagination import PaginationDetector
from .product_extractor import ProductExtractor
from .structure_detector import StructureDetector
from .jsonld_extractor import JsonLdExtractor
from .browser_fetcher import fetch_html_browser


class InstantScraper:
    """
    Motor completo nível produção:
    1. HTTP normal
    2. JSON-LD (dados perfeitos)
    3. Structure scraping
    4. Playwright fallback (JS + scroll)
    5. Paginação
    """

    def __init__(
        self,
        base_url: str,
        max_pages: int = 10,
        stop_when_empty: bool = True,
    ):
        self.base_url = self._normalize_url(base_url)
        self.max_pages = max(1, int(max_pages or 1))
        self.stop_when_empty = bool(stop_when_empty)

    def run(self) -> pd.DataFrame:
        all_frames: List[pd.DataFrame] = []
        visited = set()

        if not self.base_url:
            return pd.DataFrame()

        # ==========================================
        # 1️⃣ PRIMEIRA TENTATIVA (HTTP)
        # ==========================================
        try:
            html = fetch_html(self.base_url)
        except Exception:
            html = ""

        # ==========================================
        # 2️⃣ JSON-LD (PRIORIDADE ALTA)
        # ==========================================
        df_json = self._extract_jsonld(html)

        if not df_json.empty:
            all_frames.append(df_json)

        # ==========================================
        # 3️⃣ STRUCTURE SCRAPER
        # ==========================================
        df_struct = self._extract_structure(html, self.base_url)

        if not df_struct.empty:
            all_frames.append(df_struct)

        # ==========================================
        # 4️⃣ FALLBACK PLAYWRIGHT (SE NECESSÁRIO)
        # ==========================================
        if not all_frames:
            html_js = fetch_html_browser(self.base_url)

            df_json_js = self._extract_jsonld(html_js)
            df_struct_js = self._extract_structure(html_js, self.base_url)

            if not df_json_js.empty:
                all_frames.append(df_json_js)

            if not df_struct_js.empty:
                all_frames.append(df_struct_js)

        visited.add(self.base_url)

        # ==========================================
        # 5️⃣ PAGINAÇÃO
        # ==========================================
        pagination = PaginationDetector(self.base_url, html)
        next_urls = pagination.detect_next_urls(max_pages=self.max_pages)

        for url in next_urls:
            if len(visited) >= self.max_pages:
                break

            url = self._normalize_url(url)

            if not url or url in visited:
                continue

            visited.add(url)

            try:
                html_page = fetch_html(url)

                df_json = self._extract_jsonld(html_page)
                df_struct = self._extract_structure(html_page, url)

                if not df_json.empty:
                    all_frames.append(df_json)

                if not df_struct.empty:
                    all_frames.append(df_struct)

                if df_json.empty and df_struct.empty and self.stop_when_empty:
                    break

            except Exception:
                continue

        if not all_frames:
            return pd.DataFrame()

        df = pd.concat(all_frames, ignore_index=True)
        df = self._normalize(df)

        return df

    # ==========================================
    # 🔎 EXTRAÇÕES
    # ==========================================

    def _extract_jsonld(self, html: str) -> pd.DataFrame:
        if not html:
            return pd.DataFrame()

        try:
            extractor = JsonLdExtractor(html, self.base_url)
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

            best = candidates[0]
            elements = best.get("elements", [])

            extractor = ProductExtractor(base_url=url)
            produtos = extractor.extract(elements)

            if not produtos:
                return pd.DataFrame()

            return pd.DataFrame(produtos)

        except Exception:
            return pd.DataFrame()

    # ==========================================
    # 🧹 NORMALIZAÇÃO
    # ==========================================

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
        ]

        for col in cols:
            if col not in df.columns:
                df[col] = ""

        for col in cols:
            df[col] = df[col].astype(str).replace(
                {
                    "nan": "",
                    "None": "",
                    "none": "",
                    "NaN": "",
                }
            )

        df = df[
            (df["nome"].astype(str).str.strip() != "")
            | (df["url_produto"].astype(str).str.strip() != "")
        ]

        if df.empty:
            return pd.DataFrame(columns=cols)

        df["_dedupe"] = (
            df["url_produto"].astype(str).str.strip().str.lower()
            + "|"
            + df["sku"].astype(str).str.strip().str.lower()
            + "|"
            + df["nome"].astype(str).str.strip().str.lower()
        )

        df = df[df["_dedupe"].str.strip() != "||"]
        df = df.drop_duplicates(subset=["_dedupe"], keep="first")
        df = df.drop(columns=["_dedupe"], errors="ignore")

        return df[cols].reset_index(drop=True)

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
