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

    DESCRIPTION_BLOCK_TERMS = [
        "descrição curta",
        "descricao curta",
        "descrição complementar",
        "descricao complementar",
        "short description",
        "complementary description",
    ]

    DESCRIPTION_BAD_TEXT_TERMS = [
        "comprar",
        "adicionar ao carrinho",
        "ver produto",
        "login",
        "menu",
        "minha conta",
        "whatsapp",
        "facebook",
        "instagram",
        "youtube",
        "formas de pagamento",
        "pix",
        "boleto",
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
        nome = self._get_nome(el)

        return {
            "nome": nome,
            "preco": self._get_preco(el),
            "url_produto": self._get_link(el),
            "imagens": self._get_imagem(el),
            "sku": self._get_sku(el),
            "estoque": self._get_estoque(el),

            # Regra BLINGFIX:
            # Não gerar descrição curta nem descrição complementar automaticamente.
            # O campo descricao só entra se for uma descrição real e útil.
            "descricao": self._get_descricao(el, nome),
        }

    # ==========================================
    # 🧠 VALIDAÇÃO
    # ==========================================
    def _is_valid_product(self, p: Dict[str, Any]) -> bool:
        nome = str(p.get("nome", "") or "").strip()
        url = str(p.get("url_produto", "") or "").strip()
        preco = str(p.get("preco", "") or "").strip()

        if not nome and not url:
            return False

        if len(nome) < 5:
            return False

        nome_l = nome.lower()

        if any(bad in nome_l for bad in self.BAD_NAME_TERMS):
            return False

        score = 0

        if nome:
            score += 3

        if url:
            score += 2

        if preco:
            score += 3

        if p.get("imagens"):
            score += 1

        return score >= 4

    # ==========================================
    # 🔎 NOME
    # ==========================================
    def _get_nome(self, el) -> str:
        selectors = [
            '[itemprop="name"]',
            ".product-name",
            ".product-title",
            ".nome",
            ".title",
            "h1",
            "h2",
            "h3",
            "h4",
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

        candidatos = list(dict.fromkeys(candidatos))

        if not candidatos:
            return ""

        return sorted(candidatos, key=len)[0]

    def _looks_like_name(self, text: str) -> bool:
        if not text:
            return False

        t = text.lower()

        if len(text) < 5 or len(text) > 180:
            return False

        if any(bad in t for bad in self.BAD_NAME_TERMS):
            return False

        if any(block in t for block in self.DESCRIPTION_BLOCK_TERMS):
            return False

        if re.fullmatch(r"[\d\s.,\-R$]+", text):
            return False

        return True

    # ==========================================
    # 💰 PREÇO
    # ==========================================
    def _get_preco(self, el) -> str:
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
    def _get_link(self, el) -> str:
        candidatos = []

        for a in el.find_all("a", href=True):
            href = self._clean(a["href"])

            if not href:
                continue

            href_l = href.lower()
            texto = self._clean(a.get_text()).lower()

            if "login" in href_l or "login" in texto:
                continue

            score = 1

            if any(h in href_l for h in self.PRODUCT_HINTS):
                score += 4

            if texto:
                score += 1

            candidatos.append((score, href))

        if not candidatos:
            return ""

        candidatos.sort(reverse=True)
        return self._abs_url(candidatos[0][1])

    # ==========================================
    # 🖼 IMAGEM
    # ==========================================
    def _get_imagem(self, el) -> str:
        imgs = []

        for img in el.find_all("img"):
            src = (
                img.get("src")
                or img.get("data-src")
                or img.get("data-original")
                or img.get("data-lazy")
                or img.get("data-srcset")
                or ""
            )

            if not src:
                continue

            if "," in src:
                src = src.split(",")[0].strip().split(" ")[0]

            src = self._abs_url(src)

            if not self._is_good_image(src):
                continue

            imgs.append(src)

        return "|".join(list(dict.fromkeys(imgs))[:10])

    def _is_good_image(self, src: str) -> bool:
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
    def _get_sku(self, el) -> str:
        text = el.get_text(" ", strip=True)

        match = re.search(r"(SKU|Cód|Cod|Código|Codigo|Ref|Referência|Referencia)\s*[:\-]?\s*(\S+)", text, re.I)
        return match.group(2).strip() if match else ""

    # ==========================================
    # 📦 ESTOQUE
    # ==========================================
    def _get_estoque(self, el) -> int:
        text = el.get_text(" ", strip=True).lower()

        if any(x in text for x in ["sem estoque", "indisponível", "indisponivel", "esgotado", "zerado"]):
            return 0

        if any(x in text for x in ["em estoque", "disponível", "disponivel", "comprar"]):
            return 1

        return 0

    # ==========================================
    # 📄 DESCRIÇÃO
    # ==========================================
    def _get_descricao(self, el, nome: str = "") -> str:
        """
        BLINGFIX RAIZ:
        - Não cria Descrição Curta.
        - Não cria Descrição Complementar.
        - Não usa texto gigante do card como descrição se for só menu/botão/preço.
        - Só retorna descrição real quando encontrar texto útil.
        """

        selectors_preferidos = [
            '[itemprop="description"]',
            ".description",
            ".descricao",
            ".product-description",
            ".produto-descricao",
            ".detalhes",
            ".details",
        ]

        candidatos = []

        for selector in selectors_preferidos:
            for node in el.select(selector):
                text = self._clean(node.get_text(" ", strip=True))

                if self._is_good_description(text, nome):
                    candidatos.append(text)

        if candidatos:
            candidatos = list(dict.fromkeys(candidatos))
            return sorted(candidatos, key=len, reverse=True)[0][:500]

        return ""

    def _is_good_description(self, text: str, nome: str = "") -> bool:
        if not text:
            return False

        text = self._clean(text)
        t = text.lower()
        nome_l = self._clean(nome).lower()

        if len(text) < 40:
            return False

        if len(text) > 2000:
            return False

        if any(block in t for block in self.DESCRIPTION_BLOCK_TERMS):
            return False

        if any(bad in t for bad in self.DESCRIPTION_BAD_TEXT_TERMS):
            return False

        if nome_l and t == nome_l:
            return False

        if re.fullmatch(r"[\d\s.,\-R$]+", text):
            return False

        return True

    # ==========================================
    # 🔧 UTILS
    # ==========================================
    def _abs_url(self, url: str) -> str:
        url = str(url or "").strip()

        if url.startswith("//"):
            return "https:" + url

        if url.startswith("http"):
            return url

        return urljoin(self.base_url, url)

    def _normalize_base_url(self, url: str) -> str:
        url = str(url or "").strip()

        if not url:
            return ""

        if not url.startswith("http"):
            url = "https://" + url

        return url

    def _clean(self, v: Any) -> str:
        return re.sub(r"\s+", " ", str(v or "")).strip()
