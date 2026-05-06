from __future__ import annotations

import re
from html import unescape

IMAGE_FILE_RE = re.compile(
    r"https?:/{1,2}[^\s\"'<>|,;]+?\.(?:jpg|jpeg|png|webp|avif)(?:\?[^\s\"'<>|,;]*)?",
    re.IGNORECASE,
)
IMAGE_FIELD_RE = re.compile(
    r"(?:image|images|src|url|thumbnail|thumbnailUrl|contentUrl)\s*[\"']?\s*[:=]\s*[\[\{\s]*[\"']?(https?:/{1,2}[^\s\"'<>|,;]+?\.(?:jpg|jpeg|png|webp|avif)(?:\?[^\s\"'<>|,;]*)?)",
    re.IGNORECASE,
)
IMAGE_EXT_RE = re.compile(r"\.(?:jpg|jpeg|png|webp|avif)(?:$|[?#])", re.IGNORECASE)
BAD_IMAGE_URL_PARTS = (
    "/produto/image",
    "/product/image",
    "logo",
    "sprite",
    "placeholder",
    "favicon",
    "analytics",
    "pixel",
    "doubleclick",
    "facebook.com/tr",
    "base64,",
    "svg+xml",
)


def _fix_scheme(url: str) -> str:
    return re.sub(r"^(https?):/+(?!/)", r"\1://", str(url or "").strip(), flags=re.IGNORECASE)


def _clean_raw(value: object) -> str:
    return unescape(str(value or "")).strip().replace("\\/", "/")


def _valid_image_file_url(url: str) -> bool:
    low = str(url or "").lower().strip()
    if not low.startswith(("http://", "https://")):
        return False
    if not IMAGE_EXT_RE.search(low):
        return False
    if low.count("http://") + low.count("https://") > 1:
        return False
    if any(part in low for part in BAD_IMAGE_URL_PARTS):
        return False
    if re.search(r"(?:image|images|src|url)[\"']?\s*[:=]", low, flags=re.IGNORECASE):
        return False
    return True


def strict_image_urls_pipe(value: object, *, max_images: int = 20) -> str:
    raw = _clean_raw(value)
    if not raw:
        return ""

    candidates: list[str] = []
    for match in IMAGE_FIELD_RE.findall(raw):
        candidates.append(_fix_scheme(match))

    raw = re.sub(r"@(png|jpg|jpeg|webp|avif)", " ", raw, flags=re.IGNORECASE)
    for match in IMAGE_FILE_RE.findall(raw):
        candidates.append(_fix_scheme(match))

    output: list[str] = []
    seen: set[str] = set()
    for url in candidates:
        clean = _fix_scheme(str(url or "").strip().strip('"\'[]{}()'))
        if not _valid_image_file_url(clean):
            continue
        key = clean.lower()
        if key in seen:
            continue
        seen.add(key)
        output.append(clean)
        if len(output) >= max_images:
            break
    return "|".join(output)


def install_image_url_guard_patch() -> None:
    try:
        from bling_app_zero.ui import app_helpers
        app_helpers.normalizar_imagens_pipe = strict_image_urls_pipe
    except Exception:
        pass

    try:
        from bling_app_zero.ui import origem_mapeamento_helpers
        origem_mapeamento_helpers.normalizar_imagens_pipe = strict_image_urls_pipe
    except Exception:
        pass

    try:
        from bling_app_zero.ui.app_helpers import log_debug
        log_debug("Guard global de URL Imagens Externas instalado.", nivel="INFO")
    except Exception:
        pass
