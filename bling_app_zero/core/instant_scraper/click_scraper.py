from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any
from urllib.parse import urljoin

import pandas as pd
from bs4 import BeautifulSoup, Tag


@dataclass
class ClickTarget:
    selector: str
    label: str
    score: int
    total: int


def _txt(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "").replace("\xa0", " ")).strip()


def _safe_class_selector(tag: Tag) -> str:
    classes = tag.get("class", [])
    if not isinstance(classes, list):
        classes = [str(classes)] if classes else []
    clean = []
    for item in classes[:4]:
        item = re.sub(r"[^A-Za-z0-9_-]", "", str(item or ""))
        if item:
            clean.append(item)
    if clean:
        return tag.name + "." + ".".join(clean)
    return tag.name


def _abs(base_url: str, href: str) -> str:
    href = _txt(href)
    if not href or href.startswith(("javascript:", "mailto:", "tel:")):
        return ""
    return urljoin(base_url, href)


def _looks_price(text: str) -> bool:
    return bool(re.search(r"R\$\s*\d|\d+[\.,]\d{2}", _txt(text)))


def _score_tag(tag: Tag) -> int:
    text = _txt(tag.get_text(" ", strip=True)).lower()
    score = 0
    if tag.find("a", href=True):
        score += 15
    if tag.find("img"):
        score += 12
    if _looks_price(text):
        score += 25
    if any(x in text for x in ["comprar", "produto", "sku", "código", "codigo", "ref"]):
        score += 15
    if len(text) > 30:
        score += 8
    if len(text) > 1200:
        score -= 20
    return max(score, 0)


def discover_click_targets(html: str, min_group: int = 3) -> list[ClickTarget]:
    soup = BeautifulSoup(str(html or ""), "html.parser")
    for bad in soup(["script", "style", "noscript", "svg"]):
        bad.decompose()

    groups: dict[str, list[Tag]] = {}
    for tag in soup.find_all(["article", "li", "div", "section"], limit=3000):
        text = _txt(tag.get_text(" ", strip=True))
        if len(text) < 15:
            continue
        if not (tag.find("a", href=True) or tag.find("img") or _looks_price(text)):
            continue
        selector = _safe_class_selector(tag)
        groups.setdefault(selector, []).append(tag)

    targets: list[ClickTarget] = []
    for selector, tags in groups.items():
        if len(tags) < min_group:
            continue
        score = int(sum(_score_tag(t) for t in tags[:30]) / max(min(len(tags), 30), 1)) + min(len(tags), 50)
        label = _txt(tags[0].get_text(" ", strip=True))[:90]
        if score >= 35:
            targets.append(ClickTarget(selector=selector, label=label, score=score, total=len(tags)))

    return sorted(targets, key=lambda x: x.score, reverse=True)[:20]


def _extract_from_tag(tag: Tag, base_url: str) -> dict[str, str]:
    row: dict[str, str] = {}
    link = tag.find("a", href=True)
    if link:
        row["url_produto"] = _abs(base_url, link.get("href", ""))

    img = tag.find("img")
    if img:
        row["imagens"] = _abs(base_url, img.get("src") or img.get("data-src") or img.get("data-original") or "")
        alt = _txt(img.get("alt", ""))
        if alt:
            row["nome"] = alt

    for sel in ["[class*=title]", "[class*=name]", "[class*=nome]", "[class*=produto]", "h1", "h2", "h3", "h4", "a"]:
        el = tag.select_one(sel)
        value = _txt(el.get_text(" ", strip=True)) if el else ""
        if value and len(value) >= 3:
            row.setdefault("nome", value[:180])
            break

    text = _txt(tag.get_text(" ", strip=True))
    m = re.search(r"R\$\s*\d{1,3}(?:\.\d{3})*,\d{2}|R\$\s*\d+[\.,]\d{2}|\d{1,3}(?:\.\d{3})*,\d{2}", text)
    if m:
        row["preco"] = m.group(0)

    sku = re.search(r"(?:sku|c[oó]d(?:igo)?|ref)\s*[:#\-]?\s*([A-Za-z0-9._\-]{3,40})", text, flags=re.I)
    if sku:
        row["sku"] = sku.group(1)

    if text:
        row["descricao"] = text[:500]

    return {k: v for k, v in row.items() if _txt(v)}


def extract_by_selector(html: str, base_url: str, selector: str) -> pd.DataFrame:
    soup = BeautifulSoup(str(html or ""), "html.parser")
    rows: list[dict[str, str]] = []
    seen = set()
    for tag in soup.select(str(selector or ""))[:500]:
        if not isinstance(tag, Tag):
            continue
        row = _extract_from_tag(tag, base_url)
        key = (row.get("url_produto", ""), row.get("nome", ""), row.get("preco", ""))
        if not any(key) or key in seen:
            continue
        seen.add(key)
        rows.append(row)
    df = pd.DataFrame(rows).fillna("")
    if not df.empty:
        df["_click_selector"] = selector
    return df


def auto_click_extract(html: str, base_url: str) -> pd.DataFrame:
    targets = discover_click_targets(html)
    if not targets:
        return pd.DataFrame()
    return extract_by_selector(html, base_url, targets[0].selector)
