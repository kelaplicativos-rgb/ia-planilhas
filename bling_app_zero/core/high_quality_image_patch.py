from __future__ import annotations

"""Patch leve para priorizar imagens de alta qualidade no cadastro Bling.

A saída do Bling usa links separados por `|`. Este módulo reordena os links
para deixar primeiro as imagens maiores/originais e empurrar miniaturas para o
fim, sem alterar a quantidade de produtos.
"""

import re
from typing import Iterable


def _score_image_url(url: str) -> int:
    low = str(url or "").lower()
    score = 0

    strong_tokens = (
        ("zoom", 90),
        ("large", 85),
        ("original", 85),
        ("full", 75),
        ("big", 65),
        ("grande", 65),
        ("produto", 40),
        ("product", 40),
        ("upload", 30),
        ("cdn", 15),
    )
    for token, points in strong_tokens:
        if token in low:
            score += points

    for width, height in re.findall(r"(\d{2,5})[xX](\d{2,5})", low):
        try:
            area = int(width) * int(height)
        except Exception:
            continue
        if area >= 1_000_000:
            score += 140
        elif area >= 500_000:
            score += 100
        elif area >= 160_000:
            score += 60
        elif area < 40_000:
            score -= 100

    weak_tokens = (
        ("thumbnail", -120),
        ("thumb", -110),
        ("small", -90),
        ("mini", -85),
        ("tiny", -85),
        ("icon", -120),
        ("80x80", -120),
        ("100x100", -110),
        ("150x150", -100),
        ("200x200", -80),
    )
    for token, points in weak_tokens:
        if token in low:
            score += points

    if re.search(r"\.(webp|jpg|jpeg|png)(?:$|[?#])", low):
        score += 20

    return score


def reorder_high_quality_images(value: object, *, max_items: int = 20) -> str:
    text = "" if value is None else str(value).strip()
    if not text:
        return ""

    bad_fragments = (
        "logo",
        "sprite",
        "placeholder",
        "blank",
        "loading",
        "favicon",
        "facebook.com/tr",
        "pixel",
        "analytics",
        "doubleclick",
        "tracking",
        "whatsapp",
        "instagram",
    )

    urls: list[str] = []
    seen: set[str] = set()
    for part in re.split(r"[|,\n\r\t]+", text):
        url = part.strip().strip('"\'')
        if not url or not url.lower().startswith(("http://", "https://")):
            continue
        low = url.lower()
        if any(fragment in low for fragment in bad_fragments):
            continue
        if url in seen:
            continue
        seen.add(url)
        urls.append(url)

    urls.sort(key=_score_image_url, reverse=True)
    return "|".join(urls[:max_items])


def install_high_quality_image_patch() -> None:
    """Aplica patch na normalização final de URLs de imagem."""
    try:
        from bling_app_zero.core import product_data_quality as quality
    except Exception:
        return

    original = getattr(quality, "_normalize_pipe_urls", None)

    def patched(value: object, *, max_items: int = 20) -> str:
        result = reorder_high_quality_images(value, max_items=max_items)
        if result:
            return result
        if callable(original):
            return original(value, max_items=max_items)
        return ""

    quality._normalize_pipe_urls = patched
