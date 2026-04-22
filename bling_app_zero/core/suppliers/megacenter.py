"""
FORNECEDOR MEGA CENTER (VERSÃO PRO IA)

Agora com:
- Extração de detalhe do produto
- JSON-LD (quando disponível)
- Estoque mais confiável
- Imagens limpas
- Fallback inteligente
"""

import re
import json
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

            # 🔥 ENTRA NO DETALHE (upgrade real)
            for p in encontrados:
                detalhe = self._extrair_detalhe_produto(p.get("url_produto"))

                if detalhe:
                    p.update(detalhe)

            produtos.extend(encontrados)

        return self._deduplicar(produtos)

    # -------------------------------
    # PAGINAÇÃO
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
    # LISTA
    # -------------------------------
    def _extrair_lista_produtos(self, html: str, base_url: str) -> List[Dict]:

        soup = BeautifulSoup(html, "html.parser")
        produtos = []

        cards = soup.select(".product, .product-item, .item, .card, [class*=product]")

        for card in cards:

            try:
                texto = card.get_text(" ", strip=True)

                if not texto or len(texto) < 10:
                    continue

                link_tag = card.find("a")
                link = urljoin(base_url, link_tag.get("href")) if link_tag else ""

                if not link:
                    continue

                nome = self._extrair_nome(card, texto)

                preco_txt = self._regex_first(texto, r'R\$\s?([\d\.,]+)')
                preco = self._to_float(preco_txt)

                imagens = self._extrair_imagem(card, base_url)

                produtos.append({
                    "url_produto": link,
                    "nome": nome,
                    "preco": preco,
                    "estoque": 0,  # será ajustado no detalhe
                    "imagens": imagens,
                })

            except Exception:
                continue

        return produtos

    # -------------------------------
    # DETALHE DO PRODUTO (CRÍTICO)
    # -------------------------------
    def _extrair_detalhe_produto(self, url: str) -> Dict:

        html = self._get_html(url)
        if not html:
            return {}

        soup = BeautifulSoup(html, "html.parser")
        texto = soup.get_text(" ", strip=True)

        dados_json = self._extrair_json_ld(soup)

        nome = (
            dados_json.get("name")
            or self._extrair_nome(soup, texto)
        )

        preco = (
            dados_json.get("offers", {}).get("price")
            or self._extrair_preco(texto)
        )

        estoque = self._extrair_estoque(texto)
        imagens = self._extrair_imagens_detalhe(soup, url)

        return {
            "nome": nome,
            "preco": self._to_float(preco),
            "estoque": estoque,
            "imagens": imagens,
        }

    # -------------------------------
    # JSON LD
    # -------------------------------
    def _extrair_json_ld(self, soup):

        scripts = soup.find_all("script", type="application/ld+json")

        for script in scripts:
            try:
                data = json.loads(script.string or "")

                if isinstance(data, dict) and data.get("@type") == "Product":
                    return data

            except:
                continue

        return {}

    # -------------------------------
    # ESTOQUE (MELHORADO)
    # -------------------------------
    def _extrair_estoque(self, texto: str) -> int:

        texto = texto.lower()

        match = re.search(r'(estoque|quantidade|dispon[ií]vel)[^\d]{0,10}(\d+)', texto)
        if match:
            return int(match.group(2))

        if any(x in texto for x in [
            "esgotado",
            "indisponível",
            "indisponivel",
            "sem estoque",
            "zerado"
        ]):
            return 0

        if any(x in texto for x in [
            "disponível",
            "em estoque"
        ]):
            return 1

        return 0

    # -------------------------------
    # IMAGENS DETALHE
    # -------------------------------
    def _extrair_imagens_detalhe(self, soup, base_url: str):

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

    # -------------------------------
    # HELPERS
    # -------------------------------
    def _extrair_nome(self, tag, fallback_texto: str):

        titulo = tag.select_one("h1, h2, h3, .title, .product-title")

        if titulo:
            nome = titulo.get_text(strip=True)
            if nome:
                return nome[:200]

        return fallback_texto[:200]

    def _extrair_preco(self, texto: str) -> float:
        match = re.search(r'R\$\s?([\d\.,]+)', texto)
        return self._to_float(match.group(1)) if match else 0.0

    def _extrair_imagem(self, card, base_url: str):

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

    def _regex_first(self, text: str, pattern: str) -> str:
        match = re.search(pattern, text)
        return match.group(1) if match else ""

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
