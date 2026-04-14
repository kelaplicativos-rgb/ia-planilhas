from __future__ import annotations

import json
import math
import re
from html import unescape
from typing import Any
from urllib.parse import parse_qs, urlencode, urljoin, urlparse, urlunparse

import pandas as pd
import requests
from bs4 import BeautifulSoup

try:
    from bling_app_zero.utils.excel_logs import log_debug
except Exception:
    try:
        from bling_app_zero.utils.excel import log_debug
    except Exception:
        def log_debug(_msg: str, _nivel: str = "INFO") -> None:
            return None

try:
    from bling_app_zero.core.fornecedores_adaptativos import garantir_fornecedor_adaptativo
except Exception:
    garantir_fornecedor_adaptativo = None


EXECUTOR_VERSION = "V1_THREE_SUPPLIERS_EXECUTOR"
DEFAULT_TIMEOUT = 30
DEFAULT_PAGE_SIZE = 100
DEFAULT_STOQUI_PAGE_SIZE = 1000


# ==========================================================
# HELPERS
# ==========================================================
def _safe_str(valor: Any) -> str:
    try:
        return str(valor or "").strip()
    except Exception:
        return ""


def _safe_int(valor: Any, default: int = 0) -> int:
    try:
        if valor is None or valor == "":
            return default
        return int(float(str(valor).strip()))
    except Exception:
        return default


def _safe_float(valor: Any, default: float = 0.0) -> float:
    try:
        if valor is None or valor == "":
            return default
        return float(str(valor).strip())
    except Exception:
        return default


def _dominio(url: str) -> str:
    try:
        return urlparse(_safe_str(url)).netloc.lower().replace("www.", "")
    except Exception:
        return ""


def _strip_html(texto: Any) -> str:
    bruto = _safe_str(texto)
    if not bruto:
        return ""

    try:
        soup = BeautifulSoup(bruto, "html.parser")
        limpo = soup.get_text(" ", strip=True)
        return re.sub(r"\s+", " ", unescape(limpo)).strip()
    except Exception:
        limpo = re.sub(r"<[^>]+>", " ", bruto)
        limpo = unescape(limpo)
        return re.sub(r"\s+", " ", limpo).strip()


def _extract_attr_from_html(html_snippet: Any, attr: str) -> str:
    bruto = _safe_str(html_snippet)
    if not bruto:
        return ""

    try:
        soup = BeautifulSoup(bruto, "html.parser")
        tag = soup.find(attrs={attr: True})
        if tag:
            return _safe_str(tag.get(attr))
        tag = soup.find(True)
        if tag:
            return _safe_str(tag.get(attr))
    except Exception:
        pass

    padrao = re.compile(rf'{re.escape(attr)}=["\']([^"\']+)["\']', re.IGNORECASE)
    m = padrao.search(bruto)
    return _safe_str(m.group(1)) if m else ""


def _extract_all_img_urls_from_html(html_snippet: Any) -> list[str]:
    bruto = _safe_str(html_snippet)
    if not bruto:
        return []

    urls: list[str] = []

    try:
        soup = BeautifulSoup(bruto, "html.parser")
        for tag in soup.find_all("img"):
            for attr in ("src", "data-src", "data-original"):
                valor = _safe_str(tag.get(attr))
                if valor:
                    urls.append(valor)
        for tag in soup.find_all("a"):
            href = _safe_str(tag.get("href"))
            if href and any(href.lower().endswith(ext) for ext in (".jpg", ".jpeg", ".png", ".webp", ".gif")):
                urls.append(href)
    except Exception:
        pass

    vistos: set[str] = set()
    finais: list[str] = []
    for url in urls:
        if url and url not in vistos:
            vistos.add(url)
            finais.append(url)
    return finais


def _normalizar_lista_imagens(urls: list[str]) -> str:
    limpas = [_safe_str(u) for u in urls if _safe_str(u)]
    vistas: set[str] = set()
    finais: list[str] = []
    for url in limpas:
        if url not in vistas:
            vistas.add(url)
            finais.append(url)
    return "|".join(finais)


def _parse_brl(texto: Any) -> float | None:
    bruto = _safe_str(texto)
    if not bruto:
        return None

    limpo = _strip_html(bruto)
    if not limpo:
        return None

    # pega todos os padrões numéricos brasileiros
    candidatos = re.findall(r"\d{1,3}(?:\.\d{3})*,\d{2}|\d+\.\d{2}|\d+", limpo)
    if not candidatos:
        return None

    # usa o último número como preço atual na maioria dos casos
    valor = candidatos[-1]
    valor = valor.replace(".", "").replace(",", ".")
    try:
        return float(valor)
    except Exception:
        return None


def _parse_brl_preco_de(texto: Any) -> float | None:
    bruto = _safe_str(texto)
    if not bruto:
        return None

    limpo = _strip_html(bruto)
    if not limpo:
        return None

    candidatos = re.findall(r"\d{1,3}(?:\.\d{3})*,\d{2}|\d+\.\d{2}|\d+", limpo)
    if len(candidatos) >= 2:
        valor = candidatos[0].replace(".", "").replace(",", ".")
        try:
            return float(valor)
        except Exception:
            return None
    return None


def _parse_inventory_html(texto: Any) -> int | None:
    bruto = _safe_str(texto)
    if not bruto:
        return None

    # tenta primeiro pelo title="93 Unidades"
    m = re.search(r'title=["\']\s*(\d+)\s+unidades?', bruto, flags=re.IGNORECASE)
    if m:
        return _safe_int(m.group(1), 0)

    limpo = _strip_html(bruto).lower()
    if any(chave in limpo for chave in ["sem estoque", "indisponível", "indisponivel", "esgotado", "zerado"]):
        return 0

    m = re.search(r"(\d+)", limpo)
    if m:
        return _safe_int(m.group(1), 0)

    if "disponível" in limpo or "disponivel" in limpo:
        return 1

    return None


def _resolver_tipo_fornecedor(url: str, html: str = "") -> dict[str, Any]:
    dominio = _dominio(url)
    config: dict[str, Any] = {}

    if callable(garantir_fornecedor_adaptativo):
        try:
            config = garantir_fornecedor_adaptativo(url, html or "")
        except Exception as e:
            log_debug(f"[CONECTOR_EXECUTOR] falha ao resolver fornecedor adaptativo: {e}", "WARNING")
            config = {}

    if config:
        return config

    if dominio in {"app.obaobamix.com.br", "obaobamix.com.br"}:
        return {"dominio": dominio, "tipo": "api_datatables_auth", "links": {"api_produtos": ["/admin/products"]}}

    if dominio in {"app.stoqui.com.br", "stoqui.com.br"}:
        return {
            "dominio": dominio,
            "tipo": "api_supabase_auth",
            "links": {
                "api_produtos": ["https://bvwsyolgpsbvflhbqily.supabase.co/rest/v1/produto"],
                "api_categorias": ["https://bvwsyolgpsbvflhbqily.supabase.co/rest/v1/categoria"],
                "api_variacoes": ["https://bvwsyolgpsbvflhbqily.supabase.co/rest/v1/produto_variacao"],
            },
        }

    if dominio in {"atacadum.com.br", "www.atacadum.com.br", "sistema.sistemawbuy.com.br", "cdn.sistemawbuy.com.br"}:
        return {"dominio": dominio, "tipo": "html_wbuy", "links": {"api_produtos": ["global.php"]}}

    return {"dominio": dominio, "tipo": "generico_html"}


def _montar_df_saida(linhas: list[dict[str, Any]]) -> pd.DataFrame:
    if not linhas:
        return pd.DataFrame()

    df = pd.DataFrame(linhas)

    ordem = [
        "id_externo",
        "codigo",
        "nome",
        "descricao",
        "modelo",
        "gtin",
        "preco",
        "preco_de",
        "estoque",
        "marca",
        "categoria",
        "cor",
        "imagem_url",
        "link",
        "fonte_url",
        "fornecedor_tipo",
        "dominio",
    ]

    for coluna in ordem:
        if coluna not in df.columns:
            df[coluna] = None

    extras = [c for c in df.columns if c not in ordem]
    return df[ordem + extras]


def _montar_resultado(
    *,
    ok: bool,
    fornecedor_tipo: str,
    dominio: str,
    linhas: list[dict[str, Any]] | None = None,
    erro: str = "",
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    linhas = linhas or []
    df = _montar_df_saida(linhas)

    return {
        "ok": bool(ok),
        "fornecedor_tipo": _safe_str(fornecedor_tipo),
        "dominio": _safe_str(dominio),
        "linhas": linhas,
        "df": df,
        "total_linhas": len(df),
        "erro": _safe_str(erro),
        "metadata": metadata or {},
        "executor_version": EXECUTOR_VERSION,
    }


# ==========================================================
# OBA OBA MIX
# ==========================================================
def _oba_linha_para_dict(item: dict[str, Any], fonte_url: str) -> dict[str, Any]:
    brand = item.get("brand") or {}
    color = item.get("color") or {}

    price_html = item.get("price")
    preco = _parse_brl(price_html)
    preco_de = _parse_brl_preco_de(price_html)

    if preco_de is None:
        preco_de = _safe_float(item.get("price_of"), 0.0) or None

    imagens = _extract_all_img_urls_from_html(item.get("photo"))

    return {
        "id_externo": item.get("id"),
        "codigo": _strip_html(item.get("sku")),
        "nome": _strip_html(item.get("name")),
        "descricao": "",
        "modelo": _safe_str(item.get("model")),
        "gtin": _safe_str(item.get("ean")),
        "preco": preco,
        "preco_de": preco_de,
        "estoque": _parse_inventory_html(item.get("inventory")),
        "marca": _safe_str(brand.get("name") or item.get("brand_name")),
        "categoria": "",
        "cor": _safe_str(color.get("name")),
        "imagem_url": _normalizar_lista_imagens(imagens),
        "link": "",
        "fonte_url": fonte_url,
        "fornecedor_tipo": "api_datatables_auth",
        "dominio": _dominio(fonte_url),
        "api_active": item.get("api_active"),
        "api_mercado_livre_category": item.get("api_mercado_livre_category"),
        "info_kit": item.get("info_kit"),
    }


def executar_conector_obaobamix(
    *,
    api_response_text: str | None = None,
    api_response_json: dict[str, Any] | None = None,
    fonte_url: str = "https://app.obaobamix.com.br/admin/products",
) -> dict[str, Any]:
    try:
        payload = api_response_json
        if payload is None:
            bruto = _safe_str(api_response_text)
            if not bruto:
                return _montar_resultado(
                    ok=False,
                    fornecedor_tipo="api_datatables_auth",
                    dominio=_dominio(fonte_url),
                    erro="api_response_vazia",
                )
            payload = json.loads(bruto)

        itens = payload.get("data") or []
        if not isinstance(itens, list):
            return _montar_resultado(
                ok=False,
                fornecedor_tipo="api_datatables_auth",
                dominio=_dominio(fonte_url),
                erro="payload_datatables_invalido",
            )

        linhas = [_oba_linha_para_dict(item, fonte_url) for item in itens if isinstance(item, dict)]

        return _montar_resultado(
            ok=True,
            fornecedor_tipo="api_datatables_auth",
            dominio=_dominio(fonte_url),
            linhas=linhas,
            metadata={
                "records_total": payload.get("recordsTotal"),
                "records_filtered": payload.get("recordsFiltered"),
                "draw": payload.get("draw"),
            },
        )
    except Exception as e:
        return _montar_resultado(
            ok=False,
            fornecedor_tipo="api_datatables_auth",
            dominio=_dominio(fonte_url),
            erro=str(e),
        )


# ==========================================================
# STOQUI / SUPABASE
# ==========================================================
def _stoqui_headers(api_key: str, bearer_token: str, x_client_info: str = "supabase-js-web/2.103.0") -> dict[str, str]:
    return {
        "apikey": _safe_str(api_key),
        "Authorization": f"Bearer {_safe_str(bearer_token)}",
        "Accept": "application/json",
        "Accept-Profile": "public",
        "X-Client-Info": _safe_str(x_client_info) or "supabase-js-web/2.103.0",
    }


def _stoqui_build_url(base_url: str, user_id: str, extra_params: dict[str, Any] | None = None) -> str:
    params = {
        "select": "*",
        "user_id": f"eq.{_safe_str(user_id)}",
        "deletado_em": "is.null",
        "oculto": "eq.true",
        "oculto_por_limite": "eq.true",
    }
    if isinstance(extra_params, dict):
        for k, v in extra_params.items():
            if _safe_str(k):
                params[_safe_str(k)] = _safe_str(v)

    return f"{_safe_str(base_url)}?{urlencode(params)}"


def _stoqui_row(item: dict[str, Any], categorias_map: dict[Any, str], fonte_url: str) -> dict[str, Any]:
    categoria_id = item.get("categoria_id")
    categoria_nome = categorias_map.get(categoria_id, "") if categorias_map else ""

    imagem_url = (
        _safe_str(item.get("imagem_url"))
        or _safe_str(item.get("foto_url"))
        or _safe_str(item.get("imagem"))
    )

    return {
        "id_externo": item.get("id"),
        "codigo": _safe_str(item.get("codigo") or item.get("sku") or item.get("referencia")),
        "nome": _safe_str(item.get("nome") or item.get("titulo")),
        "descricao": _safe_str(item.get("descricao")),
        "modelo": _safe_str(item.get("modelo")),
        "gtin": _safe_str(item.get("ean") or item.get("gtin")),
        "preco": item.get("preco") if item.get("preco") is not None else item.get("preco_venda"),
        "preco_de": item.get("preco_de"),
        "estoque": item.get("estoque") if item.get("estoque") is not None else item.get("quantidade"),
        "marca": _safe_str(item.get("marca")),
        "categoria": categoria_nome,
        "cor": _safe_str(item.get("cor")),
        "imagem_url": imagem_url,
        "link": "",
        "fonte_url": fonte_url,
        "fornecedor_tipo": "api_supabase_auth",
        "dominio": _dominio(fonte_url),
        "categoria_id": categoria_id,
    }


def _stoqui_buscar_paginas(
    *,
    api_url: str,
    headers: dict[str, str],
    page_size: int = DEFAULT_STOQUI_PAGE_SIZE,
    timeout: int = DEFAULT_TIMEOUT,
) -> list[dict[str, Any]]:
    session = requests.Session()
    session.headers.update(headers)

    linhas: list[dict[str, Any]] = []
    inicio = 0

    while True:
        fim = inicio + page_size - 1
        resposta = session.get(
            api_url,
            headers={"Range": f"{inicio}-{fim}"},
            timeout=timeout,
        )
        resposta.raise_for_status()

        dados = resposta.json()
        if not isinstance(dados, list) or not dados:
            break

        linhas.extend([item for item in dados if isinstance(item, dict)])

        if len(dados) < page_size:
            break

        inicio += page_size

    return linhas


def _stoqui_buscar_categorias(
    *,
    categorias_url: str,
    headers: dict[str, str],
    user_id: str,
    timeout: int = DEFAULT_TIMEOUT,
) -> dict[Any, str]:
    params = {
        "select": "*",
        "user_id": f"eq.{_safe_str(user_id)}",
    }
    url = f"{_safe_str(categorias_url)}?{urlencode(params)}"

    try:
        resposta = requests.get(url, headers=headers, timeout=timeout)
        resposta.raise_for_status()
        dados = resposta.json()
        if not isinstance(dados, list):
            return {}
        return {item.get("id"): _safe_str(item.get("nome")) for item in dados if isinstance(item, dict)}
    except Exception as e:
        log_debug(f"[CONECTOR_EXECUTOR] falha ao buscar categorias stoqui: {e}", "WARNING")
        return {}


def executar_conector_stoqui(
    *,
    user_id: str,
    api_key: str,
    bearer_token: str,
    base_url: str = "https://bvwsyolgpsbvflhbqily.supabase.co/rest/v1/produto",
    categorias_url: str = "https://bvwsyolgpsbvflhbqily.supabase.co/rest/v1/categoria",
    extra_params: dict[str, Any] | None = None,
    x_client_info: str = "supabase-js-web/2.103.0",
) -> dict[str, Any]:
    try:
        headers = _stoqui_headers(api_key=api_key, bearer_token=bearer_token, x_client_info=x_client_info)
        api_url = _stoqui_build_url(base_url=base_url, user_id=user_id, extra_params=extra_params)
        categorias_map = _stoqui_buscar_categorias(
            categorias_url=categorias_url,
            headers=headers,
            user_id=user_id,
        )
        itens = _stoqui_buscar_paginas(api_url=api_url, headers=headers)

        linhas = [_stoqui_row(item, categorias_map, api_url) for item in itens]

        return _montar_resultado(
            ok=True,
            fornecedor_tipo="api_supabase_auth",
            dominio=_dominio(base_url),
            linhas=linhas,
            metadata={
                "api_url": api_url,
                "total_itens_brutos": len(itens),
                "categorias_mapeadas": len(categorias_map),
            },
        )
    except Exception as e:
        return _montar_resultado(
            ok=False,
            fornecedor_tipo="api_supabase_auth",
            dominio=_dominio(base_url),
            erro=str(e),
        )


# ==========================================================
# WBUY / HTML
# ==========================================================
WBUY_CARD_SELECTORS = [
    ".product",
    ".produto",
    ".item-product",
    ".product-item",
    ".box-produto",
    ".vitrine-produtos li",
    ".products-grid li",
    ".item",
]

WBUY_NAME_SELECTORS = [
    "h2 a",
    "h3 a",
    ".title a",
    ".product-name a",
    ".nome-produto",
    "a[title]",
]

WBUY_PRICE_SELECTORS = [
    ".price",
    ".preco",
    ".product_price",
    ".price-current",
    ".valor",
    ".precoPor",
]

WBUY_OLD_PRICE_SELECTORS = [
    ".price-old",
    ".precoDe",
    ".old-price",
    ".de",
]

WBUY_IMG_SELECTORS = [
    "img",
    "img[data-src]",
    "img[data-original]",
]


def _pick_first_text(node: BeautifulSoup, selectors: list[str]) -> str:
    for seletor in selectors:
        try:
            alvo = node.select_one(seletor)
            if alvo:
                texto = _strip_html(str(alvo))
                if texto:
                    return texto
        except Exception:
            continue
    return ""


def _pick_first_href(node: BeautifulSoup) -> str:
    try:
        a = node.select_one("a[href]")
        if a:
            return _safe_str(a.get("href"))
    except Exception:
        pass
    return ""


def _pick_images_from_card(node: BeautifulSoup) -> list[str]:
    urls: list[str] = []
    for seletor in WBUY_IMG_SELECTORS:
        try:
            for img in node.select(seletor):
                for attr in ("data-src", "data-original", "src"):
                    valor = _safe_str(img.get(attr))
                    if valor:
                        urls.append(valor)
        except Exception:
            continue

    vistos: set[str] = set()
    finais: list[str] = []
    for url in urls:
        if url and url not in vistos:
            vistos.add(url)
            finais.append(url)
    return finais


def _wbuy_parse_html(html: str, fonte_url: str) -> list[dict[str, Any]]:
    soup = BeautifulSoup(html, "html.parser")

    cards: list[Any] = []
    for seletor in WBUY_CARD_SELECTORS:
        try:
            achados = soup.select(seletor)
        except Exception:
            achados = []
        if len(achados) >= 2:
            cards = achados
            break

    linhas: list[dict[str, Any]] = []

    for card in cards:
        nome = _pick_first_text(card, WBUY_NAME_SELECTORS)
        preco_txt = _pick_first_text(card, WBUY_PRICE_SELECTORS)

        if not nome and not preco_txt:
            continue

        link = _pick_first_href(card)
        if link:
            link = urljoin(fonte_url, link)

        imagens = [urljoin(fonte_url, img) for img in _pick_images_from_card(card)]

        linha = {
            "id_externo": "",
            "codigo": "",
            "nome": nome,
            "descricao": "",
            "modelo": "",
            "gtin": "",
            "preco": _parse_brl(preco_txt),
            "preco_de": _parse_brl(_pick_first_text(card, WBUY_OLD_PRICE_SELECTORS)),
            "estoque": None,
            "marca": "",
            "categoria": "",
            "cor": "",
            "imagem_url": _normalizar_lista_imagens(imagens),
            "link": link,
            "fonte_url": fonte_url,
            "fornecedor_tipo": "html_wbuy",
            "dominio": _dominio(fonte_url),
        }
        linhas.append(linha)

    return linhas


def executar_conector_wbuy(
    *,
    url: str,
    html: str,
) -> dict[str, Any]:
    try:
        linhas = _wbuy_parse_html(html=html, fonte_url=url)
        return _montar_resultado(
            ok=bool(linhas),
            fornecedor_tipo="html_wbuy",
            dominio=_dominio(url),
            linhas=linhas,
            erro="" if linhas else "nenhum_produto_encontrado_no_html",
            metadata={"fonte": "html"},
        )
    except Exception as e:
        return _montar_resultado(
            ok=False,
            fornecedor_tipo="html_wbuy",
            dominio=_dominio(url),
            erro=str(e),
        )


# ==========================================================
# EXECUTOR UNIFICADO
# ==========================================================
def executar_conector_fornecedor(
    *,
    url: str,
    html: str = "",
    api_response_text: str | None = None,
    api_response_json: dict[str, Any] | None = None,
    api_url: str | None = None,
    api_headers: dict[str, Any] | None = None,
    user_id: str = "",
    api_key: str = "",
    bearer_token: str = "",
    stoqui_x_client_info: str = "supabase-js-web/2.103.0",
) -> dict[str, Any]:
    config = _resolver_tipo_fornecedor(url=url, html=html)
    fornecedor_tipo = _safe_str(config.get("tipo"))
    dominio = _safe_str(config.get("dominio") or _dominio(url))

    log_debug(
        f"[CONECTOR_EXECUTOR] START | dominio={dominio} | tipo={fornecedor_tipo}",
        "INFO",
    )

    if fornecedor_tipo == "api_datatables_auth":
        return executar_conector_obaobamix(
            api_response_text=api_response_text,
            api_response_json=api_response_json,
            fonte_url=api_url or url,
        )

    if fornecedor_tipo == "api_supabase_auth":
        headers = api_headers or {}
        api_key_final = _safe_str(headers.get("apikey") or api_key)
        bearer_final = _safe_str(
            headers.get("authorization", "").replace("Bearer ", "").strip()
            or bearer_token
        )

        base_url = _safe_str(api_url) or (
            ((config.get("links") or {}).get("api_produtos") or [""])[0]
        )
        categorias_url = (
            ((config.get("links") or {}).get("api_categorias") or [""])[0]
        )

        return executar_conector_stoqui(
            user_id=user_id,
            api_key=api_key_final,
            bearer_token=bearer_final,
            base_url=base_url,
            categorias_url=categorias_url,
            x_client_info=_safe_str(headers.get("x-client-info") or stoqui_x_client_info),
        )

    if fornecedor_tipo in {"html_wbuy", "generico_html"}:
        return executar_conector_wbuy(url=url, html=html)

    return _montar_resultado(
        ok=False,
        fornecedor_tipo=fornecedor_tipo or "desconhecido",
        dominio=dominio,
        erro="fornecedor_nao_suportado",
    )
