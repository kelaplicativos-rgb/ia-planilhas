from urllib.parse import urlparse, urldefrag


def normalize_url(url: str) -> str:
    url = urldefrag(url.strip())[0]
    return url.rstrip("/")


def same_domain(url: str, base_domain: str) -> bool:
    try:
        host = urlparse(url).netloc.lower()
        return host == base_domain or host.endswith("." + base_domain)
    except Exception:
        return False
