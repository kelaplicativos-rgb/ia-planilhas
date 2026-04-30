from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any
from urllib.parse import urljoin

import pandas as pd
from bs4 import BeautifulSoup, Tag


@dataclass
class InstantCandidate:
    kind: str
    score: int
    rows: list[dict[str, str]]
    selector_hint: str = ""


def _txt(valor: Any) -> str:
    texto = str(valor or "").replace("\xa0", " ")
    texto = re.sub(r"\s+", " ", texto).strip()
    return texto


def _clean_col(nome: Any, fallback: str) -> str:
    col = _txt(nome)
    if not col:
        return fallback
    col = re.sub(r"[^0-9A-Za-zÀ-ÿ _\-./]", "", col).strip()
    return col[:80] or fallback


def _abs_url(base_url: str, href: str) -> str:
    href = _txt(href)
    if not href:
        return ""
    if href.startswith("javascript:") or href.startswith("mailto:") or href.startswith("tel:"):
        return ""
    return urljoin(base_url, href)


def _parece_preco(texto: str) -> bool:
    texto = _txt(texto).lower()
    return bool(re.search(r"r\$\s*\d|\d+[\.,]\d{2}", texto))


def _score_rows(rows: list[dict[str, str]]) -> int:
    if not rows:
        return 0

    score = min(len(rows), 50)
    cols = set()
    textos = []

    for row in rows[:50]:
        cols.update(k.lower() for k in row.keys())
        textos.extend(str(v) for v in row.values())

    joined = " ".join(textos).lower()

    if len(cols) >= 3:
        score += 15
    if any(k in cols for k in ["nome", "produto", "descricao", "descrição", "title"]):
        score += 20
    if "preco" in cols or "preço" in cols or _parece_preco(joined):
        score += 25
    if "url_produto" in cols or "link" in cols:
        score += 15
    if "imagem" in cols or "imagens" in cols:
        score += 10
    if any(p in joined for p in ["comprar", "produto", "r$", "sku", "código", "codigo"]):
        score += 15

    if len(rows) > 20 and len(cols) <= 2 and not _parece_preco(joined):
        score -= 35

    return max(score, 0)


def _extract_tables(soup: BeautifulSoup, base_url: str) -> list[InstantCandidate]:
    candidates: list[InstantCandidate] = []

    for idx, table in enumerate(soup.find_all("table")[:20], start=1):
        headers = [_clean_col(th.get_text(" ", strip=True), f"col_{i+1}") for i, th in enumerate(table.find_all("th"))]
        rows: list[dict[str, str]] = []

        for tr in table.find_all("tr"):
            cells = tr.find_all(["td", "th"])
            if not cells or len(cells) < 2:
                continue

            headers_local = headers if headers and len(headers) == len(cells) else [f"col_{i+1}" for i in range(len(cells))]
            row: dict[str, str] = {}

            for i, cell in enumerate(cells):
                col = headers_local[i] if i < len(headers_local) else f"col_{i+1}"
                row[col] = _txt(cell.get_text(" ", strip=True))

                link = cell.find("a", href=True)
                if link and not row.get("url_produto"):
                    row["url_produto"] = _abs_url(base_url, link.get("href", ""))

                img = cell.find("img")
                if img and not row.get("imagens"):
                    row["imagens"] = _abs_url(base_url, img.get("src") or img.get("data-src") or "")

            if any(v for v in row.values()):
                rows.append(row)

        score = _score_rows(rows)
        if score >= 30:
            candidates.append(InstantCandidate("table", score, rows, f"table:{idx}"))

    return candidates


def _tag_signature(tag: Tag) -> str:
    classes = tag.get("class", [])
    if isinstance(classes, list):
        classes = ".".join(str(c) for c in classes[:4])
    return f"{tag.name}.{classes}".strip(".")


def _is_noise_tag(tag: Tag) -> bool:
    text = _txt(tag.get_text(" ", strip=True)).lower()
    classes = " ".join(tag.get("class", []) if isinstance(tag.get("class"), list) else [_txt(tag.get("class", ""))]).lower()
    tag_id = _txt(tag.get("id", "")).lower()
    marker = f"{classes} {tag_id} {text[:120]}"
    bad = ["menu", "nav", "footer", "header", "cookie", "breadcrumb", "pagination", "modal", "login"]
    return any(b in marker for b in bad)


def _extract_item(tag: Tag, base_url: str) -> dict[str, str]:
    row: dict[str, str] = {}

    link = tag.find("a", href=True)
    if link:
        row["url_produto"] = _abs_url(base_url, link.get("href", ""))

    img = tag.find("img")
    if img:
        row["imagens"] = _abs_url(base_url, img.get("src") or img.get("data-src") or img.get("data-original") or "")
        alt = _txt(img.get("alt", ""))
        if alt:
            row["nome"] = alt

    for selector in ["[class*=title]", "[class*=name]", "[class*=nome]", "[class*=produto]", "h1", "h2", "h3", "h4", "a"]:
        el = tag.select_one(selector)
        text = _txt(el.get_text(" ", strip=True)) if el else ""
        if text and len(text) >= 3:
            row.setdefault("nome", text[:180])
            break

    for selector in ["[class*=price]", "[class*=preco]", "[class*=preço]", "[data-price]", "[itemprop=price]"]:
        el = tag.select_one(selector)
        text = _txt(el.get_text(" ", strip=True) if el else "")
        data_price = _txt(el.get("data-price", "")) if el else ""
        candidate = data_price or text
        if candidate and _parece_preco(candidate):
            row["preco"] = candidate[:60]
            break

    text_all = _txt(tag.get_text(" ", strip=True))
    if "preco" not in row:
        match = re.search(r"R\$\s*\d{1,3}(?:\.\d{3})*,\d{2}|R\$\s*\d+[\.,]\d{2}|\d{1,3}(?:\.\d{3})*,\d{2}", text_all)
        if match:
            row["preco"] = match.group(0)

    if text_all:
        row["descricao"] = text_all[:500]

    sku_match = re.search(r"(?:sku|c[oó]d(?:igo)?|ref(?:er[êe]ncia)?)\s*[:#\-]?\s*([A-Za-z0-9._\-]{3,40})", text_all, flags=re.I)
    if sku_match:
        row["sku"] = sku_match.group(1)

    return {k: v for k, v in row.items() if _txt(v)}


def _extract_repeated_blocks(soup: BeautifulSoup, base_url: str) -> list[InstantCandidate]:
    candidates: list[InstantCandidate] = []
    containers = soup.find_all(["div", "li", "article", "section"], limit=2500)

    by_signature: dict[str, list[Tag]] = {}
    for tag in containers:
        if _is_noise_tag(tag):
            continue
        text = _txt(tag.get_text(" ", strip=True))
        if len(text) < 15 or len(text) > 2500:
            continue
        if not (tag.find("a", href=True) or tag.find("img") or _parece_preco(text)):
            continue
        sig = _tag_signature(tag)
        by_signature.setdefault(sig, []).append(tag)

    for sig, tags in by_signature.items():
        if len(tags) < 3:
            continue

        rows = []
        seen = set()
        for tag in tags[:120]:
            row = _extract_item(tag, base_url)
            key = (row.get("url_produto", ""), row.get("nome", ""), row.get("preco", ""))
            if not any(key) or key in seen:
                continue
            seen.add(key)
            rows.append(row)

        score = _score_rows(rows)
        if score >= 45:
            candidates.append(InstantCandidate("repeated_dom", score, rows, sig))

    return candidates


def instant_candidates(html: str, base_url: str, min_score: int = 30) -> list[InstantCandidate]:
    html = str(html or "")
    if not html.strip():
        return []

    soup = BeautifulSoup(html, "html.parser")
    for bad in soup(["script", "style", "noscript", "svg"]):
        bad.decompose()

    candidates: list[InstantCandidate] = []
    candidates.extend(_extract_tables(soup, base_url))
    candidates.extend(_extract_repeated_blocks(soup, base_url))
    return [c for c in sorted(candidates, key=lambda c: c.score, reverse=True) if c.score >= min_score]


def candidate_to_dataframe(candidate: InstantCandidate) -> pd.DataFrame:
    df = pd.DataFrame(candidate.rows).fillna("")
    if df.empty:
        return df
    df["_instant_kind"] = candidate.kind
    df["_instant_score"] = str(candidate.score)
    df["_instant_selector"] = candidate.selector_hint
    return df.reset_index(drop=True)


def instant_candidates_to_frames(html: str, base_url: str, min_score: int = 30, limit: int = 8) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for idx, cand in enumerate(instant_candidates(html, base_url, min_score=min_score)[:limit], start=1):
        df = candidate_to_dataframe(cand)
        out.append({
            "id": idx,
            "kind": cand.kind,
            "score": cand.score,
            "selector": cand.selector_hint,
            "total_rows": len(df),
            "dataframe": df,
        })
    return out


def instant_extract(html: str, base_url: str, min_score: int = 45) -> pd.DataFrame:
    candidates = instant_candidates(html, base_url, min_score=min_score)
    if not candidates:
        return pd.DataFrame()
    return candidate_to_dataframe(candidates[0])
