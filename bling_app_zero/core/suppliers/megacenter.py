"""
FORNECEDOR MEGA CENTER (SCRAPER DEDICADO PRO)

Suporte:
- megacentereletronicos.com.br
- mega-center-eletronicos.stoqui.shop

Alta precisão + fallback inteligente
"""

import re
from typing import List, Dict
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from bling_app_zero.core.suppliers.base import SupplierBase


class MegaCenterSupplier(SupplierBase):

    nome = "Mega Center Eletrônicos"
    dominio = [
        "megacentereletronicos.com.br",
        "mega-center-eletronicos.stoqui.shop",
    ]

    # -------------------------------
    # FETCH PRINCIPAL
    # -------------------------------
    def fetch(self, url: str, max_paginas: int = 30, **kwargs) -> List[Dict]:

        produtos = []

        for pagina in range(1, max_paginas + 1):

            url_pagina = self._montar_url_paginada(url, pagina)

            html = self._get_html(url_pagina)

            if not html:
                break

            encontrados = self._extrair_lista_produtos(html, url)

            if not encontrados:
                break

            produtos.extend(encontrados)

        produtos = self._deduplicar(produtos)

        return produtos

    # -------------------------------
    # PAGINAÇÃO FLEXÍVEL
    # -------------------------------
    def _montar_url_paginada(self, url: str, pagina: int) -> str:

        if "page=" in url:
            return re.sub(r"page=\d+", f"page={pagina}", url)

        if "?" in url:
            return f"{url}&page={pagina}"

        return f"{url}?page={pagina}"

    # -------------------------------
    # HTTP
    # -------------------------------
    def _get_html(self, url: str) -> str:
        try:
            headers = {
                "User-Agent": "Mozilla/5.0",
                "Accept-Language": "pt-BR,pt;q=0.9"
            }

            r = requests.get(url, headers=headers, timeout=20)

            if r.status_code != 200:
                return ""

            return r.text

        except Exception:
            return ""

    # -------------------------------
    # EXTRAÇÃO DE LISTA
    # -------------------------------
    def _extrair_lista_produtos(self, html: str, base_url: str) -> List[Dict]:

        soup = BeautifulSoup(html, "html.parser")

        produtos = []

        # múltiplos seletores (site muda layout)
        cards = soup.select(
            ".product, .product-item, .item, .card, [class*=product]"
        )

        for card in cards:

            try:
                texto = card.get_text(" ", strip=True)

                if not texto or len(texto) < 10:
                    continue

                # -------------------------------
                # LINK
                # -------------------------------
                link_tag = card.find("a")
                link = urljoin(base_url, link_tag.get("href")) if link_tag else base_url

                # -------------------------------
                # NOME
                # -------------------------------
                nome = self._extrair_nome(card, texto)

                # -------------------------------
                # PREÇO
                # -------------------------------
                preco_txt = self._regex_first(texto, r'R\$\s?([\d\.,]+)')
                preco = self._to_float(preco_txt)

                # -------------------------------
                # ESTOQUE (CRÍTICO)
                # -------------------------------
                estoque = self._detectar_estoque(texto)

                # -------------------------------
                # IMAGEM
                # -------------------------------
                imagens = self._extrair_imagem(card, base_url)

                produtos.append({
                    "url_produto": link,
                    "nome": nome,
                    "preco": preco,
                    "estoque": estoque,
                    "imagens": imagens,
                })

            except Exception:
                continue

        return produtos

    # -------------------------------
    # NOME INTELIGENTE
    # -------------------------------
    def _extrair_nome(self, card, fallback_texto: str) -> str:

        # tenta pegar título direto
        titulo = card.select_one("h1, h2, h3, .title, .product-title")

        if titulo:
            nome = titulo.get_text(strip=True)
            if nome:
                return nome[:200]

        return fallback_texto[:200]

    # -------------------------------
    # ESTOQUE (REGRA CRÍTICA)
    # -------------------------------
    def _detectar_estoque(self, texto: str) -> int:

        texto = texto.lower()

        if any(x in texto for x in [
            "esgotado",
            "indisponível",
            "indisponivel",
            "sem estoque",
            "zerado"
        ]):
            return 0

        # se não detecta, assume disponível
        return 1

    # -------------------------------
    # IMAGEM
    # -------------------------------
    def _extrair_imagem(self, card, base_url: str) -> List[str]:

        imagens = []

        img_tag = card.find("img")

        if img_tag:
            src = (
                img_tag.get("src")
                or img_tag.get("data-src")
                or img_tag.get("data-lazy")
            )

            if src:
                imagens.append(urljoin(base_url, src))

        return imagens

    # -------------------------------
    # HELPERS
    # -------------------------------
    def _regex_first(self, text: str, pattern: str) -> str:
        match = re.search(pattern, text)
        return match.group(1) if match else ""

    def _to_float(self, valor: str) -> float:
        if not valor:
            return 0.0

        valor = valor.replace(".", "").replace(",", ".")

        try:
            return float(valor)
        except:
            return 0.0

    # -------------------------------
    # DEDUPLICAÇÃO
    # -------------------------------
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
