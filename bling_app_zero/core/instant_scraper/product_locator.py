from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlparse


@dataclass(frozen=True)
class ProductUrlSignal:
    url: str
    domain: str
    looks_like_product: bool
    score: int
    reasons: tuple[str, ...]


_PRODUCT_HINTS = (
    "/produto",
    "/product",
    "/produtos",
    "/p/",
    "sku=",
    "produto=",
    "product_id=",
)

_CATEGORY_HINTS = (
    "/categoria",
    "/category",
    "/departamento",
    "/collections",
)


def analyze_product_url(url: str) -> ProductUrlSignal:
    parsed = urlparse(str(url or "").strip())
    lowered = (parsed.path + "?" + parsed.query).lower()
    reasons: list[str] = []
    score = 0

    for hint in _PRODUCT_HINTS:
        if hint in lowered:
            score += 3
            reasons.append(f"hint_produto:{hint}")

    for hint in _CATEGORY_HINTS:
        if hint in lowered:
            score -= 1
            reasons.append(f"hint_categoria:{hint}")

    if any(char.isdigit() for char in lowered):
        score += 1
        reasons.append("possui_numero")

    if lowered.count("/") >= 2:
        score += 1
        reasons.append("url_profunda")

    return ProductUrlSignal(
        url=url,
        domain=parsed.netloc.lower(),
        looks_like_product=score >= 2,
        score=score,
        reasons=tuple(reasons),
    )


def filter_product_urls(urls: list[str]) -> list[str]:
    signals = [analyze_product_url(url) for url in urls]
    signals.sort(key=lambda item: item.score, reverse=True)
    return [signal.url for signal in signals if signal.looks_like_product]
