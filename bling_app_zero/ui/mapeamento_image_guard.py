from __future__ import annotations

"""Blindagem para preservar URLs de imagens durante o mapeamento."""

import re

import pandas as pd


IMG_RE = re.compile(r"(url\s*)?(imagem|imagens|image|images|foto|fotos|gallery|galeria|thumbnail)", re.I)
URL_RE = re.compile(r"https?://[^\s\"'<>|,;]+|www\.[^\s\"'<>|,;]+", re.I)


def _norm(nome: object) -> str:
    texto = str(nome or "").strip().lower()
    texto = texto.translate(str.maketrans("áàãâéêíóôõúç", "aaaaeeiooouc"))
    return re.sub(r"[^a-z0-9]+", " ", texto).strip()


def coluna_parece_imagem(nome: object) -> bool:
    n = _norm(nome)
    if "video" in n or "youtube" in n:
        return False
    return bool(IMG_RE.search(n)) or n in {
        "url imagens externas",
        "url imagens",
        "image urls",
        "image url",
        "main image",
        "thumbnail",
    }


def _normalizar_urls(valor: object) -> str:
    texto = str(valor or "").strip().replace("\\/", "/")
    if not texto:
        return ""
    candidatos = URL_RE.findall(texto)
    if not candidatos:
        candidatos = [p.strip().strip('"\'[]{}()') for p in re.split(r"[|,\n\r\t]+", texto)]
    urls: list[str] = []
    vistos: set[str] = set()
    for candidato in candidatos:
        url = str(candidato or "").strip().strip('"\'[]{}()')
        if url.startswith("www."):
            url = "https://" + url
        low = url.lower()
        if not url.startswith(("http://", "https://")):
            continue
        if any(bad in low for bad in ("logo", "sprite", "placeholder", "favicon", "pixel", "analytics", "base64", "youtube")):
            continue
        if url in vistos:
            continue
        vistos.add(url)
        urls.append(url)
        if len(urls) >= 20:
            break
    return "|".join(urls)


def primeira_coluna_imagem(df: pd.DataFrame) -> str:
    if not isinstance(df, pd.DataFrame) or df.empty:
        return ""
    prioridades = ["URL Imagens Externas", "Imagens", "image_urls", "image_url", "main_image", "thumbnail"]
    mapa = {_norm(c): str(c) for c in df.columns}
    for prioridade in prioridades:
        col = mapa.get(_norm(prioridade))
        if col and df[col].astype(str).map(_normalizar_urls).str.strip().ne("").any():
            return col
    for col in [str(c) for c in df.columns]:
        if coluna_parece_imagem(col) and df[col].astype(str).map(_normalizar_urls).str.strip().ne("").any():
            return col
    return ""


def primeira_coluna_imagem_modelo(df_modelo: pd.DataFrame) -> str:
    if not isinstance(df_modelo, pd.DataFrame) or len(df_modelo.columns) == 0:
        return ""
    mapa = {_norm(c): str(c) for c in df_modelo.columns}
    for prioridade in ["URL Imagens Externas", "URL imagens externas", "Imagens", "Imagem"]:
        col = mapa.get(_norm(prioridade))
        if col:
            return col
    for col in [str(c) for c in df_modelo.columns]:
        if coluna_parece_imagem(col):
            return col
    return ""


def garantir_mapping_imagens(df_base: pd.DataFrame, df_modelo: pd.DataFrame, mapping: dict[str, str]) -> dict[str, str]:
    novo = dict(mapping or {})
    origem = primeira_coluna_imagem(df_base)
    destino = primeira_coluna_imagem_modelo(df_modelo)
    if origem and destino:
        novo[destino] = origem
    return novo


def aplicar_imagens_no_final(df_base: pd.DataFrame, df_modelo: pd.DataFrame, df_final: pd.DataFrame) -> pd.DataFrame:
    if not isinstance(df_final, pd.DataFrame) or df_final.empty:
        return df_final
    origem = primeira_coluna_imagem(df_base)
    destino = primeira_coluna_imagem_modelo(df_modelo)
    if not origem or not destino or origem not in df_base.columns:
        return df_final
    saida = df_final.copy().fillna("")
    if destino not in saida.columns:
        saida[destino] = ""
    valores = [_normalizar_urls(v) for v in df_base[origem].astype(str).tolist()]
    saida.loc[:, destino] = valores[: len(saida)]
    return saida.fillna("")
