
from __future__ import annotations

from typing import Any
from urllib.parse import urlparse

from bling_app_zero.core.site_crawler_config import (
    FORNECEDORES_DEDICADOS,
    STOP_IMAGE_HINTS,
)


def safe_str(valor: Any) -> str:
    try:
        if valor is None:
            return ""
        return str(valor).strip()
    except Exception:
        return ""


def normalizar_texto(valor: Any) -> str:
    return safe_str(valor).lower()


def normalizar_url(url: str) -> str:
    url = safe_str(url)
    if not url:
        return ""
    if not url.startswith(("http://", "https://")):
        url = f"https://{url}"
    return url.rstrip("/")


def dominio(url: str) -> str:
    try:
        return urlparse(url).netloc.lower().replace("www.", "")
    except Exception:
        return ""


def mesmo_dominio(base_url: str, url: str) -> bool:
    return dominio(base_url) == dominio(url)


def fornecedor_cfg(base_url: str) -> dict:
    return FORNECEDORES_DEDICADOS.get(dominio(base_url), {})


def extrair_preco(texto: str) -> str:
    import re

    texto = safe_str(texto)
    if not texto:
        return ""

    match = re.search(r"R\$\s*\d[\d\.\,]*", texto, flags=re.I)
    if match:
        return match.group(0).strip()

    match = re.search(r"\b\d{1,3}(?:\.\d{3})*,\d{2}\b", texto)
    if match:
        return match.group(0).strip()

    return ""


def normalizar_preco_para_planilha(valor: str) -> str:
    texto = safe_str(valor)
    if not texto:
        return ""

    texto = texto.replace("R$", "").replace(" ", "")
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
    return True


def normalizar_imagens(valor: Any) -> str:
    texto = safe_str(valor)
    if not texto:
        return ""

    texto = texto.replace("\n", "|").replace("\r", "|").replace(";", "|")
    partes = [p.strip() for p in texto.split("|") if p.strip()]

    vistos = set()
    urls = []
    for parte in partes:
        if not imagem_valida(parte):
            continue
        if parte not in vistos:
            vistos.add(parte)
            urls.append(parte)

    return "|".join(urls)


def descricao_detalhada_valida(descricao: str, titulo: str) -> str:
    descricao = safe_str(descricao)
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
