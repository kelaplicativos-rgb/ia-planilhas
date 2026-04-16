
from __future__ import annotations

from typing import Any, Callable, Optional

import pandas as pd


# ============================================================
# IMPORTS OPCIONAIS DOS CONECTORES
# ============================================================

try:
    from bling_app_zero.core.fornecedores.atacadum_api import buscar_produtos_atacadum
except Exception:
    buscar_produtos_atacadum = None

try:
    from bling_app_zero.core.fornecedores.megacenter_api import buscar_produtos_mega_center
except Exception:
    buscar_produtos_mega_center = None

try:
    from bling_app_zero.core.fornecedores.obaobamix_api import buscar_produtos_oba_oba_mix
except Exception:
    buscar_produtos_oba_oba_mix = None

try:
    from bling_app_zero.core.site_crawler import executar_crawler_site
except Exception:
    executar_crawler_site = None

try:
    from bling_app_zero.utils.excel_logs import log_debug
except Exception:
    def log_debug(_msg: str, _nivel: str = "INFO") -> None:
        return None


ROUTER_VERSION = "V2_FORNECEDORES_DIRETOS"


# ============================================================
# HELPERS
# ============================================================

def _safe_str(valor: Any) -> str:
    if valor is None:
        return ""
    texto = str(valor).strip()
    if texto.lower() in {"none", "nan", "nat"}:
        return ""
    return texto


def _normalizar_texto(valor: Any) -> str:
    texto = _safe_str(valor).lower()
    trocas = {
        "ã": "a",
        "á": "a",
        "à": "a",
        "â": "a",
        "é": "e",
        "ê": "e",
        "í": "i",
        "ó": "o",
        "ô": "o",
        "õ": "o",
        "ú": "u",
        "ç": "c",
        "_": " ",
        "-": " ",
        "/": " ",
        ".": " ",
        ",": " ",
        "(": " ",
        ")": " ",
        ":": " ",
        ";": " ",
    }
    for origem, destino in trocas.items():
        texto = texto.replace(origem, destino)
    return " ".join(texto.split())


def _garantir_df(df: Any) -> pd.DataFrame:
    if isinstance(df, pd.DataFrame):
        return df.copy().fillna("")
    return pd.DataFrame()


def _to_float_brasil(valor: Any) -> float:
    texto = _safe_str(valor)
    if not texto:
        return 0.0

    texto = texto.replace("R$", "").replace(" ", "")
    if "," in texto and "." in texto:
        texto = texto.replace(".", "").replace(",", ".")
    else:
        texto = texto.replace(",", ".")

    try:
        return float(texto)
    except Exception:
        return 0.0


def _formatar_numero_bling(valor: Any) -> str:
    return f"{_to_float_brasil(valor):.2f}".replace(".", ",")


def _normalizar_saida_padrao(df: pd.DataFrame) -> pd.DataFrame:
    base = _garantir_df(df)
    if base.empty:
        return base

    base.columns = [_safe_str(col) for col in base.columns]

    aliases = {
        "codigo_fornecedor": [
            "codigo_fornecedor",
            "codigo",
            "sku",
            "referencia",
            "ref",
            "id_produto",
            "codigo produto",
            "product_id",
        ],
        "descricao_fornecedor": [
            "descricao_fornecedor",
            "descricao",
            "produto",
            "nome",
            "titulo",
            "nome produto",
            "product_name",
        ],
        "preco_base": [
            "preco_base",
            "preco",
            "valor",
            "price",
            "preco site",
            "valor_unitario",
            "valor unitario",
        ],
        "quantidade_real": [
            "quantidade_real",
            "quantidade",
            "estoque",
            "saldo",
            "inventory",
            "stock",
        ],
        "gtin": [
            "gtin",
            "ean",
            "gtin ean",
            "codigo de barras",
            "barcode",
        ],
        "categoria": [
            "categoria",
            "departamento",
            "grupo",
            "family",
            "collection",
            "breadcrumb",
        ],
        "url_imagens": [
            "url_imagens",
            "imagem",
            "imagens",
            "url imagem",
            "url imagens",
            "image",
            "images",
        ],
        "link_produto": [
            "link_produto",
            "url",
            "link",
            "product_url",
            "product link",
        ],
    }

    mapa = {_normalizar_texto(col): col for col in base.columns}

    saida = pd.DataFrame(index=base.index)
    for destino, candidatos in aliases.items():
        origem_encontrada = ""
        for candidato in candidatos:
            chave = _normalizar_texto(candidato)
            if chave in mapa:
                origem_encontrada = mapa[chave]
                break

        if not origem_encontrada:
            for col in base.columns:
                ncol = _normalizar_texto(col)
                if any(_normalizar_texto(c) in ncol for c in candidatos):
                    origem_encontrada = col
                    break

        saida[destino] = base[origem_encontrada] if origem_encontrada else ""

    for col in base.columns:
        if col not in saida.columns:
            saida[col] = base[col]

    if "preco_base" in saida.columns:
        saida["preco_base"] = saida["preco_base"].apply(_formatar_numero_bling)

    if "quantidade_real" in saida.columns:
        saida["quantidade_real"] = (
            pd.to_numeric(saida["quantidade_real"], errors="coerce")
            .fillna(0)
            .astype(int)
        )

    return saida.fillna("")


def _executar_funcao_fornecedor(
    func: Optional[Callable],
    fornecedor: str,
    categoria: str = "",
    operacao: str = "",
    extra_config: Optional[dict] = None,
) -> pd.DataFrame:
    if not callable(func):
        return pd.DataFrame()

    config = {
        "fornecedor": fornecedor,
        "categoria": categoria,
        "operacao": operacao,
    }
    if isinstance(extra_config, dict):
        config.update(extra_config)

    tentativas = [
        lambda: func(config=config),
        lambda: func(
            fornecedor=fornecedor,
            categoria=categoria,
            operacao=operacao,
            config=config,
        ),
        lambda: func(
            fornecedor=fornecedor,
            categoria=categoria,
            operacao=operacao,
        ),
        lambda: func(config),
        lambda: func(fornecedor),
    ]

    for tentativa in tentativas:
        try:
            resultado = tentativa()
            df = _garantir_df(resultado)
            if not df.empty:
                log_debug(
                    f"[FETCH_ROUTER] fornecedor={fornecedor} retornou {len(df)} linha(s) via conector oficial",
                    "INFO",
                )
                return _normalizar_saida_padrao(df)
        except TypeError:
            continue
        except Exception as e:
            log_debug(
                f"[FETCH_ROUTER] falha no conector '{fornecedor}': {e}",
                "WARNING",
            )
            continue

    return pd.DataFrame()


def _executar_fallback_crawler(
    fornecedor: str,
    categoria: str = "",
) -> pd.DataFrame:
    if not callable(executar_crawler_site):
        return pd.DataFrame()

    urls_base = {
        "atacadum": "https://www.atacadum.com.br/",
        "mega_center": "https://megacentereletronicos.com.br/",
        "oba_oba_mix": "https://obaobamix.com.br/",
    }

    url = urls_base.get(fornecedor, "")
    if not url:
        return pd.DataFrame()

    categoria_txt = _safe_str(categoria)
    if categoria_txt:
        slug = (
            categoria_txt.strip()
            .lower()
            .replace(" ", "-")
            .replace("_", "-")
        )
        if fornecedor == "atacadum":
            url = f"https://www.atacadum.com.br/{slug}/"
        elif fornecedor == "mega_center":
            url = f"https://megacentereletronicos.com.br/categoria/{slug}"
        elif fornecedor == "oba_oba_mix":
            url = f"https://obaobamix.com.br/{slug}/"

    tentativas = [
        lambda: executar_crawler_site(
            url=url,
            max_paginas=8,
            max_threads=6,
            padrao_disponivel=10,
        ),
        lambda: executar_crawler_site(url, 8, 6, 10),
    ]

    for tentativa in tentativas:
        try:
            resultado = tentativa()
            df = _garantir_df(resultado)
            if not df.empty:
                log_debug(
                    f"[FETCH_ROUTER] fornecedor={fornecedor} retornou {len(df)} linha(s) via fallback crawler",
                    "INFO",
                )
                return _normalizar_saida_padrao(df)
        except Exception as e:
            log_debug(
                f"[FETCH_ROUTER] falha no fallback crawler '{fornecedor}': {e}",
                "WARNING",
            )
            continue

    return pd.DataFrame()


# ============================================================
# API PRINCIPAL
# ============================================================

def buscar_produtos_fornecedor(
    fornecedor: str,
    categoria: str = "",
    operacao: str = "",
    extra_config: Optional[dict] = None,
) -> pd.DataFrame:
    fornecedor_norm = _normalizar_texto(fornecedor)
    log_debug(
        f"[FETCH_ROUTER] início fornecedor={fornecedor_norm} categoria={categoria} operacao={operacao} version={ROUTER_VERSION}",
        "INFO",
    )

    if fornecedor_norm in {"atacadum"}:
        df = _executar_funcao_fornecedor(
            func=buscar_produtos_atacadum,
            fornecedor="atacadum",
            categoria=categoria,
            operacao=operacao,
            extra_config=extra_config,
        )
        if not df.empty:
            return df
        return _executar_fallback_crawler("atacadum", categoria)

    if fornecedor_norm in {
        "mega center",
        "mega center eletronicos",
        "mega center eletrônicos",
        "megacenter",
        "mega_center",
    }:
        df = _executar_funcao_fornecedor(
            func=buscar_produtos_mega_center,
            fornecedor="mega_center",
            categoria=categoria,
            operacao=operacao,
            extra_config=extra_config,
        )
        if not df.empty:
            return df
        return _executar_fallback_crawler("mega_center", categoria)

    if fornecedor_norm in {
        "oba oba mix",
        "obaobamix",
        "oba_oba_mix",
    }:
        df = _executar_funcao_fornecedor(
            func=buscar_produtos_oba_oba_mix,
            fornecedor="oba_oba_mix",
            categoria=categoria,
            operacao=operacao,
            extra_config=extra_config,
        )
        if not df.empty:
            return df
        return _executar_fallback_crawler("oba_oba_mix", categoria)

    log_debug(
        f"[FETCH_ROUTER] fornecedor não reconhecido: {fornecedor}",
        "WARNING",
    )
    return pd.DataFrame()


def listar_fornecedores_disponiveis() -> list[str]:
    fornecedores = []

    if callable(buscar_produtos_atacadum) or callable(executar_crawler_site):
        fornecedores.append("Atacadum")

    if callable(buscar_produtos_mega_center) or callable(executar_crawler_site):
        fornecedores.append("Mega Center Eletrônicos")

    if callable(buscar_produtos_oba_oba_mix) or callable(executar_crawler_site):
        fornecedores.append("Oba Oba Mix")

    return fornecedores
