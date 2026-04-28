from __future__ import annotations

from bs4 import BeautifulSoup
from collections import Counter


class StructureDetector:
    """
    Detecta automaticamente estruturas repetidas na página:
    - listas de produtos
    - grids
    - tabelas
    """

    def __init__(self, html: str):
        self.html = html
        self.soup = BeautifulSoup(html, "lxml")

    def detect(self):
        """
        Retorna os melhores blocos candidatos a produtos
        """
        candidates = []

        # 1️⃣ detectar por repetição de classes
        class_candidates = self._detect_by_class_repetition()
        candidates.extend(class_candidates)

        # 2️⃣ detectar por repetição de estrutura
        tag_candidates = self._detect_by_tag_pattern()
        candidates.extend(tag_candidates)

        # 3️⃣ detectar tabelas
        table_candidates = self._detect_tables()
        candidates.extend(table_candidates)

        # ordenar por score
        candidates = sorted(candidates, key=lambda x: x["score"], reverse=True)

        return candidates[:3]  # top 3 melhores

    # ==========================================
    # 🔎 DETECÇÃO POR CLASSE REPETIDA (PRINCIPAL)
    # ==========================================
    def _detect_by_class_repetition(self):
        elements = self.soup.find_all(True)

        class_counter = Counter()

        for el in elements:
            classes = el.get("class")
            if classes:
                key = " ".join(classes)
                class_counter[key] += 1

        candidates = []

        for class_name, count in class_counter.items():
            if count < 5:
                continue

            blocks = self.soup.find_all(class_=class_name.split())

            score = self._score_blocks(blocks)

            candidates.append({
                "type": "class",
                "class": class_name,
                "elements": blocks,
                "count": count,
                "score": score,
            })

        return candidates

    # ==========================================
    # 🔎 DETECÇÃO POR PADRÃO DE TAG
    # ==========================================
    def _detect_by_tag_pattern(self):
        tag_counter = Counter()

        for el in self.soup.find_all(True):
            key = el.name
            tag_counter[key] += 1

        candidates = []

        for tag, count in tag_counter.items():
            if count < 20:
                continue

            blocks = self.soup.find_all(tag)

            score = self._score_blocks(blocks)

            candidates.append({
                "type": "tag",
                "tag": tag,
                "elements": blocks,
                "count": count,
                "score": score,
            })

        return candidates

    # ==========================================
    # 🔎 DETECTAR TABELAS
    # ==========================================
    def _detect_tables(self):
        tables = self.soup.find_all("table")

        candidates = []

        for table in tables:
            rows = table.find_all("tr")

            if len(rows) < 5:
                continue

            candidates.append({
                "type": "table",
                "elements": rows,
                "count": len(rows),
                "score": len(rows) * 2,
            })

        return candidates

    # ==========================================
    # 🧠 SCORE INTELIGENTE
    # ==========================================
    def _score_blocks(self, blocks):
        score = 0

        for el in blocks[:20]:  # limita pra performance
            text = el.get_text(strip=True)

            # tem texto?
            if len(text) > 20:
                score += 2

            # tem link?
            if el.find("a"):
                score += 2

            # tem imagem?
            if el.find("img"):
                score += 2

            # tem preço?
            if any(x in text.lower() for x in ["r$", "$", "€"]):
                score += 3

        return score
