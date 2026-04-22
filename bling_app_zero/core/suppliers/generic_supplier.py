"""
FORNECEDOR GENÉRICO

Objetivo:
- usar sitemap quando existir
- respeitar auth_context
- classificar produto x categoria x login
- extrair detalhe com JSON-LD + HTML + texto
- ter fallback de listagem quando o sitemap não resolver
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from bling_app_zero.core.suppliers.base import SupplierBase
from bling_app_zero.core.suppliers.sitemap_discovery import descobrir_urls_via_sitemap


class GenericSupplier(SupplierBase):
    nome = "Fornecedor Genérico"
    dominio: List[str] = []

    def can_handle(self, url: str) -> bool:
        return True

    def fetch(
        self,
        url: str,
        limite: int = 300,
        auth_context: Optional[Dict[str, Any]] = None,
        **kwargs,
    ) -> List[Dict[str, Any]]:
        base_url = self._clean_text(url)
        if not base_url:
            return []

        produtos: List[Dict[str, Any]] = []

        # 1) URL direta de produto
        html_base = self.get_html(base_url, auth_context=auth_context, timeout=20)
        if html_base:
            soup_base = BeautifulSoup(html_base, "html.parser")
            page_type = self._detect_page_type(base_url, html_base, soup_base)

            if page_type == "produto":
                produto = self._extrair_produto_detalhe(base_url, html=html_base, auth_context=auth_context)
                if produto:
                    produtos.append(produto)

            # 2) sitemap
            if not produtos:
                urls = descobrir_urls_via_sitemap(base_url, limite=limite)
                for candidate_url in urls:
                    if not self._same_domain(base_url, candidate_url):
                        continue

                    maybe_product = self._extrair_produto_se_for_produto(
                        candidate_url,
                        auth_context=auth_context,
                    )
                    if maybe_product:
                        produtos.append(maybe_product)

                    if len(produtos) >= limite:
                        break

            # 3) fallback: extrair links da própria listagem/categoria
            if not produtos:
                links = self._extrair_links_candidatos(soup_base, base_url)
                for candidate_url in links[: limite * 2]:
                    maybe_product = self._extrair_produto_se_for_produto(
                        candidate_url,
                        auth_context=auth_context,
                    )
                    if maybe_product:
                        produtos.append(maybe_product)

                    if len(produtos) >= limite:
                        break

            # 4) fallback final: cards simples da listagem
            if not produtos:
                produtos.extend(self._extrair_cards_genericos(html_base, base_url))

        return self.validar_produtos(produtos)

    # ------------------------------------------------------------------
    # EXTRAÇÃO DE PRODUTO
    # ------------------------------------------------------------------
    def _extrair_produto_se_for_produto(
        self,
        url: str,
        auth_context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        html = self.get_html(url, auth_context=auth_context, timeout=20)
        if not html:
            return {}

        soup = BeautifulSoup(html, "html.parser")
        page_type = self._detect_page_type(url, html, soup)
        if page_type != "produto":
            return {}

        return self._extrair_produto_detalhe(url, html=html, auth_context=auth_context)

    def _extrair_produto_detalhe(
        self,
        url: str,
        html: str = "",
        auth_context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        page_html = html or self.get_html(url, auth_context=auth_context, timeout=20)
        if not page_html:
            return {}

        soup = BeautifulSoup(page_html, "html.parser")
        text = soup.get_text(" ", strip=True)

        json_ld_products = self._extract_json_ld_products(soup)
        json_ld = json_ld_products[0] if json_ld_products else {}

        offers = json_ld.get("offers") or {}
        if isinstance(offers, list):
            offers = offers[0] if offers else {}

        nome = (
            self._clean_text(json_ld.get("name"))
            or self._extract_title(soup, text)
        )
        preco = (
            offers.get("price")
            or self._extract_price_from_meta(soup)
            or self._extract_price_from_text(text)
        )
        sku = (
            self._clean_text(json_ld.get("sku"))
            or self._extract_sku_from_meta(soup)
            or self._extract_sku_from_text(text)
        )
        gtin = (
            self._clean_text(json_ld.get("gtin13"))
            or self._clean_text(json_ld.get("gtin"))
            or self._extract_gtin_from_text(text)
        )
        marca = self._extract_brand(json_ld, soup, text)
        categoria = self._extract_category(soup, text)
        descricao = self._extract_description(json_ld, soup, text)
        imagens = self._extract_images_from_json_ld(json_ld, url) or self._extract_images(soup, url)
        estoque = self._extract_stock_from_text(text)

        return {
            "url_produto": url,
            "nome": nome,
            "preco": self._to_float(preco),
            "estoque": estoque,
            "sku": sku,
            "gtin": gtin,
            "marca": marca,
            "categoria": categoria,
            "descricao": descricao,
            "imagens": imagens,
        }

    # ------------------------------------------------------------------
    # FALLBACKS
    # ------------------------------------------------------------------
    def _extrair_links_candidatos(self, soup: BeautifulSoup, base_url: str) -> List[str]:
        links: List[str] = []
        seen = set()

        for anchor in soup.find_all("a", href=True):
            href = self._absolute_url(base_url, anchor.get("href"))
            if not href:
                continue
            if not self._same_domain(base_url, href):
                continue

            text = self._clean_text(anchor.get_text(" ", strip=True))
            href_low = href.lower()
            text_low = text.lower()

            score = 0
            if self._looks_like_product_url(href):
                score += 3
            if any(token in text_low for token in ["comprar", "ver detalhes", "detalhes", "produto"]):
                score += 2
            if len(text) >= 8:
                score += 1

            if score < 2:
                continue

            if href not in seen:
                seen.add(href)
                links.append(href)

        return links

    def _extrair_cards_genericos(self, html: str, base_url: str) -> List[Dict[str, Any]]:
        soup = BeautifulSoup(html, "html.parser")
        produtos: List[Dict[str, Any]] = []

        selectors = [
            "[class*='product']",
            "[class*='produto']",
            "[class*='item']",
            "[class*='card']",
            "article",
        ]

        seen = set()

        for selector in selectors:
            for card in soup.select(selector):
                text = self._clean_text(card.get_text(" ", strip=True))
                if len(text) < 20:
                    continue

                anchor = card.find("a", href=True)
                href = self._absolute_url(base_url, anchor.get("href") if anchor else "")
                if not href:
                    continue
                if href in seen:
                    continue

                nome = ""
                title_node = card.select_one("h2, h3, h4, .title, .product-title")
                if title_node:
                    nome = self._clean_text(title_node.get_text(" ", strip=True))
                if not nome:
                    nome = text[:180]

                preco = self._extract_price_from_text(text)
                imagens = self._extract_images(card, base_url)
                estoque = self._extract_stock_from_text(text)

                produto = {
                    "url_produto": href,
                    "nome": nome,
                    "preco": preco,
                    "estoque": estoque,
                    "imagens": imagens,
                }

                seen.add(href)
                produtos.append(produto)

        return produtos

    # ------------------------------------------------------------------
    # CAMPOS AUXILIARES
    # ------------------------------------------------------------------
    def _extract_price_from_meta(self, soup: BeautifulSoup) -> float:
        selectors = [
            "meta[property='product:price:amount']",
            "meta[itemprop='price']",
        ]
        for selector in selectors:
            node = soup.select_one(selector)
            if node:
                value = self._clean_text(node.get("content"))
                if value:
                    return self._to_float(value)
        return 0.0

    def _extract_sku_from_meta(self, soup: BeautifulSoup) -> str:
        selectors = [
            "meta[itemprop='sku']",
            "meta[property='product:retailer_item_id']",
        ]
        for selector in selectors:
            node = soup.select_one(selector)
            if node:
                value = self._clean_text(node.get("content"))
                if value:
                    return value
        return ""

    def _extract_brand(self, json_ld: Dict[str, Any], soup: BeautifulSoup, text: str) -> str:
        brand = json_ld.get("brand")
        if isinstance(brand, dict):
            value = self._clean_text(brand.get("name"))
            if value:
                return value
        if isinstance(brand, str):
            value = self._clean_text(brand)
            if value:
                return value

        meta = soup.select_one("meta[property='product:brand'], meta[itemprop='brand']")
        if meta:
            value = self._clean_text(meta.get("content"))
            if value:
                return value

        match = re.search(r"(marca)\W{0,8}([A-Za-z0-9 .\-_/]+)", text, re.IGNORECASE)
        return self._clean_text(match.group(2))[:80] if match else ""

    def _extract_category(self, soup: BeautifulSoup, text: str) -> str:
        breadcrumbs = []
        for node in soup.select("nav.breadcrumb a, .breadcrumb a, [class*='breadcrumb'] a"):
            label = self._clean_text(node.get_text(" ", strip=True))
            if label:
                breadcrumbs.append(label)

        if breadcrumbs:
            return " > ".join(breadcrumbs[:6])

        match = re.search(r"(categoria)\W{0,8}([A-Za-z0-9 .\-/]+)", text, re.IGNORECASE)
        return self._clean_text(match.group(2))[:120] if match else ""

    def _extract_description(self, json_ld: Dict[str, Any], soup: BeautifulSoup, text: str) -> str:
        value = self._clean_text(json_ld.get("description"))
        if value:
            return value[:3000]

        meta = soup.select_one("meta[name='description'], meta[property='og:description']")
        if meta:
            value = self._clean_text(meta.get("content"))
            if value:
                return value[:3000]

        node = soup.select_one("[itemprop='description'], .description, .product-description")
        if node:
            value = self._clean_text(node.get_text(" ", strip=True))
            if value:
                return value[:3000]

        return self._clean_text(text)[:3000]

    def _extract_images_from_json_ld(self, json_ld: Dict[str, Any], base_url: str) -> List[str]:
        image = json_ld.get("image")
        if isinstance(image, str):
            return [self._absolute_url(base_url, image)]
        if isinstance(image, list):
            return [self._absolute_url(base_url, item) for item in image if self._absolute_url(base_url, item)]
        return []
