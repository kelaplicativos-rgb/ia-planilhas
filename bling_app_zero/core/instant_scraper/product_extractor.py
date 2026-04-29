from __future__ import annotations

import re
from typing import Any, Dict, List
from urllib.parse import urljoin


class ProductExtractor:

    BAD_IMAGE_TERMS = [
        "logo", "banner", "sprite", "placeholder", "loading",
        "icone", "icon", "whatsapp", "facebook", "instagram",
        "youtube", "pix", "boleto"
    ]

    BAD_NAME_TERMS = [
        "comprar", "carrinho", "ver produto", "menu",
        "login", "categoria", "adicionar"
    ]

    PRODUCT_HINTS = [
        "/produto", "/product", "/p/", "/item"
    ]

    def __init__(self, base_url: str = ""):
        self.base_url = self._normalize_base_url(base_url)

    # ==========================================
    # 🚀 MAIN
    # ==========================================
    def extract(self, elements) -> List[Dict[str, Any]]:
        produtos = []

        for el in elements or []:
            try:
                p = self._extract_single(el)

                if self._is_valid_product(p):
                    produtos.append(p)

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

    # ==========================================
    # 🧠 VALIDAÇÃO
    # ==========================================
    def _is_valid_product(self, p):
        nome = p.get("nome", "").strip()
        url = p.get("url_produto", "").strip()
        preco = p.get("preco", "").strip()

        if not nome and not url:
            return False

        if len(nome) < 5:
            return False

        nome_l = nome.lower()

        if any(bad in nome_l for bad in self.BAD_NAME_TERMS):
            return False

        score = 0
        if nome: score += 3
        if url: score += 2
        if preco: score += 3
        if p.get("imagens"): score += 1

        return score >= 4

    # ==========================================
    # 🔎 NOME
    # ==========================================
    def _get_nome(self, el):
        selectors = [
            '[itemprop="name"]',
            ".product-name", ".product-title",
            ".nome", ".title",
            "h1", "h2", "h3", "h4"
        ]

        candidatos = []

        for s in selectors:
            node = el.select_one(s)
            if node:
                text = self._clean(node.get_text(" ", strip=True))
                if self._looks_like_name(text):
                    candidatos.append(text)

        for a in el.find_all("a"):
            text = self._clean(a.get_text(" ", strip=True))
            if self._looks_like_name(text):
                candidatos.append(text)

        if not candidatos:
            return ""

        return sorted(candidatos, key=len)[0]

    def _looks_like_name(self, text):
        if not text:
            return False

        t = text.lower()

        if len(text) < 5 or len(text) > 180:
            return False

        if any(bad in t for bad in self.BAD_NAME_TERMS):
            return False

        if re.fullmatch(r"[\d\s.,\-R$]+", text):
            return False

        return True

    # ==========================================
    # 💰 PREÇO
    # ==========================================
    def _get_preco(self, el):
        text = el.get_text(" ", strip=True)

        patterns = [
            r"R\$\s*\d{1,3}(?:\.\d{3})*,\d{2}",
            r"R\$\s*\d+,\d{2}",
            r"\d{1,3}(?:\.\d{3})*,\d{2}",
        ]

        for p in patterns:
            m = re.search(p, text)
            if m:
                return m.group()

        return ""

    # ==========================================
    # 🔗 LINK
    # ==========================================
    def _get_link(self, el):
        candidatos = []

        for a in el.find_all("a", href=True):
            href = self._clean(a["href"])

            score = 0

            if href:
                score += 1

            if any(h in href.lower() for h in self.PRODUCT_HINTS):
                score += 4

            texto = self._clean(a.get_text()).lower()
            if texto and "login" not in texto:
                score += 1

            candidatos.append((score, href))

        if not candidatos:
            return ""

        candidatos.sort(reverse=True)
        return self._abs_url(candidatos[0][1])

    # ==========================================
    # 🖼 IMAGEM
    # ==========================================
    def _get_imagem(self, el):
        imgs = []

        for img in el.find_all("img"):
            src = (
                img.get("src")
                or img.get("data-src")
                or img.get("data-original")
                or img.get("data-lazy")
                or ""
            )

            if not src:
                continue

            src = self._abs_url(src)

            if not self._is_good_image(src):
                continue

            imgs.append(src)

        return "|".join(list(dict.fromkeys(imgs))[:10])

    def _is_good_image(self, src):
        s = src.lower()

        if not s.startswith("http"):
            return False

        if any(b in s for b in self.BAD_IMAGE_TERMS):
            return False

        if not any(ext in s for ext in [".jpg", ".png", ".jpeg", ".webp"]):
            return False

        return True

    # ==========================================
    # 🔢 SKU
    # ==========================================
    def _get_sku(self, el):
        text = el.get_text(" ", strip=True)

        match = re.search(r"(SKU|Cód|Ref)\s*[:\-]?\s*(\S+)", text, re.I)
        return match.group(2) if match else ""

    # ==========================================
    # 📦 ESTOQUE
    # ==========================================
    def _get_estoque(self, el):
        text = el.get_text(" ", strip=True).lower()

        if any(x in text for x in ["sem estoque", "indisponível", "esgotado"]):
            return 0

        if any(x in text for x in ["em estoque", "disponível", "comprar"]):
            return 1

        return 0

    # ==========================================
    # 📄 DESCRIÇÃO
    # ==========================================
    def _get_descricao(self, el):
        text = self._clean(el.get_text(" ", strip=True))

        if len(text) > 40:
            return text[:500]

        return ""

    # ==========================================
    # 🔧 UTILS
    # ==========================================
    def _abs_url(self, url):
        if url.startswith("//"):
            return "https:" + url
        if url.startswith("http"):
            return url
        return urljoin(self.base_url, url)

    def _normalize_base_url(self, url):
        url = str(url or "").strip()

        if not url:
            return ""

        if not url.startswith("http"):
            url = "https://" + url

        return url

    def _clean(self, v):
        return re.sub(r"\s+", " ", str(v or "")).strip()
