from __future__ import annotations

import re
from typing import Any
from urllib.parse import urlparse

import pandas as pd


COLUNAS_SAIDA_AI = [
    "nome",
    "preco",
    "url_produto",
    "imagens",
    "descricao",
    "marca",
    "categoria",
    "sku",
    "gtin",
    "estoque",
    "_ai_score",
    "_ai_status",
    "_ai_alertas",
]


PALAVRAS_LIXO = {
    "",
    "nan",
    "none",
    "null",
    "undefined",
    "loading",
    "loading...",
    "carregando",
    "carregando...",
    "entrando",
    "entrando...",
}


MARCAS_COMUNS = [
    "samsung",
    "apple",
    "xiaomi",
    "motorola",
    "lg",
    "sony",
    "jbl",
    "philips",
    "multilaser",
    "intelbras",
    "positivo",
    "lenovo",
    "hp",
    "dell",
    "asus",
    "acer",
    "epson",
    "canon",
    "elgin",
    "mondial",
    "britania",
    "philco",
]


def _txt(valor: Any) -> str:
    texto = str(valor or "").strip()
    texto = texto.replace("\u00a0", " ")
    texto = re.sub(r"\s+", " ", texto).strip()
    if texto.lower() in PALAVRAS_LIXO:
        return ""
    return texto


def _normalizar_url(valor: Any) -> str:
    url = _txt(valor)
    if not url:
        return ""
    if url.startswith("//"):
        url = "https:" + url
    if not url.startswith(("http://", "https://")):
        return ""
    return url


def _normalizar_nome(valor: Any) -> str:
    nome = _txt(valor)
    if not nome:
        return ""

    nome = re.sub(r"(?i)^produto\s*[:\-]\s*", "", nome).strip()
    nome = re.sub(r"\s+[|\-]\s+R\$\s*\d+[\d\.,]*.*$", "", nome).strip()
    nome = re.sub(r"(?i)comprar agora|adicionar ao carrinho|ver produto", "", nome).strip()
    nome = re.sub(r"\s+", " ", nome).strip()

    if len(nome) < 3:
        return ""
    return nome[:180]


def _normalizar_preco(valor: Any) -> str:
    texto = _txt(valor)
    if not texto:
        return ""

    match = re.search(r"R\$\s*\d{1,3}(?:\.\d{3})*,\d{2}|R\$\s*\d+[\.,]\d{2}|\d{1,3}(?:\.\d{3})*,\d{2}|\d+\.\d{2}", texto)
    if not match:
        return ""

    preco = match.group(0).replace("R$", "").strip()

    if "," in preco:
        preco = preco.replace(".", "").replace(",", ".")

    try:
        valor_float = float(preco)
    except Exception:
        return ""

    if valor_float <= 0:
        return ""

    return f"{valor_float:.2f}".replace(".", ",")


def _normalizar_imagens(valor: Any) -> str:
    texto = _txt(valor)
    if not texto:
        return ""

    partes = re.split(r"[|,;\n\t]+", texto)
    boas = []
    vistos = set()

    for parte in partes:
        url = _normalizar_url(parte)
        if not url:
            continue
        baixo = url.lower()
        if any(lixo in baixo for lixo in ["logo", "sprite", "placeholder", "blank", "banner", "favicon"]):
            continue
        if not any(ext in baixo for ext in [".jpg", ".jpeg", ".png", ".webp", ".gif"]):
            continue
        if url in vistos:
            continue
        vistos.add(url)
        boas.append(url)
        if len(boas) >= 12:
            break

    return "|".join(boas)


def _normalizar_gtin(valor: Any) -> str:
    digitos = re.sub(r"\D+", "", _txt(valor))
    if len(digitos) in {8, 12, 13, 14}:
        return digitos
    return ""


def _inferir_marca(nome: str, marca_atual: Any = "") -> str:
    marca = _txt(marca_atual)
    if marca:
        return marca[:80]

    nome_l = nome.lower()
    for marca_comum in MARCAS_COMUNS:
        if re.search(rf"\b{re.escape(marca_comum)}\b", nome_l):
            return marca_comum.title()

    return ""


def _inferir_sku(row: pd.Series) -> str:
    for coluna in ["sku", "codigo", "Código", "codigo_produto", "referencia", "referência"]:
        if coluna in row.index:
            valor = _txt(row.get(coluna, ""))
            if valor and len(valor) <= 80:
                return valor

    url = _txt(row.get("url_produto", ""))
    if url:
        path = urlparse(url).path.strip("/")
        trecho = path.split("/")[-1] if path else ""
        trecho = re.sub(r"[^A-Za-z0-9._-]+", "-", trecho).strip("-")
        if trecho:
            return trecho[:80]

    return ""


def _inferir_categoria(row: pd.Series) -> str:
    for coluna in ["categoria", "category", "breadcrumb", "departamento"]:
        if coluna in row.index:
            valor = _txt(row.get(coluna, ""))
            if valor:
                return valor[:160]
    return ""


def _normalizar_estoque(valor: Any) -> str:
    texto = _txt(valor).lower()
    if not texto:
        return ""
    if any(palavra in texto for palavra in ["sem estoque", "indisponível", "indisponivel", "esgotado", "zerado"]):
        return "0"
    match = re.search(r"\d+", texto)
    if match:
        return match.group(0)
    if any(palavra in texto for palavra in ["em estoque", "disponível", "disponivel", "comprar"]):
        return "1"
    return ""


def _score_produto(row: pd.Series) -> tuple[int, str, str]:
    score = 0
    alertas = []

    nome = _txt(row.get("nome", ""))
    preco = _txt(row.get("preco", ""))
    url = _txt(row.get("url_produto", ""))
    imagens = _txt(row.get("imagens", ""))
    descricao = _txt(row.get("descricao", ""))
    gtin = _txt(row.get("gtin", ""))

    if nome and len(nome) >= 8:
        score += 30
    else:
        alertas.append("nome_fraco")

    if preco:
        score += 25
    else:
        alertas.append("sem_preco")

    if url.startswith(("http://", "https://")):
        score += 15
    else:
        alertas.append("sem_url")

    if imagens:
        score += 12
    else:
        alertas.append("sem_imagem")

    if descricao and len(descricao) >= 30:
        score += 8

    if gtin:
        score += 5

    if _txt(row.get("marca", "")):
        score += 3

    if _txt(row.get("sku", "")):
        score += 2

    score = min(score, 100)

    if score >= 75:
        status = "bom"
    elif score >= 50:
        status = "revisar"
    else:
        status = "fraco"

    return score, status, ", ".join(alertas)


def normalizar_produtos_ai(df: pd.DataFrame) -> pd.DataFrame:
    """
    BLINGAI MODE local:
    - limpa nome, preço, imagens, GTIN e estoque;
    - infere marca, SKU e categoria quando possível;
    - cria score de qualidade para revisão.
    """
    if not isinstance(df, pd.DataFrame) or df.empty:
        return pd.DataFrame(columns=COLUNAS_SAIDA_AI)

    base = df.copy().fillna("")

    for coluna in COLUNAS_SAIDA_AI:
        if coluna not in base.columns:
            base[coluna] = ""

    base["nome"] = base["nome"].apply(_normalizar_nome)
    base["preco"] = base["preco"].apply(_normalizar_preco)
    base["url_produto"] = base["url_produto"].apply(_normalizar_url)
    base["imagens"] = base["imagens"].apply(_normalizar_imagens)
    base["descricao"] = base["descricao"].apply(lambda v: _txt(v)[:900])
    base["gtin"] = base["gtin"].apply(_normalizar_gtin)
    base["estoque"] = base["estoque"].apply(_normalizar_estoque)

    base["marca"] = base.apply(lambda row: _inferir_marca(row.get("nome", ""), row.get("marca", "")), axis=1)
    base["sku"] = base.apply(_inferir_sku, axis=1)
    base["categoria"] = base.apply(_inferir_categoria, axis=1)

    scores = base.apply(_score_produto, axis=1)
    base["_ai_score"] = scores.apply(lambda item: item[0])
    base["_ai_status"] = scores.apply(lambda item: item[1])
    base["_ai_alertas"] = scores.apply(lambda item: item[2])

    # Remove linhas completamente inúteis.
    base = base[base["nome"].astype(str).str.strip().ne("")].copy()

    if "url_produto" in base.columns and "nome" in base.columns:
        base = base.drop_duplicates(subset=["url_produto", "nome"], keep="first")

    colunas_ordenadas = COLUNAS_SAIDA_AI + [c for c in base.columns if c not in COLUNAS_SAIDA_AI]
    return base[colunas_ordenadas].fillna("").reset_index(drop=True)
