"""
FORNECEDOR GENÉRICO (VERSÃO IA ABSURDA)

Agora com:
- Sitemap + fallback HTML
- Classificação produto vs categoria
- Extração multi-camada (JSON-LD + HTML + texto)
- Estoque extremamente robusto
- Imagens filtradas
"""

import re
import json
from typing import List, Dict, Any
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from bling_app_zero.core.suppliers.base import SupplierBase
from bling_app_zero.core.suppliers.sitemap_discovery import descobrir_urls_via_sitemap


class GenericSupplier(SupplierBase):

    nome = "Fornecedor Genérico"
    dominio = []

    def can_handle(self, url: str) -> bool:
        return True

    # ===============================
    # FETCH PRINCIPAL
    # ===============================
    def fetch(self, url: str, limite: int = 200, **kwargs) -> List[Dict[str, Any]]:

        produtos = []

        # ===============================
        # 1. SITEMAP (PRIORIDADE)
        # ===============================
        urls = descobrir_urls_via_sitemap(url, limite=limite)

        for u in urls:
            if not self._parece_produto_url(u):
                continue

            produto = self._extrair_produto_detalhe(u)

            if produto and produto.get("nome"):
                produtos.append(produto)

        # ===============================
        # 2. FALLBACK HTML
        # ===============================
        if not produtos:
            html = self._get_html(url)

            if html:
                produtos.extend(self._extrair_html_generico(html, url))

        return self._deduplicar(produtos)

    # ===============================
    # CLASSIFICA URL
    # ===============================
    def _parece_produto_url(self, url: str) -> bool:

        url = url.lower()

        sinais_produto = [
            "/produto",
            "/product",
            "/p/",
            "-p",
            "sku",
            "item"
        ]

        return any(s in url for s in sinais_produto)

    # ===============================
    # EXTRAÇÃO DETALHE (ULTRA)
    # ===============================
    def _extrair_produto_detalhe(self, url: str) -> Dict:

        html = self._get_html(url)
        if not html:
            return {}

        soup = BeautifulSoup(html, "html.parser")
        texto = soup.get_text(" ", strip=True)

        # ===============================
        # 1. JSON-LD (PRIORIDADE)
        # ===============================
        dados_json = self._extrair_json_ld(soup)

        nome = (
            dados_json.get("name")
            or self._extrair_nome(soup, texto)
        )

        preco = (
            dados_json.get("offers", {}).get("price")
            or self._extrair_preco(texto)
        )

        sku = (
            dados_json.get("sku")
            or self._extrair_sku(texto)
        )

        imagens = (
            dados_json.get("image")
            or self._extrair_imagens(soup, url)
        )

        estoque = self._extrair_estoque(texto)

        return {
            "url_produto": url,
            "nome": nome,
            "preco": self._to_float(preco),
            "estoque": estoque,
            "sku": sku,
            "imagens": imagens if isinstance(imagens, list) else [imagens],
        }

    # ===============================
    # JSON-LD
    # ===============================
    def _extrair_json_ld(self, soup) -> Dict:

        scripts = soup.find_all("script", type="application/ld+json")

        for script in scripts:
            try:
                data = json.loads(script.string or "")

                if isinstance(data, list):
                    for item in data:
                        if item.get("@type") == "Product":
                            return item

                if isinstance(data, dict) and data.get("@type") == "Product":
                    return data

            except:
                continue

        return {}

    # ===============================
    # ESTOQUE (SUPER ROBUSTO)
    # ===============================
    def _extrair_estoque(self, texto: str) -> int:

        texto = texto.lower()

        # NUMÉRICO
        match = re.search(r'(estoque|quantidade|dispon[ií]vel)[^\d]{0,10}(\d+)', texto)
        if match:
            return int(match.group(2))

        # ZERO
        if any(x in texto for x in [
            "esgotado",
            "sem estoque",
            "indisponível",
            "indisponivel",
            "zerado"
        ]):
            return 0

        # DISPONÍVEL
        if any(x in texto for x in [
            "em estoque",
            "disponível",
            "disponivel",
            "available",
            "in stock"
        ]):
            return 1

        return 0

    # ===============================
    # SKU
    # ===============================
    def _extrair_sku(self, texto: str) -> str:

        match = re.search(r'(sku|c[oó]digo)[^\w]{0,5}([\w\-]+)', texto, re.IGNORECASE)
        return match.group(2) if match else ""

    # ===============================
    # NOME
    # ===============================
    def _extrair_nome(self, soup, texto: str) -> str:

        tag = soup.select_one("h1, h2, .product-title")

        if tag:
            nome = tag.get_text(strip=True)
            if nome:
                return nome[:200]

        return texto[:200]

    # ===============================
    # PREÇO
    # ===============================
    def _extrair_preco(self, texto: str) -> float:

        match = re.search(r'R\$\s?([\d\.,]+)', texto)

        if match:
            return self._to_float(match.group(1))

        return 0.0

    # ===============================
    # IMAGENS (FILTRADAS)
    # ===============================
    def _extrair_imagens(self, soup, base_url: str) -> List[str]:

        imagens = []

        for img in soup.find_all("img"):

            src = img.get("src") or img.get("data-src")

            if not src:
                continue

            src = urljoin(base_url, src)

            if any(x in src.lower() for x in ["logo", "icon", "banner"]):
                continue

            imagens.append(src)

        return list(dict.fromkeys(imagens))[:5]

    # ===============================
    # FALLBACK HTML
    # ===============================
    def _extrair_html_generico(self, html: str, base_url: str) -> List[Dict]:

        soup = BeautifulSoup(html, "html.parser")

        produtos = []

        cards = soup.select("[class*=product], [class*=item]")

        for el in cards[:100]:

            texto = el.get_text(" ", strip=True)

            if len(texto) < 15:
                continue

            estoque = self._extrair_estoque(texto)

            link_tag = el.find("a")
            link = urljoin(base_url, link_tag.get("href")) if link_tag else base_url

            produtos.append({
                "url_produto": link,
                "nome": texto[:120],
                "estoque": estoque,
            })

        return produtos

    # ===============================
    # HTTP
    # ===============================
    def _get_html(self, url: str) -> str:
        try:
            r = requests.get(url, timeout=20, headers={"User-Agent": "Mozilla/5.0"})
            if r.status_code != 200:
                return ""
            return r.text
        except:
            return ""

    # ===============================
    # HELPERS
    # ===============================
    def _to_float(self, valor: str) -> float:

        if not valor:
            return 0.0

        valor = str(valor).replace(".", "").replace(",", ".")

        try:
            return float(valor)
        except:
            return 0.0

    def _deduplicar(self, produtos: List[Dict]) -> List[Dict]:

        vistos = set()
        resultado = []

        for p in produtos:

            key = p.get("url_produto") or p.get("nome")

            if not key:
                continue

            if key in vistos:
                continue

            vistos.add(key)
            resultado.append(p)

        return resultado
