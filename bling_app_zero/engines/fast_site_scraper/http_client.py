from __future__ import annotations

import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urlparse

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7',
    'Cache-Control': 'no-cache, no-store, max-age=0',
    'Pragma': 'no-cache',
}

ALT_HEADERS = {
    **HEADERS,
    'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/121.0 Safari/537.36',
}

DESKTOP_HEADERS = {
    **HEADERS,
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
    'Connection': 'keep-alive',
    'DNT': '1',
    'Sec-Fetch-Dest': 'document',
    'Sec-Fetch-Mode': 'navigate',
    'Sec-Fetch-Site': 'same-origin',
    'Sec-Fetch-User': '?1',
    'Upgrade-Insecure-Requests': '1',
}

_TEXT_CONTENT_HINTS = ('text/', 'html', 'xml', 'json', 'javascript')
_BLOCKED_TEXT_HINTS = (
    'access denied',
    'attention required',
    'enable javascript',
    'checking your browser',
    'cf-browser-verification',
)
_THREAD_LOCAL = threading.local()


def _session() -> requests.Session:
    session = getattr(_THREAD_LOCAL, 'session', None)
    if session is not None:
        return session

    retry = Retry(
        total=2,
        connect=2,
        read=1,
        status=2,
        backoff_factor=0.25,
        status_forcelist=(403, 406, 408, 425, 429, 500, 502, 503, 504),
        allowed_methods=('GET', 'HEAD'),
        raise_on_status=False,
    )
    adapter = HTTPAdapter(pool_connections=64, pool_maxsize=64, max_retries=retry)
    session = requests.Session()
    session.mount('http://', adapter)
    session.mount('https://', adapter)
    _THREAD_LOCAL.session = session
    return session


def _origin(url: str) -> str:
    parsed = urlparse(str(url or ''))
    return f'{parsed.scheme}://{parsed.netloc}' if parsed.scheme and parsed.netloc else ''


def _with_navigation_headers(url: str, headers: dict[str, str]) -> dict[str, str]:
    origin = _origin(url)
    if not origin:
        return dict(headers)
    return {**headers, 'Referer': origin + '/', 'Origin': origin}


def _looks_text_response(response: requests.Response) -> bool:
    content_type = str(response.headers.get('content-type') or '').lower()
    if not content_type:
        return True
    return any(hint in content_type for hint in _TEXT_CONTENT_HINTS)


def _response_text(response: requests.Response) -> str:
    if not _looks_text_response(response):
        return ''
    if not response.encoding:
        response.encoding = response.apparent_encoding or 'utf-8'
    return response.text or ''


def _looks_blocked_or_empty(text: str) -> bool:
    clean = str(text or '').strip()
    if not clean:
        return True
    low = clean[:5000].lower()
    return len(clean) < 300 and any(hint in low for hint in _BLOCKED_TEXT_HINTS)


def _fetch_once(session: requests.Session, url: str, headers: dict[str, str], timeout: int) -> tuple[int, str]:
    response = session.get(url, headers=headers, timeout=(4, max(4, int(timeout))), allow_redirects=True)
    if response.status_code >= 400:
        return response.status_code, ''
    return response.status_code, _response_text(response)


def fetch_live(url: str, timeout: int = 8) -> str:
    if not url:
        return ''
    try:
        session = _session()
        attempts = [
            (HEADERS, timeout),
            (_with_navigation_headers(url, DESKTOP_HEADERS), max(timeout, 12)),
            (_with_navigation_headers(url, ALT_HEADERS), max(timeout, 12)),
        ]
        for headers, attempt_timeout in attempts:
            status_code, text = _fetch_once(session, url, headers, attempt_timeout)
            if text and not _looks_blocked_or_empty(text):
                return text
            if status_code not in {403, 406, 408, 425, 429, 500, 502, 503, 504} and text:
                return text
    except Exception:
        return ''
    return ''


def fetch_many_live(urls: list[str], timeout: int = 8, workers: int = 48) -> dict[str, str]:
    result: dict[str, str] = {}
    clean_urls = [url for url in dict.fromkeys(urls) if url]
    if not clean_urls:
        return result

    with ThreadPoolExecutor(max_workers=max(1, min(workers, len(clean_urls)))) as executor:
        futures = {executor.submit(fetch_live, url, timeout): url for url in clean_urls}
        for future in as_completed(futures):
            url = futures[future]
            try:
                result[url] = future.result() or ''
            except Exception:
                result[url] = ''
    return result
