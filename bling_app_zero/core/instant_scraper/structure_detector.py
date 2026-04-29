from __future__ import annotations

import re
from collections import Counter, defaultdict
from typing import Any, Dict, List, Tuple

from bs4 import BeautifulSoup, Tag


class StructureDetector:
    """
    BLINGGOD — StructureDetector

    Detecta automaticamente estruturas repetidas na página:
    - cards de produto
    - grids
    - vitrines
    - listas
    - tabelas

    Objetivo:
    funcionar no estilo Instant Data Scraper, priorizando padrões reais de produto
    e evitando menu, banner, rodapé, carrossel genérico e blocos institucionais.
    """

    BAD_AREA_TERMS = [
        "menu",
        "nav",
        "navbar",
        "header",
        "footer",
        "rodape",
        "breadcrumb",
        "banner",
        "carousel",
        "carrossel",
        "slider",
        "slide",
        "social",
        "newsletter",
        "cookie",
        "modal",
        "popup",
        "login",
        "account",
        "conta",
        "politica",
        "terms",
        "privacy",
        "whatsapp",
        "instagram",
        "facebook",
        "youtube",
        "payment",
        "pagamento",
        "frete",
        "shipping",
    ]

    GOOD_CLASS_TERMS = [
        "product",
        "produto",
        "item",
        "card",
        "grid",
        "shelf",
        "vitrine",
        "catalog",
        "catalogo",
        "list",
        "lista",
        "collection",
        "showcase",
        "sku",
        "goods",
        "shop",
        "store",
    ]

    PRODUCT_SELECTORS = [
        '[itemtype*="Product"]',
        '[itemtype*="schema.org/Product"]',
        '[data-product-id]',
        '[data-product-sku]',
        '[data-sku]',
        '[data-id]',
        ".product",
        ".produto",
        ".product-item",
        ".produto-item",
        ".product-card",
        ".produto-card",
        ".item-product",
        ".card-product",
        ".vitrine-produto",
        ".shelf-item",
        ".catalog-item",
        ".catalogo-item",
        ".grid-product",
        ".grid-item",
    ]

    PRICE_RE = re.compile(
        r"(?:R\$\s*)?\d{1,3}(?:\.\d{3})*,\d{2}|(?:R\$\s*)?\d+,\d{2}",
        flags=re.I,
    )

    PRODUCT_URL_RE = re.compile(
        r"/produto|/produtos|/product|/products|/p/|/item|/sku|/prd",
        flags=re.I,
    )

    def __init__(self, html: str):
        self.html = html or ""
        self.soup = BeautifulSoup(self.html, "lxml")
        self._cleanup()

    def detect(self) -> List[Dict[str, Any]]:
        candidates: List[Dict[str, Any]] = []

        candidates.extend(self._detect_by_product_selectors())
        candidates.extend(self._detect_by_class_repetition())
        candidates.extend(self._detect_by_signature_repetition())
        candidates.extend(self._detect_by_parent_children_pattern())
        candidates.extend(self._detect_tables())

        candidates = self._normalize_candidates(candidates)
        candidates = [c for c in candidates if c.get("score", 0) > 0]
        candidates = sorted(candidates, key=lambda x: x["score"], reverse=True)

        return candidates[:8]

    def _cleanup(self) -> None:
        for tag in self.soup(["script", "style", "noscript", "svg", "iframe", "canvas"]):
            try:
                tag.decompose()
            except Exception:
                pass

    def _detect_by_product_selectors(self) -> List[Dict[str, Any]]:
        candidates: List[Dict[str, Any]] = []

        for selector in self.PRODUCT_SELECTORS:
            try:
                blocks = self.soup.select(selector)
            except Exception:
                blocks = []

            blocks = self._filter_blocks(blocks)

            if len(blocks) < 1:
                continue

            score = self._score_blocks(blocks) + 18

            candidates.append(
                {
                    "type": "selector",
                    "selector": selector,
                    "elements": blocks,
                    "count": len(blocks),
                    "score": score,
                }
            )

        return candidates

    def _detect_by_class_repetition(self) -> List[Dict[str, Any]]:
        class_counter: Counter[str] = Counter()

        for el in self.soup.find_all(True):
            if self._is_bad_area(el):
                continue

            classes = el.get("class")
            if not classes:
                continue

            key = self._class_key(classes)
            if not key:
                continue

            class_counter[key] += 1

        candidates: List[Dict[str, Any]] = []

        for class_name, count in class_counter.items():
            if count < 2:
                continue

            blocks = self._find_by_class_key(class_name)
            blocks = self._filter_blocks(blocks)

            if len(blocks) < 2:
                continue

            score = self._score_blocks(blocks)
            class_l = class_name.lower()

            if any(term in class_l for term in self.GOOD_CLASS_TERMS):
                score += 14

            if any(term in class_l for term in self.BAD_AREA_TERMS):
                score -= 20

            candidates.append(
                {
                    "type": "class",
                    "class": class_name,
                    "elements": blocks,
                    "count": len(blocks),
                    "score": max(score, 0),
                }
            )

        return candidates

    def _detect_by_signature_repetition(self) -> List[Dict[str, Any]]:
        groups: Dict[str, List[Tag]] = defaultdict(list)

        for el in self.soup.find_all(["li", "article", "div", "section", "tr"]):
            if self._is_bad_area(el):
                continue

            text = self._text(el)

            if len(text) < 15:
                continue

            if len(text) > 2500:
                continue

            sig = self._signature(el)
            if not sig:
                continue

            groups[sig].append(el)

        candidates: List[Dict[str, Any]] = []

        for sig, blocks in groups.items():
            if len(blocks) < 2:
                continue

            blocks = self._filter_blocks(blocks)
            if len(blocks) < 2:
                continue

            score = self._score_blocks(blocks)

            if any(term in sig.lower() for term in self.GOOD_CLASS_TERMS):
                score += 10

            candidates.append(
                {
                    "type": "signature",
                    "signature": sig,
                    "elements": blocks,
                    "count": len(blocks),
                    "score": score,
                }
            )

        return candidates

    def _detect_by_parent_children_pattern(self) -> List[Dict[str, Any]]:
        candidates: List[Dict[str, Any]] = []

        for parent in self.soup.find_all(["main", "div", "section", "ul", "ol", "tbody"]):
            if self._is_bad_area(parent):
                continue

            children = [
                child
                for child in parent.find_all(recursive=False)
                if isinstance(child, Tag)
            ]

            if len(children) < 2:
                continue

            useful_children = self._filter_blocks(children)

            if len(useful_children) < 2:
                continue

            score = self._score_blocks(useful_children)

            parent_attrs = self._attrs_text(parent)
            if any(term in parent_attrs for term in self.GOOD_CLASS_TERMS):
                score += 12

            if score <= 0:
                continue

            candidates.append(
                {
                    "type": "children_pattern",
                    "elements": useful_children,
                    "count": len(useful_children),
                    "score": score,
                }
            )

        return candidates

    def _detect_tables(self) -> List[Dict[str, Any]]:
        candidates: List[Dict[str, Any]] = []

        for table in self.soup.find_all("table"):
            if self._is_bad_area(table):
                continue

            rows = table.find_all("tr")
            rows = self._filter_blocks(rows)

            if len(rows) < 2:
                continue

            score = self._score_blocks(rows) + len(rows)

            candidates.append(
                {
                    "type": "table",
                    "elements": rows,
                    "count": len(rows),
                    "score": score,
                }
            )

        return candidates

    def _normalize_candidates(self, candidates: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        normalized: List[Dict[str, Any]] = []
        seen = set()

        for candidate in candidates:
            elements = candidate.get("elements", [])
            elements = self._filter_blocks(elements)

            if not elements:
                continue

            key = self._candidate_key(elements)
            if key in seen:
                continue

            seen.add(key)

            candidate["elements"] = elements
            candidate["count"] = len(elements)
            candidate["score"] = int(candidate.get("score", 0)) + self._diversity_bonus(elements)

            normalized.append(candidate)

        return normalized

    def _candidate_key(self, elements: List[Any]) -> str:
        ids = []
        for el in elements[:8]:
            try:
                ids.append(str(id(el)))
            except Exception:
                pass
        return "|".join(ids)

    def _filter_blocks(self, blocks) -> List[Any]:
        filtered = []

        for block in blocks or []:
            if not isinstance(block, Tag):
                continue

            if self._is_bad_area(block):
                continue

            text = self._text(block)

            if not text and not block.find("img"):
                continue

            if len(text) > 2500:
                continue

            if self._looks_like_noise(block):
                continue

            filtered.append(block)

        return filtered

    def _score_blocks(self, blocks) -> int:
        score = 0

        for el in list(blocks or [])[:60]:
            text = self._text(el)
            text_l = text.lower()
            attrs_text = self._attrs_text(el)

            if len(text) >= 8:
                score += 1

            if len(text) >= 25:
                score += 2

            if len(text) >= 80:
                score += 1

            links = el.find_all("a", href=True)
            imgs = el.find_all("img")

            if links:
                score += 3

            if any(self.PRODUCT_URL_RE.search(str(a.get("href", ""))) for a in links):
                score += 6

            if imgs:
                score += 4

            if self.PRICE_RE.search(text):
                score += 8

            if any(x in text_l for x in ["comprar", "carrinho", "produto", "detalhes", "ver produto"]):
                score += 2

            if any(term in attrs_text for term in self.GOOD_CLASS_TERMS):
                score += 5

            if any(term in attrs_text for term in self.BAD_AREA_TERMS):
                score -= 12

            if self._has_product_microdata(el):
                score += 10

            if self._has_bad_link_ratio(el):
                score -= 8

        count = len(list(blocks or []))
        if count >= 3:
            score += min(count, 40)

        return max(score, 0)

    def _diversity_bonus(self, elements: List[Any]) -> int:
        names = []
        urls = []
        prices = 0
        imgs = 0

        for el in elements[:50]:
            text = self._text(el)
            if self.PRICE_RE.search(text):
                prices += 1

            if el.find("img"):
                imgs += 1

            a = el.find("a", href=True)
            if a:
                href = str(a.get("href") or "").strip().lower()
                if href:
                    urls.append(href)

            title = self._best_text_candidate(el)
            if title:
                names.append(title.lower())

        bonus = 0
        bonus += min(len(set(names)), 30)
        bonus += min(len(set(urls)), 30)
        bonus += min(prices, 30) * 2
        bonus += min(imgs, 30)

        return bonus

    def _looks_like_noise(self, el: Tag) -> bool:
        text = self._text(el).lower()
        attrs = self._attrs_text(el)

        if len(text) < 3 and not el.find("img"):
            return True

        if any(term in attrs for term in self.BAD_AREA_TERMS):
            return True

        link_count = len(el.find_all("a", href=True))
        img_count = len(el.find_all("img"))

        if link_count > 30 and img_count == 0:
            return True

        if len(text) > 0:
            bad_words = ["política de privacidade", "todos os direitos reservados", "newsletter"]
            if any(word in text for word in bad_words):
                return True

        return False

    def _is_bad_area(self, el) -> bool:
        try:
            attrs_text = self._attrs_text(el)
            return any(term in attrs_text for term in self.BAD_AREA_TERMS)
        except Exception:
            return False

    def _has_product_microdata(self, el: Tag) -> bool:
        attrs = self._attrs_text(el)
        return "product" in attrs or "produto" in attrs or "schema.org/product" in attrs

    def _has_bad_link_ratio(self, el: Tag) -> bool:
        links = el.find_all("a", href=True)
        if len(links) < 8:
            return False

        bad = 0
        for a in links:
            href = str(a.get("href") or "").lower()
            text = self._text(a).lower()
            if any(x in href or x in text for x in ["login", "conta", "carrinho", "checkout", "politica"]):
                bad += 1

        return bad / max(len(links), 1) > 0.45

    def _best_text_candidate(self, el: Tag) -> str:
        for selector in [
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
        ]:
            node = el.select_one(selector)
            if node:
                text = self._text(node)
                if 4 <= len(text) <= 180:
                    return text

        a = el.find("a")
        if a:
            text = self._text(a)
            if 4 <= len(text) <= 180:
                return text

        return ""

    def _signature(self, el: Tag) -> str:
        classes = el.get("class") or []
        if isinstance(classes, str):
            classes = classes.split()

        cleaned = []
        for c in classes:
            c = str(c or "").strip().lower()
            if not c:
                continue
            if re.search(r"\d{4,}", c):
                continue
            cleaned.append(c)

        cleaned = sorted(cleaned[:6])
        return f"{el.name}|{'.'.join(cleaned)}"

    def _class_key(self, classes: Any) -> str:
        if isinstance(classes, str):
            classes = classes.split()

        clean = []
        for c in classes or []:
            c = str(c or "").strip().lower()
            if not c:
                continue
            if re.search(r"\d{4,}", c):
                continue
            clean.append(c)

        return " ".join(sorted(clean[:6]))

    def _find_by_class_key(self, class_key: str) -> List[Tag]:
        wanted = [c for c in class_key.split(" ") if c]
        if not wanted:
            return []

        result = []

        for el in self.soup.find_all(True):
            classes = el.get("class") or []
            if isinstance(classes, str):
                classes = classes.split()

            classes_l = {str(c).lower() for c in classes}
            if all(c in classes_l for c in wanted):
                result.append(el)

        return result

    def _attrs_text(self, el: Tag) -> str:
        try:
            classes = el.get("class", [])
            if isinstance(classes, list):
                classes = " ".join(str(c) for c in classes)
            else:
                classes = str(classes or "")

            return " ".join(
                [
                    str(el.name or ""),
                    str(el.get("id", "")),
                    classes,
                    str(el.get("role", "")),
                    str(el.get("itemtype", "")),
                    str(el.get("itemprop", "")),
                    str(el.get("data-product-id", "")),
                    str(el.get("data-product-sku", "")),
                    str(el.get("data-sku", "")),
                ]
            ).lower()
        except Exception:
            return ""

    def _text(self, el: Any) -> str:
        try:
            text = el.get_text(" ", strip=True)
        except Exception:
            text = ""

        text = re.sub(r"\s+", " ", str(text or "")).strip()
        return text
