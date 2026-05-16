from __future__ import annotations

from difflib import SequenceMatcher
from typing import Any

import pandas as pd

from bling_app_zero.ai.ai_dataframe_tools import dataframe_snapshot, normalize_column_name
from bling_app_zero.ai.ai_schema import AIResult

SYNONYMS = {
    'descricao': {'descricao', 'produto', 'nome', 'titulo', 'name', 'title', 'product'},
    'preco': {'preco', 'valor', 'price', 'preco venda', 'valor venda', 'unitario'},
    'estoque': {'estoque', 'saldo', 'quantidade', 'qtd', 'stock', 'inventory', 'qty'},
    'codigo': {'codigo', 'sku', 'referencia', 'ref', 'id', 'code'},
    'gtin': {'gtin', 'ean', 'codigo barras', 'barcode', 'cod barras'},
    'imagem': {'imagem', 'foto', 'url imagem', 'image', 'photo', 'pictures'},
    'categoria': {'categoria', 'departamento', 'category', 'grupo'},
    'marca': {'marca', 'brand', 'fabricante'},
    'ncm': {'ncm', 'classificacao fiscal'},
}


def _semantic_bucket(text: str) -> str:
    normalized = normalize_column_name(text)
    for bucket, words in SYNONYMS.items():
        for word in words:
            if word in normalized:
                return bucket
    return normalized


def _score(source: str, target: str) -> float:
    source_norm = normalize_column_name(source)
    target_norm = normalize_column_name(target)
    if not source_norm or not target_norm:
        return 0.0
    if source_norm == target_norm:
        return 1.0
    source_bucket = _semantic_bucket(source_norm)
    target_bucket = _semantic_bucket(target_norm)
    if source_bucket and source_bucket == target_bucket:
        return 0.92
    if source_norm in target_norm or target_norm in source_norm:
        return 0.82
    return round(SequenceMatcher(None, source_norm, target_norm).ratio(), 3)


def suggest_header_matches(source_df: pd.DataFrame, target_df: pd.DataFrame) -> AIResult:
    source_columns = [str(column) for column in source_df.columns] if isinstance(source_df, pd.DataFrame) else []
    target_columns = [str(column) for column in target_df.columns] if isinstance(target_df, pd.DataFrame) else []
    suggestions: list[dict[str, Any]] = []

    for target in target_columns:
        ranked = sorted(
            [{'source_column': source, 'score': _score(source, target)} for source in source_columns],
            key=lambda item: item['score'],
            reverse=True,
        )
        best = ranked[0] if ranked else {'source_column': '', 'score': 0.0}
        suggestions.append(
            {
                'target_column': target,
                'source_column': best['source_column'] if best['score'] >= 0.45 else '',
                'confidence': float(best['score']),
                'reason': 'similaridade de cabeçalho e sinônimos conhecidos' if best['score'] >= 0.45 else 'sem correspondência segura',
                'alternatives': ranked[:3],
            }
        )

    return AIResult(
        ok=True,
        task='header_matcher',
        message=f'{len(suggestions)} campo(s) de destino analisado(s).',
        data={
            'source_snapshot': dataframe_snapshot(source_df),
            'target_columns': target_columns,
            'suggestions': suggestions,
        },
    )


__all__ = ['suggest_header_matches']
