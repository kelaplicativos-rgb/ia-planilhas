from __future__ import annotations

import re
from typing import List, Dict, Any
from urllib.parse import urljoin


class ProductExtractor:
    """
    Extrai dados dos blocos detectados pelo StructureDetector
    """

    def __init__(self, base_url: str = ""):
        self.base_url = base_url or ""

    def extract(self, elements) -> List[Dict[str, Any]]:
        produtos = []

        for el in elements:
            try:
                produto = self._extract_single(el)

                if produto["nome"] or produto["url_produto"]:
                    produtos.append(produto)

            except Exception:
                continue

        return produtos

    def _extract_single(self, el) -> Dict[str, Any]:
        return {
            "nome": self._get_nome(el),
            "preco": self._get_preco(el),
            "url_produto": self._get_link(el),
            "imagens": self._get_imagem(el),
            "sku": self._get_sku(el),
            "estoque": self._get_estoque(el),
            "descricao": self._get_descricao(el),
        }

    # ==============================
    # CAMPOS
    # ==============================

    def _get_nome(self, el):
        for tag in ["h1", "h2", "h3", "span", "p"]:
            nodes = el.find_all(tag)
            for node in nodes:
                text = node.get_text(strip=True)
                if len(text) > 5:
                    return text
        return ""

    def _get_preco(self, el):
        text = el.get_text(" ", strip=True)

        match = re.search(r"(R\$|\$|€)\s?\d+[.,]?\d*", text)
        if match:
            return match.group()

        return ""

    def _get_link(self, el):
        a = el.find("a", href=True)
        if not a:
            return ""

        href = str(a["href"]).strip()

        if href.startswith("//"):
            return "https:" + href

        if href.startswith("/"):
            return urljoin(self.base_url, href)

        return href

    def _get_imagem(self, el):
        img = el.find("img")
        if not img:
            return ""

        src = img.get("src") or img.get("data-src") or ""

        if src.startswith("//"):
            return "https:" + src

        if src.startswith("/"):
            return urljoin(self.base_url, src)

        return src

    def _get_sku(self, el):
        text = el.get_text(" ", strip=True)

        match = re.search(r"(SKU|Cód|Ref)[\s:]*([A-Za-z0-9\-]+)", text, re.I)
        if match:
            return match.group(2)

        return ""

    def _get_estoque(self, el):
        text = el.get_text(" ", strip=True).lower()

        if any(x in text for x in ["esgotado", "sem estoque", "indisponível", "indisponivel"]):
            return 0

        if any(x in text for x in ["em estoque", "disponível", "disponivel"]):
            return 1

        return 0

    def _get_descricao(self, el):
        text = el.get_text(" ", strip=True)

        if len(text) > 50:
            return text[:500]

        return ""
