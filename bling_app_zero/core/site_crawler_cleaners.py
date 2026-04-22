
from __future__ import annotations

import re
import unicodedata
from typing import Any
from urllib.parse import urlparse

from bling_app_zero.core.site_crawler_config import (
    FORNECEDORES_DEDICADOS,
    STOP_IMAGE_HINTS,
)

try:
    from bling_app_zero.core.site_supplier_profiles import get_supplier_profile
except Exception:
    def get_supplier_profile(url: str):
        return None


ANTI_LIXO_EXATO = {
    "",
    "entrando...",
    "entrando",
    "loading...",
    "loading",
    "carregando...",
    "carregando",
    "aguarde...",
    "aguarde",
    "please wait",
    "dark",
    "light",
    "theme",
    "default",
    "ers-color-scheme",
    "color-scheme",
    "undefined",
    "null",
    "none",
    "nan",
    "produto",
    "produtos",
    "home",
    "inicio",
    "início",
}

ANTI_LIXO_CONTEM = [
    "ers-color-scheme",
    "color-scheme",
    "prefers-color-scheme",
    "__next",
    "__nuxt",
    "loading",
    "carregando",
    "skeleton",
    "placeholder",
    "hydration",
    "theme-provider",
    "theme switch",
    "dark mode",
    "light mode",
    "javascript required",
    "enable javascript",
]

ANTI_TITULO_RUIM = [
    "entrando",
    "loading",
    "carregando",
    "aguarde",
    "tema",
    "theme",
    "produto",
    "produtos",
    "catálogo",
    "catalogo",
    "home",
    "início",
    "inicio",
]

ANTI_MARCA_RUIM = {
    "dark",
    "light",
    "theme",
    "loading",
    "entrando",
    "produto",
    "produtos",
    "store",
    "shop",
}

ANTI_CODIGO_RUIM = {
    "dark",
    "light",
    "theme",
    "loading",
    "entrando",
    "undefined",
    "null",
    "none",
    "ers-color-scheme",
    "color-scheme",
}


def safe_str(valor: Any) -> str:
    try:
        if valor is None:
            return ""
        return str(valor).strip()
    except Exception:
        return ""


def normalizar_texto(valor: Any) -> str:
    return safe_str(valor).lower()


def _sem_acentos(texto: str) -> str:
    texto = safe_str(texto)
    if not texto:
        return ""
    return "".join(
        ch for ch in unicodedata.normalize("NFKD", texto)
        if not unicodedata.combining(ch)
    )


def normalizar_url(url: str) -> str:
    url = safe_str(url)
    if not url:
        return ""
    if not url.startswith(("http://", "https://")):
        url = f"https://{url}"
    return url.rstrip("/")


def dominio(url: str) -> str:
    try:
        return urlparse(normalizar_url(url)).netloc.lower().replace("www.", "")
    except Exception:
        return ""


def mesmo_dominio(base_url: str, url: str) -> bool:
    return dominio(base_url) == dominio(url)


def _eh_lixo_generico(texto: str) -> bool:
    bruto = safe_str(texto)
    if not bruto:
        return True

    texto_n = normalizar_texto(bruto)
    texto_sa = _sem_acentos(texto_n)

    if texto_n in ANTI_LIXO_EXATO or texto_sa in ANTI_LIXO_EXATO:
        return True

    if any(token in texto_n for token in ANTI_LIXO_CONTEM):
        return True

    if len(texto_n) <= 2:
        return True

    if re.fullmatch(r"[\W_]+", texto_n):
        return True

    return False


def limpar_texto_produto(valor: Any, max_len: int = 4000) -> str:
    texto = safe_str(valor)
    if not texto:
        return ""

    texto = re.sub(r"[\t\r\n]+", " ", texto)
    texto = re.sub(r"\s{2,}", " ", texto).strip()

    if _eh_lixo_generico(texto):
        return ""

    if max_len > 0:
        texto = texto[:max_len].strip()

    return texto


def fornecedor_cfg(base_url: str) -> dict:
    cfg = dict(FORNECEDORES_DEDICADOS.get(dominio(base_url), {}) or {})

    try:
        profile = get_supplier_profile(base_url)
    except Exception:
        profile = None

    if profile is None:
        return cfg

    if hasattr(profile, "__dict__"):
        profile_data = dict(profile.__dict__)
    elif isinstance(profile, dict):
        profile_data = profile
    else:
        profile_data = {}

    if not cfg.get("nome"):
        cfg["nome"] = safe_str(profile_data.get("nome"))
    if not cfg.get("slug"):
        cfg["slug"] = safe_str(profile_data.get("slug"))

    produto_hints = list(cfg.get("produto_hints", []) or [])
    categoria_hints = list(cfg.get("categoria_hints", []) or [])

    for hint in tuple(profile_data.get("product_url_keywords", ()) or ()):
        hint_n = safe_str(hint)
        if not hint_n:
            continue
        if not hint_n.startswith("/"):
            hint_n = f"/{hint_n}"
        if hint_n not in produto_hints:
            produto_hints.append(hint_n)

    for hint in tuple(profile_data.get("category_path_hints", ()) or ()):
        hint_n = safe_str(hint)
        if not hint_n:
            continue
        if hint_n not in categoria_hints:
            categoria_hints.append(hint_n)

    for hint in tuple(profile_data.get("category_url_keywords", ()) or ()):
        hint_n = safe_str(hint)
        if not hint_n:
            continue
        if not hint_n.startswith("/"):
            hint_n = f"/{hint_n}"
        if hint_n not in categoria_hints:
            categoria_hints.append(hint_n)

    cfg["produto_hints"] = produto_hints
    cfg["categoria_hints"] = categoria_hints

    return cfg


def extrair_preco(texto: str) -> str:
    texto = safe_str(texto)
    if not texto:
        return ""

    match = re.search(r"R\$\s*\d[\d\.\,]*", texto, flags=re.I)
    if match:
        return match.group(0).strip()

    match = re.search(r"\b\d{1,3}(?:\.\d{3})*,\d{2}\b", texto)
    if match:
        return match.group(0).strip()

    match = re.search(r"\b\d+\.\d{2}\b", texto)
    if match:
        return match.group(0).strip()

    return ""


def normalizar_preco_para_planilha(valor: str) -> str:
    texto = safe_str(valor)
    if not texto:
        return ""

    texto = texto.replace("R$", "").replace(" ", "")
    texto = texto.replace("\xa0", "")

    if "," in texto and "." in texto:
        texto = texto.replace(".", "").replace(",", ".")
    else:
        texto = texto.replace(",", ".")

    try:
        numero = float(texto)
        if numero <= 0:
            return ""
        return f"{numero:.2f}".replace(".", ",")
    except Exception:
        return ""


def imagem_valida(url: str) -> bool:
    url_n = normalizar_texto(url)
    if not url_n:
        return False
    if not url_n.startswith(("http://", "https://")):
        return False
    if any(h in url_n for h in STOP_IMAGE_HINTS):
        return False
    if any(x in url_n for x in ["logo", "favicon", "icon", "sprite", "placeholder", "pixel"]):
        return False
    return True


def normalizar_imagens(valor: Any) -> str:
    texto = safe_str(valor)
    if not texto:
        return ""

    texto = texto.replace("\n", "|").replace("\r", "|").replace(";", "|").replace(",", "|")
    partes = [p.strip() for p in texto.split("|") if p.strip()]

    vistos = set()
    urls = []
    for parte in partes:
        if not imagem_valida(parte):
            continue
        if parte not in vistos:
            vistos.add(parte)
            urls.append(parte)

    return "|".join(urls[:12])


def limpar_codigo(valor: Any) -> str:
    texto = limpar_texto_produto(valor, max_len=120)
    if not texto:
        return ""

    texto_n = normalizar_texto(texto)
    if texto_n in ANTI_CODIGO_RUIM:
        return ""

    texto = re.sub(r"[\t\r\n]+", " ", texto)
    texto = re.sub(r"\s{2,}", " ", texto).strip()

    if len(texto) < 3:
        return ""

    if re.fullmatch(r"[A-Za-z]{1,2}", texto):
        return ""

    return texto[:120]


def limpar_gtin(valor: Any) -> str:
    texto = re.sub(r"\D+", "", safe_str(valor))
    if len(texto) in {8, 12, 13, 14}:
        return texto
    return ""


def limpar_marca(valor: Any) -> str:
    texto = limpar_texto_produto(valor, max_len=60)
    if not texto:
        return ""

    texto_n = normalizar_texto(texto)
    if texto_n in ANTI_MARCA_RUIM:
        return ""

    if texto.isdigit():
        return ""

    if len(texto.split()) > 4:
        return ""

    return texto[:60]


def titulo_produto_valido(valor: Any) -> bool:
    texto = limpar_texto_produto(valor, max_len=220)
    if not texto:
        return False

    texto_n = normalizar_texto(texto)
    texto_sa = _sem_acentos(texto_n)

    if texto_n in ANTI_LIXO_EXATO or texto_sa in ANTI_LIXO_EXATO:
        return False

    if any(token in texto_n for token in ANTI_TITULO_RUIM):
        return False

    if len(texto) < 4:
        return False

    if re.fullmatch(r"[\d\W_]+", texto):
        return False

    return True


def descricao_detalhada_valida(descricao: str, titulo: str) -> str:
    descricao = limpar_texto_produto(descricao, max_len=4000)
    titulo_n = normalizar_texto(titulo)
    desc_n = normalizar_texto(descricao)

    if not descricao:
        return ""

    if len(descricao) < 25:
        return ""

    from bling_app_zero.core.site_crawler_config import STOP_DESC_HINTS

    if any(h in desc_n for h in STOP_DESC_HINTS):
        return ""

    if titulo_n and desc_n == titulo_n:
        return ""

    return descricao
