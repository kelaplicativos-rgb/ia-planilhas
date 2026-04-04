from typing import Dict

import requests

DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8",
}


def baixar_html(url: str, timeout: int = 20) -> Dict:
    url = (url or "").strip()
    if not url:
        return {"ok": False, "erro": "URL vazia.", "url": url, "html": ""}

    try:
        resposta = requests.get(
            url,
            headers=DEFAULT_HEADERS,
            timeout=timeout,
            allow_redirects=True,
        )
        resposta.raise_for_status()

        content_type = resposta.headers.get("Content-Type", "")
        html = resposta.text or ""

        return {
            "ok": True,
            "erro": "",
            "url": resposta.url,
            "status_code": resposta.status_code,
            "content_type": content_type,
            "html": html,
        }
    except Exception as e:
        return {
            "ok": False,
            "erro": str(e),
            "url": url,
            "html": "",
        }
