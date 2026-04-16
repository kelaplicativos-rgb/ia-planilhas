
from __future__ import annotations

from typing import Any, Callable, Optional

import pandas as pd


# ============================================================
# IMPORTS OPCIONAIS DOS FORNECEDORES
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


def _formatar_numero_bling(valor: Any) -> str:
    texto = _safe_str(valor).replace("R$", "").replace(" ", "")
    if not texto:
        return ""
    if "," in texto and "." in texto:
        texto = texto.replace(".", "").replace(",", ".")
    else:
        texto = texto.replace(",", ".")
    try:
        return f"{float(texto):.2f}".replace(".", ",")
    except Exception:
        return _safe_str(valor)


def _normalizar_saida_padrao(df: pd.DataFrame) -> pd.DataFrame:
    base = _garantir_df(df)
    if base.empty:
        return base

    colunas_obrigatorias = [
        "codigo_fornecedor",
        "descricao_fornecedor",
        "preco_base",
        "quantidade_real",
        "gtin",
        "categoria",
        "url_imagens",
        "link_produto",
    ]

    mapa = {_normalizar_texto(col): col for col in base.columns}

    aliases = {
        "codigo_fornecedor": [
            "codigo_fornecedor",
            "codigo",
            "sku",
            "referencia",
            "ref",
            "id_produto",
            "codigo produto",
        ],
        "descricao_fornecedor": [
            "descricao_fornecedor",
            "descricao",
            "produto",
            "nome",
            "titulo",
            "nome produto",
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

    saida = pd.DataFrame(index=base.index)

    for coluna_destino in colunas_obrigatorias:
        coluna_origem = ""
        for alias in aliases.get(coluna_destino, []):
            chave = _normalizar_texto(alias)
            if chave in mapa:
                coluna_origem = mapa[chave]
                break

        if coluna_origem:
            saida[coluna_destino] = base[coluna_origem]
        else:
            saida[coluna_destino] = ""

    for col in base.columns:
        if col not in saida.columns:
            saida[col] = base[col]

    if "preco_base" in saida.columns:
        saida["preco_base"] = saida["preco_base"].apply(_formatar_numero_bling)

    if "quantidade_real" in saida.columns:
        saida["quantidade_real"] = pd.to_numeric(
            saida["quantidade_real"], errors="coerce"
        ).fillna(0).astype(int)

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
                return _normalizar_saida_padrao(df)
        except TypeError:
            continue
        except Exception:
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

    if fornecedor_norm in {"atacadum"}:
        return _executar_funcao_fornecedor(
            func=buscar_produtos_atacadum,
            fornecedor="atacadum",
            categoria=categoria,
            operacao=operacao,
            extra_config=extra_config,
        )

    if fornecedor_norm in {
        "mega center",
        "mega center eletronicos",
        "mega center eletrônicos",
        "megacenter",
        "mega_center",
    }:
        return _executar_funcao_fornecedor(
            func=buscar_produtos_mega_center,
            fornecedor="mega_center",
            categoria=categoria,
            operacao=operacao,
            extra_config=extra_config,
        )

    if fornecedor_norm in {
        "oba oba mix",
        "obaobamix",
        "oba_oba_mix",
    }:
        return _executar_funcao_fornecedor(
            func=buscar_produtos_oba_oba_mix,
            fornecedor="oba_oba_mix",
            categoria=categoria,
            operacao=operacao,
            extra_config=extra_config,
        )

    return pd.DataFrame()


def listar_fornecedores_disponiveis() -> list[str]:
    fornecedores = []

    if callable(buscar_produtos_atacadum):
        fornecedores.append("Atacadum")

    if callable(buscar_produtos_mega_center):
        fornecedores.append("Mega Center Eletrônicos")

    if callable(buscar_produtos_oba_oba_mix):
        fornecedores.append("Oba Oba Mix")

    return fornecedores
