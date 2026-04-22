from __future__ import annotations

from typing import Any, Dict, Iterable, Optional
from urllib.parse import urlparse

import requests


DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8",
}


def _clean_text(value: Any) -> str:
    text = str(value or "").strip()
    return "" if text.lower() in {"none", "null", "nan"} else text


def normalize_url(url: str) -> str:
    value = _clean_text(url)
    if not value:
        return ""
    if not value.startswith(("http://", "https://")):
        value = f"https://{value}"
    return value


def _normalize_cookie_item(cookie: Any) -> Optional[Dict[str, Any]]:
    if isinstance(cookie, requests.cookies.CookieConflictError):
        return None

    if isinstance(cookie, dict):
        name = _clean_text(cookie.get("name"))
        value = _clean_text(cookie.get("value"))
        domain = _clean_text(cookie.get("domain"))
        path = _clean_text(cookie.get("path")) or "/"
        if not name:
            return None
        return {
            "name": name,
            "value": value,
            "domain": domain,
            "path": path,
        }

    return None


def _cookie_domain_matches(hostname: str, cookie_domain: str) -> bool:
    host = _clean_text(hostname).lower().lstrip(".")
    domain = _clean_text(cookie_domain).lower().lstrip(".")
    if not domain:
        return True
    return host == domain or host.endswith(f".{domain}")


def _apply_cookies(session: requests.Session, cookies: Iterable[Any], target_url: str) -> None:
    hostname = (urlparse(target_url).hostname or "").strip().lower()

    for raw_cookie in cookies or []:
        cookie = _normalize_cookie_item(raw_cookie)
        if not cookie:
            continue

        if cookie["domain"] and hostname and not _cookie_domain_matches(hostname, cookie["domain"]):
            continue

        session.cookies.set(
            cookie["name"],
            cookie["value"],
            domain=cookie["domain"] or None,
            path=cookie["path"] or "/",
        )


def build_session(
    *,
    auth_context: Optional[Dict[str, Any]] = None,
    target_url: str = "",
    extra_headers: Optional[Dict[str, str]] = None,
) -> requests.Session:
    session = requests.Session()
    session.headers.update(DEFAULT_HEADERS)

    if extra_headers:
        session.headers.update({str(k): str(v) for k, v in extra_headers.items() if str(k).strip()})

    if isinstance(auth_context, dict) and auth_context:
        headers = auth_context.get("headers") or {}
        if isinstance(headers, dict):
            session.headers.update({str(k): str(v) for k, v in headers.items() if str(k).strip()})

        cookies = auth_context.get("cookies") or []
        _apply_cookies(session, cookies, target_url=target_url)

    return session


def get_response(
    url: str,
    *,
    auth_context: Optional[Dict[str, Any]] = None,
    timeout: int = 20,
    extra_headers: Optional[Dict[str, str]] = None,
) -> Optional[requests.Response]:
    target_url = normalize_url(url)
    if not target_url:
        return None

    try:
        session = build_session(
            auth_context=auth_context,
            target_url=target_url,
            extra_headers=extra_headers,
        )
        response = session.get(target_url, timeout=timeout, allow_redirects=True)
        if response.status_code >= 400:
            return None
        return response
    except Exception:
        return None


def get_html(
    url: str,
    *,
    auth_context: Optional[Dict[str, Any]] = None,
    timeout: int = 20,
    extra_headers: Optional[Dict[str, str]] = None,
) -> str:
    response = get_response(
        url,
        auth_context=auth_context,
        timeout=timeout,
        extra_headers=extra_headers,
    )
    if response is None:
        return ""
    return response.text or ""
