from __future__ import annotations

from bs4 import BeautifulSoup

NEXT_TEXTS = (
    "próxima", "proxima", "próximo", "proximo", "next",
    "carregar mais", "ver mais", "mostrar mais", "load more",
)


def detect_next_links(html: str, base_url: str) -> list[str]:
    from urllib.parse import urljoin

    soup = BeautifulSoup(html or "", "html.parser")
    links: list[str] = []
    seen: set[str] = set()
    for tag in soup.find_all(["a", "button"]):
        text = " ".join(tag.get_text(" ").lower().split())
        rel = " ".join(tag.get("rel") or []).lower() if isinstance(tag.get("rel"), list) else str(tag.get("rel") or "").lower()
        aria = str(tag.get("aria-label") or "").lower()
        klass = " ".join(tag.get("class") or []).lower() if isinstance(tag.get("class"), list) else str(tag.get("class") or "").lower()
        looks_next = any(term in text for term in NEXT_TEXTS) or any(term in aria for term in NEXT_TEXTS) or "next" in rel or "next" in klass or "pagination-next" in klass
        href = tag.get("href")
        if looks_next and href:
            url = urljoin(base_url, str(href))
            if url not in seen:
                seen.add(url)
                links.append(url)
    return links[:5]


def next_button_locators() -> list[str]:
    return [
        "text=/carregar mais/i", "text=/ver mais/i", "text=/mostrar mais/i",
        "text=/pr[oó]xima/i", "text=/pr[oó]ximo/i", "text=/next/i",
        "button[aria-label*='Next']", "button[aria-label*='Próxima']",
        "a[rel='next']", ".pagination-next", ".next",
    ]
