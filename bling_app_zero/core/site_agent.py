
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
        if safe_str(kwargs.get("descricao_detalhada")):
            score += 1
        if safe_str(kwargs.get("marca")):
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
    "itemprop=\"price\"",
    "itemprop='price'",
    "itemprop=\"sku\"",
    "itemprop='sku'",
    "og:type",
    "availability",
    "in stock",
    "out of stock",
    "description",
    "descrição",
    "descricao",
    "marca",
    "brand",
    "ncm",
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
    for token in tokens[:6]:
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


def _descricao_detalhada_fallback(html_produto: str) -> str:
    html = safe_str(html_produto)
    if not html:
        return ""

    candidatos: list[str] = []

    padroes = [
        r'<meta[^>]+name=["\']description["\'][^>]+content=["\']([^"\']+)["\']',
        r'<meta[^>]+property=["\']og:description["\'][^>]+content=["\']([^"\']+)["\']',
    ]
    for pattern in padroes:
        m = re.search(pattern, html, flags=re.IGNORECASE)
        if m:
            candidatos.append(safe_str(m.group(1)))

    if BeautifulSoup is not None:
        try:
            soup = BeautifulSoup(html, "html.parser")
            for sel in [
                "[itemprop='description']",
                "[itemprop=\"description\"]",
                "[class*='description']",
                "[class*='descricao']",
                "[id*='description']",
                "[id*='descricao']",
                ".product-description",
                ".product__description",
                ".descricao-produto",
                ".tab-description",
            ]:
                for el in soup.select(sel):
                    texto = safe_str(el.get_text(" ", strip=True))
                    if texto:
                        candidatos.append(texto)
        except Exception:
            pass

    for candidato in candidatos:
        if len(candidato) >= 30:
            return candidato[:5000]

    return ""


def _ncm_fallback(html_produto: str) -> str:
    html = safe_str(html_produto)
    if not html:
        return ""

    padroes = [
        r"(?:\bNCM\b)[^\d]{0,8}(\d{6,8})",
        r"(?:\bNCM\b)[^\d]{0,8}(\d{4}\.?\d{2}\.?\d{2})",
    ]
    for pattern in padroes:
        m = re.search(pattern, html, flags=re.IGNORECASE)
        if m:
            valor = re.sub(r"\D+", "", safe_str(m.group(1)))
            if len(valor) >= 6:
                return valor[:8]
    return ""


def _capturar_meta_basica(html_produto: str, propriedade: str) -> str:
    html = safe_str(html_produto)
    if not html:
        return ""
    pattern = rf'<meta[^>]+(?:property|name)=["\']{re.escape(propriedade)}["\'][^>]+content=["\']([^"\']+)["\']'
    m = re.search(pattern, html, flags=re.IGNORECASE)
    return safe_str(m.group(1)) if m else ""


def _montar_linha_saida(final: dict) -> dict:
    return {
        "Código": safe_str(final.get("codigo")),
        "Descrição": safe_str(final.get("descricao")),
        "Descrição Curta": _descricao_curta_padrao(final),
        "Descrição Detalhada": safe_str(final.get("descricao_detalhada")),
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
        "Descrição Detalhada",
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


def _score_produto(item: dict) -> int:
    score = pontuar_produto(
        titulo=safe_str(item.get("descricao")),
        preco=safe_str(item.get("preco")),
        codigo=safe_str(item.get("codigo")),
        gtin=safe_str(item.get("gtin")),
        imagens=safe_str(item.get("url_imagens")),
        categoria=safe_str(item.get("categoria")),
        url_produto=safe_str(item.get("url_produto")),
    )
    if safe_str(item.get("descricao_detalhada")):
        score += 1
    if safe_str(item.get("marca")):
        score += 1
    if safe_str(item.get("ncm")):
        score += 1
    return score


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
        return f"falt

