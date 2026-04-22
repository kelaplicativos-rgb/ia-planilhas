"""
BASE DE FORNECEDORES

Contrato padrão para todos os fornecedores do fluxo de site.
Centraliza:
- sessão HTTP com auth_context
- leitura HTML
- normalização
- validação mínima real
"""

from __future__ import annotations

from abc import ABC, abstractmethod
import json
import re
from typing import Any, Dict, List, Optional
from urllib.parse import urljoin, urlparse

import pandas as pd
from bs4 import BeautifulSoup

from bling_app_zero.core.suppliers.http_utils import get_html, normalize_url


class SupplierBase(ABC):
    nome: str = "Fornecedor Base"
    dominio: List[str] = []

    def can_handle(self, url: str) -> bool:
        if not url:
            return False

        value = str(url).lower()
        for domain in self.dominio:
            if domain and domain.lower() in value:
                return True
        return False

    @abstractmethod
    def fetch(self, url: str, **kwargs) -> List[Dict[str, Any]]:
        raise NotImplementedError

    # ------------------------------------------------------------------
    # HTTP / HTML
    # ------------------------------------------------------------------
    def get_html(self, url: str, auth_context: Optional[Dict[str, Any]] = None, timeout: int = 20) -> str:
        return get_html(url, auth_context=auth_context, timeout=timeout)

    # ------------------------------------------------------------------
    # HELPERS
    # ------------------------------------------------------------------
    def _clean_text(self, value: Any) -> str:
        text = str(value or "").strip()
        return "" if text.lower() in {"none", "null", "nan"} else text

    def _absolute_url(self, base_url: str, maybe_relative: str) -> str:
        raw = self._clean_text(maybe_relative)
        if not raw:
            return ""
        return urljoin(normalize_url(base_url), raw)

    def _same_domain(self, base_url: str, candidate_url: str) -> bool:
        try:
            base_host = (urlparse(normalize_url(base_url)).netloc or "").replace("www.", "").lower()
            candidate_host = (urlparse(normalize_url(candidate_url)).netloc or "").replace("www.", "").lower()
            if not base_host or not candidate_host:
                return True
            return base_host == candidate_host
        except Exception:
            return True

    def _looks_like_product_url(self, url: str) -> bool:
        value = self._clean_text(url).lower()
        if not value:
            return False

        product_signals = [
            "/produto/",
            "/produto-",
            "/produtos/",
            "/product/",
            "/products/",
            "/p/",
            "/pd/",
            "/item/",
            "/sku/",
            ".html",
            ".htm",
        ]
        negative_signals = [
            "/blog",
            "/login",
            "/conta",
            "/account",
            "/checkout",
            "/cart",
            "/carrinho",
            "/institucional",
            "/quem-somos",
            "/politica",
            "/tag/",
            "/author/",
        ]

        if any(token in value for token in negative_signals):
            return False

        if any(token in value for token in product_signals):
            return True

        # slug longo com identificador costuma ser produto
        slug = value.rstrip("/").split("/")[-1]
        if len(slug) >= 12 and any(ch.isdigit() for ch in slug):
            return True

        return False

    def _extract_json_ld_products(self, soup: BeautifulSoup) -> List[Dict[str, Any]]:
        results: List[Dict[str, Any]] = []

        for script in soup.find_all("script", type="application/ld+json"):
            raw = script.string or script.get_text(strip=False) or ""
            raw = raw.strip()
            if not raw:
                continue

            try:
                data = json.loads(raw)
            except Exception:
                continue

            stack = data if isinstance(data, list) else [data]
            while stack:
                item = stack.pop()
                if isinstance(item, list):
                    stack.extend(item)
                    continue
                if not isinstance(item, dict):
                    continue

                item_type = str(item.get("@type", "")).lower()
                if item_type == "product":
                    results.append(item)

                if "@graph" in item and isinstance(item["@graph"], list):
                    stack.extend(item["@graph"])

        return results

    def _extract_price_from_text(self, text: str) -> float:
        match = re.search(r"R\$\s*([\d\.\,]+)", text or "", re.IGNORECASE)
        if not match:
            return 0.0
        return self._to_float(match.group(1))

    def _extract_stock_from_text(self, text: str) -> int:
        base = self._clean_text(text).lower()
        if not base:
            return 0

        numeric_patterns = [
            r"(estoque|quantidade|dispon[ií]vel)[^\d]{0,20}(\d+)",
            r"(\d+)[^\d]{0,10}(unidades|itens|peças|pecas)\s+(em estoque|dispon[ií]vel)",
        ]

        for pattern in numeric_patterns:
            match = re.search(pattern, base, re.IGNORECASE)
            if match:
                groups = [g for g in match.groups() if g and str(g).isdigit()]
                if groups:
                    try:
                        return max(int(groups[-1]), 0)
                    except Exception:
                        pass

        zero_signals = [
            "esgotado",
            "sem estoque",
            "indisponível",
            "indisponivel",
            "zerado",
            "out of stock",
        ]
        if any(token in base for token in zero_signals):
            return 0

        positive_signals = [
            "em estoque",
            "disponível",
            "disponivel",
            "available",
            "in stock",
        ]
        if any(token in base for token in positive_signals):
            return 1

        return 0

    def _extract_sku_from_text(self, text: str) -> str:
        match = re.search(r"(sku|c[oó]digo|ref(?:er[êe]ncia)?)\W{0,8}([\w\-./]+)", text or "", re.IGNORECASE)
        return self._clean_text(match.group(2)) if match else ""

    def _extract_gtin_from_text(self, text: str) -> str:
        match = re.search(r"\b(\d{8}|\d{12}|\d{13}|\d{14})\b", text or "")
        return self._clean_text(match.group(1)) if match else ""

    def _extract_title(self, soup: BeautifulSoup, fallback_text: str = "") -> str:
        selectors = [
            "h1",
            "meta[property='og:title']",
            ".product-title",
            ".product_title",
            "[class*='title']",
        ]

        for selector in selectors:
            node = soup.select_one(selector)
            if not node:
                continue

            if node.name == "meta":
                value = self._clean_text(node.get("content"))
            else:
                value = self._clean_text(node.get_text(" ", strip=True))

            if value and len(value) >= 3:
                return value[:220]

        return self._clean_text(fallback_text)[:220]

    def _extract_images(self, soup: BeautifulSoup, base_url: str) -> List[str]:
        images: List[str] = []
        seen = set()

        og = soup.select_one("meta[property='og:image']")
        if og:
            src = self._absolute_url(base_url, og.get("content"))
            if src and src not in seen:
                seen.add(src)
                images.append(src)

        for img in soup.find_all("img"):
            src = (
                img.get("src")
                or img.get("data-src")
                or img.get("data-lazy")
                or img.get("data-original")
            )
            src = self._absolute_url(base_url, src)
            if not src:
                continue

            low = src.lower()
            if any(token in low for token in ["logo", "icon", "banner", "avatar", "placeholder"]):
                continue

            if src in seen:
                continue

            seen.add(src)
            images.append(src)

            if len(images) >= 8:
                break

        return images

    def _detect_page_type(self, url: str, html: str, soup: Optional[BeautifulSoup] = None) -> str:
        page = self._clean_text(html).lower()
        parsed_url = self._clean_text(url).lower()
        soup = soup or BeautifulSoup(html or "", "html.parser")

        json_ld_products = self._extract_json_ld_products(soup)
        if json_ld_products:
            return "produto"

        if self._looks_like_product_url(parsed_url):
            if any(token in page for token in ["sku", "ean", "gtin", "comprar", "adicionar ao carrinho"]):
                return "produto"

        if any(token in parsed_url for token in ["/categoria", "/categories", "/collections", "/catalog"]):
            return "categoria"

        if any(token in page for token in ["fazer login", "senha", "autenticação", "autenticacao"]):
            return "login"

        product_signals = 0
        for token in ["sku", "ean", "gtin", "comprar", "adicionar ao carrinho", "em estoque", "R$"]:
            if token.lower() in page:
                product_signals += 1

        if product_signals >= 3:
            return "produto"

        return "categoria"

    # ------------------------------------------------------------------
    # NORMALIZAÇÃO
    # ------------------------------------------------------------------
    def normalizar_produto(self, produto: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "fornecedor": self.nome,
            "url_produto": self._clean_text(produto.get("url_produto")),
            "nome": self._clean_text(produto.get("nome")),
            "sku": self._clean_text(produto.get("sku")),
            "marca": self._clean_text(produto.get("marca")),
            "categoria": self._clean_text(produto.get("categoria")),
            "preco": produto.get("preco", 0),
            "estoque": produto.get("estoque", 0),
            "gtin": self._clean_text(produto.get("gtin")),
            "descricao": self._clean_text(produto.get("descricao")),
            "imagens": self._normalizar_imagens(produto.get("imagens", "")),
        }

    def _normalizar_imagens(self, imagens: Any) -> str:
        if isinstance(imagens, list):
            itens = [self._clean_text(item) for item in imagens if self._clean_text(item)]
            return "|".join(dict.fromkeys(itens))

        if isinstance(imagens, str):
            bruto = imagens.replace(",", "|").replace(";", "|")
            itens = [self._clean_text(item) for item in bruto.split("|") if self._clean_text(item)]
            return "|".join(dict.fromkeys(itens))

        return ""

    def to_dataframe(self, produtos: List[Dict[str, Any]]) -> pd.DataFrame:
        normalizados = [self.normalizar_produto(p) for p in produtos if isinstance(p, dict)]
        if not normalizados:
            return pd.DataFrame()
        return pd.DataFrame(normalizados)

    def validar_produtos(self, produtos: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        validos: List[Dict[str, Any]] = []
        vistos = set()

        for produto in produtos or []:
            if not isinstance(produto, dict):
                continue

            nome = self._clean_text(produto.get("nome"))
            url_produto = self._clean_text(produto.get("url_produto"))
            preco = produto.get("preco", 0)
            sku = self._clean_text(produto.get("sku"))
            descricao = self._clean_text(produto.get("descricao"))

            if not nome or len(nome) < 3:
                continue

            if nome.lower() in {"produto", "item", "sem nome", "clique aqui"}:
                continue

            if len(nome.split()) < 2 and not sku and not url_produto:
                continue

            try:
                preco_float = float(preco or 0)
            except Exception:
                preco_float = 0.0

            has_signal = bool(url_produto or sku or preco_float > 0 or len(descricao) >= 20)
            if not has_signal:
                continue

            key = url_produto or sku or nome.lower()
            if key in vistos:
                continue

            vistos.add(key)
            validos.append(self.normalizar_produto(produto))

        return validos

    def _to_float(self, valor: Any) -> float:
        raw = self._clean_text(valor)
        if not raw:
            return 0.0

        raw = raw.replace("R$", "").replace("r$", "").strip()
        raw = re.sub(r"[^\d,.\-]", "", raw)

        if raw.count(",") > 0 and raw.count(".") > 0:
            raw = raw.replace(".", "").replace(",", ".")
        elif raw.count(",") > 0:
            raw = raw.replace(",", ".")

        try:
            return float(raw)
        except Exception:
            return 0.0

