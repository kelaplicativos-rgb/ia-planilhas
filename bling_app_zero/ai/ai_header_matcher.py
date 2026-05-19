from __future__ import annotations

from difflib import SequenceMatcher
from typing import Any

import pandas as pd

from bling_app_zero.ai.ai_dataframe_tools import dataframe_snapshot, normalize_column_name
from bling_app_zero.ai.ai_schema import AIResult

SYNONYMS = {
    'descricao': {'descricao', 'descrição', 'produto', 'nome', 'titulo', 'título', 'name', 'title', 'product'},
    'preco': {'preco', 'preço', 'valor', 'price', 'preco venda', 'preço venda', 'valor venda', 'unitario', 'unitário'},
    'estoque': {'estoque', 'saldo', 'quantidade', 'qtd', 'stock', 'inventory', 'qty'},
    'codigo': {'codigo', 'código', 'sku', 'referencia', 'referência', 'ref', 'id', 'code'},
    'gtin': {'gtin', 'ean', 'codigo barras', 'código barras', 'barcode', 'cod barras'},
    'imagem': {'imagem', 'foto', 'url imagem', 'image', 'photo', 'pictures'},
    'categoria': {'categoria', 'departamento', 'category', 'grupo'},
    'marca': {'marca', 'brand', 'fabricante'},
    'ncm': {'ncm', 'classificacao fiscal', 'classificação fiscal'},
}

PRICE_HINTS = {'r$', 'preco', 'preço', 'valor', 'price'}
IMAGE_HINTS = {'http', 'https', '.jpg', '.jpeg', '.png', '.webp', 'imagem', 'foto'}
TEXT_PRODUCT_HINTS = {'kit', 'un', 'usb', 'cabo', 'fonte', 'controle', 'carregador', 'adaptador', 'caixa'}


def _semantic_bucket(text: str) -> str:
    normalized = normalize_column_name(text)
    for bucket, words in SYNONYMS.items():
        for word in words:
            if normalize_column_name(word) in normalized:
                return bucket
    return normalized


def _sample_values(df: pd.DataFrame, column: str, *, limit: int = 20) -> list[str]:
    if not isinstance(df, pd.DataFrame) or column not in df.columns:
        return []
    values: list[str] = []
    try:
        series = df[column].dropna().astype(str).map(str.strip)
        for value in series:
            if value and value.lower() not in {'nan', 'none', 'null'}:
                values.append(value[:180])
            if len(values) >= limit:
                break
    except Exception:
        return []
    return values


def _looks_price(values: list[str]) -> float:
    if not values:
        return 0.0
    hits = 0
    for value in values:
        text = value.lower().strip()
        compact = text.replace('.', '').replace(',', '.')
        has_currency = any(hint in text for hint in PRICE_HINTS)
        try:
            number = float(''.join(ch for ch in compact if ch.isdigit() or ch == '.') or '0')
        except Exception:
            number = 0.0
        if has_currency or (0 < number < 100000 and any(ch.isdigit() for ch in text) and len(text) <= 32):
            hits += 1
    return hits / max(1, len(values))


def _looks_gtin(values: list[str]) -> float:
    if not values:
        return 0.0
    hits = 0
    for value in values:
        digits = ''.join(ch for ch in value if ch.isdigit())
        if len(digits) in {8, 12, 13, 14} and len(value.strip()) <= 24:
            hits += 1
    return hits / max(1, len(values))


def _looks_image(values: list[str]) -> float:
    if not values:
        return 0.0
    hits = 0
    for value in values:
        text = value.lower()
        if any(hint in text for hint in IMAGE_HINTS):
            hits += 1
    return hits / max(1, len(values))


def _looks_description(values: list[str]) -> float:
    if not values:
        return 0.0
    hits = 0
    for value in values:
        text = value.lower().strip()
        words = [part for part in text.replace('-', ' ').replace('/', ' ').split() if part]
        has_letters = any(ch.isalpha() for ch in text)
        has_product_hint = any(hint in text for hint in TEXT_PRODUCT_HINTS)
        if has_letters and (len(words) >= 2 or len(text) >= 18 or has_product_hint):
            hits += 1
    return hits / max(1, len(values))


def _looks_code(values: list[str]) -> float:
    if not values:
        return 0.0
    hits = 0
    for value in values:
        text = value.strip()
        if 1 <= len(text) <= 32 and any(ch.isdigit() for ch in text) and not ('http' in text.lower()):
            hits += 1
    return hits / max(1, len(values))


def _content_score(source: str, target: str, source_df: pd.DataFrame) -> tuple[float, str]:
    bucket = _semantic_bucket(target)
    values = _sample_values(source_df, source)
    if not values:
        return 0.0, 'sem amostra de conteúdo'

    if bucket == 'preco':
        score = _looks_price(values)
        return score, 'conteúdo parece preço' if score >= 0.5 else 'conteúdo não parece preço'
    if bucket == 'gtin':
        score = _looks_gtin(values)
        return score, 'conteúdo parece GTIN/EAN' if score >= 0.5 else 'conteúdo não parece GTIN/EAN'
    if bucket == 'imagem':
        score = _looks_image(values)
        return score, 'conteúdo parece link de imagem' if score >= 0.5 else 'conteúdo não parece imagem'
    if bucket == 'descricao':
        score = _looks_description(values)
        return score, 'conteúdo parece nome/descrição de produto' if score >= 0.5 else 'conteúdo não parece descrição'
    if bucket in {'codigo', 'estoque'}:
        score = _looks_code(values)
        return score, 'conteúdo parece código/número' if score >= 0.5 else 'conteúdo não parece código/número'
    return 0.0, 'sem regra de conteúdo para este campo'


def _header_score(source: str, target: str) -> float:
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


def _score(source: str, target: str, source_df: pd.DataFrame) -> tuple[float, str]:
    header = _header_score(source, target)
    content, content_reason = _content_score(source, target, source_df)
    bucket = _semantic_bucket(target)

    if bucket in {'descricao', 'preco', 'gtin', 'imagem', 'codigo', 'estoque'}:
        combined = (header * 0.45) + (content * 0.55)
        if header >= 0.9 and content >= 0.25:
            combined = max(combined, 0.82)
        if content >= 0.85 and header >= 0.35:
            combined = max(combined, 0.78)
    else:
        combined = header

    reason = f'cabeçalho {header:.2f}; {content_reason} ({content:.2f})'
    return round(max(0.0, min(1.0, combined)), 3), reason


def suggest_header_matches(source_df: pd.DataFrame, target_df: pd.DataFrame) -> AIResult:
    source_columns = [str(column) for column in source_df.columns] if isinstance(source_df, pd.DataFrame) else []
    target_columns = [str(column) for column in target_df.columns] if isinstance(target_df, pd.DataFrame) else []
    suggestions: list[dict[str, Any]] = []

    for target in target_columns:
        ranked = []
        for source in source_columns:
            score, reason = _score(source, target, source_df)
            ranked.append({'source_column': source, 'score': score, 'reason': reason})
        ranked = sorted(ranked, key=lambda item: item['score'], reverse=True)
        best = ranked[0] if ranked else {'source_column': '', 'score': 0.0, 'reason': 'sem colunas de origem'}
        suggestions.append(
            {
                'target_column': target,
                'source_column': best['source_column'] if best['score'] >= 0.62 else '',
                'confidence': float(best['score']),
                'reason': best.get('reason') if best['score'] >= 0.62 else 'sem correspondência segura pelo conteúdo',
                'alternatives': ranked[:3],
            }
        )

    return AIResult(
        ok=True,
        task='header_matcher',
        message=f'{len(suggestions)} campo(s) de destino analisado(s) por cabeçalho e conteúdo real.',
        data={
            'source_snapshot': dataframe_snapshot(source_df),
            'target_columns': target_columns,
            'suggestions': suggestions,
        },
    )


__all__ = ['suggest_header_matches']
