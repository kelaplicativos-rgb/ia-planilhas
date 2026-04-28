from __future__ import annotations

import re
from typing import Any, Dict, List
from urllib.parse import urljoin


class ProductExtractor:
    """
    Extrai dados dos blocos detectados pelo StructureDetector.

    Melhorias:
    - prioriza título real do produto
    - melhora captura de preço BR
    - melhora captura de imagem lazy-load
    - normaliza links relativos
    - evita lixo de banner/menu/rodapé
    """

    BAD_IMAGE_TERMS = [
        "logo",
        "banner",
        "sprite",
        "placeholder",
        "loading",
        "icone",
        "icon",
        "whatsapp",
        "facebook",
        "instagram",
        "youtube",
        "pix",
        "boleto",
    ]

    BAD_NAME_TERMS = [
        "comprar",
        "adicionar",
        "carrinho",
        "ver produto",
        "saiba mais",
        "mais detalhes",
        "menu",
        "categoria",
        "entrar",
        "login",
    ]

    def __init__(self, base_url: str = ""):
        self.base_url = self._normalize_base_url(base_url)

    def extract(self, elements) -> List[Dict[str, Any]]:
        produtos: List[Dict[str, Any]] = []

        for el in elements or []:
            try:
                produto = self._extract_single(el)

                if self._is_valid_product(produto):
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

    def _is_valid_product(self, produto: Dict[str, Any]) -> bool:
        nome = str(produto.get("nome") or "").strip()
        url = str(produto.get("url_produto") or "").strip()
        preco = str(produto.get("preco") or "").strip()
        imagem = str(produto.get("imagens") or "").strip()

        if not nome and not url:
            return False

        if nome and len(nome) < 4:
            return False

        nome_l = nome.lower()
        if nome_l in self.BAD_NAME_TERMS:
            return False

        if any(term == nome_l for term in self.BAD_NAME_TERMS):
            return False

        score = 0
        if nome:
            score += 2
        if url:
            score += 1
        if preco:
            score += 2
        if imagem:
            score += 1

        return score >= 2

    def _get_nome(self, el) -> str:
        selectors = [
            '[itemprop="name"]',
            ".product-name",
            ".product-title",
            ".nome-produto",
            ".titulo-produto",
            ".name",
            ".title",
            "h1",
            "h2",
            "h3",
            "h4",
        ]

        for selector in selectors:
            node = el.select_one(selector)
            text = self._clean_text(node.get_text(" ", strip=True) if node else "")
            if self._looks_like_name(text):
                return text

        for tag in ["a", "span", "p"]:
            nodes = el.find_all(tag)
            for node in nodes:
                text = self._clean_text(node.get_text(" ", strip=True))
                if self._looks_like_name(text):
                    return text

        return ""

    def _looks_like_name(self, text: str) -> bool:
        text = self._clean_text(text)
        if not text:
            return False

        text_l = text.lower()

        if len(text) < 5:
            return False

        if len(text) > 180:
            return False

        if any(term in text_l for term in self.BAD_NAME_TERMS):
            return False

        if re.fullmatch(r"[\d\s.,\-R$]+", text, flags=re.I):
            return False

        return True

    def _get_preco(self, el) -> str:
        selectors = [
            '[itemprop="price"]',
            ".price",
            ".preco",
            ".valor",
            ".product-price",
            ".sale-price",
            ".price-sales",
            ".preco-produto",
            ".precoPor",
        ]

        for selector in selectors:
            node = el.select_one(selector)
            if not node:
                continue

            attr_value = (
                node.get("content")
                or node.get("data-price")
                or node.get("value")
                or ""
            )

            preco = self._extract_price(attr_value)
            if preco:
                return preco

            preco = self._extract_price(node.get_text(" ", strip=True))
            if preco:
                return preco

        text = el.get_text(" ", strip=True)
        return self._extract_price(text)

    def _extract_price(self, text: Any) -> str:
        text = self._clean_text(text)
        if not text:
            return ""

        patterns = [
            r"R\$\s*\d{1,3}(?:\.\d{3})*,\d{2}",
            r"R\$\s*\d+,\d{2}",
            r"R\$\s*\d+(?:\.\d{2})?",
            r"\d{1,3}(?:\.\d{3})*,\d{2}",
            r"\d+,\d{2}",
        ]

        for pattern in patterns:
            match = re.search(pattern, text, flags=re.I)
            if match:
                return match.group(0).strip()

        return ""

    def _get_link(self, el) -> str:
        candidates = []

        for a in el.find_all("a", href=True):
            href = self._clean_text(a.get("href"))
            text = self._clean_text(a.get_text(" ", strip=True)).lower()
            cls = " ".join(a.get("class", [])).lower()

            score = 0
            if href:
                score += 1
            if any(x in href.lower() for x in ["/produto", "/product", "/p/", "produto"]):
                score += 3
            if text and not any(bad in text for bad in ["login", "entrar", "carrinho"]):
                score += 1
            if "product" in cls or "produto" in cls:
                score += 2

            candidates.append((score, href))

        if not candidates:
            return ""

        candidates.sort(key=lambda x: x[0], reverse=True)
        return self._abs_url(candidates[0][1])

    def _get_imagem(self, el) -> str:
        imgs = []

        for img in el.find_all("img"):
            src = (
                img.get("src")
                or img.get("data-src")
                or img.get("data-original")
                or img.get("data-lazy")
                or img.get("data-image")
                or img.get("data-srcset")
                or ""
            )

            if not src and img.get("srcset"):
                src = self._best_srcset(img.get("srcset"))

            src = self._clean_text(src)

            if not src:
                continue

            if "," in src and " " in src:
                src = self._best_srcset(src)

            src_abs = self._abs_url(src)

            if not self._is_good_image(src_abs):
                continue

            imgs.append(src_abs)

        final = []
        seen = set()

        for img in imgs:
            if img in seen:
                continue
            seen.add(img)
            final.append(img)

        return "|".join(final[:12])

    def _best_srcset(self, srcset: str) -> str:
        srcset = str(srcset or "").strip()
        if not srcset:
            return ""

        parts = [p.strip() for p in srcset.split(",") if p.strip()]
        if not parts:
            return ""

        last = parts[-1].split(" ")[0].strip()
        return last

    def _is_good_image(self, src: str) -> bool:
        src_l = src.lower()

        if not src_l.startswith(("http://", "https://")):
            return False

        if any(term in src_l for term in self.BAD_IMAGE_TERMS):
            return False

        if not any(ext in src_l for ext in [".jpg", ".jpeg", ".png", ".webp", ".avif"]):
            return False

        return True

    def _get_sku(self, el) -> str:
        text = el.get_text(" ", strip=True)

        patterns = [
            r"(?:SKU|Sku|sku)\s*[:\-]?\s*([A-Za-z0-9._\-\/]+)",
            r"(?:Cód|Cod|Código|Codigo)\s*[:\-]?\s*([A-Za-z0-9._\-\/]+)",
            r"(?:Ref|REF|Referência|Referencia)\s*[:\-]?\s*([A-Za-z0-9._\-\/]+)",
            r"(?:Modelo|MODEL|Model)\s*[:\-]?\s*([A-Za-z0-9._\-\/]+)",
        ]

        for pattern in patterns:
            match = re.search(pattern, text, re.I)
            if match:
                return self._clean_text(match.group(1))[:80]

        for attr in ["data-sku", "data-product-sku", "data-id", "data-product-id"]:
            value = el.get(attr)
            if value:
                return self._clean_text(value)[:80]

        return ""

    def _get_estoque(self, el) -> int:
        text = el.get_text(" ", strip=True).lower()

        if any(
            x in text
            for x in [
                "esgotado",
                "sem estoque",
                "indisponível",
                "indisponivel",
                "fora de estoque",
                "out of stock",
                "sold out",
            ]
        ):
            return 0

        match = re.search(r"(?:estoque|quantidade|qtd)\s*[:\-]?\s*(\d+)", text, re.I)
        if match:
            try:
                return max(int(match.group(1)), 0)
            except Exception:
                return 0

        if any(
            x in text
            for x in [
                "em estoque",
                "disponível",
                "disponivel",
                "in stock",
                "available",
                "comprar",
                "adicionar ao carrinho",
            ]
        ):
            return 1

        return 0

    def _get_descricao(self, el) -> str:
        selectors = [
            '[itemprop="description"]',
            ".description",
            ".descricao",
            ".short-description",
            ".descricao-curta",
            ".product-description",
        ]

        for selector in selectors:
            node = el.select_one(selector)
            text = self._clean_text(node.get_text(" ", strip=True) if node else "")
            if len(text) >= 30:
                return text[:800]

        text = self._clean_text(el.get_text(" ", strip=True))
        if len(text) > 50:
            return text[:800]

        return ""

    def _abs_url(self, url: str) -> str:
        url = self._clean_text(url)

        if not url:
            return ""

        if url.startswith("//"):
            return "https:" + url

        if url.startswith(("http://", "https://")):
            return url

        return urljoin(self.base_url, url)

    def _normalize_base_url(self, url: str) -> str:
        url = str(url or "").strip()

        if not url:
            return ""

        if url.startswith("//"):
            url = "https:" + url

        if not url.startswith(("http://", "https://")):
            url = "https://" + url

        return url

    def _clean_text(self, value: Any) -> str:
        text = str(value or "").strip()

        if text.lower() in {"none", "null", "nan"}:
            return ""

        text = re.sub(r"[\r\n\t]+", " ", text)
        text = re.sub(r"\s+", " ", text).strip()
        return text
