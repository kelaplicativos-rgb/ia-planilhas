from __future__ import annotations

import re
from html import unescape

from bling_app_zero.core.image_quality_validator import filter_product_image_urls

IMAGE_FILE_RE = re.compile(
    r"https?:/{1,2}[^\s\"'<>|,;]+?\.(?:jpg|jpeg|png|webp|avif)(?:\?[^\s\"'<>|,;]*)?",
    re.IGNORECASE,
)
IMAGE_FIELD_RE = re.compile(
    r"(?:image|images|src|url|thumbnail|thumbnailUrl|contentUrl)\s*[\"']?\s*[:=]\s*[\[\{\s]*[\"']?(https?:/{1,2}[^\s\"'<>|,;]+?\.(?:jpg|jpeg|png|webp|avif)(?:\?[^\s\"'<>|,;]*)?)",
    re.IGNORECASE,
)


def _fix_scheme(url: str) -> str:
    return re.sub(r"^(https?):/+(?!/)", r"\1://", str(url or "").strip(), flags=re.IGNORECASE)


def _clean_raw(value: object) -> str:
    return unescape(str(value or "")).strip().replace("\\/", "/")


def strict_image_urls_pipe(
    value: object,
    *,
    max_images: int = 20,
    product_title: object = "",
    context: object = "",
    validate_remote: bool = False,
) -> str:
    raw = _clean_raw(value)
    if not raw:
        return ""

    candidates: list[str] = []
    for match in IMAGE_FIELD_RE.findall(raw):
        candidates.append(_fix_scheme(match))

    raw = re.sub(r"@(png|jpg|jpeg|webp|avif)", " ", raw, flags=re.IGNORECASE)
    for match in IMAGE_FILE_RE.findall(raw):
        candidates.append(_fix_scheme(match))

    if not candidates:
        candidates = re.split(r"[|,\n\r\t]+", raw)

    return filter_product_image_urls(
        candidates,
        product_title=product_title,
        context=context,
        max_images=max_images,
        require_remote=validate_remote,
        require_product_match=False,
    )


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
        log_debug("Guard global de URL Imagens Externas instalado com validação de qualidade.", nivel="INFO")
    except Exception:
        pass
