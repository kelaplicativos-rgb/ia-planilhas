from __future__ import annotations

from typing import Any

import httpx

from .html_fetcher import fetch_html


DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
    "Cache-Control": "no-cache",
    "Pragma": "no-cache",
}


def _txt(value: Any) -> str:
    return str(value or "").strip()


def normalize_cookie(raw_cookie: str) -> str:
    cookie = _txt(raw_cookie)
    if not cookie:
        return ""
    cookie = cookie.replace("\n", "; ").replace("\r", "; ")
    parts = []
    for item in cookie.split(";"):
        item = item.strip()
        if not item or "=" not in item:
            continue
        parts.append(item)
    return "; ".join(dict.fromkeys(parts))


def fetch_html_with_auth(url: str, auth_context: dict | None = None, timeout: int = 25) -> str:
    auth_context = auth_context or {}
    cookie = normalize_cookie(auth_context.get("cookie") or auth_context.get("cookies") or "")
    extra_headers = auth_context.get("headers") if isinstance(auth_context.get("headers"), dict) else {}

    if not cookie and not extra_headers:
        return fetch_html(url, force_refresh=True)

    headers = DEFAULT_HEADERS.copy()
    headers.update({str(k): str(v) for k, v in extra_headers.items() if str(k).strip()})
    if cookie:
        headers["Cookie"] = cookie

    try:
        with httpx.Client(timeout=timeout, follow_redirects=True, headers=headers) as client:
            response = client.get(str(url or "").strip())
            if response.status_code >= 400:
                return ""
            text = response.text or ""
            if "<html" not in text.lower() and "<!doctype" not in text.lower():
                return ""
            return text[:1_200_000]
    except Exception:
        return ""
