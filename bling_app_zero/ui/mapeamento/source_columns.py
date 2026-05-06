from __future__ import annotations

"""Filtro das colunas reais da origem usadas no mapeamento.

O seletor manual deve mostrar somente colunas vindas da planilha/captura do
fornecedor. Colunas do modelo Bling, colunas finais calculadas e campos internos
não podem aparecer como origem, porque isso gera duplicidade como:
Preço / Preço unitário / Preço unitário (OBRIGATÓRIO).
"""

import re
from collections.abc import Iterable

import pandas as pd


_COLUNAS_INTERNAS_EXATAS = {
    "df_final",
    "df_saida",
    "mapping_manual",
    "modelo_bling",
    "modelo cadastro",
    "modelo estoque",
}

_FRAGMENTOS_DESTINO_OU_INTERNO = (
    "obrigatorio",
    "obrigatoria",
    "modelo bling",
    "campo bling",
    "campo destino",
    "destino bling",
    "coluna destino",
    "mapeamento",
    "calculado automaticamente",
    "preco unitario obrigatorio",
)


def normalizar_nome_coluna(valor: object) -> str:
    texto = str(valor or "").strip().lower()
    texto = texto.translate(str.maketrans("áàãâéêíóôõúç", "aaaaeeiooouc"))
    return re.sub(r"[^a-z0-9]+", " ", texto).strip()


def _nomes_modelo(df_modelo: pd.DataFrame | None) -> set[str]:
    if not isinstance(df_modelo, pd.DataFrame):
        return set()
    return {normalizar_nome_coluna(c) for c in df_modelo.columns.tolist() if str(c).strip()}


def _parece_coluna_destino_ou_interna(coluna: object, nomes_modelo: set[str]) -> bool:
    original = str(coluna or "").strip()
    nome = normalizar_nome_coluna(original)

    if not nome:
        return True
    if nome in _COLUNAS_INTERNAS_EXATAS:
        return True
    if any(fragmento in nome for fragmento in _FRAGMENTOS_DESTINO_OU_INTERNO):
        return True

    # Remove do seletor qualquer coluna que seja literalmente uma coluna do modelo Bling.
    # Exceção: se a origem tem nomes simples e comuns, como Preço, Nome, Código, eles podem ser reais.
    nomes_simples_permitidos = {
        "preco", "preco unitario", "valor", "price", "nome", "produto", "descricao", "codigo", "sku", "gtin", "ean", "estoque", "quantidade",
    }
    if nome in nomes_modelo and nome not in nomes_simples_permitidos:
        return True

    return False


def colunas_reais_da_origem(
    df_base: pd.DataFrame,
    df_modelo: pd.DataFrame | None = None,
    *,
    bloquear_video: bool = True,
    video_checker=None,
) -> list[str]:
    """Retorna somente colunas reais da origem para dropdown de mapeamento."""
    if not isinstance(df_base, pd.DataFrame):
        return []

    nomes_modelo = _nomes_modelo(df_modelo)
    resultado: list[str] = []
    vistos: set[str] = set()

    for coluna in df_base.columns.tolist():
        col = str(coluna or "").strip()
        chave = normalizar_nome_coluna(col)
        if not col or chave in vistos:
            continue
        if bloquear_video and callable(video_checker) and video_checker(col):
            continue
        if _parece_coluna_destino_ou_interna(col, nomes_modelo):
            continue
        vistos.add(chave)
        resultado.append(col)

    return resultado


def opcoes_origem_mapeamento(
    df_base: pd.DataFrame,
    df_modelo: pd.DataFrame | None = None,
    *,
    incluir_vazio: bool = True,
    bloquear_video: bool = True,
    video_checker=None,
) -> list[str]:
    colunas = colunas_reais_da_origem(
        df_base,
        df_modelo,
        bloquear_video=bloquear_video,
        video_checker=video_checker,
    )
    return ([""] if incluir_vazio else []) + colunas
