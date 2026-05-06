from __future__ import annotations

"""Blindagem das colunas exibidas no mapeamento.

Objetivo:
- o seletor do mapeamento deve mostrar somente colunas reais da origem/captura;
- remover duplicidades visuais/semânticas criadas por merges, crawlers ou modelos;
- impedir que colunas de saída/final/modelo Bling contaminem as opções.
"""

import re
from collections.abc import Iterable

import pandas as pd


DESTINO_FRAGMENTOS_BLOQUEADOS = (
    "obrigatorio",
    "obrigatoria",
    "campo bling",
    "campo destino",
    "destino bling",
    "coluna destino",
    "mapeamento",
    "calculado automaticamente",
    "modelo bling",
    "modelo cadastro",
    "modelo estoque",
)

DESTINO_EXATOS_BLOQUEADOS = {
    "df final",
    "df saida",
    "mapping manual",
    "modelo bling",
    "modelo cadastro",
    "modelo estoque",
}

NOMES_SIMPLES_PERMITIDOS = {
    "preco",
    "preco unitario",
    "valor",
    "price",
    "nome",
    "produto",
    "descricao",
    "codigo",
    "sku",
    "gtin",
    "ean",
    "estoque",
    "quantidade",
    "marca",
    "categoria",
    "url imagem",
    "url imagens",
    "imagem",
    "imagens",
}


_TRANSLATE = str.maketrans("áàãâéêíóôõúç", "aaaaeeiooouc")


def normalizar_coluna(valor: object) -> str:
    texto = str(valor or "").strip().lower().translate(_TRANSLATE)
    texto = re.sub(r"\.[0-9]+$", "", texto)  # pandas: coluna, coluna.1, coluna.2
    texto = re.sub(r"\s*\([0-9]+\)$", "", texto)  # UI/crawler: coluna (2)
    texto = re.sub(r"[^a-z0-9]+", " ", texto)
    return re.sub(r"\s+", " ", texto).strip()


def _modelo_normalizado(df_modelo: pd.DataFrame | None) -> set[str]:
    if not isinstance(df_modelo, pd.DataFrame):
        return set()
    return {normalizar_coluna(c) for c in df_modelo.columns.tolist() if str(c).strip()}


def parece_coluna_destino_ou_interna(coluna: object, nomes_modelo: set[str] | None = None) -> bool:
    nome = normalizar_coluna(coluna)
    if not nome:
        return True
    if nome in DESTINO_EXATOS_BLOQUEADOS:
        return True
    if any(fragmento in nome for fragmento in DESTINO_FRAGMENTOS_BLOQUEADOS):
        return True
    if nomes_modelo and nome in nomes_modelo and nome not in NOMES_SIMPLES_PERMITIDOS:
        return True
    return False


def colunas_unicas_reais(
    colunas: Iterable[object],
    *,
    df_modelo: pd.DataFrame | None = None,
    bloquear_video: bool = True,
    video_checker=None,
) -> list[str]:
    nomes_modelo = _modelo_normalizado(df_modelo)
    resultado: list[str] = []
    vistos: set[str] = set()

    for coluna in colunas:
        original = str(coluna or "").strip()
        chave = normalizar_coluna(original)
        if not original or not chave:
            continue
        if chave in vistos:
            continue
        if bloquear_video and callable(video_checker) and video_checker(original):
            continue
        if parece_coluna_destino_ou_interna(original, nomes_modelo):
            continue
        vistos.add(chave)
        resultado.append(original)

    return resultado


def limpar_dataframe_origem_para_mapeamento(
    df: pd.DataFrame,
    *,
    df_modelo: pd.DataFrame | None = None,
    bloquear_video: bool = True,
    video_checker=None,
) -> pd.DataFrame:
    if not isinstance(df, pd.DataFrame) or df.empty:
        return pd.DataFrame()

    colunas_validas = colunas_unicas_reais(
        df.columns.tolist(),
        df_modelo=df_modelo,
        bloquear_video=bloquear_video,
        video_checker=video_checker,
    )
    if not colunas_validas:
        return pd.DataFrame(index=df.index)

    return df.loc[:, colunas_validas].copy()
