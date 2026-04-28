from __future__ import annotations

from collections import Counter
from typing import Any, Dict, List

from bs4 import BeautifulSoup


class StructureDetector:
    """
    Detecta automaticamente estruturas repetidas na página:
    - cards de produto
    - listas
    - grids
    - tabelas

    Melhorias:
    - reduz risco de pegar menu/rodapé/banner
    - prioriza blocos com preço + link + imagem + texto útil
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
        "social",
        "newsletter",
        "cookie",
        "modal",
        "popup",
        "login",
        "account",
        "conta",
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
    ]

    def __init__(self, html: str):
        self.html = html or ""
        self.soup = BeautifulSoup(self.html, "lxml")

    def detect(self) -> List[Dict[str, Any]]:
        candidates: List[Dict[str, Any]] = []

        candidates.extend(self._detect_by_product_selectors())
        candidates.extend(self._detect_by_class_repetition())
        candidates.extend(self._detect_by_parent_children_pattern())
        candidates.extend(self._detect_tables())

        candidates = [c for c in candidates if c.get("score", 0) > 0]
        candidates = sorted(candidates, key=lambda x: x["score"], reverse=True)

        return candidates[:5]

    def _detect_by_product_selectors(self) -> List[Dict[str, Any]]:
        selectors = [
            '[itemtype*="Product"]',
            '[itemtype*="schema.org/Product"]',
            '[data-product-id]',
            '[data-product-sku]',
            ".product",
            ".produto",
            ".product-item",
            ".produto-item",
            ".product-card",
            ".produto-card",
            ".item-product",
            ".card-product",
            ".vitrine-produto",
        ]

        candidates: List[Dict[str, Any]] = []

        for selector in selectors:
            blocks = self.soup.select(selector)
            blocks = self._filter_blocks(blocks)

            if len(blocks) < 1:
                continue

            score = self._score_blocks(blocks) + 10

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
        elements = self.soup.find_all(True)
        class_counter: Counter[str] = Counter()

        for el in elements:
            if self._is_bad_area(el):
                continue

            classes = el.get("class")
            if not classes:
                continue

            key = " ".join(str(c).strip() for c in classes if str(c).strip())
            if not key:
                continue

            class_counter[key] += 1

        candidates: List[Dict[str, Any]] = []

        for class_name, count in class_counter.items():
            if count < 3:
                continue

            blocks = self.soup.find_all(class_=class_name.split())
            blocks = self._filter_blocks(blocks)

            if len(blocks) < 2:
                continue

            score = self._score_blocks(blocks)
            class_l = class_name.lower()

            if any(term in class_l for term in self.GOOD_CLASS_TERMS):
                score += 8

            candidates.append(
                {
                    "type": "class",
                    "class": class_name,
                    "elements": blocks,
                    "count": len(blocks),
                    "score": score,
                }
            )

        return candidates

    def _detect_by_parent_children_pattern(self) -> List[Dict[str, Any]]:
        candidates: List[Dict[str, Any]] = []

        for parent in self.soup.find_all(["div", "section", "ul", "ol"]):
            if self._is_bad_area(parent):
                continue

            children = [
                child
                for child in parent.find_all(recursive=False)
                if getattr(child, "name", None)
            ]

            if len(children) < 3:
                continue

            useful_children = self._filter_blocks(children)

            if len(useful_children) < 2:
                continue

            score = self._score_blocks(useful_children)

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
        tables = self.soup.find_all("table")
        candidates: List[Dict[str, Any]] = []

        for table in tables:
            if self._is_bad_area(table):
                continue

            rows = table.find_all("tr")

            if len(rows) < 3:
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

    def _filter_blocks(self, blocks) -> List[Any]:
        filtered = []

        for block in blocks or []:
            if self._is_bad_area(block):
                continue

            text = block.get_text(" ", strip=True)
            if not text and not block.find("img"):
                continue

            if len(text) > 1500:
                continue

            filtered.append(block)

        return filtered

    def _score_blocks(self, blocks) -> int:
        score = 0

        for el in list(blocks or [])[:40]:
            text = el.get_text(" ", strip=True)
            text_l = text.lower()

            if len(text) >= 8:
                score += 1

            if len(text) >= 25:
                score += 2

            if el.find("a", href=True):
                score += 3

            if el.find("img"):
                score += 3

            if any(x in text_l for x in ["r$", "$", "€"]):
                score += 5

            if any(x in text_l for x in ["comprar", "carrinho", "produto", "detalhes"]):
                score += 2

            attrs_text = " ".join(
                [
                    " ".join(el.get("class", []) if isinstance(el.get("class"), list) else []),
                    str(el.get("id", "")),
                    str(el.get("itemtype", "")),
                ]
            ).lower()

            if any(term in attrs_text for term in self.GOOD_CLASS_TERMS):
                score += 4

            if any(term in attrs_text for term in self.BAD_AREA_TERMS):
                score -= 8

        return max(score, 0)

    def _is_bad_area(self, el) -> bool:
        try:
            attrs_text = " ".join(
                [
                    str(el.name or ""),
                    str(el.get("id", "")),
                    " ".join(el.get("class", []) if isinstance(el.get("class"), list) else []),
                    str(el.get("role", "")),
                ]
            ).lower()

            return any(term in attrs_text for term in self.BAD_AREA_TERMS)
        except Exception:
            return False

