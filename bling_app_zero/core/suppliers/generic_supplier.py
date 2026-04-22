"""
FORNECEDOR GENÉRICO (ESTOQUE PRIORIDADE TOTAL)

Agora com:
- Sitemap FIRST
- Extração agressiva de estoque
- Entrada em página de detalhe
- Fallback inteligente
"""

import re
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

    # -------------------------------
    # FETCH PRINCIPAL (ESTOQUE FIRST)
    # -------------------------------
    def fetch(self, url: str, limite: int = 200, **kwargs) -> List[Dict[str, Any]]:

        produtos = []

        # ===============================
        # 1. SITEMAP (PRIORIDADE)
        # ===============================
        urls = descobrir_urls_via_sitemap(url, limite=limite)

        for u in urls:
            produto = self._extrair_produto_detalhe(u)

            if produto:
                produtos.append(produto)

        # ===============================
        # 2. FALLBACK HTML (se vazio)
        # ===============================
        if not produtos:
            html = self._get_html(url)

            if html:
                produtos.extend(self._extrair_html_generico(html, url))

        produtos = self._deduplicar(produtos)

        return produtos

    # -------------------------------
    # EXTRAÇÃO DETALHE (CRÍTICO)
    # -------------------------------
    def _extrair_produto_detalhe(self, url: str) -> Dict:

        html = self._get_html(url)

        if not html:
            return {}

        soup = BeautifulSoup(html, "html.parser")

        texto = soup.get_text(" ", strip=True)

        nome = self._extrair_nome(soup, texto)
        preco = self._extrair_preco(texto)
        estoque = self._extrair_estoque(texto)
        sku = self._extrair_sku(texto)

        imagens = self._extrair_imagens(soup, url)

        return {
            "url_produto": url,
            "nome": nome,
            "preco": preco,
            "estoque": estoque,
            "sku": sku,
            "imagens": imagens,
        }

    # -------------------------------
    # ESTOQUE (PRIORIDADE TOTAL)
    # -------------------------------
    def _extrair_estoque(self, texto: str) -> int:

        texto = texto.lower()

        # 1. NUMÉRICO
        match = re.search(r'(estoque|dispon[ií]vel|quantidade)[^\d]{0,10}(\d+)', texto)
        if match:
            try:
                return int(match.group(2))
            except:
                pass

        # 2. TEXTO
        if any(x in texto for x in [
            "esgotado",
            "sem estoque",
            "indisponível",
            "indisponivel",
            "zerado"
        ]):
            return 0

        # 3. DISPONÍVEL SEM NÚMERO
        if "disponível" in texto or "em estoque" in texto:
            return 1

        return 0

    # -------------------------------
    # SKU
    # -------------------------------
    def _extrair_sku(self, texto: str) -> str:

        match = re.search(r'(sku|c[oó]digo)[^\w]{0,5}([\w\-]+)', texto, re.IGNORECASE)
        if match:
            return match.group(2)

        return ""

    # -------------------------------
    # NOME
    # -------------------------------
    def _extrair_nome(self, soup, fallback_texto: str) -> str:

        tag = soup.select_one("h1, h2, .product-title")

        if tag:
            nome = tag.get_text(strip=True)
            if nome:
                return nome[:200]

        return fallback_texto[:200]

    # -------------------------------
    # PREÇO
    # -------------------------------
    def _extrair_preco(self, texto: str) -> float:

        match = re.search(r'R\$\s?([\d\.,]+)', texto)

        if match:
            return self._to_float(match.group(1))

        return 0.0

    # -------------------------------
    # IMAGENS
    # -------------------------------
    def _extrair_imagens(self, soup, base_url: str) -> List[str]:

        imagens = []

        for img in soup.find_all("img")[:5]:
            src = img.get("src") or img.get("data-src")

            if src:
                imagens.append(urljoin(base_url, src))

        return imagens

    # -------------------------------
    # FALLBACK HTML
    # -------------------------------
    def _extrair_html_generico(self, html: str, base_url: str) -> List[Dict]:

        soup = BeautifulSoup(html, "html.parser")

        produtos = []

        cards = soup.select("[class*=product], [class*=item]")

        for el in cards[:100]:

            texto = el.get_text(" ", strip=True)

            if len(texto) < 10:
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

    # -------------------------------
    # HTTP
    # -------------------------------
    def _get_html(self, url: str) -> str:
        try:
            r = requests.get(url, timeout=15, headers={"User-Agent": "Mozilla/5.0"})
            if r.status_code != 200:
                return ""
            return r.text
        except:
            return ""

    # -------------------------------
    # HELPERS
    # -------------------------------
    def _to_float(self, valor: str) -> float:
        if not valor:
            return 0.0

        valor = valor.replace(".", "").replace(",", ".")

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
