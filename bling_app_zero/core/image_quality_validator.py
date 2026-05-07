from __future__ import annotations

"""Validação de qualidade para URLs de imagens de produtos.

Este módulo trabalha em três níveis:
1. Higiene de URL: bloqueia logo, banner, pixel, rastreador, ícones, redes sociais etc.
2. Qualidade técnica: opcionalmente consulta a URL e valida status, content-type, peso e dimensão.
3. Compatibilidade com produto: usa tokens do nome do produto na URL/arquivo/contexto para priorizar imagens que parecem ser do item.

Observação importante: sem visão computacional/API externa não existe 100% de certeza visual.
A validação aqui é determinística, rápida e segura para Streamlit Cloud.
"""

from dataclasses import dataclass
from functools import lru_cache
import re
import struct
import unicodedata
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import requests

IMAGE_EXTENSIONS = (".jpg", ".jpeg", ".png", ".webp", ".avif")
MIN_IMAGE_BYTES = 3_000
MIN_IMAGE_WIDTH = 180
MIN_IMAGE_HEIGHT = 180
DEFAULT_TIMEOUT = 4

DROP_QUERY_PARAMS = {
    "fbclid", "gclid", "gbraid", "wbraid", "utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content",
    "utm_id", "mc_cid", "mc_eid", "igshid", "ref", "source", "campaign",
}

BAD_URL_PARTS = (
    "logo", "sprite", "placeholder", "favicon", "pixel", "analytics", "doubleclick", "googletagmanager",
    "google-analytics", "googleadservices", "googleads", "adsystem", "hotjar", "clarity", "tracking", "track",
    "noscript", "blank", "loading", "spacer", "transparent", "base64", "svg+xml", "banner", "payment", "pagamento",
    "boleto", "pix", "visa", "mastercard", "ssl", "security", "seguro", "captcha", "avatar", "footer", "header",
    "menu", "icone", "icon", "whatsapp", "instagram", "facebook", "youtube", "tiktok", "linkedin", "twitter",
    "x-twitter", "user", "usuario", "store-logo", "brand-logo",
)

GOOD_PATH_HINTS = (
    "/produto/", "/product/", "/products/", "/produtos/", "/cdn/shop/", "/uploads/", "/upload/", "/media/",
    "/catalog/", "/catalogo/", "/fotos/", "/foto/", "/images/", "/image/", "/img/", "/files/", "/storage/",
)

STOP_WORDS = {
    "para", "com", "sem", "por", "de", "da", "do", "das", "dos", "em", "no", "na", "nos", "nas", "a", "o", "as", "os",
    "um", "uma", "uns", "umas", "produto", "produtos", "kit", "novo", "nova", "preto", "branco", "azul", "vermelho",
    "verde", "amarelo", "rosa", "cinza", "inox", "un", "und", "pcs", "peca", "peça", "pecas", "peças",
}

URL_RE = re.compile(r"^https?://", re.IGNORECASE)
IMAGE_EXT_RE = re.compile(r"\.(?:jpg|jpeg|png|webp|avif)(?:$|[?#])", re.IGNORECASE)
TOKEN_RE = re.compile(r"[a-z0-9]{3,}")


@dataclass(frozen=True)
class ImageQualityResult:
    url: str
    ok: bool
    reason: str = ""
    width: int = 0
    height: int = 0
    bytes_size: int = 0
    product_score: float = 0.0


def normalize_text(value: object) -> str:
    text = str(value or "").strip().lower()
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def product_tokens(product_title: object) -> set[str]:
    norm = normalize_text(product_title)
    tokens = {t for t in TOKEN_RE.findall(norm) if t not in STOP_WORDS and not t.isdigit()}
    return {t for t in tokens if len(t) >= 3}


def clean_image_url(url: object) -> str:
    raw = str(url or "").strip().strip('"\'[]{}()')
    raw = raw.replace("\\/", "/")
    raw = re.sub(r"^(https?):/+(?!/)", r"\1://", raw, flags=re.IGNORECASE)
    raw = re.sub(r"[\]\[\}\{\)\(\"']+$", "", raw).strip()
    raw = re.sub(r"[.,;:]+$", "", raw).strip()
    if raw.startswith("//"):
        raw = "https:" + raw
    if raw.startswith("www."):
        raw = "https://" + raw
    if not URL_RE.search(raw):
        return ""
    parsed = urlsplit(raw)
    query = [(k, v) for k, v in parse_qsl(parsed.query, keep_blank_values=True) if k.lower() not in DROP_QUERY_PARAMS]
    return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, urlencode(query, doseq=True), ""))


def image_url_key(url: object) -> str:
    clean = clean_image_url(url)
    if not clean:
        return ""
    parsed = urlsplit(clean.lower())
    return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, "", ""))


def has_image_extension(url: object) -> bool:
    return bool(IMAGE_EXT_RE.search(str(url or "")))


def looks_like_possible_product_image(url: object) -> bool:
    clean = clean_image_url(url)
    if not clean:
        return False
    low = clean.lower()
    parsed = urlsplit(low)
    if not parsed.netloc or not parsed.path:
        return False
    if any(bad in low for bad in BAD_URL_PARTS):
        return False
    if re.search(r"(?:^|[-_/])(?:1x1|2x2|pixel|spacer|transparent)(?:[-_.?/]|$)", low):
        return False
    if parsed.path.lower().endswith((".svg", ".gif", ".ico", ".css", ".js", ".json", ".xml", ".txt", ".php")):
        return False
    if has_image_extension(low):
        return True
    return any(hint in low for hint in GOOD_PATH_HINTS)


def product_match_score(url: object, product_title: object = "", context: object = "") -> float:
    tokens = product_tokens(product_title)
    if not tokens:
        return 0.0
    haystack = normalize_text(" ".join([str(url or ""), str(context or "")]))
    if not haystack:
        return 0.0
    hits = sum(1 for token in tokens if token in haystack)
    return round(hits / max(len(tokens), 1), 4)


def _png_size(data: bytes) -> tuple[int, int]:
    if len(data) >= 24 and data.startswith(b"\x89PNG\r\n\x1a\n"):
        return struct.unpack(">II", data[16:24])
    return 0, 0


def _jpeg_size(data: bytes) -> tuple[int, int]:
    if len(data) < 4 or not data.startswith(b"\xff\xd8"):
        return 0, 0
    i = 2
    while i + 9 < len(data):
        if data[i] != 0xFF:
            i += 1
            continue
        marker = data[i + 1]
        i += 2
        if marker in (0xD8, 0xD9):
            continue
        if i + 2 > len(data):
            break
        length = int.from_bytes(data[i:i + 2], "big")
        if length < 2:
            break
        if marker in {0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF}:
            if i + 7 <= len(data):
                height = int.from_bytes(data[i + 3:i + 5], "big")
                width = int.from_bytes(data[i + 5:i + 7], "big")
                return width, height
            break
        i += length
    return 0, 0


def _webp_size(data: bytes) -> tuple[int, int]:
    if len(data) < 30 or data[:4] != b"RIFF" or data[8:12] != b"WEBP":
        return 0, 0
    chunk = data[12:16]
    if chunk == b"VP8X" and len(data) >= 30:
        width = 1 + int.from_bytes(data[24:27], "little")
        height = 1 + int.from_bytes(data[27:30], "little")
        return width, height
    if chunk == b"VP8 " and len(data) >= 30:
        width = int.from_bytes(data[26:28], "little") & 0x3FFF
        height = int.from_bytes(data[28:30], "little") & 0x3FFF
        return width, height
    return 0, 0


def image_size_from_bytes(data: bytes) -> tuple[int, int]:
    return _png_size(data) or _jpeg_size(data) or _webp_size(data) or (0, 0)


@lru_cache(maxsize=1024)
def _remote_probe(url: str) -> tuple[bool, str, int, int, int]:
    headers = {
        "User-Agent": "Mozilla/5.0 (compatible; IA-Planilhas-Bling/1.0; image-validator)",
        "Accept": "image/avif,image/webp,image/apng,image/*,*/*;q=0.8",
    }
    try:
        head = requests.head(url, headers=headers, timeout=DEFAULT_TIMEOUT, allow_redirects=True)
        status = int(head.status_code or 0)
        content_type = str(head.headers.get("content-type", "")).lower()
        content_length = int(head.headers.get("content-length") or 0)
        if status >= 400:
            return False, f"status_http_{status}", 0, 0, content_length
        if content_type and "image" not in content_type and not has_image_extension(url):
            return False, "content_type_nao_imagem", 0, 0, content_length
        if content_length and content_length < MIN_IMAGE_BYTES:
            return False, "imagem_muito_leve", 0, 0, content_length
    except Exception:
        content_length = 0

    try:
        resp = requests.get(url, headers={**headers, "Range": "bytes=0-131071"}, timeout=DEFAULT_TIMEOUT, stream=True, allow_redirects=True)
        status = int(resp.status_code or 0)
        if status >= 400:
            return False, f"status_http_{status}", 0, 0, content_length
        content_type = str(resp.headers.get("content-type", "")).lower()
        if content_type and "image" not in content_type and not has_image_extension(url):
            return False, "content_type_nao_imagem", 0, 0, content_length
        data = b""
        for chunk in resp.iter_content(chunk_size=16384):
            if chunk:
                data += chunk
            if len(data) >= 131072:
                break
        if len(data) < min(MIN_IMAGE_BYTES, max(content_length, 0) or MIN_IMAGE_BYTES):
            return False, "imagem_muito_leve", 0, 0, max(content_length, len(data))
        width, height = image_size_from_bytes(data)
        if width and height and (width < MIN_IMAGE_WIDTH or height < MIN_IMAGE_HEIGHT):
            return False, "dimensao_muito_pequena", width, height, max(content_length, len(data))
        return True, "ok", width, height, max(content_length, len(data))
    except Exception:
        return False, "falha_ao_baixar_imagem", 0, 0, content_length


def validate_image_url(
    url: object,
    *,
    product_title: object = "",
    context: object = "",
    require_remote: bool = False,
    require_product_match: bool = False,
) -> ImageQualityResult:
    clean = clean_image_url(url)
    if not clean:
        return ImageQualityResult(url="", ok=False, reason="url_vazia_ou_invalida")
    if not looks_like_possible_product_image(clean):
        return ImageQualityResult(url=clean, ok=False, reason="url_nao_parece_imagem_de_produto")

    score = product_match_score(clean, product_title, context)
    tokens = product_tokens(product_title)
    if require_product_match and tokens and score <= 0:
        return ImageQualityResult(url=clean, ok=False, reason="imagem_nao_combina_com_nome_do_produto", product_score=score)

    if require_remote:
        ok, reason, width, height, bytes_size = _remote_probe(clean)
        return ImageQualityResult(url=clean, ok=ok, reason=reason, width=width, height=height, bytes_size=bytes_size, product_score=score)

    return ImageQualityResult(url=clean, ok=True, reason="ok", product_score=score)


def filter_product_image_urls(
    urls: object,
    *,
    product_title: object = "",
    context: object = "",
    max_images: int = 12,
    require_remote: bool = False,
    require_product_match: bool = False,
) -> str:
    if urls is None:
        return ""
    if isinstance(urls, (list, tuple, set)):
        raw_parts = [str(item or "") for item in urls]
    else:
        text = str(urls or "")
        raw_parts = re.findall(r"(?:https?:)?//[^\s\"'<>|,;]+|www\.[^\s\"'<>|,;]+", text, flags=re.IGNORECASE)
        if not raw_parts:
            raw_parts = re.split(r"[|,\n\r\t]+", text)

    accepted: list[ImageQualityResult] = []
    seen: set[str] = set()
    for part in raw_parts:
        result = validate_image_url(
            part,
            product_title=product_title,
            context=context,
            require_remote=require_remote,
            require_product_match=require_product_match,
        )
        if not result.ok:
            continue
        key = image_url_key(result.url)
        if not key or key in seen:
            continue
        seen.add(key)
        accepted.append(result)

    # Mantém a ordem original, mas prioriza URLs que combinam com o nome quando houver empate de captura.
    accepted.sort(key=lambda item: item.product_score, reverse=True)
    return "|".join(item.url for item in accepted[: max(1, int(max_images or 12))])
