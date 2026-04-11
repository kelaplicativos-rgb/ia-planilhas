from __future__ import annotations

import re
from urllib.parse import urlparse, urlunparse

import pandas as pd


VALORES_GENERICOS = {
    "",
    "nan",
    "none",
    "null",
    "n/a",
    "na",
    "não informado",
    "nao informado",
    "não encontrado",
    "nao encontrado",
    "sem informação",
    "sem informacao",
    "sem dados",
    "indefinido",
    "desconhecido",
    "genérica",
    "generica",
    "genérico",
    "generico",
    "-",
    "--",
    "---",
    ".",
}


def _texto(valor) -> str:
    try:
        return str(valor or "").strip()
    except Exception:
        return ""


def _texto_norm(valor) -> str:
    return _texto(valor).strip().lower()


def _eh_generico(valor) -> bool:
    texto = _texto_norm(valor)
    return texto in VALORES_GENERICOS


def _eh_url_real(valor) -> bool:
    texto = _texto(valor)
    if not texto:
        return False

    try:
        parsed = urlparse(texto)
        return parsed.scheme in {"http", "https"} and bool(parsed.netloc)
    except Exception:
        return False


def _normalizar_url_imagem_real(url: str) -> str:
    """
    Mantém somente URL real.
    Remove parâmetros comuns de thumbnail quando existirem,
    sem inventar imagem nova.
    """
    texto = _texto(url)
    if not _eh_url_real(texto):
        return ""

    try:
        parsed = urlparse(texto)
        path = parsed.path or ""

        # remove padrões comuns de thumbs no caminho, preservando a imagem real
        path = re.sub(r"[-_](\d{2,4})x(\d{2,4})(?=\.)", "", path, flags=re.IGNORECASE)
        path = re.sub(r"/thumbs?/", "/", path, flags=re.IGNORECASE)
        path = re.sub(r"/thumbnail/", "/", path, flags=re.IGNORECASE)

        # remove query string comum de resize/crop/cache
        query = parsed.query or ""
        if query:
            parametros_bloqueados = {
                "w", "width", "h", "height", "fit", "crop", "resize", "quality",
                "q", "auto", "dpr", "fm", "format"
            }
            pares = []
            for parte in query.split("&"):
                if "=" in parte:
                    k, v = parte.split("=", 1)
                else:
                    k, v = parte, ""
                if k.strip().lower() not in parametros_bloqueados:
                    pares.append((k, v))

            query = "&".join([f"{k}={v}" if v != "" else k for k, v in pares])

        limpo = urlunparse(
            (
                parsed.scheme,
                parsed.netloc,
                path,
                parsed.params,
                query,
                "",
            )
        ).strip()

        return limpo if _eh_url_real(limpo) else texto
    except Exception:
        return texto


def _normalizar_lista_imagens(valor) -> str:
    """
    Mantém apenas URLs reais.
    Preserva o separador padrão '|'.
    """
    texto = _texto(valor)
    if not texto:
        return ""

    partes = re.split(r"[|,\n\r;]+", texto)
    urls_validas = []

    for parte in partes:
        url = _normalizar_url_imagem_real(parte)
        if url and url not in urls_validas:
            urls_validas.append(url)

    return "|".join(urls_validas)


def _normalizar_codigo_real(valor) -> str:
    texto = _texto(valor)
    if not texto or _eh_generico(texto):
        return ""

    # bloqueia placeholders óbvios
    if _texto_norm(texto).startswith(("sku-", "codigo-", "cod-", "auto-", "tmp-")):
        return ""

    return texto


def _normalizar_gtin_real(valor) -> str:
    texto = re.sub(r"\D+", "", _texto(valor))
    if not texto:
        return ""

    if texto in {
        "0",
        "00",
        "000",
        "0000",
        "00000",
        "000000",
        "0000000",
        "00000000",
        "0000000000000",
        "1111111111111",
        "9999999999999",
    }:
        return ""

    if len(texto) not in {8, 12, 13, 14}:
        return ""

    return texto


def _normalizar_texto_real(valor) -> str:
    texto = _texto(valor)
    if _eh_generico(texto):
        return ""
    return texto


def sanitizar_dados_reais(df: pd.DataFrame) -> pd.DataFrame:
    """
    Regra central:
    - não inventa nada
    - só mantém valores que pareçam reais
    - o que não for real fica vazio
    """
    if not isinstance(df, pd.DataFrame):
        return df

    out = df.copy()
    colunas = [str(c).strip() for c in out.columns]
    out.columns = colunas

    for col in out.columns:
        nome = col.strip().lower()

        if any(x in nome for x in ["marca"]):
            out[col] = out[col].apply(_normalizar_texto_real)

        elif any(x in nome for x in ["categoria"]):
            out[col] = out[col].apply(_normalizar_texto_real)

        elif nome in {"código", "codigo", "sku", "cod", "ref", "referência", "referencia"}:
            out[col] = out[col].apply(_normalizar_codigo_real)

        elif any(x in nome for x in ["gtin", "ean", "código de barras", "codigo de barras"]):
            out[col] = out[col].apply(_normalizar_gtin_real)

        elif any(x in nome for x in ["imagem", "imagens", "foto", "fotos", "url imagem", "url imagens"]):
            out[col] = out[col].apply(_normalizar_lista_imagens)

        else:
            out[col] = out[col].replace({None: ""}).fillna("")

    return out
