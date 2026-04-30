from __future__ import annotations

"""
Normalizador da captura por site para o fluxo Bling.

Este módulo existe para manter compatibilidade entre o painel antigo
`origem_site_panel.py` e a estrutura modular nova (`origem_site_view`,
`origem_site_execution`, `site_product_enricher`).

O erro atual do Streamlit Cloud acontece quando algum arquivo ainda tenta
importar `normalizar_captura_site_para_bling` daqui. Por isso a função fica
explícita neste arquivo, em vez de depender apenas de import curinga.
"""

import re
from typing import Any

import pandas as pd

from bling_app_zero.ui.site_product_enricher import (
    infer_additional_info,
    infer_brand,
    infer_category,
    infer_department,
    infer_ncm,
    infer_tags,
)


COLUNAS_BLING_SITE = [
    "Código",
    "Descrição",
    "Descrição complementar",
    "Unidade",
    "NCM",
    "Preço unitário",
    "Preço unitário (OBRIGATÓRIO)",
    "Marca",
    "Categoria",
    "Departamento",
    "GTIN/EAN",
    "GTIN/EAN da embalagem",
    "Estoque",
    "URL origem da busca",
    "URL do produto",
    "URL das imagens",
    "Observações",
    "Tags",
]


POSSIVEIS_DESCRICAO = [
    "Descrição",
    "descricao",
    "descrição",
    "Nome",
    "nome",
    "Produto",
    "produto",
    "Título",
    "titulo",
    "title",
    "name",
]

POSSIVEIS_PRECO = [
    "Preço unitário",
    "Preço",
    "preco",
    "preço",
    "price",
    "valor",
    "Valor",
]

POSSIVEIS_CODIGO = [
    "Código",
    "codigo",
    "Cód.",
    "COD",
    "SKU",
    "sku",
    "Referência",
    "referencia",
    "ref",
]

POSSIVEIS_IMAGENS = [
    "URL das imagens",
    "Imagens",
    "imagens",
    "Imagem",
    "imagem",
    "image",
    "images",
    "img",
]

POSSIVEIS_URL = [
    "URL do produto",
    "URL origem da busca",
    "url",
    "URL",
    "link",
    "Link",
]

POSSIVEIS_GTIN = [
    "GTIN/EAN",
    "GTIN",
    "EAN",
    "ean",
    "gtin",
    "barcode",
    "código de barras",
    "codigo de barras",
]


_DOMINIOS_IMG_RUINS = (
    "logo",
    "banner",
    "placeholder",
    "sprite",
    "icone",
    "icon",
    "whatsapp",
    "facebook",
    "instagram",
    "youtube",
    "tracking",
)


def _texto(valor: Any) -> str:
    if valor is None:
        return ""
    if isinstance(valor, float) and pd.isna(valor):
        return ""
    return " ".join(str(valor).replace("\x00", " ").split()).strip()


def _norm_coluna(nome: Any) -> str:
    texto = _texto(nome).lower()
    tabela = str.maketrans("áàãâéêíóôõúç", "aaaaeeiooouc")
    texto = texto.translate(tabela)
    texto = re.sub(r"[^a-z0-9]+", " ", texto)
    return " ".join(texto.split())


def _primeira_coluna(df: pd.DataFrame, candidatos: list[str]) -> str | None:
    if df.empty:
        return None

    mapa = {_norm_coluna(col): col for col in df.columns}
    for candidato in candidatos:
        chave = _norm_coluna(candidato)
        if chave in mapa:
            return mapa[chave]

    for col in df.columns:
        col_norm = _norm_coluna(col)
        for candidato in candidatos:
            cand_norm = _norm_coluna(candidato)
            if cand_norm and (cand_norm in col_norm or col_norm in cand_norm):
                return col
    return None


def _valor_linha(row: pd.Series, coluna: str | None, padrao: str = "") -> str:
    if not coluna or coluna not in row.index:
        return padrao
    return _texto(row.get(coluna, padrao))


def _normalizar_preco(valor: Any) -> str:
    texto = _texto(valor)
    if not texto:
        return ""

    texto = texto.replace("R$", "").replace("r$", "").strip()
    texto = re.sub(r"[^0-9,.-]", "", texto)

    if not texto:
        return ""

    if "," in texto and "." in texto:
        if texto.rfind(",") > texto.rfind("."):
            texto = texto.replace(".", "").replace(",", ".")
        else:
            texto = texto.replace(",", "")
    elif "," in texto:
        texto = texto.replace(".", "").replace(",", ".")

    try:
        numero = float(texto)
    except Exception:
        return ""

    if numero <= 0:
        return ""
    return f"{numero:.2f}".replace(".", ",")


def _normalizar_gtin(valor: Any) -> str:
    digitos = re.sub(r"\D+", "", _texto(valor))
    if len(digitos) in {8, 12, 13, 14}:
        return digitos
    return ""


def _normalizar_imagens(valor: Any) -> str:
    texto = _texto(valor)
    if not texto:
        return ""

    partes = re.split(r"[|,;\n\r\t]+", texto)
    imagens: list[str] = []
    vistos: set[str] = set()

    for parte in partes:
        url = _texto(parte)
        if not url:
            continue
        url_lower = url.lower()
        if not (url_lower.startswith("http://") or url_lower.startswith("https://")):
            continue
        if any(ruim in url_lower for ruim in _DOMINIOS_IMG_RUINS):
            continue
        if url_lower in vistos:
            continue
        vistos.add(url_lower)
        imagens.append(url)
        if len(imagens) >= 12:
            break

    return "|".join(imagens)


def _gerar_codigo(row: pd.Series, codigo_col: str | None, url_col: str | None, indice: int) -> str:
    codigo = _valor_linha(row, codigo_col)
    if codigo:
        return codigo

    url = _valor_linha(row, url_col)
    numeros_url = re.findall(r"\d{3,}", url)
    if numeros_url:
        return numeros_url[-1]

    return f"SITE-{indice + 1:05d}"


def normalizar_captura_site_para_bling(df: pd.DataFrame | list[dict[str, Any]] | dict[str, Any] | None) -> pd.DataFrame:
    """
    Converte a captura bruta do site para uma base estável usada no fluxo Bling.

    Aceita DataFrame, lista de dicionários ou dicionário único. A saída sempre
    retorna um DataFrame com colunas padronizadas, preço saneado, GTIN inválido
    vazio e imagens separadas por `|`.
    """
    if df is None:
        return pd.DataFrame(columns=COLUNAS_BLING_SITE)

    if isinstance(df, pd.DataFrame):
        origem = df.copy()
    elif isinstance(df, list):
        origem = pd.DataFrame(df)
    elif isinstance(df, dict):
        origem = pd.DataFrame([df])
    else:
        return pd.DataFrame(columns=COLUNAS_BLING_SITE)

    if origem.empty:
        return pd.DataFrame(columns=COLUNAS_BLING_SITE)

    descricao_col = _primeira_coluna(origem, POSSIVEIS_DESCRICAO)
    preco_col = _primeira_coluna(origem, POSSIVEIS_PRECO)
    codigo_col = _primeira_coluna(origem, POSSIVEIS_CODIGO)
    imagens_col = _primeira_coluna(origem, POSSIVEIS_IMAGENS)
    url_col = _primeira_coluna(origem, POSSIVEIS_URL)
    gtin_col = _primeira_coluna(origem, POSSIVEIS_GTIN)
    marca_col = _primeira_coluna(origem, ["Marca", "marca", "brand"])
    categoria_col = _primeira_coluna(origem, ["Categoria", "categoria", "category", "breadcrumb"])
    ncm_col = _primeira_coluna(origem, ["NCM", "ncm"])
    estoque_col = _primeira_coluna(origem, ["Estoque", "estoque", "stock", "quantity", "quantidade"])

    linhas: list[dict[str, Any]] = []

    for indice, row in origem.iterrows():
        descricao = _valor_linha(row, descricao_col)
        if not descricao:
            descricao = _valor_linha(row, codigo_col) or f"Produto capturado {indice + 1}"

        preco = _normalizar_preco(_valor_linha(row, preco_col))
        marca = infer_brand(descricao, _valor_linha(row, marca_col))
        categoria = infer_category(descricao, _valor_linha(row, categoria_col))
        ncm = infer_ncm(descricao, _valor_linha(row, ncm_col))
        departamento = infer_department(categoria)
        gtin = _normalizar_gtin(_valor_linha(row, gtin_col))
        imagens = _normalizar_imagens(_valor_linha(row, imagens_col))
        url = _valor_linha(row, url_col)
        estoque = _valor_linha(row, estoque_col)

        if not estoque:
            estoque = "0" if "indispon" in descricao.lower() or "sem estoque" in descricao.lower() else ""

        observacoes = infer_additional_info(descricao, ncm, categoria, marca)

        linhas.append(
            {
                "Código": _gerar_codigo(row, codigo_col, url_col, int(indice) if isinstance(indice, int) else len(linhas)),
                "Descrição": descricao,
                "Descrição complementar": "",
                "Unidade": "UN",
                "NCM": ncm,
                "Preço unitário": preco,
                "Preço unitário (OBRIGATÓRIO)": preco,
                "Marca": marca,
                "Categoria": categoria,
                "Departamento": departamento,
                "GTIN/EAN": gtin,
                "GTIN/EAN da embalagem": "",
                "Estoque": estoque,
                "URL origem da busca": url,
                "URL do produto": url,
                "URL das imagens": imagens,
                "Observações": observacoes,
                "Tags": infer_tags(descricao),
            }
        )

    saida = pd.DataFrame(linhas)

    for coluna in COLUNAS_BLING_SITE:
        if coluna not in saida.columns:
            saida[coluna] = ""

    return saida[COLUNAS_BLING_SITE].fillna("")


# Alias de compatibilidade para chamadas antigas/novas.
normalizar_captura_site = normalizar_captura_site_para_bling
normalizar_site_para_bling = normalizar_captura_site_para_bling


__all__ = [
    "COLUNAS_BLING_SITE",
    "normalizar_captura_site_para_bling",
    "normalizar_captura_site",
    "normalizar_site_para_bling",
]
