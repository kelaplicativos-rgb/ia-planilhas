from __future__ import annotations

from typing import Iterable

import pandas as pd

# Colunas criadas pelo MapeiaAI para rastreio/diagnóstico. Elas podem existir
# na origem durante o processamento, mas nunca podem virar contrato do modelo
# Bling nem aparecer como campo-alvo no mapeamento ou no download final.
GENERATED_INTERNAL_COLUMN_KEYS = {
    'arquivoorigem',
    'paginaorigem',
    'categoriaatualia',
    'categoriasugeridaia',
    'acaocategoriaia',
    'confiancacategoriaia',
    'motivocategoriaia',
}


def _column_key(value: object) -> str:
    text = str(value or '').strip().casefold()
    for old, new in {
        'ã': 'a',
        'á': 'a',
        'à': 'a',
        'â': 'a',
        'é': 'e',
        'ê': 'e',
        'í': 'i',
        'ó': 'o',
        'ô': 'o',
        'õ': 'o',
        'ú': 'u',
        'ç': 'c',
    }.items():
        text = text.replace(old, new)
    return ''.join(ch for ch in text if ch.isalnum())


def is_generated_internal_column(column: object) -> bool:
    return _column_key(column) in GENERATED_INTERNAL_COLUMN_KEYS


def clean_model_columns(columns: Iterable[object]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for column in columns or []:
        name = str(column)
        if is_generated_internal_column(name):
            continue
        if name in seen:
            continue
        seen.add(name)
        out.append(name)
    return out


def strip_generated_internal_columns(df: pd.DataFrame | None) -> pd.DataFrame:
    if not isinstance(df, pd.DataFrame):
        return pd.DataFrame()
    columns = clean_model_columns(getattr(df, 'columns', []))
    return df.loc[:, [column for column in columns if column in df.columns]].copy()


__all__ = [
    'GENERATED_INTERNAL_COLUMN_KEYS',
    'clean_model_columns',
    'is_generated_internal_column',
    'strip_generated_internal_columns',
]
