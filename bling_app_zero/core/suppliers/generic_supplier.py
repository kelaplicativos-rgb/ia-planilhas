"""
FORNECEDOR GENÉRICO (SUPER FALLBACK)

Responsável por:
- Buscar produtos em QUALQUER site
- Usar múltiplas estratégias
- Servir como fallback universal
"""

import re
from typing import List, Dict, Any
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from bling_app_zero.core.suppliers.base import SupplierBase


class GenericSupplier(SupplierBase):

    nome = "Fornecedor Genérico"
    dominio = []  # aceita qualquer URL

    # -------------------------------
    # SEMPRE PODE TRATAR (fallback)
    # -------------------------------
    def can_handle(self, url: str) -> bool:
        return True

    # -------------------------------
    # FETCH PRINCIPAL
    # -------------------------------
    def fetch(self, url: str, **kwargs) -> List[Dict[str, Any]]:

        html = self._get_html(url)

        if not html:
            return []

        produtos = []

        # Estratégia 1: JSON-LD
        produtos.extend(self._extrair_json_ld(html, url))

        # Estratégia 2: HTML heurístico
        produtos.extend(self._extrair_html_generico(html, url))

        # remove duplicados por URL
        produtos = self._deduplicar(produtos)

        return produtos

    # -------------------------------
    # HTTP
    # -------------------------------
    def _get_html(self, url: str) -> str:
        try:
            headers = {
                "User-Agent": "Mozilla/5.0"
            }
            resp = requests.get(url, headers=headers, timeout=15)

            if resp.status_code != 200:
                return ""

            return resp.text

        except Exception:
            return ""

    # -------------------------------
    # JSON-LD (melhor fonte)
    # -------------------------------
    def _extrair_json_ld(self, html: str, base_url: str) -> List[Dict]:

        produtos = []

        soup = BeautifulSoup(html, "html.parser")

        scripts = soup.find_all("script", type="application/ld+json")

        for s in scripts:
            try:
                content = s.string
                if not content:
                    continue

                if "Product" not in content:
                    continue

                nome = self._regex_first(content, r'"name"\s*:\s*"([^"]+)"')
                preco = self._regex_first(content, r'"price"\s*:\s*"([^"]+)"')
                sku = self._regex_first(content, r'"sku"\s*:\s*"([^"]+)"')
                gtin = self._regex_first(content, r'"gtin\d*"\s*:\s*"([^"]+)"')

                produtos.append({
                    "url_produto": base_url,
                    "nome": nome,
                    "preco": self._to_float(preco),
                    "sku": sku,
                    "gtin": gtin,
                })

            except Exception:
                continue

        return produtos

    # -------------------------------
    # HTML GENÉRICO
    # -------------------------------
    def _extrair_html_generico(self, html: str, base_url: str) -> List[Dict]:

        produtos = []

        soup = BeautifulSoup(html, "html.parser")

        possiveis = soup.select(
            "[class*=product], [class*=item], [class*=card]"
        )

        for el in possiveis[:200]:

            try:
                texto = el.get_text(" ", strip=True)

                if not texto or len(texto) < 20:
                    continue

                preco = self._regex_first(texto, r'R\$\s?([\d\.,]+)')

                link_tag = el.find("a")
                link = urljoin(base_url, link_tag.get("href")) if link_tag else base_url

                nome = texto[:120]

                imagens = []
                img_tag = el.find("img")
                if img_tag:
                    src = img_tag.get("src") or img_tag.get("data-src")
                    if src:
                        imagens.append(urljoin(base_url, src))

                produtos.append({
                    "url_produto": link,
                    "nome": nome,
                    "preco": self._to_float(preco),
                    "imagens": imagens,
                })

            except Exception:
                continue

        return produtos

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
