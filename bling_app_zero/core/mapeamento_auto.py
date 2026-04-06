from __future__ import annotations

import re
import unicodedata
from typing import Any

import pandas as pd


# ==========================================================
# NORMALIZAÇÃO
# ==========================================================
def _normalizar_texto(valor: Any) -> str:
    texto = str(valor or "").strip().lower()
    texto = unicodedata.normalize("NFKD", texto)
    texto = "".join(ch for ch in texto if not unicodedata.combining(ch))
    texto = re.sub(r"[^a-z0-9]+", " ", texto).strip()
    return texto


def _tokens(valor: Any) -> set[str]:
    texto = _normalizar_texto(valor)
    if not texto:
        return set()
    return {t for t in texto.split() if t}


def _serie_texto(serie: pd.Series, limite: int = 40) -> pd.Series:
    try:
        s = serie.copy()
        s = s.dropna()
        s = s.astype(str).map(str.strip)
        s = s[s != ""]
        return s.head(limite)
    except Exception:
        return pd.Series(dtype="object")


# ==========================================================
# MAPA INTELIGENTE
# ==========================================================
ALIASES_INTELIGENTES = {
    "descricao": [
        "descricao",
        "descrição",
        "nome",
        "nome produto",
        "produto",
        "titulo",
        "título",
        "descricao produto",
        "descrição produto",
        "nome do produto",
        "item",
    ],
    "descricao curta": [
        "descricao curta",
        "descrição curta",
        "resumo",
        "detalhe",
        "detalhes",
        "short description",
    ],
    "preco": [
        "preco",
        "preço",
        "valor",
        "price",
        "vlr",
        "preco venda",
        "preço venda",
        "valor venda",
    ],
    "preco de venda": [
        "preco",
        "preço",
        "valor",
        "price",
        "preco venda",
        "preço venda",
        "valor venda",
    ],
    "preco de custo": [
        "custo",
        "preco custo",
        "preço custo",
        "preco de custo",
        "preço de custo",
        "valor custo",
        "compra",
        "preco compra",
        "preço compra",
    ],
    "preco de compra": [
        "compra",
        "preco compra",
        "preço compra",
        "preco de compra",
        "preço de compra",
        "custo",
        "preco custo",
        "preço custo",
    ],
    "estoque": [
        "estoque",
        "quantidade",
        "qtd",
        "saldo",
        "stock",
        "inventory",
        "disponivel",
        "disponível",
    ],
    "saldo": [
        "estoque",
        "quantidade",
        "qtd",
        "saldo",
        "stock",
        "inventory",
        "disponivel",
        "disponível",
    ],
    "gtin": [
        "gtin",
        "ean",
        "codigo de barras",
        "código de barras",
        "barcode",
        "gtin ean",
    ],
    "ean": [
        "ean",
        "gtin",
        "codigo de barras",
        "código de barras",
        "barcode",
        "gtin ean",
    ],
    "marca": [
        "marca",
        "brand",
        "fabricante",
    ],
    "categoria": [
        "categoria",
        "departamento",
        "grupo",
        "grupo produto",
        "grupo de produtos",
        "setor",
    ],
    "ncm": [
        "ncm",
        "classificacao fiscal",
        "classificação fiscal",
    ],
    "sku": [
        "sku",
        "referencia",
        "referência",
        "ref",
        "codigo",
        "código",
        "codigo produto",
        "código produto",
        "cod",
    ],
    "codigo": [
        "codigo",
        "código",
        "sku",
        "referencia",
        "referência",
        "ref",
        "cod",
        "id",
    ],
    "imagem": [
        "imagem",
        "imagens",
        "foto",
        "fotos",
        "image",
        "images",
        "url imagem",
        "url imagens",
    ],
    "url imagens externas": [
        "imagem",
        "imagens",
        "foto",
        "fotos",
        "image",
        "images",
        "url imagem",
        "url imagens",
        "url imagens externas",
    ],
    "link externo": [
        "link",
        "url",
        "site",
        "url produto",
        "produto url",
        "link externo",
    ],
    "peso liquido": [
        "peso liquido",
        "peso líquido",
        "peso",
        "peso liq",
    ],
    "peso bruto": [
        "peso bruto",
        "peso br",
        "peso",
    ],
    "largura": [
        "largura",
        "width",
    ],
    "altura": [
        "altura",
        "height",
    ],
    "profundidade": [
        "profundidade",
        "comprimento",
        "length",
    ],
    "deposito": [
        "deposito",
        "depósito",
        "armazem",
        "armazém",
        "warehouse",
    ],
}


# ==========================================================
# HEURÍSTICAS DE NOME
# ==========================================================
def _score_nome_coluna(destino: str, origem: str) -> int:
    destino_norm = _normalizar_texto(destino)
    origem_norm = _normalizar_texto(origem)

    if not destino_norm or not origem_norm:
        return 0

    score = 0

    if destino_norm == origem_norm:
        score += 200

    if destino_norm in origem_norm:
        score += 80

    if origem_norm in destino_norm and len(origem_norm) > 2:
        score += 50

    tokens_destino = _tokens(destino_norm)
    tokens_origem = _tokens(origem_norm)
    intersec = len(tokens_destino.intersection(tokens_origem))
    if intersec > 0:
        score += intersec * 20

    aliases = []
    for chave, lista in ALIASES_INTELIGENTES.items():
        if chave in destino_norm:
            aliases.extend(lista)

    for alias in aliases:
        alias_norm = _normalizar_texto(alias)
        if not alias_norm:
            continue
        if alias_norm == origem_norm:
            score += 140
        elif alias_norm in origem_norm:
            score += 70
        else:
            alias_tokens = _tokens(alias_norm)
            if alias_tokens:
                score += len(alias_tokens.intersection(tokens_origem)) * 18

    return score


# ==========================================================
# HEURÍSTICAS DE VALORES
# ==========================================================
def _score_numerico(serie: pd.Series) -> int:
    try:
        s = (
            serie.astype(str)
            .str.replace(".", "", regex=False)
            .str.replace(",", ".", regex=False)
        )
        nums = pd.to_numeric(s, errors="coerce")
        validos = nums.notna().sum()
        if validos == 0:
            return 0
        return int((validos / max(len(serie), 1)) * 100)
    except Exception:
        return 0


def _score_gtin(serie: pd.Series) -> int:
    try:
        s = serie.astype(str).str.replace(r"\D", "", regex=True)
        validos = s.map(lambda x: len(x) in (8, 12, 13, 14)).sum()
        if validos == 0:
            return 0
        return int((validos / max(len(s), 1)) * 100)
    except Exception:
        return 0


def _score_ncm(serie: pd.Series) -> int:
    try:
        s = serie.astype(str).str.replace(r"\D", "", regex=True)
        validos = s.map(lambda x: len(x) == 8).sum()
        if validos == 0:
            return 0
        return int((validos / max(len(s), 1)) * 100)
    except Exception:
        return 0


def _score_url(serie: pd.Series) -> int:
    try:
        s = _serie_texto(serie, limite=50)
        if s.empty:
            return 0
        validos = s.str.contains(r"http|www\.", case=False, regex=True).sum()
        return int((validos / max(len(s), 1)) * 100)
    except Exception:
        return 0


def _score_texto_longo(serie: pd.Series) -> int:
    try:
        s = _serie_texto(serie, limite=40)
        if s.empty:
            return 0
        media = s.map(len).mean()
        if media >= 80:
            return 100
        if media >= 40:
            return 70
        if media >= 20:
            return 35
        return 0
    except Exception:
        return 0


def _score_texto_curto(serie: pd.Series) -> int:
    try:
        s = _serie_texto(serie, limite=40)
        if s.empty:
            return 0
        media = s.map(len).mean()
        if 3 <= media <= 25:
            return 80
        if media <= 40:
            return 40
        return 0
    except Exception:
        return 0


def _score_valores(destino: str, origem: str, serie: pd.Series) -> int:
    destino_norm = _normalizar_texto(destino)
    origem_norm = _normalizar_texto(origem)
    score = 0

    if any(x in destino_norm for x in ["preco", "preço", "valor", "custo", "compra"]):
        score += int(_score_numerico(serie) * 0.7)

    if any(x in destino_norm for x in ["estoque", "saldo", "quantidade", "qtd"]):
        score += int(_score_numerico(serie) * 0.8)

    if any(x in destino_norm for x in ["gtin", "ean"]):
        score += int(_score_gtin(serie) * 1.4)

    if "ncm" in destino_norm:
        score += int(_score_ncm(serie) * 1.4)

    if any(x in destino_norm for x in ["imagem", "foto", "url imagens", "url imagem"]):
        score += int(_score_url(serie) * 1.2)

    if "link externo" in destino_norm or destino_norm == "link":
        score += int(_score_url(serie) * 1.2)

    if "descricao curta" in destino_norm:
        score += int(_score_texto_longo(serie) * 0.8)

    if destino_norm == "descricao" or "descricao" in destino_norm or "descrição" in destino_norm:
        score += int(_score_texto_longo(serie) * 0.5)
        score += int(_score_texto_curto(serie) * 0.5)

    if any(x in destino_norm for x in ["sku", "codigo", "código", "referencia", "referência"]):
        score += int(_score_texto_curto(serie) * 0.6)

    if "marca" in destino_norm:
        score += int(_score_texto_curto(serie) * 0.4)

    if any(x in origem_norm for x in ["ean", "gtin", "barcode"]):
        score += 25

    if any(x in origem_norm for x in ["ncm"]):
        score += 25

    if any(x in origem_norm for x in ["preco", "preço", "valor", "custo"]):
        score += 15

    if any(x in origem_norm for x in ["estoque", "saldo", "qtd", "quantidade"]):
        score += 15

    return score


# ==========================================================
# CONFIANÇA / RESOLUÇÃO
# ==========================================================
def _limite_minimo(destino: str) -> int:
    destino_norm = _normalizar_texto(destino)

    if any(x in destino_norm for x in ["gtin", "ean", "ncm"]):
        return 60

    if any(x in destino_norm for x in ["preco", "preço", "estoque", "saldo"]):
        return 50

    if any(x in destino_norm for x in ["imagem", "foto", "link"]):
        return 45

    return 40


def _score_total(destino: str, origem: str, serie: pd.Series) -> int:
    return _score_nome_coluna(destino, origem) + _score_valores(destino, origem, serie)


# ==========================================================
# IA PRINCIPAL
# ==========================================================
def sugestao_automatica(
    df: pd.DataFrame,
    colunas_destino: list[str] | None = None,
) -> dict:
    """
    Gera sugestões automáticas de mapeamento entre colunas da origem e destino.

    Compatível com:
    - chamada antiga: sugestao_automatica(df)
    - chamada nova: sugestao_automatica(df, colunas_destino)

    Retorna:
        dict {coluna_destino: coluna_origem}
    """

    if df is None or df.empty:
        return {}

    colunas_origem = list(df.columns)

    if not colunas_destino:
        return {col: col for col in colunas_origem}

    sugestoes: dict[str, str] = {}
    usadas: set[str] = set()

    ranking_global: list[tuple[str, str, int]] = []

    for destino in colunas_destino:
        for origem in colunas_origem:
            try:
                serie = df[origem]
            except Exception:
                continue

            score = _score_total(destino, origem, serie)
            ranking_global.append((destino, origem, score))

    ranking_global.sort(key=lambda x: x[2], reverse=True)

    destinos_preenchidos: set[str] = set()

    for destino, origem, score in ranking_global:
        if destino in destinos_preenchidos:
            continue
        if origem in usadas:
            continue
        if score < _limite_minimo(destino):
            continue

        sugestoes[destino] = origem
        destinos_preenchidos.add(destino)
        usadas.add(origem)

    return sugestoes
