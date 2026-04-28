from __future__ import annotations

import pandas as pd

from .html_fetcher import fetch_html
from .structure_detector import StructureDetector
from .product_extractor import ProductExtractor


class InstantScraper:
    """
    Motor completo estilo Instant Data Scraper
    """

    def __init__(self, base_url: str):
        self.base_url = base_url

    def run(self) -> pd.DataFrame:
        # 1️⃣ buscar HTML
        html = fetch_html(self.base_url)

        # 2️⃣ detectar estruturas
        detector = StructureDetector(html)
        candidates = detector.detect()

        if not candidates:
            return pd.DataFrame()

        # 3️⃣ escolher melhor candidato
        best = candidates[0]
        elements = best.get("elements", [])

        # 4️⃣ extrair produtos
        extractor = ProductExtractor(base_url=self.base_url)
        produtos = extractor.extract(elements)

        if not produtos:
            return pd.DataFrame()

        # 5️⃣ transformar em DataFrame
        df = pd.DataFrame(produtos)

        # 6️⃣ limpeza básica
        df = self._normalize(df)

        return df

    # ==========================================
    # 🧹 NORMALIZAÇÃO
    # ==========================================
    def _normalize(self, df: pd.DataFrame) -> pd.DataFrame:
        if df.empty:
            return df

        df = df.fillna("")

        # garantir colunas padrão
        cols = [
            "nome",
            "preco",
            "url_produto",
            "imagens",
            "sku",
            "estoque",
            "descricao",
        ]

        for c in cols:
            if c not in df.columns:
                df[c] = ""

        # remover vazios
        df = df[
            (df["nome"].astype(str).str.strip() != "")
            | (df["url_produto"].astype(str).str.strip() != "")
        ]

        # remover duplicados
        df = df.drop_duplicates(subset=["nome", "url_produto"])

        return df.reset_index(drop=True)


# função rápida para uso direto
def run_scraper(url: str) -> pd.DataFrame:
    scraper = InstantScraper(url)
    return scraper.run()
