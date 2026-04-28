from __future__ import annotations

from typing import List

import pandas as pd

from .html_fetcher import fetch_html
from .pagination import PaginationDetector
from .product_extractor import ProductExtractor
from .structure_detector import StructureDetector


class InstantScraper:
    """
    Motor completo estilo Instant Data Scraper:
    - busca HTML
    - detecta estrutura
    - extrai produtos
    - detecta paginação
    - junta todas as páginas
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

        first_html = ""

        try:
            first_html = fetch_html(self.base_url)
        except Exception:
            return pd.DataFrame()

        df_first = self._extract_from_html(first_html, self.base_url)

        if isinstance(df_first, pd.DataFrame) and not df_first.empty:
            all_frames.append(df_first)

        visited.add(self.base_url)

        pagination = PaginationDetector(self.base_url, first_html)
        next_urls = pagination.detect_next_urls(max_pages=self.max_pages)

        for url in next_urls:
            if len(visited) >= self.max_pages:
                break

            url = self._normalize_url(url)

            if not url or url in visited:
                continue

            visited.add(url)

            try:
                html = fetch_html(url)
                df_page = self._extract_from_html(html, url)

                if isinstance(df_page, pd.DataFrame) and not df_page.empty:
                    all_frames.append(df_page)
                elif self.stop_when_empty:
                    break

            except Exception:
                continue

        if not all_frames:
            return pd.DataFrame()

        df = pd.concat(all_frames, ignore_index=True)
        df = self._normalize(df)

        return df

    def _extract_from_html(self, html: str, url: str) -> pd.DataFrame:
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
