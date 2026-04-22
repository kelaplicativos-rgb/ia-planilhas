
from __future__ import annotations

import re
from urllib.parse import urlparse

from bling_app_zero.core.site_crawler_cleaners import normalizar_texto, safe_str
from bling_app_zero.core.site_crawler_config import STOP_TITLE_EXATO, STOP_URL_HINTS

try:
    from bling_app_zero.core.site_supplier_profiles import get_supplier_profile
except Exception:
    def get_supplier_profile(url: str):
        return None


STOP_PATH_EXACT = {
    "",
    "/",
    "/home",
    "/inicio",
    "/início",
    "/shop",
    "/loja",
    "/catalogo",
    "/catalog",
    "/produtos",
    "/todos-os-produtos",
    "/conta",
    "/login",
    "/checkout",
    "/carrinho",
}

STOP_TITLE_HINTS = (
    "todos os produtos",
    "resultado da busca",
    "busca",
    "categoria",
    "categorias",
    "departamento",
    "departamentos",
    "loja oficial",
    "minha conta",
    "entrar",
    "cadastro",
    "contato",
    "quem somos",
    "sobre nós",
    "sobre nos",
)

STOP_CATEGORY_HINTS = (
    " > home",
    "home > ",
    "início > ",
    "inicio > ",
)

PRODUTO_URL_HINTS = (
    "/produto",
    "/product",
    "/p/",
    "/item/",
    "/sku/",
)

CATEGORY_URL_HINTS = (
    "/categoria",
    "/categorias",
    "/departamento",
    "/departamentos",
    "/colecao",
    "/colecoes",
    "/collections",
    "/busca",
    "/search",
)

INSTITUTIONAL_TITLE_EXACT = {
    "mega center eletrônicos",
    "mega center eletronicos",
    "atacadum",
    "home",
    "loja",
    "produtos",
}


def _path_url(url: str) -> str:
    try:
        return (urlparse(url).path or "").strip().lower().rstrip("/")
    except Exception:
        return ""


def _query_url(url: str) -> str:
    try:
        return (urlparse(url).query or "").strip().lower()
    except Exception:
        return ""


def _profile(url: str):
    try:
        return get_supplier_profile(url)
    except Exception:
        return None


def _profile_product_keywords(url: str) -> tuple[str, ...]:
    profile = _profile(url)
    if profile is None:
        return ()
    return tuple(getattr(profile, "product_url_keywords", ()) or ())


def _profile_category_keywords(url: str) -> tuple[str, ...]:
    profile = _profile(url)
    if profile is None:
        return ()
    return tuple(getattr(profile, "category_url_keywords", ()) or ())


def _profile_category_hints(url: str) -> tuple[str, ...]:
    profile = _profile(url)
    if profile is None:
        return ()
    return tuple(getattr(profile, "category_path_hints", ()) or ())


def _eh_home_ou_raiz(url_produto: str) -> bool:
    path = _path_url(url_produto)
    return path in STOP_PATH_EXACT


def _eh_url_categoria(url_produto: str) -> bool:
    url_n = normalizar_texto(url_produto)
    path = _path_url(url_produto)
    query = _query_url(url_produto)

    if any(h in url_n for h in CATEGORY_URL_HINTS):
        return True

    if "categoria" in path or "departamento" in path or "colecao" in path:
        return True

    if "search" in path or "busca" in path:
        return True

    if "category" in query or "categoria" in query:
        return True

    for hint in _profile_category_hints(url_produto):
        hint_n = normalizar_texto(hint)
        if hint_n and hint_n in url_n:
            return True

    for token in _profile_category_keywords(url_produto):
        token_n = normalizar_texto(token)
        if token_n and token_n in url_n:
            return True

    return False


def _eh_url_produto_forte(url_produto: str) -> bool:
    url_n = normalizar_texto(url_produto)

    if any(h in url_n for h in PRODUTO_URL_HINTS):
        return True

    if re.search(r"/p/[\w\-]+", url_n):
        return True

    if re.search(r"/produto/[\w\-]+", url_n):
        return True

    if re.search(r"/product/[\w\-]+", url_n):
        return True

    for token in _profile_product_keywords(url_produto):
        token_n = normalizar_texto(token)
        if token_n and token_n in url_n and not _eh_url_categoria(url_produto):
            return True

    path = _path_url(url_produto)
    ultimo_slug = path.split("/")[-1] if path else ""
    if ultimo_slug and "-" in ultimo_slug and len(ultimo_slug) >= 10 and not _eh_url_categoria(url_produto):
        return True

    return False


def _titulo_parece_institucional(titulo: str) -> bool:
    titulo_n = normalizar_texto(titulo)

    if not titulo_n:
        return True

    if titulo_n in INSTITUTIONAL_TITLE_EXACT:
        return True

    if titulo_n in STOP_TITLE_EXATO:
        return True

    if any(h in titulo_n for h in STOP_TITLE_HINTS):
        return True

    return False


def _categoria_invalida(categoria: str) -> bool:
    categoria_n = normalizar_texto(categoria)

    if not categoria_n:
        return False

    if re.fullmatch(r"[\d\s>\-]+", categoria_n):
        return True

    if len(categoria_n) <= 2:
        return True

    if any(h in categoria_n for h in STOP_CATEGORY_HINTS):
        return True

    if categoria_n in {"1", "2", "3", "4", "5"}:
        return True

    return False


def _imagens_validas_minimas(imagens: str) -> bool:
    imagens_n = safe_str(imagens)
    if not imagens_n:
        return False

    partes = [p.strip() for p in imagens_n.split("|") if p.strip()]
    if not partes:
        return False

    invalidas = 0
    validas = 0

    for parte in partes:
        p = normalizar_texto(parte)

        if not p.startswith(("http://", "https://")):
            invalidas += 1
            continue

        if any(x in p for x in ["logo", "placeholder", "facebook.com/tr", ".svg", "favicon", "icon"]):
            invalidas += 1
            continue

        validas += 1

    return validas > 0 and validas >= invalidas


def _descricao_tem_cara_de_produto(descricao: str) -> bool:
    descricao_n = normalizar_texto(descricao)

    if not descricao_n:
        return False

    if _titulo_parece_institucional(descricao):
        return False

    if len(descricao_n) < 4:
        return False

    if re.fullmatch(r"[\d\W_]+", descricao_n):
        return False

    return True


def _tem_sinais_minimos_de_produto(
    descricao: str,
    preco: str,
    codigo: str,
    gtin: str,
    imagens: str,
) -> bool:
    sinais = 0

    if _descricao_tem_cara_de_produto(descricao):
        sinais += 1
    if safe_str(preco):
        sinais += 1
    if safe_str(codigo):
        sinais += 1
    if safe_str(gtin):
        sinais += 1
    if _imagens_validas_minimas(imagens):
        sinais += 1

    return sinais >= 2


def titulo_valido(titulo: str, url_produto: str) -> bool:
    titulo_n = normalizar_texto(titulo)
    url_n = normalizar_texto(url_produto)

    if not titulo_n:
        return False

    if titulo_n in STOP_TITLE_EXATO:
        return False

    if _titulo_parece_institucional(titulo):
        return False

    if any(h in url_n for h in STOP_URL_HINTS):
        return False

    if _eh_home_ou_raiz(url_produto):
        return False

    if _eh_url_categoria(url_produto):
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

    if safe_str(preco):
        score += 2

    if safe_str(codigo):
        score += 2

    if safe_str(gtin):
        score += 1

    if _imagens_validas_minimas(imagens):
        score += 1

    if safe_str(categoria) and not _categoria_invalida(categoria):
        score += 1

    if _eh_url_produto_forte(url_produto):
        score += 3

    if _eh_url_categoria(url_produto):
        score -= 6

    if _eh_home_ou_raiz(url_produto):
        score -= 5

    if any(h in url_n for h in STOP_URL_HINTS):
        score -= 5

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

    if _eh_home_ou_raiz(url_produto):
        return False

    if _eh_url_categoria(url_produto):
        return False

    if _categoria_invalida(categoria):
        categoria = ""

    if not _tem_sinais_minimos_de_produto(
        descricao=titulo,
        preco=preco,
        codigo=codigo,
        gtin=gtin,
        imagens=imagens,
    ):
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

    if _eh_url_produto_forte(url_produto):
        return score >= 3

    return score >= 5
