from __future__ import annotations

import json
from typing import Any, Dict, List
from urllib.parse import urljoin

import pandas as pd
from bs4 import BeautifulSoup


class JsonLdExtractor:
    """
    Extrai produtos de JSON-LD:
    - Product
    - ItemList
    - BreadcrumbList parcialmente
    """

    def __init__(self, html: str, base_url: str = ""):
        self.html = html or ""
        self.base_url = base_url or ""
        self.soup = BeautifulSoup(self.html, "lxml")

    def extract_dataframe(self) -> pd.DataFrame:
        produtos: List[Dict[str, Any]] = []

        for data in self._load_jsonld_blocks():
            produtos.extend(self._extract_from_node(data))

        if not produtos:
            return pd.DataFrame()

        df = pd.DataFrame(produtos)
        return self._normalize(df)

    def _load_jsonld_blocks(self) -> List[Any]:
        blocks: List[Any] = []

        scripts = self.soup.find_all("script", attrs={"type": "application/ld+json"})

        for script in scripts:
            raw = script.string or script.get_text() or ""

            raw = raw.strip()
            if not raw:
                continue

            try:
                data = json.loads(raw)
                blocks.append(data)
            except Exception:
                continue

        return blocks

    def _extract_from_node(self, node: Any) -> List[Dict[str, Any]]:
        produtos: List[Dict[str, Any]] = []

        if isinstance(node, list):
            for item in node:
                produtos.extend(self._extract_from_node(item))
            return produtos

        if not isinstance(node, dict):
            return produtos

        graph = node.get("@graph")
        if isinstance(graph, list):
            for item in graph:
                produtos.extend(self._extract_from_node(item))

        node_type = node.get("@type")

        if isinstance(node_type, list):
            types = [str(x).lower() for x in node_type]
        else:
            types = [str(node_type or "").lower()]

        if "product" in types:
            produtos.append(self._product_to_row(node))

        if "itemlist" in types:
            item_list = node.get("itemListElement") or []
            if isinstance(item_list, list):
                for item in item_list:
                    produtos.extend(self._extract_from_itemlist_element(item))

        return produtos

    def _extract_from_itemlist_element(self, item: Any) -> List[Dict[str, Any]]:
        if not isinstance(item, dict):
            return []

        inner = item.get("item")

        if isinstance(inner, dict):
            return self._extract_from_node(inner)

        url = inner if isinstance(inner, str) else item.get("url")
        name = item.get("name")

        if url or name:
            return [
                {
                    "nome": str(name or "").strip(),
                    "url_produto": self._abs_url(str(url or "").strip()),
                    "preco": "",
                    "imagens": "",
                    "sku": "",
                    "estoque": 0,
                    "descricao": "",
                    "gtin": "",
                    "marca": "",
                    "categoria": "",
                }
            ]

        return []

    def _product_to_row(self, product: Dict[str, Any]) -> Dict[str, Any]:
        offers = product.get("offers") or {}
        if isinstance(offers, list):
            offers = offers[0] if offers else {}

        brand = product.get("brand") or ""
        if isinstance(brand, dict):
            brand = brand.get("name") or ""

        image = product.get("image") or ""
        if isinstance(image, list):
            image = "|".join(self._abs_url(str(x)) for x in image if x)

        availability = str(offers.get("availability") or "").lower()
        estoque = 0 if "outofstock" in availability or "soldout" in availability else 1

        preco = (
            offers.get("price")
            or offers.get("lowPrice")
            or offers.get("highPrice")
            or product.get("price")
            or ""
        )

        url = product.get("url") or offers.get("url") or ""

        gtin = (
            product.get("gtin")
            or product.get("gtin8")
            or product.get("gtin12")
            or product.get("gtin13")
            or product.get("gtin14")
            or product.get("ean")
            or ""
        )

        return {
            "nome": str(product.get("name") or "").strip(),
            "preco": preco,
            "url_produto": self._abs_url(str(url or "").strip()),
            "imagens": image if isinstance(image, str) else "",
            "sku": str(product.get("sku") or product.get("mpn") or "").strip(),
            "estoque": estoque,
            "descricao": str(product.get("description") or "").strip(),
            "gtin": str(gtin or "").strip(),
            "marca": str(brand or "").strip(),
            "categoria": str(product.get("category") or "").strip(),
        }

    def _normalize(self, df: pd.DataFrame) -> pd.DataFrame:
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

        df = df.copy().fillna("")

        for col in cols:
            if col not in df.columns:
                df[col] = ""

        df = df[
            (df["nome"].astype(str).str.strip() != "")
            | (df["url_produto"].astype(str).str.strip() != "")
        ]

        df = df.drop_duplicates(subset=["nome", "url_produto"], keep="first")

        return df[cols].reset_index(drop=True)

    def _abs_url(self, url: str) -> str:
        url = str(url or "").strip()

        if not url:
            return ""

        if url.startswith("//"):
            return "https:" + url

        if url.startswith(("http://", "https://")):
            return url

        return urljoin(self.base_url, url)
