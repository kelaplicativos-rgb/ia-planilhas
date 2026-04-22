
from __future__ import annotations

import concurrent.futures
import json
import re
import threading
from typing import Any
from urllib.parse import urljoin, urlparse

import pandas as pd
import requests

try:
    from bs4 import BeautifulSoup
except Exception:
    BeautifulSoup = None


try:
    from bling_app_zero.core.site_crawler_cleaners import normalizar_url, safe_str
except Exception:
    def normalizar_url(url: str) -> str:
        url = str(url or "").strip()
        if url and not url.startswith(("http://", "https://")):
            url = f"https://{url}"
        parsed = urlparse(url)
        if parsed.scheme and parsed.netloc:
            root = f"{parsed.scheme}://{parsed.netloc}"
            path = parsed.path.rstrip("/")
            return f"{root}{path}" if path else root
        return url.rstrip("/")

    def safe_str(value: Any) -> str:
        return str(value or "").strip()


try:
    from bling_app_zero.core.site_crawler_http import extrair_detalhes_heuristicos
except Exception:
    try:
        from bling_app_zero.core.site_crawler_extractors import extrair_detalhes_heuristicos
    except Exception:
        extrair_detalhes_heuristicos = None


try:
    from bling_app_zero.core.site_crawler_gpt import gpt_extrair_produto
except Exception:
    gpt_extrair_produto = None


try:
    from bling_app_zero.core.site_crawler_http import fetch_html_retry
except Exception:
    fetch_html_retry = None


try:
    from bling_app_zero.core.site_crawler_links import descobrir_produtos_no_dominio
except Exception:
    descobrir_produtos_no_dominio = None


try:
    from bling_app_zero.core.site_crawler_sitemap import descobrir_produtos_via_sitemap
except Exception:
    descobrir_produtos_via_sitemap = None


try:
    from bling_app_zero.core.site_crawler_validators import (
        pontuar_produto,
        produto_final_valido,
        titulo_valido,
    )
except Exception:
    def pontuar_produto(**kwargs) -> int:
        score = 0
        if safe_str(kwargs.get("titulo")):
            score += 2
        if safe_str(kwargs.get("preco")):
            score += 1
        if safe_str(kwargs.get("codigo")):
            score += 2
        if safe_str(kwargs.get("gtin")):
            score += 1
        if safe_str(kwargs.get("imagens")):
            score += 1
        if safe_str(kwargs.get("categoria")):
            score += 1
        if safe_str(kwargs.get("url_produto")):
            score += 1
        return score

    def produto_final_valido(item: dict) -> bool:
        return bool(safe_str(item.get("descricao")) and safe_str(item.get("url_produto")))

    def titulo_valido(titulo: str, url_produto: str = "") -> bool:
        titulo_n = safe_str(titulo)
        if not titulo_n:
            return False
        if len(titulo_n) < 3:
            return False
        return True


try:
    from bling_app_zero.core.site_supplier_profiles import get_supplier_profile
except Exception:
    def get_supplier_profile(url: str):
        return None


try:
    from bling_app_zero.core.session_manager import (
        STATUS_LOGIN_CAPTCHA_DETECTADO,
        STATUS_LOGIN_REQUERIDO,
        STATUS_SESSAO_PRONTA,
        detectar_login_captcha,
        montar_auth_context,
        salvar_status_login_em_sessao,
    )
except Exception:
    STATUS_LOGIN_CAPTCHA_DETECTADO = "login_captcha_detectado"
    STATUS_LOGIN_REQUERIDO = "login_required"
    STATUS_SESSAO_PRONTA = "session_ready"

    def detectar_login_captcha(html: str, url_atual: str = "") -> dict[str, Any]:
        html_n = safe_str(html).lower()
        url_n = safe_str(url_atual).lower()

        sinais_login = [
            "fazer login",
            "faça login",
            "entrar",
            "login",
            "senha",
            "autenticacao",
            "autenticação",
            "minha conta",
        ]
        sinais_captcha = [
            "captcha",
            "g-recaptcha",
            "grecaptcha",
            "hcaptcha",
            "cloudflare",
            "verify you are human",
            "não sou um robô",
            "nao sou um robo",
        ]

        url_sugere_login = any(
            token in url_n
            for token in ["/login", "/entrar", "/conta", "/account", "/auth", "/admin"]
        )
        html_sugere_login = any(token in html_n for token in sinais_login)
        captcha_detectado = any(token in html_n for token in sinais_captcha)
        exige_login = url_sugere_login or html_sugere_login

        if exige_login and captcha_detectado:
            status = STATUS_LOGIN_CAPTCHA_DETECTADO
        elif exige_login:
            status = STATUS_LOGIN_REQUERIDO
        else:
            status = "publico"

        return {
            "exige_login": exige_login,
            "captcha_detectado": captcha_detectado,
            "status": status,
            "motivos": [],
        }

    def montar_auth_context(base_url: str, fornecedor: str = "") -> dict[str, Any]:
        return {}

    def salvar_status_login_em_sessao(
        *,
        base_url: str,
        status: str,
        mensagem: str = "",
        exige_login: bool = False,
        captcha_detectado: bool = False,
        fornecedor: str = "",
    ) -> None:
        return None


DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8",
    "Cache-Control": "no-cache",
    "Pragma": "no-cache",
}

MOBILE_HEADERS = {
    **DEFAULT_HEADERS,
    "User-Agent": (
        "Mozilla/5.0 (Linux; Android 12; SM-G991B) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Mobile Safari/537.36"
    ),
}

ASSET_EXTENSIONS = {
    ".css", ".js", ".mjs", ".map", ".svg", ".png", ".jpg", ".jpeg", ".gif", ".webp",
    ".ico", ".woff", ".woff2", ".ttf", ".eot", ".pdf", ".zip", ".xml", ".txt", ".json",
}

INSTITUTIONAL_SLUGS = [
    "politica-de-privacidade",
    "politica-de-frete",
    "politica-de-reembolso",
    "politica-de-trocas",
    "trocas-e-devolucoes",
    "atendimento-ao-cliente",
    "contato",
    "quem-somos",
    "sobre",
    "blog",
    "institucional",
    "termos-de-uso",
    "seguranca",
    "privacidade",
    "regras-dropshipping",
]

PRODUCT_URL_SIGNALS = [
    "/produto/",
    "/produtos/",
    "/product/",
    "/products/",
    "/p/",
    "/item/",
    "/sku/",
    "/prd/",
]

CATEGORY_URL_SIGNALS = [
    "/categoria",
    "/categorias",
    "/departamento",
    "/collection",
    "/collections",
    "/busca",
    "/search",
]

PRODUCT_TEXT_SIGNALS = [
    '"@type":"product"',
    '"@type": "product"',
    '"@type":"Product"',
    '"@type": "Product"',
    "application/ld+json",
    "add to cart",
    "adicionar ao carrinho",
    "comprar agora",
    "buy now",
    "sku",
    "código",
    "codigo",
    "gtin",
    "ean",
    "parcel",
    "r$",
    "price",
    "product",
    "produto",
    "product_id",
    "productid",
    'itemprop="price"',
    "itemprop='price'",
    'itemprop="sku"',
    "itemprop='sku'",
    "og:type",
    "availability",
    "in stock",
    "out of stock",
]

BLOCK_PAGE_SIGNALS = [
    "cloudflare",
    "attention required",
    "verify you are human",
    "checking your browser",
    "access denied",
    "forbidden",
    "captcha",
    "g-recaptcha",
    "hcaptcha",
]

DIAG_COLUNAS = [
    "url_produto",
    "status",
    "motivo",
    "score",
    "descricao",
    "codigo",
    "gtin",
    "categoria",
    "marca",
    "preco",
    "fontes_html",
    "url_html_principal",
]


def _streamlit_ctx():
    try:
        import streamlit as st
        return st
    except Exception:
        return None


def _em_thread_secundaria() -> bool:
    return threading.current_thread() is not threading.main_thread()


def _log_debug(msg: str, nivel: str = "INFO") -> None:
    if _em_thread_secundaria():
        try:
            print(f"[SITE_AGENT][{nivel}] {msg}")
        except Exception:
            pass
        return

    try:
        from bling_app_zero.ui.app_helpers import log_debug  # type: ignore
        log_debug(msg, nivel=nivel)
    except Exception:
        try:
            print(f"[SITE_AGENT][{nivel}] {msg}")
        except Exception:
            pass


def _url_raiz(url: str) -> str:
    parsed = urlparse(normalizar_url(url))
    if parsed.scheme and parsed.netloc:
        return f"{parsed.scheme}://{parsed.netloc}"
    return normalizar_url(url)


def _host(url: str) -> str:
    try:
        return (urlparse(normalizar_url(url)).netloc or "").replace("www.", "").strip().lower()
    except Exception:
        return ""


def _limite_tecnico(limite_links: int | None) -> int:
    limite_padrao = 8000
    if not isinstance(limite_links, int):
        return limite_padrao
    if limite_links <= 0:
        return limite_padrao
    return min(max(limite_links, 1), limite_padrao)


def _max_workers(total: int) -> int:
    if total <= 0:
        return 1
    return min(max(total // 20, 4), 12)


def _descricao_curta_padrao(final: dict[str, Any]) -> str:
    descricao_curta = safe_str(final.get("descricao_curta"))
    if descricao_curta:
        return descricao_curta[:120]

    descricao = safe_str(final.get("descricao"))
    if descricao:
        return descricao[:120]

    descricao_detalhada = safe_str(final.get("descricao_detalhada"))
    if descricao_detalhada:
        return descricao_detalhada[:120]

    return ""


def _quantidade_padrao(final: dict[str, Any]) -> str:
    quantidade = safe_str(final.get("quantidade"))
    if quantidade:
        return quantidade

    descricao = safe_str(final.get("descricao_detalhada")).lower()
    if any(
        x in descricao
        for x in ["sem estoque", "indisponível", "indisponivel", "esgotado", "zerado", "out of stock"]
    ):
        return "0"

    return "1"


def _limpar_marca(marca: str, titulo: str = "") -> str:
    marca = safe_str(marca).strip()
    titulo = safe_str(titulo).strip()

    if not marca:
        return ""

    marca_lower = marca.lower()
    titulo_lower = titulo.lower()

    bloqueadas_parciais = [
        "mega center",
        "eletronicos",
        "eletrônicos",
        "minha loja",
        "nossa loja",
        "loja oficial",
        "distribuidora",
        "atacadista",
        "atacado",
        "varejo",
        "store",
        "shop",
        "ecommerce",
        "e-commerce",
        "iphone",
        "hdmi",
        "ouvido",
        "completo",
        "fonte",
    ]

    for termo in bloqueadas_parciais:
        if termo in marca_lower:
            return ""

    genericas = {
        "fone",
        "fones",
        "cabo",
        "cabos",
        "carregador",
        "carregadores",
        "caixa",
        "som",
        "produto",
        "produtos",
        "acessorio",
        "acessório",
        "acessorios",
        "acessórios",
        "eletronico",
        "eletrônico",
        "eletronicos",
        "eletrônicos",
        "bluetooth",
        "usb",
        "usb-c",
        "tipo-c",
        "celular",
        "smartphone",
        "original",
        "premium",
        "max",
        "pro",
    }

    if marca_lower in genericas:
        return ""

    if len(marca) > 40:
        return ""

    if marca.isdigit():
        return ""

    if titulo_lower and marca_lower == titulo_lower:
        return ""

    if marca.count(" ") >= 4:
        return ""

    return marca


def _inferir_marca_do_titulo(titulo: str) -> str:
    titulo = safe_str(titulo).strip()
    if not titulo:
        return ""

    palavras_invalidas = {
        "fone", "fones", "cabo", "cabos", "carregador", "carregadores", "caixa", "som",
        "produto", "kit", "para", "com", "sem", "de", "da", "do", "usb", "bluetooth",
        "wireless", "tipo", "celular", "smartphone", "iphone", "hdmi", "ouvido",
        "completo", "fonte",
    }

    tokens = re.split(r"\s+", titulo)
    for token in tokens[:5]:
        candidato = re.sub(r"[^A-Za-z0-9\-]", "", safe_str(token)).strip()
        if not candidato:
            continue
        if len(candidato) <= 2:
            continue
        if candidato.lower() in palavras_invalidas:
            continue
        if candidato.isdigit():
            continue
        return candidato

    return ""


def _resolver_marca(final: dict[str, Any], heuristica: dict[str, Any]) -> str:
    descricao = safe_str(final.get("descricao")) or safe_str(heuristica.get("descricao"))

    candidatos = [
        safe_str(final.get("marca")),
        safe_str(heuristica.get("marca")),
    ]

    for candidato in candidatos:
        marca_limpa = _limpar_marca(candidato, descricao)
        if marca_limpa:
            return marca_limpa

    marca_titulo = _inferir_marca_do_titulo(descricao)
    return _limpar_marca(marca_titulo, descricao)


def _montar_linha_saida(final: dict) -> dict:
    return {
        "Código": safe_str(final.get("codigo")),
        "Descrição": safe_str(final.get("descricao")),
        "Descrição Curta": _descricao_curta_padrao(final),
        "Categoria": safe_str(final.get("categoria")),
        "Marca": safe_str(final.get("marca")),
        "GTIN": safe_str(final.get("gtin")),
        "NCM": safe_str(final.get("ncm")),
        "Preço de custo": safe_str(final.get("preco")),
        "Quantidade": _quantidade_padrao(final),
        "URL Imagens": safe_str(final.get("url_imagens")),
        "URL Produto": safe_str(final.get("url_produto")),
    }


def _df_saida(rows: list[dict]) -> pd.DataFrame:
    if not rows:
        return pd.DataFrame()

    df = pd.DataFrame(rows).fillna("")

    if "URL Produto" in df.columns:
        df = df.drop_duplicates(subset=["URL Produto"], keep="first")

    colunas_ordenadas = [
        "Código",
        "Descrição",
        "Descrição Curta",
        "Categoria",
        "Marca",
        "GTIN",
        "NCM",
        "Preço de custo",
        "Quantidade",
        "URL Imagens",
        "URL Produto",
    ]

    for col in colunas_ordenadas:
        if col not in df.columns:
            df[col] = ""

    return df[colunas_ordenadas].reset_index(drop=True)


def _df_diagnostico(rows: list[dict]) -> pd.DataFrame:
    if not rows:
        return pd.DataFrame(columns=DIAG_COLUNAS)

    base = pd.DataFrame(rows).fillna("")
    for col in DIAG_COLUNAS:
        if col not in base.columns:
            base[col] = ""
    return base[DIAG_COLUNAS].reset_index(drop=True)


def _score_produto(item: dict) -> int:
    return pontuar_produto(
        titulo=safe_str(item.get("descricao")),
        preco=safe_str(item.get("preco")),
        codigo=safe_str(item.get("codigo")),
        gtin=safe_str(item.get("gtin")),
        imagens=safe_str(item.get("url_imagens")),
        categoria=safe_str(item.get("categoria")),
        url_produto=safe_str(item.get("url_produto")),
    )


def _campos_criticos_ok(final: dict[str, Any]) -> tuple[bool, list[str]]:
    faltando: list[str] = []

    campos = {
        "codigo": safe_str(final.get("codigo")),
        "descricao": safe_str(final.get("descricao")),
        "url_produto": safe_str(final.get("url_produto")),
    }

    for chave, valor in campos.items():
        if not valor:
            faltando.append(chave)

    criticos_duros = {"descricao", "url_produto"}
    if any(campo in faltando for campo in criticos_duros):
        return False, faltando

    return True, faltando


def _motivo_rejeicao(final: dict) -> str:
    descricao = safe_str(final.get("descricao"))
    url_produto = safe_str(final.get("url_produto"))
    url_n = url_produto.lower()

    if not descricao:
        return "sem_descricao"

    if not titulo_valido(descricao, url_produto):
        return "titulo_invalido_ou_pagina_institucional"

    if url_n in {"", "/"} or url_n.endswith("/conta") or url_n.endswith("/login"):
        return "url_institucional"

    if _url_eh_categoria(url_n):
        return "url_de_categoria"

    campos_ok, faltando = _campos_criticos_ok(final)
    if not campos_ok:
        return f"faltando_campos_criticos_{'_'.join(faltando)}"

    score = _score_produto(final)
    if score <= 0:
        return "sem_sinais_minimos_de_produto"

    return f"reprovado_na_validacao_final_score_{score}"


def _fornecedor_slug_do_contexto(base_url: str, auth_context: dict[str, Any] | None) -> str:
    if isinstance(auth_context, dict):
        slug = safe_str(auth_context.get("fornecedor_slug"))
        if slug:
            return slug
    profile = None
    try:
        profile = get_supplier_profile(base_url)
    except Exception:
        profile = None
    if profile is not None:
        slug = safe_str(getattr(profile, "slug", ""))
        if slug:
            return slug
    base = safe_str(base_url).lower()
    base = re.sub(r"^https?://", "", base)
    base = base.replace("www.", "")
    base = re.sub(r"[^a-z0-9]+", "_", base).strip("_")
    return base or "fornecedor"


def _texto_tem_sinais_de_produto(texto: str) -> bool:
    texto_n = safe_str(texto).lower()
    if not texto_n:
        return False
    return any(s in texto_n for s in PRODUCT_TEXT_SIGNALS)


def _html_tem_sinais_de_bloqueio(html: str) -> bool:
    html_n = safe_str(html).lower()
    if not html_n:
        return False
    return any(s in html_n for s in BLOCK_PAGE_SIGNALS)


def _score_html_produto(texto: str) -> int:
    texto_n = safe_str(texto).lower()
    if not texto_n:
        return 0

    score = 0
    if '"@type":"product"' in texto_n or '"@type": "product"' in texto_n or '"@type":"Product"' in texto_n:
        score += 4
    if "adicionar ao carrinho" in texto_n or "add to cart" in texto_n or "comprar agora" in texto_n:
        score += 2
    if "sku" in texto_n or "gtin" in texto_n or "ean" in texto_n or "código" in texto_n or "codigo" in texto_n:
        score += 1
    if "r$" in texto_n or "price" in texto_n or "parcel" in texto_n:
        score += 1
    if "og:type" in texto_n and "product" in texto_n:
        score += 2
    return score


def _parece_html_login_puro(html: str, url_atual: str = "") -> bool:
    try:
        analise = detectar_login_captcha(html=html, url_atual=url_atual)
    except Exception:
        return False

    status = safe_str(analise.get("status"))
    if status not in {STATUS_LOGIN_CAPTCHA_DETECTADO, STATUS_LOGIN_REQUERIDO}:
        return False

    if _texto_tem_sinais_de_produto(html):
        return False

    return _score_html_produto(html) <= 0


def _normalizar_url_candidata(base_url: str, href: str) -> str:
    href = safe_str(href)
    if not href:
        return ""

    try:
        return normalizar_url(urljoin(base_url, href))
    except Exception:
        return ""


def _url_mesmo_dominio(base_url: str, candidata: str) -> bool:
    try:
        host_base = _host(base_url)
        host_cand = _host(candidata)
        return bool(host_base and host_cand and host_base == host_cand)
    except Exception:
        return False


def _url_tem_extensao_asset(url: str) -> bool:
    path = safe_str(urlparse(url).path).lower()
    return any(path.endswith(ext) for ext in ASSET_EXTENSIONS)


def _url_eh_admin(base_url: str) -> bool:
    url_n = safe_str(base_url).lower()
    return any(x in url_n for x in ["/admin", "/painel", "/dashboard", "/seller", "/merchant"])


def _url_eh_institucional(url: str) -> bool:
    url_n = safe_str(url).lower()
    return any(slug in url_n for slug in INSTITUTIONAL_SLUGS)


def _profile_for_url(url: str):
    try:
        return get_supplier_profile(url)
    except Exception:
        return None


def _url_eh_categoria(url: str) -> bool:
    url_n = safe_str(url).lower()
    profile = _profile_for_url(url_n)

    if any(s in url_n for s in CATEGORY_URL_SIGNALS):
        return True

    if profile is not None:
        hints = getattr(profile, "category_path_hints", ()) or ()
        for hint in hints:
            if safe_str(hint).lower() and safe_str(hint).lower() in url_n:
                return True

        category_keywords = getattr(profile, "category_url_keywords", ()) or ()
        for token in category_keywords:
            token_n = safe_str(token).lower()
            if token_n and token_n in url_n:
                return True

    return False


def _url_tem_sinal_forte_de_produto(url: str) -> bool:
    url_n = safe_str(url).lower()
    profile = _profile_for_url(url_n)

    if any(s in url_n for s in PRODUCT_URL_SIGNALS):
        return True

    if profile is not None:
        product_keywords = getattr(profile, "product_url_keywords", ()) or ()
        for token in product_keywords:
            token_n = safe_str(token).lower()
            if token_n and token_n in url_n:
                return True

    return False


def _score_url_produto(url: str, anchor_text: str = "", contexto_texto: str = "") -> int:
    url_n = safe_str(url).lower()
    texto = f"{safe_str(anchor_text)} {safe_str(contexto_texto)}".lower()
    score = 0

    if not url_n:
        return -999

    if _url_tem_extensao_asset(url_n):
        return -999

    if _url_eh_institucional(url_n):
        return -999

    if any(
        b in url_n
        for b in ["/login", "/conta", "/account", "/carrinho", "/cart", "/checkout", "javascript:", "mailto:", "tel:"]
    ):
        return -999

    if _url_tem_sinal_forte_de_produto(url_n):
        score += 8

    if _url_eh_categoria(url_n):
        score -= 6

    ultimo_slug = safe_str(urlparse(url_n).path.split("/")[-1])
    if ultimo_slug and "-" in ultimo_slug and len(ultimo_slug) >= 10:
        score += 2

    if re.search(r"\b(r\$|sku|ean|gtin|comprar|adicionar)\b", texto):
        score += 3

    if len(safe_str(anchor_text)) >= 10:
        score += 1

    return score


def _url_parece_produto(url: str) -> bool:
    return _score_url_produto(url) >= 2 and not _url_eh_categoria(url)


def _html_parece_pagina_produto_real(url: str, html: str) -> bool:
    url_n = safe_str(url).lower()
    html_n = safe_str(html).lower()

    if not html_n:
        return False

    if _url_eh_institucional(url_n):
        return False

    if _url_eh_categoria(url_n):
        return False

    if _score_url_produto(url_n) >= 6 and _score_html_produto(html_n) >= 1:
        return True

    if _score_html_produto(html_n) >= 4:
        return True

    if _texto_tem_sinais_de_produto(html_n) and not _html_tem_sinais_de_bloqueio(html_n):
        return True

    return False


def _extrair_links_bs4(base_url: str, html: str, limite: int) -> list[str]:
    if BeautifulSoup is None:
        return []

    try:
        soup = BeautifulSoup(html, "html.parser")
    except Exception:
        return []

    candidatos: list[tuple[int, str]] = []
    vistos: set[str] = set()

    for a in soup.find_all("a", href=True):
        href = safe_str(a.get("href"))
        if not href:
            continue

        url = _normalizar_url_candidata(base_url, href)
        if not url:
            continue
        if not _url_mesmo_dominio(base_url, url):
            continue

        anchor_text = safe_str(a.get_text(" ", strip=True))
        parent_text = safe_str(a.parent.get_text(" ", strip=True)) if getattr(a, "parent", None) is not None else ""
        score = _score_url_produto(url, anchor_text=anchor_text, contexto_texto=parent_text)

        if score < 2:
            continue
        if url in vistos:
            continue
        vistos.add(url)
        candidatos.append((score, url))

    candidatos.sort(key=lambda x: x[0], reverse=True)
    return [url for _, url in candidatos[:limite]]


def _extrair_links_regex(base_url: str, html: str, limite: int) -> list[str]:
    hrefs = re.findall(r"""href=["']([^"'#]+)["']""", safe_str(html), flags=re.IGNORECASE)
    saida: list[tuple[int, str]] = []
    vistos: set[str] = set()

    for href in hrefs:
        url = _normalizar_url_candidata(base_url, href)
        if not url:
            continue
        if not _url_mesmo_dominio(base_url, url):
            continue

        score = _score_url_produto(url)
        if score < 2:
            continue
        if url in vistos:
            continue
        vistos.add(url)
        saida.append((score, url))

    saida.sort(key=lambda x: x[0], reverse=True)
    return [url for _, url in saida[:limite]]


def _extrair_links_json_embutido(base_url: str, html: str, limite: int) -> list[str]:
    candidatos: list[tuple[int, str]] = []
    vistos: set[str] = set()

    padrao_urls = re.findall(r"""https?://[^\s"'<>]+|/[A-Za-z0-9_\-/%\.]+""", safe_str(html))
    for bruto in padrao_urls:
        url = _normalizar_url_candidata(base_url, bruto)
        if not url:
            continue
        if not _url_mesmo_dominio(base_url, url):
            continue
        score = _score_url_produto(url)
        if score < 2:
            continue
        if url in vistos:
            continue
        vistos.add(url)
        candidatos.append((score, url))

    if BeautifulSoup is not None:
        try:
            soup = BeautifulSoup(html, "html.parser")
            for script in soup.find_all("script", attrs={"type": "application/ld+json"}):
                texto = safe_str(script.string or script.get_text(" ", strip=True))
                if not texto:
                    continue
                try:
                    data = json.loads(texto)
                except Exception:
                    continue

                def _coletar_urls(obj: Any) -> None:
                    if isinstance(obj, dict):
                        url = safe_str(obj.get("url"))
                        if url:
                            url_n = _normalizar_url_candidata(base_url, url)
                            if _url_mesmo_dominio(base_url, url_n):
                                score_local = _score_url_produto(url_n)
                                if score_local >= 2 and url_n not in vistos:
                                    vistos.add(url_n)
                                    candidatos.append((score_local + 2, url_n))
                        for v in obj.values():
                            _coletar_urls(v)
                    elif isinstance(obj, list):
                        for item in obj:
                            _coletar_urls(item)

                _coletar_urls(data)
        except Exception:
            pass

    candidatos.sort(key=lambda x: x[0], reverse=True)
    return [url for _, url in candidatos[:limite]]


def _extrair_links_produto_html(base_url: str, html: str, limite: int) -> list[str]:
    conjuntos = [
        _extrair_links_bs4(base_url, html, limite),
        _extrair_links_regex(base_url, html, limite),
        _extrair_links_json_embutido(base_url, html, limite),
    ]

    saida: list[str] = []
    vistos: set[str] = set()

    for conjunto in conjuntos:
        for url in conjunto:
            if url in vistos:
                continue
            if not _url_parece_produto(url):
                continue
            vistos.add(url)
            saida.append(url)
            if len(saida) >= limite:
                return saida

    return saida


def _html_base_parece_listagem(html: str, base_url: str = "") -> bool:
    html_n = safe_str(html).lower()

    if not html_n:
        return False

    if _url_eh_admin(base_url):
        return False

    if _html_parece_pagina_produto_real(base_url, html):
        return False

    if _url_eh_categoria(base_url):
        return True

    qtd_links = len(_extrair_links_produto_html(base_url or "https://example.com", html, 200))
    if qtd_links >= 3:
        return True

    sinais_listagem = [
        "resultado",
        "produtos",
        "vitrine",
        "category",
        "categoria",
        "departamento",
        "prateleira",
        "grid",
        "shelf",
        "listing",
    ]
    return any(s in html_n for s in sinais_listagem)


def _extrair_categoria_do_html(url_produto: str, html_produto: str) -> str:
    html_n = safe_str(html_produto)

    breadcrumb_match = re.search(
        r"(breadcrumb|migalha|categoria)[\s\S]{0,1600}",
        html_n,
        flags=re.IGNORECASE,
    )
    if breadcrumb_match:
        trecho = breadcrumb_match.group(0)
        categorias = re.findall(r">([^<>]{3,120})<", trecho)
        categorias = [safe_str(c) for c in categorias if safe_str(c)]
        if categorias:
            categorias = [c for c in categorias if c.lower() not in {"home", "início", "inicio"}]
            if categorias:
                return " > ".join(categorias[:5])

    path_parts = [p for p in urlparse(url_produto).path.split("/") if p]
    if path_parts:
        if "produto" in path_parts and len(path_parts) >= 2:
            idx = path_parts.index("produto")
            if idx > 0:
                return safe_str(path_parts[idx - 1]).replace("-", " ").title()

    profile = _profile_for_url(url_produto)
    if profile is not None:
        for hint in getattr(profile, "category_path_hints", ()) or ():
            hint_n = safe_str(hint).strip("/")
            for p in path_parts:
                if safe_str(p).lower() == hint_n.lower():
                    return safe_str(p).replace("-", " ").title()

    for p in path_parts[:-1]:
        p_n = safe_str(p)
        if p_n and len(p_n) > 2 and not p_n.isdigit():
            if p_n.lower() not in {"produto", "produtos", "product", "products"}:
                return p_n.replace("-", " ").title()

    return ""


def _extrair_imagens_basicas(url_produto: str, html_produto: str) -> str:
    imgs_ok: list[str] = []
    vistos: set[str] = set()

    if BeautifulSoup is not None:
        try:
            soup = BeautifulSoup(html_produto, "html.parser")

            seletores = [
                "meta[property='og:image']",
                "meta[name='twitter:image']",
                "[itemprop='image']",
                "img",
                "a[href$='.jpg']",
                "a[href$='.jpeg']",
                "a[href$='.png']",
                "a[href$='.webp']",
            ]

            for sel in seletores:
                try:
                    elementos = soup.select(sel)
                except Exception:
                    elementos = []

                for el in elementos:
                    src = safe_str(
                        el.get("content")
                        or el.get("src")
                        or el.get("data-src")
                        or el.get("data-lazy-src")
                        or el.get("data-zoom-image")
                        or el.get("data-original")
                        or el.get("href")
                    )
                    img_url = _normalizar_url_candidata(url_produto, src)
                    img_l = img_url.lower()
                    if not img_url:
                        continue
                    if not _url_tem_extensao_asset(img_url):
                        continue
                    if any(
                        x in img_l
                        for x in [
                            "sprite", "icon", "logo", "banner", "placeholder",
                            "facebook", "tracking", "pixel", "favicon",
                        ]
                    ):
                        continue
                    if img_url in vistos:
                        continue
                    vistos.add(img_url)
                    imgs_ok.append(img_url)
                    if len(imgs_ok) >= 12:
                        break
                if len(imgs_ok) >= 12:
                    break
        except Exception:
            pass

    return "|".join(imgs_ok)


def _extrair_codigo_basico(url_produto: str, html_produto: str) -> str:
    html_n = safe_str(html_produto)

    patterns = [
        r"(?:sku|c[oó]digo|codigo|ref\.?|refer[eê]ncia)[^A-Za-z0-9]{0,20}([A-Za-z0-9\-_./]{3,60})",
        r'"sku"\s*:\s*"([^"]{3,60})"',
        r'"productid"\s*:\s*"([^"]{3,60})"',
        r'"product_id"\s*:\s*"([^"]{3,60})"',
        r'"reference"\s*:\s*"([^"]{3,60})"',
    ]
    for pattern in patterns:
        m = re.search(pattern, html_n, flags=re.IGNORECASE)
        if m:
            codigo = safe_str(m.group(1))
            if codigo:
                return codigo

    slug = safe_str(urlparse(url_produto).path.split("/")[-1])
    if slug and "-" in slug and len(slug) >= 8:
        return slug[:60]

    return ""


def _extrair_titulo_basico(html_produto: str) -> str:
    html_n = safe_str(html_produto)

    m_og = re.search(
        r'<meta[^>]+property=["\']og:title["\'][^>]+content=["\']([^"\']+)["\']',
        html_n,
        flags=re.IGNORECASE,
    )
    if m_og:
        return safe_str(m_og.group(1))

    m_twitter = re.search(
        r'<meta[^>]+name=["\']twitter:title["\'][^>]+content=["\']([^"\']+)["\']',
        html_n,
        flags=re.IGNORECASE,
    )
    if m_twitter:
        return safe_str(m_twitter.group(1))

    m_title = re.search(r"<title[^>]*>(.*?)</title>", html_n, flags=re.IGNORECASE | re.DOTALL)
    if m_title:
        titulo = re.sub(r"\s+", " ", safe_str(m_title.group(1))).strip()
        if titulo:
            return titulo

    if BeautifulSoup is not None:
        try:
            soup = BeautifulSoup(html_n, "html.parser")
            for sel in ["h1", "[itemprop='name']", '[itemprop="name"]']:
                el = soup.select_one(sel)
                if el:
                    texto = safe_str(el.get_text(" ", strip=True))
                    if texto:
                        return texto
        except Exception:
            pass

    return ""


def _extrair_descricao_detalhada_basica(html_produto: str) -> str:
    if BeautifulSoup is None:
        return ""

    try:
        soup = BeautifulSoup(html_produto, "html.parser")
        seletores = [
            "[itemprop='description']",
            '[itemprop="description"]',
            "meta[name='description']",
            "meta[property='og:description']",
            "[class*='description']",
            "[class*='descricao']",
            "[id*='description']",
            "[id*='descricao']",
        ]
        for sel in seletores:
            try:
                el = soup.select_one(sel)
            except Exception:
                el = None
            if not el:
                continue

            if el.name == "meta":
                content = safe_str(el.get("content"))
                if content and len(content) >= 20:
                    return content

            texto = safe_str(el.get_text(" ", strip=True))
            if texto and len(texto) >= 20:
                return texto[:4000]
    except Exception:
        pass

    return ""


def _extrair_ncm_basico(html_produto: str) -> str:
    html_n = safe_str(html_produto)
    m = re.search(r"(?:\bNCM\b)[^0-9]{0,20}([0-9.\-]{6,12})", html_n, flags=re.IGNORECASE)
    if not m:
        return ""
    return re.sub(r"\D+", "", safe_str(m.group(1)))[:8]


def _extrair_gtin_basico(html_produto: str) -> str:
    html_n = safe_str(html_produto)
    patterns = [
        r"(?:gtin|ean)[^0-9]{0,20}(\d{8}|\d{12,14})",
        r'"gtin(?:8|12|13|14)?"\s*:\s*"(\d{8}|\d{12,14})"',
    ]
    for pattern in patterns:
        m = re.search(pattern, html_n, flags=re.IGNORECASE)
        if m:
            return safe_str(m.group(1))

    m_generic = re.search(r"\b(\d{13}|\d{14}|\d{12}|\d{8})\b", html_n)
    if m_generic:
        return safe_str(m_generic.group(1))

    return ""


def _extrair_preco_basico(html_produto: str) -> str:
    html_n = safe_str(html_produto)
    patterns = [
        r'R\$\s*[\d\.\,]+',
        r'"price"\s*:\s*"([\d\.\,]+)"',
        r'content=["\']([\d\.\,]+)["\']\s*itemprop=["\']price["\']',
    ]
    for pattern in patterns:
        m = re.search(pattern, html_n, flags=re.IGNORECASE)
        if not m:
            continue
        valor = safe_str(m.group(0) if pattern.startswith("R\\$") else m.group(1))
        if valor:
            return valor
    return ""


def _enriquecer_heuristica_com_html(url_produto: str, html_produto: str, heuristica: dict[str, Any]) -> dict[str, Any]:
    base = dict(heuristica or {})

    if not base.get("url_produto"):
        base["url_produto"] = url_produto

    if not safe_str(base.get("descricao")) and not safe_str(base.get("titulo")):
        titulo = _extrair_titulo_basico(html_produto)
        if titulo:
            base["titulo"] = titulo

    if not safe_str(base.get("descricao_detalhada")):
        descricao_detalhada = _extrair_descricao_detalhada_basica(html_produto)
        if descricao_detalhada:
            base["descricao_detalhada"] = descricao_detalhada

    if not safe_str(base.get("preco")):
        preco = _extrair_preco_basico(html_produto)
        if preco:
            base["preco"] = preco

    if not safe_str(base.get("gtin")):
        gtin = _extrair_gtin_basico(html_produto)
        if gtin:
            base["gtin"] = gtin

    if not safe_str(base.get("ncm")):
        ncm = _extrair_ncm_basico(html_produto)
        if ncm:
            base["ncm"] = ncm

    if not safe_str(base.get("categoria")):
        categoria = _extrair_categoria_do_html(url_produto, html_produto)
        if categoria:
            base["categoria"] = categoria

    if not safe_str(base.get("url_imagens")):
        imagens = _extrair_imagens_basicas(url_produto, html_produto)
        if imagens:
            base["url_imagens"] = imagens

    if not safe_str(base.get("codigo")):
        codigo = _extrair_codigo_basico(url_produto, html_produto)
        if codigo:
            base["codigo"] = codigo

    return base


def _auth_context_tem_dados_http(auth_context: dict[str, Any] | None) -> bool:
    if not isinstance(auth_context, dict):
        return False

    auth_http_ok = bool(auth_context.get("auth_http_ok", False))
    cookies = auth_context.get("cookies")
    cookies_count = int(auth_context.get("cookies_count", 0) or 0)
    tem_cookies = isinstance(cookies, list) and len(cookies) > 0

    return bool(auth_http_ok and (tem_cookies or cookies_count > 0))


def _auth_context_valido(auth_context: dict[str, Any] | None) -> bool:
    if not isinstance(auth_context, dict):
        return False

    if not _auth_context_tem_dados_http(auth_context):
        return False

    if bool(auth_context.get("session_ready", False)):
        return True

    return False


def _normalizar_headers_auth(headers: dict[str, Any] | None) -> dict[str, str]:
    if not isinstance(headers, dict):
        return {}

    saida: dict[str, str] = {}
    for chave, valor in headers.items():
        k = safe_str(chave)
        v = safe_str(valor)
        if k and v:
            saida[k] = v
    return saida


def _criar_sessao_autenticada(auth_context: dict[str, Any] | None) -> requests.Session:
    session = requests.Session()
    session.headers.update(DEFAULT_HEADERS)

    if not _auth_context_valido(auth_context):
        return session

    headers = _normalizar_headers_auth(auth_context.get("headers"))
    if headers:
        session.headers.update(headers)

    cookies = auth_context.get("cookies", [])
    if isinstance(cookies, list):
        for cookie in cookies:
            if not isinstance(cookie, dict):
                continue

            nome = safe_str(cookie.get("name"))
            valor = safe_str(cookie.get("value"))
            dominio = safe_str(cookie.get("domain"))
            path = safe_str(cookie.get("path")) or "/"

            if not nome:
                continue

            try:
                session.cookies.set(
                    nome,
                    valor,
                    domain=dominio or None,
                    path=path,
                )
            except Exception:
                continue

    return session


def _url_produtos_contexto(base_url: str, auth_context: dict[str, Any] | None) -> str:
    if isinstance(auth_context, dict):
        products_url = safe_str(auth_context.get("products_url"))
        if products_url:
            return normalizar_url(products_url)
    return normalizar_url(base_url)


def _expandir_urls_tentativa(url: str) -> list[str]:
    url = normalizar_url(url)
    if not url:
        return []

    urls = [url]

    if url.endswith("/"):
        urls.append(url.rstrip("/"))
    else:
        urls.append(url + "/")

    if url.startswith("https://"):
        urls.append("http://" + url[len("https://"):])
    elif url.startswith("http://"):
        urls.append("https://" + url[len("http://"):])

    saida: list[str] = []
    vistos: set[str] = set()
    for item in urls:
        item_n = safe_str(item)
        if item_n and item_n not in vistos:
            vistos.add(item_n)
            saida.append(item_n)
    return saida


def _request_html(url_tentativa: str, headers: dict[str, str], timeout: int = 30, verify: bool = True) -> str:
    with requests.Session() as session:
        session.headers.update(headers)
        response = session.get(
            url_tentativa,
            timeout=timeout,
            allow_redirects=True,
            verify=verify,
        )
        if response.ok and safe_str(response.text):
            return safe_str(response.text)
    return ""


def _fetch_html_publico(url_produto: str) -> str:
    urls_tentativa = _expandir_urls_tentativa(url_produto)

    if fetch_html_retry is not None:
        ultima_exc: Exception | None = None
        for url_tentativa in urls_tentativa:
            for tentativas in (2, 3):
                try:
                    html = safe_str(fetch_html_retry(url_tentativa, tentativas=tentativas))
                    if html:
                        return html
                except Exception as exc:
                    ultima_exc = exc

        if ultima_exc is not None:
            _log_debug(f"fetch_html_retry falhou | url={url_produto} | erro={ultima_exc}", nivel="ERRO")

    for headers in (DEFAULT_HEADERS, MOBILE_HEADERS):
        for url_tentativa in urls_tentativa:
            for verify in (True, False):
                try:
                    html = _request_html(url_tentativa, headers=headers, timeout=30, verify=verify)
                    if html:
                        return html
                except Exception as exc:
                    _log_debug(
                        f"requests público falhou | url={url_tentativa} | verify={verify} | erro={exc}",
                        nivel="ERRO",
                    )

    return ""


def _fetch_html_autenticado(url_produto: str, auth_context: dict[str, Any] | None) -> str:
    if not _auth_context_valido(auth_context):
        return ""

    session = _criar_sessao_autenticada(auth_context)

    ultima_exc: Exception | None = None
    for url_tentativa in _expandir_urls_tentativa(url_produto):
        for _ in range(2):
            try:
                response = session.get(url_tentativa, timeout=45, allow_redirects=True)
                if response.ok and safe_str(response.text):
                    html = safe_str(response.text)
                    if "<html" in html.lower() or "</body>" in html.lower() or len(html) > 500:
                        return html
                ultima_exc = RuntimeError(f"HTTP {response.status_code}")
            except Exception as exc:
                ultima_exc = exc

    if ultima_exc is not None:
        raise ultima_exc

    return ""


def _primeiro_fetch_para_deteccao(
    base_url: str,
    auth_context: dict[str, Any] | None = None,
) -> tuple[str, str]:
    alvo = _url_produtos_contexto(base_url, auth_context=auth_context)

    if _auth_context_valido(auth_context):
        try:
            html_auth = _fetch_html_autenticado(alvo, auth_context=auth_context)
            if html_auth:
                return html_auth, alvo
        except Exception as exc:
            _log_debug(
                f"Falha no fetch autenticado para detecção inicial | url={alvo} | erro={exc}",
                nivel="ERRO",
            )

    try:
        html = _fetch_html_publico(alvo)
        if html:
            return html, alvo
    except Exception as exc:
        _log_debug(
            f"Falha no fetch público para detecção inicial | url={alvo} | erro={exc}",
            nivel="ERRO",
        )

    return "", alvo


def _detectar_bloqueio_login(
    base_url: str,
    auth_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    html, url_final = _primeiro_fetch_para_deteccao(base_url, auth_context=auth_context)
    fornecedor = _fornecedor_slug_do_contexto(base_url, auth_context)

    if not html:
        return {
            "status": "",
            "exige_login": False,
            "captcha_detectado": False,
            "mensagem": "",
            "auth_context": auth_context or {},
        }

    if _url_eh_admin(base_url):
        return {
            "status": STATUS_LOGIN_REQUERIDO,
            "exige_login": True,
            "captcha_detectado": False,
            "mensagem": (
                "Rota administrativa detectada. A IA só consegue trabalhar com sessão HTTP válida "
                "ou com um catálogo público acessível."
            ),
            "auth_context": auth_context or {},
        }

    if _html_base_parece_listagem(html, base_url=base_url):
        return {
            "status": "publico",
            "exige_login": False,
            "captcha_detectado": False,
            "mensagem": "Listagem pública detectada. Busca seguirá por HTTP + IA.",
            "auth_context": auth_context or {},
        }

    if _html_parece_pagina_produto_real(base_url, html):
        return {
            "status": "publico",
            "exige_login": False,
            "captcha_detectado": False,
            "mensagem": "Página de produto detectada. Busca seguirá diretamente.",
            "auth_context": auth_context or {},
        }

    analise = detectar_login_captcha(html=html, url_atual=url_final)
    status = safe_str(analise.get("status"))
    mensagem = ""

    if status == STATUS_LOGIN_CAPTCHA_DETECTADO:
        mensagem = "Login com captcha detectado."
    elif status == STATUS_LOGIN_REQUERIDO:
        mensagem = "Login detectado."

    if status in {STATUS_LOGIN_CAPTCHA_DETECTADO, STATUS_LOGIN_REQUERIDO}:
        try:
            salvar_status_login_em_sessao(
                base_url=_url_raiz(base_url),
                fornecedor=fornecedor,
                status=status,
                mensagem=mensagem,
                exige_login=bool(analise.get("exige_login")),
                captcha_detectado=bool(analise.get("captcha_detectado")),
            )
        except Exception:
            pass

    return {
        **analise,
        "mensagem": mensagem,
        "auth_context": auth_context or {},
    }


def _resolver_auth_context(base_url: str, auth_context: dict[str, Any] | None = None) -> dict[str, Any]:
    if _auth_context_valido(auth_context):
        return auth_context or {}

    try:
        fornecedor = _fornecedor_slug_do_contexto(base_url, auth_context)
        contexto_salvo = montar_auth_context(base_url=_url_raiz(base_url), fornecedor=fornecedor)
        if _auth_context_valido(contexto_salvo):
            _log_debug(
                f"Sessão HTTP autenticada reutilizada com sucesso | url={base_url} | fornecedor={fornecedor}",
                nivel="INFO",
            )
            return contexto_salvo
    except Exception as exc:
        _log_debug(
            f"Falha ao montar auth_context salvo | url={base_url} | erro={exc}",
            nivel="ERRO",
        )

    return auth_context or {}


def _executar_fetch_html(url_produto: str, auth_context: dict[str, Any] | None = None) -> str:
    if _auth_context_valido(auth_context):
        try:
            html_auth = _fetch_html_autenticado(url_produto, auth_context=auth_context)
            if html_auth and not _parece_html_login_puro(html_auth, url_atual=url_produto):
                return html_auth

            if html_auth and _parece_html_login_puro(html_auth, url_atual=url_produto):
                _log_debug(
                    f"Resposta autenticada parece página de login; tentando modo público | url={url_produto}",
                    nivel="INFO",
                )
        except Exception as exc:
            _log_debug(
                f"Falha no fetch autenticado, usando fallback comum | url={url_produto} | erro={exc}",
                nivel="ERRO",
            )

    return _fetch_html_publico(url_produto)


def _executar_heuristica(url_produto: str, html_produto: str) -> dict[str, Any]:
    if extrair_detalhes_heuristicos is None:
        return _enriquecer_heuristica_com_html(url_produto, html_produto, {})

    try:
        dados = extrair_detalhes_heuristicos(url_produto, html_produto)
        dados = dados if isinstance(dados, dict) else {}
        return _enriquecer_heuristica_com_html(url_produto, html_produto, dados)
    except Exception as exc:
        _log_debug(f"Heurística falhou | url={url_produto} | erro={exc}", nivel="ERRO")
        return _enriquecer_heuristica_com_html(url_produto, html_produto, {})


def _executar_gpt(url_produto: str, html_produto: str, heuristica: dict[str, Any]) -> dict[str, Any]:
    if gpt_extrair_produto is None:
        return {}

    ultimo_resultado: dict[str, Any] = {}
    for _ in range(2):
        try:
            dados = gpt_extrair_produto(url_produto, html_produto, heuristica)
            if isinstance(dados, dict) and dados:
                return dados
            if isinstance(dados, dict):
                ultimo_resultado = dados
        except Exception as exc:
            _log_debug(f"GPT falhou | url={url_produto} | erro={exc}", nivel="ERRO")
            continue

    return ultimo_resultado


def _coletar_urls_canonicas_produto(url_produto: str, html_produto: str) -> list[str]:
    urls: list[str] = []
    vistos: set[str] = set()

    def _add(u: str) -> None:
        url_n = _normalizar_url_candidata(url_produto, u)
        if not url_n:
            return
        if not _url_mesmo_dominio(url_produto, url_n):
            return
        if _url_eh_categoria(url_n):
            return
        if url_n in vistos:
            return
        vistos.add(url_n)
        urls.append(url_n)

    _add(url_produto)

    if BeautifulSoup is not None:
        try:
            soup = BeautifulSoup(html_produto, "html.parser")
            for sel, attr in [
                ("link[rel='canonical']", "href"),
                ("meta[property='og:url']", "content"),
                ("meta[name='twitter:url']", "content"),
            ]:
                try:
                    el = soup.select_one(sel)
                except Exception:
                    el = None
                if el:
                    _add(safe_str(el.get(attr)))
        except Exception:
            pass

    try:
        for texto in re.findall(r'"url"\s*:\s*"([^"]+)"', safe_str(html_produto), flags=re.IGNORECASE):
            _add(texto)
    except Exception:
        pass

    return urls


def _escolher_melhor_valor(*valores: Any) -> str:
    melhor = ""
    melhor_score = -1

    for valor in valores:
        texto = safe_str(valor)
        if not texto:
            continue

        score = len(texto)
        if "|" in texto:
            score += 80
        if ">" in texto:
            score += 30
        if re.search(r"\d", texto):
            score += 15
        if re.search(r"[A-Za-zÀ-ÿ]", texto):
            score += 10
        if score > melhor_score:
            melhor = texto
            melhor_score = score

    return melhor


def _mesclar_imagens(*valores: Any) -> str:
    saida: list[str] = []
    vistos: set[str] = set()

    for valor in valores:
        texto = safe_str(valor)
        if not texto:
            continue
        partes = [p.strip() for p in texto.replace("\n", "|").replace(";", "|").split("|") if p.strip()]
        for parte in partes:
            if not parte.startswith(("http://", "https://")):
                continue
            parte_n = parte.lower()
            if any(x in parte_n for x in ["logo", "placeholder", "favicon", "icon", "sprite", "pixel", "facebook"]):
                continue
            if parte in vistos:
                continue
            vistos.add(parte)
            saida.append(parte)

    return "|".join(saida[:12])


def _mesclar_quantidade(*valores: Any) -> str:
    for valor in valores:
        texto = safe_str(valor)
        if texto == "0":
            return "0"
    for valor in valores:
        texto = safe_str(valor)
        if texto:
            return texto
    return ""


def _mesclar_dados_produto(url_produto: str, itens: list[dict[str, Any]]) -> dict[str, Any]:
    base = {"url_produto": url_produto}
    if not itens:
        return base

    melhores_descricoes = []
    melhores_curtas = []
    melhores_detalhadas = []
    categorias = []
    marcas = []
    imagens = []
    codigos = []
    gtins = []
    ncms = []
    precos = []
    quantidades = []

    for item in itens:
        if not isinstance(item, dict):
            continue
        melhores_descricoes.append(item.get("descricao") or item.get("titulo") or item.get("nome"))
        melhores_curtas.append(item.get("descricao_curta"))
        melhores_detalhadas.append(item.get("descricao_detalhada"))
        categorias.append(item.get("categoria"))
        marcas.append(item.get("marca"))
        imagens.append(item.get("url_imagens"))
        codigos.append(item.get("codigo"))
        gtins.append(item.get("gtin"))
        ncms.append(item.get("ncm"))
        precos.append(item.get("preco"))
        quantidades.append(item.get("quantidade"))

    base["descricao"] = _escolher_melhor_valor(*melhores_descricoes)
    base["descricao_curta"] = _escolher_melhor_valor(*melhores_curtas)
    base["descricao_detalhada"] = _escolher_melhor_valor(*melhores_detalhadas)
    base["categoria"] = _escolher_melhor_valor(*categorias)
    base["marca"] = _escolher_melhor_valor(*marcas)
    base["url_imagens"] = _mesclar_imagens(*imagens)
    base["codigo"] = _escolher_melhor_valor(*codigos)
    base["gtin"] = _escolher_melhor_valor(*gtins)
    base["ncm"] = _escolher_melhor_valor(*ncms)
    base["preco"] = _escolher_melhor_valor(*precos)
    base["quantidade"] = _mesclar_quantidade(*quantidades)

    return base


def _coletar_fontes_html_produto(
    url_produto: str,
    auth_context: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    html_principal = _executar_fetch_html(url_produto, auth_context=auth_context)
    if not html_principal:
        return []

    urls_candidatas = _coletar_urls_canonicas_produto(url_produto, html_principal)
    saida: list[dict[str, Any]] = []
    vistos_urls: set[str] = set()

    for idx, url_html in enumerate(urls_candidatas[:4]):
        if url_html in vistos_urls:
            continue
        vistos_urls.add(url_html)

        html = html_principal if idx == 0 else _executar_fetch_html(url_html, auth_context=auth_context)
        if not html:
            continue

        saida.append(
            {
                "url_html": url_html,
                "html": html,
                "principal": idx == 0,
            }
        )

    return saida


def _enriquecer_produto_pagina_a_pagina(
    url_produto: str,
    auth_context: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], list[dict[str, Any]], str, int, str]:
    fontes_html = _coletar_fontes_html_produto(url_produto, auth_context=auth_context)
    if not fontes_html:
        return {}, [], "", 0, "sem_html_produto"

    heuristicas: list[dict[str, Any]] = []
    gpts: list[dict[str, Any]] = []
    url_html_principal = safe_str(fontes_html[0].get("url_html"))
    html_principal = safe_str(fontes_html[0].get("html"))
    motivo = ""

    for fonte in fontes_html:
        url_html = safe_str(fonte.get("url_html"))
        html = safe_str(fonte.get("html"))
        if not html:
            continue

        heuristica = _executar_heuristica(url_html, html)
        heuristicas.append(heuristica)

        gpt = _executar_gpt(url_html, html, heuristica)
        if isinstance(gpt, dict) and gpt:
            gpts.append(gpt)

    dados_mesclados = _mesclar_dados_produto(url_produto, heuristicas + gpts)
    final = _resolver_final(url_produto, dados_mesclados, {})
    final["url_html_principal"] = url_html_principal
    final["fontes_html"] = len(fontes_html)

    if not safe_str(final.get("descricao")) and html_principal:
        final["descricao"] = _extrair_titulo_basico(html_principal)

    if not safe_str(final.get("descricao_detalhada")) and html_principal:
        final["descricao_detalhada"] = _extrair_descricao_detalhada_basica(html_principal)

    if not safe_str(final.get("categoria")) and html_principal:
        final["categoria"] = _extrair_categoria_do_html(url_produto, html_principal)

    if not safe_str(final.get("url_imagens")) and html_principal:
        final["url_imagens"] = _extrair_imagens_basicas(url_produto, html_principal)

    final["descricao_curta"] = _descricao_curta_padrao(final)
    final["quantidade"] = _quantidade_padrao(final)
    final["marca"] = _resolver_marca(final, dados_mesclados)

    score = _score_produto(final)
    if score <= 0:
        motivo = "score_zero_apos_enriquecimento"

    return final, fontes_html, url_html_principal, score, motivo


def _resolver_final(url_produto: str, heuristica: dict[str, Any], gpt: dict[str, Any]) -> dict[str, Any]:
    final: dict[str, Any] = {}

    for campo in [
        "descricao",
        "descricao_curta",
        "descricao_detalhada",
        "categoria",
        "marca",
        "url_imagens",
        "codigo",
        "gtin",
        "ncm",
        "preco",
        "quantidade",
    ]:
        final[campo] = safe_str(gpt.get(campo)) or safe_str(heuristica.get(campo))

    final["url_produto"] = (
        safe_str(gpt.get("url_produto"))
        or safe_str(heuristica.get("url_produto"))
        or url_produto
    )
    final["descricao"] = (
        safe_str(final.get("descricao"))
        or safe_str(heuristica.get("titulo"))
        or safe_str(heuristica.get("nome"))
    )
    final["descricao_curta"] = _descricao_curta_padrao(final)
    final["quantidade"] = _quantidade_padrao(final)
    final["marca"] = _resolver_marca(final, heuristica)

    return final


def _deve_bloquear_produto_por_login(
    html_produto: str,
    url_produto: str,
    heuristica: dict[str, Any],
    auth_context: dict[str, Any] | None = None,
) -> bool:
    if _auth_context_valido(auth_context):
        return False

    if _texto_tem_sinais_de_produto(html_produto):
        return False

    if _html_parece_pagina_produto_real(url_produto, html_produto):
        return False

    if heuristica:
        score_heuristica = pontuar_produto(
            titulo=safe_str(heuristica.get("descricao")) or safe_str(heuristica.get("titulo")),
            preco=safe_str(heuristica.get("preco")),
            codigo=safe_str(heuristica.get("codigo")),
            gtin=safe_str(heuristica.get("gtin")),
            imagens=safe_str(heuristica.get("url_imagens")),
            categoria=safe_str(heuristica.get("categoria")),
            url_produto=safe_str(heuristica.get("url_produto")) or url_produto,
        )
        if score_heuristica > 0:
            return False

    try:
        analise_bloqueio = detectar_login_captcha(html_produto, url_atual=url_produto)
    except Exception:
        return False

    status = safe_str(analise_bloqueio.get("status"))
    if status not in {STATUS_LOGIN_CAPTCHA_DETECTADO, STATUS_LOGIN_REQUERIDO}:
        return False

    return _parece_html_login_puro(html_produto, url_atual=url_produto)


def _payload_diagnostico(
    *,
    url_produto: str,
    status: str,
    motivo: str,
    final: dict[str, Any] | None = None,
    score: int = 0,
    fontes_html: int = 0,
    url_html_principal: str = "",
) -> dict[str, Any]:
    final = final or {}
    return {
        "url_produto": url_produto,
        "status": status,
        "motivo": motivo,
        "score": score,
        "descricao": safe_str(final.get("descricao")),
        "codigo": safe_str(final.get("codigo")),
        "gtin": safe_str(final.get("gtin")),
        "categoria": safe_str(final.get("categoria")),
        "marca": safe_str(final.get("marca")),
        "preco": safe_str(final.get("preco")),
        "fontes_html": fontes_html,
        "url_html_principal": url_html_principal,
    }


def _processar_um_produto(
    url_produto: str,
    diagnostico: bool = False,
    auth_context: dict[str, Any] | None = None,
) -> tuple[str, dict[str, Any]]:
    url_produto = safe_str(url_produto)

    if not url_produto:
        return "rejeitado", {
            "url_produto": url_produto,
            "motivo": "url_vazia",
            "diag": _payload_diagnostico(url_produto=url_produto, status="rejeitado", motivo="url_vazia"),
        }

    try:
        html_produto = _executar_fetch_html(url_produto, auth_context=auth_context)
    except Exception as exc:
        return "erro", {
            "url_produto": url_produto,
            "motivo": "erro_fetch_html",
            "erro": str(exc),
            "diag": _payload_diagnostico(url_produto=url_produto, status="erro", motivo="erro_fetch_html"),
        }

    heuristica_base = _executar_heuristica(url_produto, html_produto)

    if _deve_bloquear_produto_por_login(
        html_produto=html_produto,
        url_produto=url_produto,
        heuristica=heuristica_base,
        auth_context=auth_context,
    ):
        return "bloqueado_login", {
            "url_produto": url_produto,
            "motivo": "login_ou_captcha_sem_sessao_http_utilizavel",
            "erro": "",
            "heuristica": heuristica_base,
            "gpt": {},
            "final": {},
            "diag": _payload_diagnostico(
                url_produto=url_produto,
                status="bloqueado_login",
                motivo="login_ou_captcha_sem_sessao_http_utilizavel",
            ),
        }

    final, fontes_html, url_html_principal, score_enriquecido, motivo_enriquecimento = _enriquecer_produto_pagina_a_pagina(
        url_produto=url_produto,
        auth_context=auth_context,
    )

    if not final:
        final = _resolver_final(url_produto, heuristica_base, {})

    campos_ok, faltando = _campos_criticos_ok(final)
    if faltando:
        _log_debug(
            f"Produto com campos críticos faltando | url={url_produto} | faltando={', '.join(faltando)}",
            nivel="ERRO" if not campos_ok else "INFO",
        )

    if not produto_final_valido(final):
        motivo = motivo_enriquecimento or _motivo_rejeicao(final)
        return "rejeitado", {
            "url_produto": url_produto,
            "final": final,
            "motivo": motivo,
            "diag": _payload_diagnostico(
                url_produto=url_produto,
                status="rejeitado",
                motivo=motivo,
                final=final,
                score=score_enriquecido or _score_produto(final),
                fontes_html=len(fontes_html),
                url_html_principal=url_html_principal,
            ),
        }

    if not campos_ok:
        motivo = _motivo_rejeicao(final)
        return "rejeitado", {
            "url_produto": url_produto,
            "final": final,
            "motivo": motivo,
            "diag": _payload_diagnostico(
                url_produto=url_produto,
                status="rejeitado",
                motivo=motivo,
                final=final,
                score=score_enriquecido or _score_produto(final),
                fontes_html=len(fontes_html),
                url_html_principal=url_html_principal,
            ),
        }

    return "aprovado", {
        "url_produto": url_produto,
        "final": final,
        "row": _montar_linha_saida(final),
        "diag": _payload_diagnostico(
            url_produto=url_produto,
            status="aprovado",
            motivo="ok",
            final=final,
            score=score_enriquecido or _score_produto(final),
            fontes_html=len(fontes_html),
            url_html_principal=url_html_principal,
        ),
    }


def _descoberta_http_direta(
    base_url: str,
    limite: int,
    auth_context: dict[str, Any] | None = None,
) -> list[str]:
    html_base = _executar_fetch_html(base_url, auth_context=auth_context)
    if not html_base:
        return []

    saida: list[str] = []
    vistos: set[str] = set()

    if _html_parece_pagina_produto_real(base_url, html_base):
        base_normalizada = normalizar_url(base_url)
        if base_normalizada and not _url_eh_categoria(base_normalizada):
            vistos.add(base_normalizada)
            saida.append(base_normalizada)

    links = _extrair_links_produto_html(base_url, html_base, limite=min(max(limite, 20), 1500))
    for link in links:
        if link in vistos:
            continue
        vistos.add(link)
        saida.append(link)

    if saida:
        _log_debug(
            f"Descoberta HTTP direta encontrou {len(saida)} links de produto | url={base_url}",
            nivel="INFO",
        )
    return saida[:limite]


def _coletar_produto_direto_se_fizer_sentido(
    base_url: str,
    auth_context: dict[str, Any] | None = None,
) -> list[str]:
    try:
        html = _executar_fetch_html(base_url, auth_context=auth_context)
    except Exception as exc:
        _log_debug(f"Falha no fallback direto de produto | url={base_url} | erro={exc}", nivel="ERRO")
        return []

    if _html_parece_pagina_produto_real(base_url, html):
        return [normalizar_url(base_url)]

    return []


def _deduplicar_urls(urls: list[str], limite: int | None = None) -> list[str]:
    saida: list[str] = []
    vistos: set[str] = set()

    for url in urls:
        url_n = safe_str(url)
        if not url_n:
            continue
        if url_n in vistos:
            continue
        vistos.add(url_n)
        saida.append(url_n)
        if isinstance(limite, int) and limite > 0 and len(saida) >= limite:
            break

    return saida


def _filtrar_urls_produto(urls: list[str], limite: int) -> list[str]:
    saida: list[str] = []
    vistos: set[str] = set()

    for url in urls:
        url_n = safe_str(url)
        if not url_n:
            continue
        if not _url_parece_produto(url_n):
            continue
        if _url_eh_categoria(url_n):
            continue
        if url_n in vistos:
            continue
        vistos.add(url_n)
        saida.append(url_n)
        if len(saida) >= limite:
            break

    return saida


def _descobrir_produtos_via_sitemap_com_contexto(
    base_url: str,
    limite: int,
) -> list[str]:
    if descobrir_produtos_via_sitemap is None:
        return []

    try:
        raiz = _url_raiz(base_url)
        produtos = descobrir_produtos_via_sitemap(
            base_url=raiz,
            limite=limite,
            max_sitemaps=80,
            max_urls_total=max(limite * 15, 12000),
        )
        produtos = [safe_str(url) for url in produtos if safe_str(url)]
        produtos = _filtrar_urls_produto(produtos, limite=limite)
        if produtos:
            _log_debug(
                f"Descoberta via sitemap encontrou {len(produtos)} links de produto | url={raiz}",
                nivel="INFO",
            )
        return _deduplicar_urls(produtos, limite=limite)
    except Exception as exc:
        _log_debug(
            f"Falha na descoberta via sitemap | url={base_url} | erro={exc}",
            nivel="ERRO",
        )
        return []


def _descobrir_produtos_com_contexto(
    base_url: str,
    termo: str,
    limite: int,
    auth_context: dict[str, Any] | None = None,
) -> tuple[list[str], str]:
    alvo_descoberta = _url_produtos_contexto(base_url, auth_context)
    raiz_alvo = _url_raiz(alvo_descoberta)

    if _url_eh_admin(alvo_descoberta) and not _auth_context_valido(auth_context):
        _log_debug(
            f"Rota administrativa sem sessão HTTP válida | url={alvo_descoberta}",
            nivel="ERRO",
        )
        return [], ""

    profile = _profile_for_url(raiz_alvo)
    discovery_mode = safe_str(getattr(profile, "preferred_discovery_mode", "")) if profile is not None else ""

    if discovery_mode in {"sitemap_first", "auto", ""} and not _url_eh_admin(alvo_descoberta):
        produtos_sitemap = _descobrir_produtos_via_sitemap_com_contexto(raiz_alvo, limite=limite)
        if produtos_sitemap:
            return produtos_sitemap, "sitemap"

    candidatos_tentativa: list[tuple[str, dict[str, Any] | None]] = []

    if _auth_context_valido(auth_context):
        candidatos_tentativa.append((alvo_descoberta, auth_context))

    candidatos_tentativa.append((alvo_descoberta, None))
    if raiz_alvo != alvo_descoberta:
        candidatos_tentativa.append((raiz_alvo, None))

    vistos_urls: set[str] = set()
    saida: list[str] = []

    for alvo, ctx in candidatos_tentativa:
        chave = f"{alvo}|{'auth' if ctx else 'publico'}"
        if chave in vistos_urls:
            continue
        vistos_urls.add(chave)

        if descobrir_produtos_no_dominio is not None:
            try:
                kwargs: dict[str, Any] = {
                    "base_url": alvo,
                    "termo": termo,
                    "max_paginas": 600,
                    "max_produtos": limite,
                    "max_segundos": 1200,
                }
                if ctx is not None:
                    kwargs["auth_context"] = ctx

                produtos = descobrir_produtos_no_dominio(**kwargs)
                if isinstance(produtos, list) and produtos:
                    for url in produtos:
                        url_n = safe_str(url)
                        if not url_n:
                            continue
                        if not _url_parece_produto(url_n):
                            continue
                        if url_n not in saida:
                            saida.append(url_n)
                    if saida:
                        return _deduplicar_urls(saida, limite=limite), "crawler_links"
            except Exception as exc:
                modo = "autenticado_http" if ctx else "publico"
                _log_debug(
                    f"Falha ao descobrir produtos | modo={modo} | url={alvo} | erro={exc}",
                    nivel="ERRO",
                )

        try:
            links_http = _descoberta_http_direta(alvo, limite=limite, auth_context=ctx)
            for url in links_http:
                if url not in saida:
                    saida.append(url)
            if saida:
                return _deduplicar_urls(saida, limite=limite), "http_direto"
        except Exception as exc:
            _log_debug(
                f"Falha na descoberta HTTP direta | url={alvo} | erro={exc}",
                nivel="ERRO",
            )

        try:
            links_diretos = _coletar_produto_direto_se_fizer_sentido(alvo, auth_context=ctx)
            for url in links_diretos:
                if url not in saida:
                    saida.append(url)
            if saida:
                return _deduplicar_urls(saida, limite=limite), "produto_direto"
        except Exception as exc:
            _log_debug(
                f"Falha no fallback de produto direto | url={alvo} | erro={exc}",
                nivel="ERRO",
            )

    return [], ""


def _persistir_diagnostico_streamlit(
    *,
    produtos_descobertos: list[str],
    diag_rows: list[dict[str, Any]],
) -> None:
    st = _streamlit_ctx()
    if st is None:
        return

    total_descobertos = len(produtos_descobertos)
    total_validos = sum(1 for row in diag_rows if safe_str(row.get("status")) == "aprovado")
    total_rejeitados = max(len(diag_rows) - total_validos, 0)

    st.session_state["site_busca_diagnostico_df"] = _df_diagnostico(diag_rows)
    st.session_state["site_busca_diagnostico_total_descobertos"] = total_descobertos
    st.session_state["site_busca_diagnostico_total_validos"] = total_validos
    st.session_state["site_busca_diagnostico_total_rejeitados"] = total_rejeitados


def buscar_produtos_site_com_gpt(
    base_url: str,
    termo: str = "",
    limite_links: int | None = None,
    diagnostico: bool = False,
    auth_context: dict[str, Any] | None = None,
) -> pd.DataFrame:
    st = _streamlit_ctx()

    base_url = normalizar_url(base_url)
    termo = safe_str(termo)

    if not base_url:
        _log_debug("Busca por site cancelada: base_url vazia.", nivel="ERRO")
        return pd.DataFrame()

    limite = _limite_tecnico(limite_links)

    progress_bar = None
    status_box = None
    contador_box = None

    if st is not None:
        progress_bar = st.progress(0)
        status_box = st.empty()
        contador_box = st.empty()
        status_box.info("🔍 Descobrindo produtos no site...")

    auth_context = _resolver_auth_context(base_url=base_url, auth_context=auth_context)
    fornecedor = _fornecedor_slug_do_contexto(base_url, auth_context)
    manual_mode = isinstance(auth_context, dict) and bool(auth_context.get("manual_mode", False))
    auth_http_ok = _auth_context_valido(auth_context)

    auth_mode = "autenticado_http" if auth_http_ok else "publico"
    _log_debug(
        f"Iniciando busca por site | url={base_url} | termo={termo or '-'} | limite={limite} | modo={auth_mode}",
        nivel="INFO",
    )
    _log_debug(
        (
            "Auth context | "
            f"manual_mode={manual_mode} | "
            f"session_ready={safe_str(auth_context.get('session_ready'))} | "
            f"auth_http_ok={auth_http_ok}"
        ),
        nivel="INFO",
    )

    login_status = _detectar_bloqueio_login(base_url=base_url, auth_context=auth_context)
    login_status_normalizado = safe_str(login_status.get("status"))

    if st is not None:
        st.session_state["site_busca_login_status"] = login_status

    if login_status_normalizado in {STATUS_LOGIN_CAPTCHA_DETECTADO, STATUS_LOGIN_REQUERIDO}:
        mensagem_info = safe_str(login_status.get("mensagem"))
        if not mensagem_info:
            if login_status_normalizado == STATUS_LOGIN_CAPTCHA_DETECTADO:
                mensagem_info = (
                    "Possível captcha/login detectado. Tentando captura por HTTP público/autenticado "
                    "sem depender de navegador visível."
                )
            else:
                mensagem_info = (
                    "Possível página com login detectada. Tentando captura por HTTP público/autenticado "
                    "sem depender de navegador visível."
                )

        if status_box is not None:
            status_box.warning(mensagem_info)

        _log_debug(
            f"Detecção inicial de login/captcha não interrompeu o crawler | url={base_url} | status={login_status_normalizado}",
            nivel="INFO",
        )

    if auth_http_ok:
        salvar_status_login_em_sessao(
            base_url=_url_raiz(base_url),
            fornecedor=fornecedor,
            status=STATUS_SESSAO_PRONTA,
            mensagem="Sessão HTTP autenticada pronta para uso.",
            exige_login=False,
            captcha_detectado=False,
        )

    produtos, fonte_descoberta = _descobrir_produtos_com_contexto(
        base_url=base_url,
        termo=termo,
        limite=limite,
        auth_context=auth_context,
    )

    if st is not None:
        st.session_state["site_busca_fonte_descoberta"] = fonte_descoberta or ""

    if fonte_descoberta and status_box is not None:
        if fonte_descoberta == "sitemap":
            status_box.info("🗺️ Produtos descobertos via sitemap do fornecedor.")
        elif fonte_descoberta == "crawler_links":
            status_box.info("🕸️ Produtos descobertos via varredura de links do domínio.")
        elif fonte_descoberta == "http_direto":
            status_box.info("🌐 Produtos descobertos via leitura direta do HTML.")
        elif fonte_descoberta == "produto_direto":
            status_box.info("📦 URL inicial já aparenta ser uma página de produto.")

    if not produtos:
        if _url_eh_admin(base_url) and not auth_http_ok:
            mensagem = (
                "Rota administrativa detectada sem sessão HTTP válida. "
                "A IA não consegue captar produtos sem acesso real ao conteúdo protegido."
            )
            salvar_status_login_em_sessao(
                base_url=_url_raiz(base_url),
                fornecedor=fornecedor,
                status=STATUS_LOGIN_REQUERIDO,
                mensagem=mensagem,
                exige_login=True,
                captcha_detectado=False,
            )
            if status_box is not None:
                status_box.warning(mensagem)
        elif login_status_normalizado in {STATUS_LOGIN_CAPTCHA_DETECTADO, STATUS_LOGIN_REQUERIDO} and not auth_http_ok:
            mensagem = (
                "Fornecedor aparenta exigir login/captcha e não há sessão HTTP utilizável. "
                "Busca pública não encontrou catálogo."
            )
            salvar_status_login_em_sessao(
                base_url=_url_raiz(base_url),
                fornecedor=fornecedor,
                status=login_status_normalizado or STATUS_LOGIN_REQUERIDO,
                mensagem=mensagem,
                exige_login=bool(login_status.get("exige_login")),
                captcha_detectado=bool(login_status.get("captcha_detectado")),
            )
            if status_box is not None:
                status_box.warning(mensagem)
        else:
            if status_box is not None:
                status_box.warning("Nenhum produto encontrado na descoberta inicial do domínio.")
            _log_debug("Nenhum produto encontrado na descoberta inicial do domínio.", nivel="ERRO")

        _persistir_diagnostico_streamlit(produtos_descobertos=[], diag_rows=[])
        return pd.DataFrame()

    produtos = _filtrar_urls_produto(produtos, limite=limite)
    total = len(produtos)

    rows: list[dict] = []
    rows_lock = threading.Lock()

    diag_rows: list[dict] = []
    diag_lock = threading.Lock()

    vistos_aprovados: set[str] = set()
    aprovados_lock = threading.Lock()

    login_bloqueios = 0

    _log_debug(
        f"Links de produto descobertos: {total} | fonte={fonte_descoberta or 'desconhecida'}",
        nivel="INFO",
    )

    workers = _max_workers(total)
    processados = 0

    def worker(url_produto: str) -> tuple[str, dict[str, Any]]:
        return _processar_um_produto(
            url_produto=url_produto,
            diagnostico=diagnostico,
            auth_context=auth_context,
        )

    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
            future_to_url = {
                executor.submit(worker, url_produto): url_produto
                for url_produto in produtos
            }

            for future in concurrent.futures.as_completed(future_to_url):
                url_produto = future_to_url[future]
                processados += 1

                try:
                    status, payload = future.result()
                except Exception as exc:
                    status = "erro"
                    payload = {
                        "url_produto": url_produto,
                        "motivo": "erro_worker_nao_tratado",
                        "erro": repr(exc),
                        "diag": _payload_diagnostico(
                            url_produto=url_produto,
                            status="erro",
                            motivo="erro_worker_nao_tratado",
                        ),
                    }
                    _log_debug(
                        f"Worker falhou sem tratamento | url={url_produto} | erro={repr(exc)}",
                        nivel="ERRO",
                    )

                percentual = int((processados / max(total, 1)) * 100)
                percentual = max(0, min(percentual, 100))

                if progress_bar is not None:
                    progress_bar.progress(percentual)
                if contador_box is not None:
                    contador_box.write(f"Processando {processados} de {total}")
                if status_box is not None:
                    status_box.info(f"🌐 Processando produto {processados}/{total}\n\n{url_produto}")

                diag = payload.get("diag")
                if isinstance(diag, dict):
                    with diag_lock:
                        diag_rows.append(diag)

                if status == "aprovado":
                    row = payload.get("row", {})

                    with aprovados_lock:
                        if url_produto in vistos_aprovados:
                            continue
                        vistos_aprovados.add(url_produto)

                    with rows_lock:
                        rows.append(row)
                    continue

                if status == "bloqueado_login":
                    login_bloqueios += 1

    except Exception as exc:
        _log_debug(f"Falha geral no processamento paralelo: {repr(exc)}", nivel="ERRO")
        raise RuntimeError(f"Falha no processamento paralelo dos produtos: {repr(exc)}") from exc

    if login_bloqueios > 0 and len(rows) == 0 and not auth_http_ok:
        mensagem_bloqueio = (
            "Os links processados aparentam exigir login/captcha e não existe sessão HTTP utilizável "
            "para continuar a captura no deploy atual."
        )
        salvar_status_login_em_sessao(
            base_url=_url_raiz(base_url),
            fornecedor=fornecedor,
            status=STATUS_LOGIN_CAPTCHA_DETECTADO,
            mensagem=mensagem_bloqueio,
            exige_login=True,
            captcha_detectado=True,
        )
        if status_box is not None:
            status_box.warning(mensagem_bloqueio)
        _log_debug(
            f"Todos os itens foram bloqueados por login/captcha | url={base_url} | bloqueios={login_bloqueios}",
            nivel="ERRO",
        )

    if progress_bar is not None:
        progress_bar.progress(100)

    if status_box is not None:
        if len(rows) > 0:
            status_box.success(f"🎉 Busca finalizada. Produtos válidos: {len(rows)}")
        elif login_bloqueios > 0 and not auth_http_ok:
            status_box.warning("Busca finalizada sem produtos válidos por login/captcha sem sessão HTTP utilizável.")
        else:
            status_box.warning("Busca finalizada sem produtos válidos.")

    _persistir_diagnostico_streamlit(produtos_descobertos=produtos, diag_rows=diag_rows)

    _log_debug(
        (
            "Busca por site finalizada | "
            f"fonte={fonte_descoberta or 'desconhecida'} | "
            f"descobertos={len(produtos)} | "
            f"validos={len(rows)} | "
            f"rejeitados={max(len(diag_rows) - len(rows), 0)} | "
            f"login_bloqueios={login_bloqueios} | "
            f"manual_mode={manual_mode} | "
            f"auth_http_ok={auth_http_ok}"
        ),
        nivel="INFO",
    )

    return _df_saida(rows)
