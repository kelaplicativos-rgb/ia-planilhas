from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed

import requests

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


def fetch_live(url: str, timeout: int = 10) -> str:
    if not url:
        return ''
    try:
        with requests.Session() as session:
            response = session.get(url, headers=HEADERS, timeout=timeout, allow_redirects=True)
            if response.status_code in {403, 406, 429}:
                response = session.get(url, headers=ALT_HEADERS, timeout=timeout, allow_redirects=True)
            response.raise_for_status()
            return response.text or ''
    except Exception:
        return ''


def fetch_many_live(urls: list[str], timeout: int = 10, workers: int = 32) -> dict[str, str]:
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
