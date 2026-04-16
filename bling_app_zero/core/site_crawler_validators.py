
from __future__ import annotations

from bling_app_zero.core.site_crawler_cleaners import normalizar_texto, safe_str
from bling_app_zero.core.site_crawler_config import STOP_TITLE_EXATO, STOP_URL_HINTS


def titulo_valido(titulo: str, url_produto: str) -> bool:
    titulo_n = normalizar_texto(titulo)
    url_n = normalizar_texto(url_produto)

    if not titulo_n:
        return False

    if titulo_n in STOP_TITLE_EXATO:
        return False

    if "todos os produtos" in titulo_n:
        return False

    if any(h in url_n for h in STOP_URL_HINTS):
        return False

    if len(titulo_n) < 3:
        return False

    return True


def pontuar_produto(
    titulo: str,
    preco: str,
    codigo: str,
    gtin: str,
    imagens: str,
    categoria: str,
    url_produto: str,
) -> int:
    score = 0
    url_n = normalizar_texto(url_produto)

    if titulo_valido(titulo, url_produto):
        score += 3
    if preco:
        score += 2
    if codigo:
        score += 1
    if gtin:
        score += 1
    if imagens:
        score += 1
    if categoria:
        score += 1
    if any(x in url_n for x in ["/produto", "/product", "/p/", "/item/", "/sku/"]):
        score += 2

    return score


def produto_final_valido(item: dict) -> bool:
    titulo = safe_str(item.get("descricao"))
    preco = safe_str(item.get("preco"))
    codigo = safe_str(item.get("codigo"))
    gtin = safe_str(item.get("gtin"))
    imagens = safe_str(item.get("url_imagens"))
    categoria = safe_str(item.get("categoria"))
    url_produto = safe_str(item.get("url_produto"))

    if not titulo_valido(titulo, url_produto):
        return False

    score = pontuar_produto(
        titulo=titulo,
        preco=preco,
        codigo=codigo,
        gtin=gtin,
        imagens=imagens,
        categoria=categoria,
        url_produto=url_produto,
    )

    return score >= 5
